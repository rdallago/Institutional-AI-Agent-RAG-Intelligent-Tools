import asyncio
from dataclasses import replace
import pytest

from app.application.rag.articles import resolve_article
from app.application.rag.dto import Evidence
from app.application.rag.relevance import AcademicRelevance
from app.application.rag.structured_output import Claim, StructuredGeneration, supported_text
from app.application.agent.context import conversation_memory_reference, resolve_conversation_memory
from app.application.ia.dto import GeneracionSalida
from tests.rag.test_core import setup


def evidence():
    _,scope,*_=setup()
    r=resolve_article(((1,'REGIMEN ACADEMICO MARCO\nArticulo 24. La asistencia es obligatoria.\nArticulo 25. Otra norma.'),),scope,24)
    return (Evidence(citation='F1',chunk=r.chunks[0]),)


@pytest.mark.parametrize('claim',[
    'La asistencia es obligatoria.',
    'El artículo 24 establece que la asistencia es obligatoria.',
    'El artículo 24 del Régimen Académico Marco dispone que la asistencia es obligatoria.',
    'Según el artículo 24, la asistencia es obligatoria.',
])
def test_verified_metadata_framing_preserves_support(claim):
    e=evidence();question='Que establece el articulo 24 del Regimen Academico Marco?'
    output,_=supported_text(StructuredGeneration((Claim(claim,('F1',)),)),question,e,AcademicRelevance())
    assert output.respuesta!='SIN_EVIDENCIA' and '[F1]' in output.respuesta
    assert AcademicRelevance().supports_answer(question,output.respuesta,e)


@pytest.mark.parametrize('claim',[
    'El artículo 124 establece que la asistencia es obligatoria.',
    'El artículo 24 del Reglamento Electoral establece que la asistencia es obligatoria.',
    'El artículo 24 establece que la asistencia no es obligatoria.',
    'El artículo 24 establece que la asistencia es del 80 por ciento.',
    'El artículo 24 establece que el Rector administra presupuestos.',
])
def test_framing_never_authorizes_wrong_source_or_predicate(claim):
    output,_=supported_text(StructuredGeneration((Claim(claim,('F1',)),)),
        'Articulo 24',evidence(),AcademicRelevance())
    assert output.respuesta=='SIN_EVIDENCIA'


def test_unlinked_framing_and_mixed_versions_rejected():
    e=evidence()[0];policy=AcademicRelevance()
    unlinked=replace(e,chunk=replace(e.chunk,article=None))
    assert not policy.supports_answer('Articulo 24','El articulo 24 establece que la asistencia es obligatoria.',(unlinked,))
    _,other,*_=setup()
    wrong=replace(e,chunk=replace(e.chunk,scope=other))
    assert not policy.supports_answer('Articulo 24','El articulo 24 establece que la asistencia es obligatoria.',(wrong,))


@pytest.mark.parametrize('query,expected',[
    ('Cual fue mi ultima pregunta?', ['Tercera consulta']),
    ('Cual fue mi penultima pregunta?', ['Segunda consulta']),
    ('Cual fue mi primera pregunta?', ['Primera consulta']),
    ('Cuales fueron mis ultimas 2 preguntas?', ['Segunda consulta','Tercera consulta']),
    ('Cuales fueron mis preguntas anteriores?', ['Primera consulta','Segunda consulta','Tercera consulta']),
])
def test_temporal_memory_uses_order_not_unique_question(query,expected):
    history=tuple(m for q in ('Primera consulta','Segunda consulta','Tercera consulta')
        for m in ({'role':'user','content':q},{'role':'assistant','content':'PRIVATE_ASSISTANT'}))
    assert conversation_memory_reference(query)
    result=resolve_conversation_memory(query,history)
    assert all(q in result for q in expected) and 'PRIVATE_ASSISTANT' not in result


def test_duplicate_questions_are_distinct_turns_and_missing_count_abstains():
    h=({'role':'user','content':'Consulta repetida'},)*2
    assert resolve_conversation_memory('Mis ultimas 2 preguntas',h).count('Consulta repetida')==2
    assert resolve_conversation_memory('Mis ultimas 3 preguntas',h) is None
    assert resolve_conversation_memory('Mi ultima pregunta',()) is None
    h=(*h,{'role':'user','content':'Cual fue mi ultima pregunta?'})
    assert 'Cual fue mi ultima pregunta?' in resolve_conversation_memory('Mi ultima pregunta',h)


def test_memory_branch_calls_no_provider_with_multiple_prior_questions():
    from tests.rag.test_agent import fixture
    p,_,agent,_,direct,_,provider,embedding,_=fixture()
    result=asyncio.run(agent.execute(p,'Cual fue mi ultima pregunta?',history=(
        {'role':'user','content':'Consulta uno'},{'role':'user','content':'Consulta dos'})))
    assert result.status=='GENERADA' and 'Consulta dos' in result.answer and 'Consulta uno' not in result.answer
    assert not direct.calls and not provider.inputs and embedding.calls==0 and not result.citations


def test_conversation_service_passes_larger_authorized_window_only_for_memory():
    from uuid import UUID, uuid4
    from tests.rag.test_agent import fixture
    from tests.rag.test_tools_memory import MemoryConversations
    from app.application.agent.conversations import Conversations
    async def run():
        p,_,agent,*_=fixture()
        repo=MemoryConversations()
        service=Conversations(authorizer=agent.authorizer,repository=repo,agent=agent)
        a=UUID((await service.create(p))['id'])
        b=UUID((await service.create(p))['id'])
        repo.rows[a]=[m for i in range(8) for m in (
            {'role':'user','content':f'Consulta {i}','strategy':'LLM_DIRECTO'},
            {'role':'assistant','content':'No usar como evidencia','strategy':'LLM_DIRECTO'})]
        result=await service.turn(p,a,uuid4(),'Mis ultimas 6 preguntas','AUTO',None)
        answer=result['resultado']['respuesta']
        assert 'Consulta 2' in answer and 'Consulta 7' in answer and 'Consulta 0' not in answer
        other=await service.turn(p,b,uuid4(),'Mi ultima pregunta','AUTO',None)
        assert other['resultado']['estado']=='ACLARACION'
    asyncio.run(run())


@pytest.mark.parametrize('status',['SIN_EVIDENCIA','ACLARACION','FUNDAMENTADA'])
@pytest.mark.parametrize('query',['¿Sobre qué te había preguntado antes?','¿Qué te pregunté antes?',
                                '¿Cuál fue mi última pregunta?','¿De qué veníamos hablando?'])
def test_reported_memory_case_ignores_previous_answer_status(status,query):
    from tests.rag.test_agent import fixture
    p,_,agent,_,direct,_,provider,embedding,_=fixture()
    previous='¿Qué establece el artículo 24 del Régimen Académico Marco?'
    history=({'role':'user','content':'Consulta más antigua'},
             {'role':'assistant','content':'Respuesta anterior antigua','strategy':'LLM_DIRECTO'},
             {'role':'user','content':previous,'strategy':'RAG'},
             {'role':'assistant','content':'No hay evidencia suficiente.','strategy':'RAG','status':status})
    result=asyncio.run(agent.execute(p,query,history=history))
    assert result.status=='GENERADA' and previous in result.answer
    assert not direct.calls and not provider.inputs and not embedding.calls


@pytest.mark.parametrize('query',['¿Qué me respondiste anteriormente?','¿Podés repetir tu respuesta anterior?'])
def test_repeat_answer_is_literal_memory_not_documental_evidence(query):
    from tests.rag.test_agent import fixture
    p,_,agent,_,direct,_,provider,embedding,_=fixture()
    history=({'role':'user','content':'Articulo 24'},
             {'role':'assistant','content':'No hay evidencia suficiente.','strategy':'RAG','status':'SIN_EVIDENCIA'})
    result=asyncio.run(agent.execute(p,query,history=history))
    assert result.status=='GENERADA' and 'No hay evidencia suficiente.' in result.answer
    assert 'no evidencia nueva' in result.answer and not result.citations
    assert not direct.calls and not provider.inputs and not embedding.calls


def test_next_article_expands_exact_reference_and_reauthorizes_document():
    from app.application.agent.context import effective_question
    from tests.rag.test_agent import fixture
    from app.application.rag.articles import resolve_article
    p,s,agent,catalog,direct,_,provider,embedding,case=fixture()
    previous='¿Qué establece el artículo 24 del reglamento académico, en el Régimen Académico Marco?'
    async def listing(principal):return [{'id':str(s.document_id),'titulo':'reglamento académico'}]
    catalog.list_documents=listing
    history=({'role':'user','content':previous},
             {'role':'assistant','content':'No hay evidencia.','strategy':'RAG','status':'SIN_EVIDENCIA'})
    expanded,_=effective_question('¿Y qué establece el siguiente?',history)
    assert 'artículo 25' in expanded and 'Régimen Académico Marco' in expanded
    calls=[]
    async def exact(principal,scope,number,question):
        calls.append(number)
        assert scope==s and number==25 and 'Régimen Académico Marco' in question
        return resolve_article(((1,'Articulo 25. La asistencia es obligatoria.\nArticulo 26. Fin.'),),s,25)
    case.vectors.resolve_article=exact;case.vectors.explicit_article=lambda *a:None
    provider.output=GeneracionSalida(
        respuesta='La asistencia es obligatoria [F1].',finalizacion='completa')
    result=asyncio.run(agent.execute(p,'¿Y qué establece el siguiente?',history=history))
    assert result.status=='FUNDAMENTADA' and calls==[25] and result.citations
    assert catalog.documents.calls>=2 and not embedding.calls


def test_next_article_no_antecedent_asks_without_provider():
    from tests.rag.test_agent import fixture
    p,_,agent,_,direct,_,provider,embedding,_=fixture()
    result=asyncio.run(agent.execute(p,'¿Y qué establece el siguiente?'))
    assert result.status=='ACLARACION' and not provider.inputs and not embedding.calls and not direct.calls
