"""Regresiones de contaminacion de contexto y correlacion; sin modelos o SQL."""
import asyncio
import json
from uuid import UUID, uuid4

import pytest

from app.application.agent.context import direct_context
from app.application.agent.conversations import Conversations
from app.application.agent.diagnostics import execution_trace
from app.application.agent.planning import validate_proposal
from app.application.ia.dto import GeneracionSalida
from app.application.ia.exceptions import IATiempoAgotado
from tests.rag.test_agent import fixture
from tests.rag.test_tools_memory import MemoryConversations
from tests.rag.test_semantic_planning import WEATHER_HISTORY, ACADEMIC_HISTORY


@pytest.mark.parametrize('history', [WEATHER_HISTORY, ACADEMIC_HISTORY])
def test_autonomous_current_question_reaches_direct_provider_unchanged(history):
    async def run():
        p, scope, agent, *_ = fixture()
        class Planner:
            async def plan(self, payload):
                return validate_proposal(json.dumps({'accion':'responder_llm_directo','argumentos':{}}))
        class Direct:
            async def ejecutar(self, principal, data):
                assert data.prompt == 'contame un chiste'
                return GeneracionSalida(respuesta='Respuesta propia de esta solicitud.',finalizacion='completa')
        agent.planner, agent.direct = Planner(), Direct()
        result = await agent.execute(p,'contame un chiste',history=history)
        assert result.answer == 'Respuesta propia de esta solicitud.'
        assert result.strategy == 'LLM_DIRECTO' and result.status == 'GENERADA'
        assert result.tool is None
    asyncio.run(run())


def test_direct_followup_only_uses_direct_history_not_tool_outputs():
    history = WEATHER_HISTORY + (
        {'role':'user','content':'Explica HTTP','strategy':'LLM_DIRECTO'},
        {'role':'assistant','content':'Es un protocolo.','strategy':'LLM_DIRECTO'},)
    prompt = json.loads(direct_context('¿Y cómo funciona?',history))
    assert [m['content'] for m in prompt['historial_no_confiable']] == ['Explica HTTP','Es un protocolo.']
    assert prompt['pregunta_actual'] == '¿Y cómo funciona?'


def test_turn_persistence_response_replay_and_failure_are_request_bound(caplog):
    async def run():
        p, scope, agent, *_ = fixture()
        class Direct:
            async def ejecutar(self, principal, data):
                assert data.prompt in ('Primera pregunta independiente','Segunda pregunta independiente')
                return GeneracionSalida(respuesta='Salida para '+data.prompt,finalizacion='completa')
        agent.direct = Direct()
        repo = MemoryConversations()
        service = Conversations(authorizer=agent.authorizer,repository=repo,agent=agent)
        conversation = UUID((await service.create(p))['id'])
        keys = [uuid4(),uuid4()]
        results = []
        for key,question in zip(keys,('Primera pregunta independiente','Segunda pregunta independiente')):
            result = await service.turn(p,conversation,key,question,'LLM_DIRECTO',None)
            assert result['solicitud_id'] == str(key)
            assert result['resultado']['respuesta'] == 'Salida para '+question
            results.append(result)
        assert await service.turn(p,conversation,keys[0],'Primera pregunta independiente','LLM_DIRECTO',None) == results[0]
        assert len(await service.history(p,conversation)) == 4
        class BrokenPlanner:
            async def plan(self, payload): raise TimeoutError()
        agent.planner = BrokenPlanner()
        key = uuid4()
        with pytest.raises(IATiempoAgotado):
            await service.turn(p,conversation,key,
                '¿En el reglamento académico de Institutos Superiores, cuáles son las funciones del Rectorado?',
                'AUTO',None)
        assert repo.requests[(conversation,key)]['state'] == 'FALLIDA'
        assert len(await service.history(p,conversation)) == 4
        assert execution_trace.get() == 'isolated'
        assert 'stage=planner code=IA_TIEMPO_AGOTADO' in caplog.text
        assert 'Primera pregunta' not in caplog.text and 'Rectorado' not in caplog.text
    asyncio.run(run())
