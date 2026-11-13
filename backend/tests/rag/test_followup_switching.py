"""Context and dispatch regressions: in-memory doubles, no services."""
import asyncio
import json

import pytest

from app.application.agent.context import AgentResult, contextual_reference, direct_context, effective_question
from app.application.agent.planning import planning_context, validate_proposal
from tests.rag.test_agent import fixture
from tests.rag.test_semantic_planning import ACADEMIC_HISTORY, WEATHER_HISTORY, WeatherCapture


@pytest.mark.parametrize('question', [
    '¿Y cuáles son los requisitos?', '¿Y cuál es el plazo?',
    'Volviendo al reglamento, ¿qué establece?',
    'Retomando la consulta anterior', 'Regresando al tema anterior',
])
def test_followup_forms(question):
    assert contextual_reference(question)


@pytest.mark.parametrize('question', [
    'Cambiando de tema, ¿qué es Python?',
    'Y cambiando de tema, ¿qué temperatura hace hoy?',
    'Otro tema: requisitos académicos', 'Ahora hablemos de programación',
])
def test_explicit_topic_reset(question):
    assert not contextual_reference(question)
    assert effective_question(question, ACADEMIC_HISTORY) == (question, None)
    assert direct_context(question, WEATHER_HISTORY) == question
    data = json.loads(planning_context(question, ACADEMIC_HISTORY, [], None))
    assert data['historial_no_confiable'] == []


def test_followup_history_never_recycles_rag_answers():
    question = '¿Y cuáles son los requisitos?'
    data = planning_context(question, ACADEMIC_HISTORY, [], None)
    assert 'Regularidad curricular' in data
    assert 'OLD_RAG_NOT_EVIDENCE' not in data and 'PRIVATE_RESPONSE' not in data
    assert direct_context(question, ACADEMIC_HISTORY) == question
    expanded, _ = effective_question(question, ACADEMIC_HISTORY)
    assert 'OLD_RAG_NOT_EVIDENCE' not in expanded
    long_history = ({'role':'user','content':'x'*4000},
                    {'role':'assistant','strategy':'RAG','tool_context':{'topic':'x'*4000}})
    assert effective_question(question, long_history) == (question, None)


def test_same_conversation_switches_rag_weather_general_and_back():
    async def run():
        p, scope, agent, catalog, direct, *_ = fixture()
        history = []
        payloads, rag_questions = [], []
        async def listed(principal):
            return [{'id':str(scope.document_id), 'titulo':'Reglamento Orgánico Marco'}]
        catalog.list_documents = listed
        class RAG:
            async def execute(self, principal, document, question, **kwargs):
                await catalog.require_active(principal, document)
                rag_questions.append(question)
                return AgentResult(strategy='RAG',status='SIN_EVIDENCIA',answer='PRIVATE_RAG_OUTPUT')
        class Planner:
            async def plan(self, raw):
                data = json.loads(raw)
                payloads.append(data)
                q = data['pregunta_actual']
                if 'programación' in q:
                    proposal = {'accion':'responder_llm_directo','argumentos':{}}
                elif q == '¿Y mañana?':
                    assert data['ubicacion_previa']['ciudad'] == 'Esquina'
                    proposal = {'accion':'consultar_clima','argumentos':{
                        'ciudad':'Esquina','provincia':'Corrientes','pais':'AR','fecha':'mañana'}}
                else:
                    proposal = {'accion':'consultar_documentos_academicos','argumentos':{
                        'documento_id':str(scope.document_id),'documento_solicitado':None,'consulta':q}}
                return validate_proposal(json.dumps(proposal))
        agent.rag, agent.planner, agent.weather = RAG(), Planner(), WeatherCapture()
        questions = [
            '¿Cuáles son las funciones del Rectorado según el Reglamento Orgánico Marco?',
            '¿Y cómo está el clima en Esquina, Corrientes, Argentina hoy?',
            '¿Qué es la programación orientada a objetos?',
            '¿Y cuáles son los requisitos para ser coordinador de carrera?',
            '¿Y mañana?',
            'Volviendo al reglamento, ¿qué establece sobre el Rectorado?',
        ]
        strategies = []
        for question in questions:
            result = await agent.execute(p, question, history=tuple(history))
            strategies.append(result.strategy)
            history.extend([
                {'role':'user','content':question,'strategy':result.strategy},
                {'role':'assistant','content':result.answer,'strategy':result.strategy,
                 'tool':result.tool,'tool_context':result.tool_context},
            ])
        assert strategies == ['RAG','TOOL','LLM_DIRECTO','RAG','TOOL','RAG']
        assert agent.weather.calls[0].ciudad == 'Esquina'
        assert agent.weather.calls[1].dia == 'mañana'
        assert direct.calls[0].prompt == questions[2]
        followup = next(x for x in payloads if x['pregunta_actual'] == questions[3])
        assert questions[0] in followup['historial_no_confiable']
        returning = payloads[-1]
        assert returning['historial_no_confiable']
        assert 'PRIVATE_RAG_OUTPUT' not in json.dumps(payloads)
        assert rag_questions[-1] == questions[-1]
    asyncio.run(run())
