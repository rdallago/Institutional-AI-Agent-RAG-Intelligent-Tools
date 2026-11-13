import asyncio
import json
from dataclasses import replace

import pytest

from app.application.agent.context import resolve_conversation_memory
from app.application.agent.diagnostics import record_private, private_diagnostics, request_identifier
from app.application.agent.planning import validate_proposal
from app.application.ia.exceptions import IARespuestaInvalida
from app.application.rag.continuity import complete_article, requirement_section
from app.application.rag.core import build_context
from app.application.rag.relevance import AcademicRelevance
from app.infrastructure.rag.text import ConservativeCounter
from tests.rag.test_article_continuity import make
from tests.rag.test_agent import fixture


def test_extractive_memory_ambiguity_and_ignores_assistant_and_repeated_meta_questions():
    q = '¿Sobre qué órgano del Reglamento Orgánico Marco te pregunté anteriormente?'
    first = '¿Cuáles son las funciones del Rectorado según el Reglamento Orgánico Marco?'
    history = ({'role':'user','content':first}, {'role':'assistant','content':'El Rector'},
               {'role':'user','content':q})
    assert resolve_conversation_memory(q, history) == 'Me preguntaste por Rectorado.'
    assert resolve_conversation_memory(q, history+({'role':'user','content':first.replace('Rectorado','Consejo')},)) is None
    assert resolve_conversation_memory(q, ({'role':'assistant','content':first},)) is None
    assert resolve_conversation_memory(q, ({'role':'user','content':first.replace('Rectorado','Rector y Vicerrector')},)) is None
    assert resolve_conversation_memory('¿Qué te pregunté antes?', ({'role':'user','content':'¿Qué es REST?'},)) == 'Tu pregunta anterior fue: «¿Qué es REST?»'
    assert 'artículo 52' in resolve_conversation_memory('¿Sobre qué artículo te pregunté antes?', ({'role':'user','content':'¿Qué establece el artículo 52?'},))
    assert resolve_conversation_memory('¿Sobre qué artículo te pregunté antes?', ({'role':'user','content':'¿Qué establecen el artículo 24 y el artículo 52?'},)) is None


def article52():
    _, scope, *_ = fixture()
    texts = {32:'Articulo 52. Acceso por concurso.\n'+('Antecedentes. '*180),
             33:'Requisitos del Coordinador de Carrera\n-Titulo docente superior.\n-Experiencia docente.\nPara la evaluacion del Proyecto:\n'+('Evaluacion. '*160),
             34:'Continuacion de evaluacion.\n'+('Condiciones. '*160),
             35:'Fin del concurso.\nArticulo 53. Funciones de otro cargo.'}
    rows = tuple((make(scope, p, value), len(value)) for p,value in texts.items())
    seed = make(scope,33,texts[33],0,80)
    return seed, rows


def test_article52_section_preserves_exact_slices_and_fits_context():
    seed, rows = article52()
    assert complete_article(seed, rows[:3]) == ()
    article = complete_article(seed, rows)
    assert [x.page for x in article] == [32,33,34,35]
    section = requirement_section(seed, article)
    assert len(section)==1 and section[0].page==33
    chunk = section[0]
    source = rows[1][0].text
    assert chunk.text == source[chunk.start:chunk.end]
    assert 'Evaluacion.' not in chunk.text and 'Articulo 53' not in chunk.text
    assert chunk.id != seed.id and chunk.scope == seed.scope
    q='Requisitos para acceder al concurso de coordinación de carrera'
    assert AcademicRelevance().select(q, section) == section
    context = build_context(q,section,ConservativeCounter())
    assert context and tuple(e.chunk for e in context.evidence)==section
    assert chunk.section.startswith('Sección normativa parcial:')


def test_section_requires_proven_article_boundary_and_complete_list():
    seed, rows = article52()
    assert requirement_section(seed, ()) == ()
    article = complete_article(seed,rows)
    bad = tuple(replace(x,text=x.text.replace('Para la evaluacion del Proyecto:', 'Sin encabezado')) if x.page==33 else x for x in article)
    assert requirement_section(seed,bad)==()
    bad = tuple(replace(x,text=x.text.replace('-Experiencia docente.', '-Experiencia docente')) if x.page==33 else x for x in article)
    assert requirement_section(seed,bad)==()


def test_section_is_not_silently_truncated_when_over_budget():
    seed, rows=article52()
    article=complete_article(seed,rows)
    section=requirement_section(seed,article)
    large=replace(section[0],text=section[0].text+'x'*5000)
    assert build_context('Requisitos de coordinación de carrera',(large,),ConservativeCounter()) is None


def test_section_response_is_explicitly_partial_after_strict_validation():
    from app.application.rag.dto import Candidate
    from app.application.rag.structured_output import StructuredGeneration, Claim
    async def run():
        p, scope, *_, case=fixture()
        value='Requisitos del Coordinador de Carrera\n-Titulo docente superior.\n'
        chunk=replace(case.vectors.items[0].chunk,scope=scope,text=value,start=0,end=len(value),
                      section='Sección normativa parcial: Requisitos del Coordinador de Carrera')
        case.vectors.items=(Candidate(chunk=chunk,similarity=.99),)
        async def continuity(*args):return (chunk,)
        async def generate(input):return StructuredGeneration((Claim('Titulo docente superior',('F1',)),))
        case.continuity=continuity
        case.provider.generate_grounded=generate
        result=await case.execute(p,scope.document_id,'Requisitos para acceder al concurso de coordinación de carrera')
        assert result.status=='FUNDAMENTADA'
        assert result.answer.startswith('Respuesta parcial: se responde solo con la sección normativa recuperada.')
        assert len(result.citations)==1
    asyncio.run(run())


def test_private_diagnostics_are_redacted_bounded_and_not_logged(tmp_path, monkeypatch, caplog):
    monkeypatch.setenv('AGENT_PRIVATE_DIAGNOSTIC_DIR',str(tmp_path))
    token=request_identifier.set('request-fixture')
    try:
        for _ in range(70):
            record_private('weather_proposal',arguments={'ciudad':'Bearer private-value','pais':'AR','password':'never-export'}, reason='test')
    finally:request_identifier.reset(token)
    events=private_diagnostics()
    assert len(events)==64
    assert len(list(tmp_path.glob('agent-private-*.json')))==64
    encoded=json.dumps(events)
    assert 'private-value' not in encoded and 'never-export' not in encoded
    assert events[-1]['request_id']=='request-fixture'
    assert not caplog.text


@pytest.mark.parametrize('raw,reason', [
    ('{"accion":"x","accion":"y"}', 'duplicate_key'),
    ('{"accion":', 'json_syntax'),
    ('{"accion":"responder_llm_directo","argumentos":{"password":"secret-value"}}', 'schema_rejected'),
    ('{"accion":"unknown","argumentos":{}}','schema_rejected'),
])
def test_strict_planner_records_rule_without_input(raw, reason):
    with pytest.raises(IARespuestaInvalida):validate_proposal(raw)
    event=private_diagnostics()[-1]
    assert event['reason']==reason
    assert 'secret-value' not in json.dumps(event)
    assert 'password' not in json.dumps(event)


def test_geocoder_rejection_observed_without_forecast_or_real_http():
    from app.infrastructure.rag.weather import OpenMeteo
    from app.application.agent.tools import WeatherArgs
    from app.application.agent.skills.registry import SkillRegistry
    from app.infrastructure.rag.skills import PackagedSkillLoader
    import httpx
    async def run():
        calls=[]
        def handler(request):
            calls.append(request.url.host)
            return httpx.Response(200,json={'results':[]})
        weather=OpenMeteo(transport=httpx.MockTransport(handler))
        try:
            result=await weather.execute(WeatherArgs(ciudad='Esquina',pais='AR',region='Corrientes',dia='hoy'),SkillRegistry(PackagedSkillLoader()).load('weather').instructions)
            assert result.status=='ACLARACION'
            assert calls==['geocoding-api.open-meteo.com']
            event=private_diagnostics()[-1]
            assert event['match_count']==0 and event['reason']=='no_match'
        finally:await weather.close()
    asyncio.run(run())
