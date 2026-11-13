"""Recuerdo de preguntas autorizadas: sin LLM, SQL o servicios externos."""
import asyncio
import json
from uuid import UUID, uuid4

import pytest

from app.application.agent.context import conversation_memory_reference, conversation_memory_context
from app.application.agent.conversations import Conversations
from app.application.ia.dto import GeneracionSalida, ConsultaDatos, validate_prompt
from tests.rag.test_agent import fixture
from tests.rag.test_tools_memory import MemoryConversations

FIRST = '¿Cuáles son las funciones del Rectorado según el Reglamento Orgánico Marco?'
FOLLOW = '¿Sobre qué órgano del Reglamento Orgánico Marco te pregunté anteriormente?'


@pytest.mark.parametrize('question', [FOLLOW, '¿Qué te pregunté antes?',
    '¿Cuál fue mi pregunta anterior?', '¿Qué te había preguntado previamente?'])
def test_explicit_memory_reference(question):
    assert conversation_memory_reference(question)


@pytest.mark.parametrize('question', [FIRST, '¿Qué establece el artículo anterior?',
    'Volviendo al reglamento, ¿qué establece el artículo 24?',
    '¿Cómo está el clima en Esquina, Corrientes, Argentina?', '¿Qué es una API REST?'])
def test_documentary_and_other_questions_are_not_memory_queries(question):
    assert not conversation_memory_reference(question)


def test_context_only_contains_user_questions_and_respects_budget():
    history = ({'role':'user','content':FIRST,'strategy':'RAG'},
               {'role':'assistant','content':'PRIVATE_RAG_RESPONSE','strategy':'RAG'})
    prompt = conversation_memory_context(FOLLOW, history)
    data = json.loads(prompt)
    assert data['pregunta_actual'] == FOLLOW
    assert data['historial_no_confiable'] == [{'role':'user','content':FIRST}]
    assert 'PRIVATE_RAG_RESPONSE' not in prompt
    validate_prompt(ConsultaDatos(prompt=prompt))
    assert conversation_memory_context(FOLLOW, ()) is None
    assert conversation_memory_context(FOLLOW, (*history, {'role':'user','content':'x'*1000})) is None
    bounded = conversation_memory_context(FOLLOW, tuple({'role':'user','content':'🙂'*20} for _ in range(30)))
    validate_prompt(ConsultaDatos(prompt=bounded))
    assert len(json.loads(bounded)['historial_no_confiable']) <= 8


def test_memory_precedes_document_routing_and_never_uses_assistant_evidence():
    async def run():
        p, scope, agent, *_ = fixture()
        class MustNotRun:
            async def list_documents(self, *args): raise AssertionError('No catalog lookup')
            async def execute(self, *args, **kwargs): raise AssertionError('No RAG/weather')
            async def plan(self, *args): raise AssertionError('No planner')
        blocker = MustNotRun()
        agent.documents = agent.rag = agent.weather = agent.planner = blocker
        class Direct:
            async def ejecutar(self, principal, data):
                raise AssertionError('Memory must not call Qwen')
        agent.direct = Direct()
        result = await agent.execute(p, FOLLOW, history=(
            {'role':'user','content':FIRST,'strategy':'RAG'},
            {'role':'assistant','content':'Untrusted answer','strategy':'RAG'}))
        assert result.strategy == 'LLM_DIRECTO' and result.status == 'GENERADA'
        assert result.answer == 'Me preguntaste por Rectorado.'
        assert result.citations == () and result.tool is None
    asyncio.run(run())


def test_empty_memory_asks_for_clarification_without_generation():
    async def run():
        p, _, agent, _, direct, *_ = fixture()
        result = await agent.execute(p, FOLLOW)
        assert result.status == 'ACLARACION' and not direct.calls
        assert result.citations == ()
    asyncio.run(run())


def test_real_window_counts_organs_not_unrelated_questions():
    from app.application.agent.context import resolve_conversation_memory
    history = (
        {'role':'user','content':'¿Cuál es el clima en Esquina Corrientes Argentina?'},
        {'role':'assistant','content':'No location','strategy':'TOOL'},
        {'role':'user','content':'¿Cuáles son los requisitos para acceder al concurso de coordinación de carrera según el Reglamento Orgánico Marco?'},
        {'role':'assistant','content':'No evidence','strategy':'RAG'},
        {'role':'user','content':FOLLOW},
        {'role':'assistant','content':'Previous clarification','strategy':'LLM_DIRECTO'},
        {'role':'user','content':FIRST},
        {'role':'assistant','content':'RAG answer not used','strategy':'RAG'},
    )
    assert resolve_conversation_memory(FOLLOW, history) == 'Me preguntaste por Rectorado.'
    assert resolve_conversation_memory(FOLLOW, ({'role':'user','content':FIRST},
        {'role':'user','content':FIRST.lower()}, {'role':'user','content':FOLLOW})) == 'Me preguntaste por rectorado.'
    assert resolve_conversation_memory(FOLLOW, ({'role':'user','content':FIRST},
        {'role':'user','content':FIRST.replace('Rectorado','Consejo')})) is None


def test_two_conversations_do_not_share_memory_and_current_question_is_not_recalled():
    async def run():
        p, _, agent, *_ = fixture()
        repo = MemoryConversations()
        service = Conversations(authorizer=agent.authorizer, repository=repo, agent=agent)
        a = UUID((await service.create(p))['id'])
        b = UUID((await service.create(p))['id'])
        repo.rows[a] = [{'role':'user','content':FIRST,'strategy':'RAG'},
                        {'role':'assistant','content':'PRIVATE_ANSWER','strategy':'RAG'}]
        class Direct:
            async def ejecutar(self, principal, data):
                raise AssertionError('Memory must not call Qwen')
        agent.direct = Direct()
        result = await service.turn(p, a, uuid4(), FOLLOW, 'AUTO', None)
        assert result['resultado']['respuesta'] == 'Me preguntaste por Rectorado.'
        other = await service.turn(p, b, uuid4(), FOLLOW, 'AUTO', None)
        assert other['resultado']['estado'] == 'ACLARACION'
    asyncio.run(run())
