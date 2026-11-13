import asyncio
import json
from dataclasses import replace

import pytest

from app.application.ia.dto import GeneracionSalida
from app.application.ia.exceptions import IARespuestaInvalida
from app.application.rag.dto import Evidence
from app.application.rag.relevance import AcademicRelevance
from app.application.rag.structured_output import parse, schema, supported_text
from app.infrastructure.configuration.llm import LLMConfig
from app.infrastructure.rag.ollama import GroundedProvider
from app.application.rag.core import build_context
from app.infrastructure.rag.text import ConservativeCounter
from tests.rag.test_agent import fixture

QUESTION='Funciones del Rectorado'
SOURCE='Del Rectorado: Es la unidad de gestion institucional.'


def evidence():
    *_,case=fixture()
    chunk=replace(case.vectors.items[0].chunk,text=SOURCE,end=len(SOURCE))
    return (Evidence(citation='F1',chunk=chunk),)


def output(claims):
    return GeneracionSalida(respuesta=json.dumps({'claims':claims}),finalizacion='completa')


def test_valid_references_schema_and_supported_render():
    e=evidence()
    assert schema(e)['properties']['claims']['items']['properties']['source_ids']['items']['enum']==['F1']
    parsed=parse(output([{'text':'El Rectorado es la unidad de gestion institucional.','source_ids':['F1']}]),e)
    rendered,partial=supported_text(parsed,QUESTION,e,AcademicRelevance())
    assert rendered.respuesta.endswith('[F1]') and not partial


@pytest.mark.parametrize('body',[
    '{', '{"claims":[]', '{"claims":[],"claims":[]}',
    '{"claims":[],"extra":0}', '{"claims":NaN}',
    '{"claims":[{"text":"algo","source_ids":[]}]}',
    '{"claims":[{"text":"algo","source_ids":["F2"]}]}',
    '{"claims":[{"text":"algo","source_ids":["F1","F1"]}]}',
    '{"claims":[{"text":"algo [F1]","source_ids":["F1"]}]}',
    '{"claims":[{"text":"algo","source_ids":["F1"],"extra":0}]}',
])
def test_invalid_json_or_references_are_technical_errors(body):
    with pytest.raises(IARespuestaInvalida):
        parse(GeneracionSalida(respuesta=body,finalizacion='completa'),evidence())


def test_length_finalization_rejects_even_parseable_json():
    with pytest.raises(IARespuestaInvalida):
        parse(GeneracionSalida(respuesta='{"claims":[]}',finalizacion='limite'),evidence())


def test_inventions_wrong_role_empty_and_partial():
    e=evidence();policy=AcademicRelevance()
    claims=[{'text':'El Rectorado es la unidad de gestion institucional.','source_ids':['F1']},
            {'text':'El Rectorado concede becas.','source_ids':['F1']},
            {'text':'El Rector es la unidad de gestion institucional.','source_ids':['F1']}]
    rendered,partial=supported_text(parse(output(claims),e),QUESTION,e,policy)
    assert partial and 'becas' not in rendered.respuesta and 'El Rector es' not in rendered.respuesta
    for subset in ([],claims[1:]):
        rendered,partial=supported_text(parse(output(subset),e),QUESTION,e,policy)
        assert rendered.respuesta=='SIN_EVIDENCIA' and not partial


def test_authorized_continuation_remains_subject_to_existing_pertinence():
    e=evidence()
    continuation='El funcionamiento de los organos colegiados.'
    next_page=Evidence(citation='F2',chunk=replace(e[0].chunk,id='page12',page=12,
        start=0,end=len(continuation),text=continuation))
    context=(*e,next_page)
    claim={'text':continuation,'source_ids':['F2']}
    assert 'F2' in schema(context)['properties']['claims']['items']['properties']['source_ids']['items']['enum']
    parsed=parse(output([claim]),context)
    # Es accesible y referenciable, pero sin encabezado no pasa la regla actual.
    rendered,_=supported_text(parsed,QUESTION,context,AcademicRelevance())
    assert rendered.respuesta=='SIN_EVIDENCIA'


def test_use_case_marks_partial_response_and_publishes_only_valid_sources():
    async def run():
        p,scope,*_,case=fixture()
        e=evidence()
        chunk=replace(e[0].chunk,scope=scope)
        case.vectors.items=(replace(case.vectors.items[0],chunk=chunk,similarity=.99),)
        case.relevance=AcademicRelevance()
        async def generate(input):
            return parse(output([{'text':SOURCE,'source_ids':['F1']},
                {'text':'El Rectorado concede becas.','source_ids':['F1']}]),input.evidence)
        case.provider.generate_grounded=generate
        result=await case.execute(p,scope.document_id,QUESTION)
        assert result.status=='FUNDAMENTADA' and result.answer.startswith('Respuesta parcial:')
        assert 'concede becas' not in result.answer and len(result.citations)==1
    asyncio.run(run())


def test_local_adapter_passes_schema_and_preserves_generation_budgets():
    async def run():
        e=evidence();context=build_context(QUESTION,(e[0].chunk,),ConservativeCounter())
        provider=GroundedProvider(LLMConfig(enabled=True,environment='local-development',
            model='qwen2.5:1.5b',enforce_memory_guard=False))
        calls=[]
        async def generate(input,**kwargs):
            calls.append(kwargs)
            assert input.max_output_tokens==256 and input.context_tokens==4096
            return output([])
        provider._generate_validated=generate
        try:
            result=await provider.generate_grounded(context)
            assert not result.claims and calls[0]['output_format']==schema(context.evidence)
        finally:await provider.aclose()
    asyncio.run(run())
