"""Defectos de relevancia y cambio de tema; sin inferencia, SQL o vectores reales."""
import asyncio
from dataclasses import replace
import json

import pytest

from app.application.agent.planning import validate_proposal,planning_context
from app.application.ia.dto import GeneracionSalida
from app.application.rag.dto import Candidate
from tests.rag.test_agent import fixture
from tests.rag.test_semantic_planning import WEATHER_HISTORY,ACADEMIC_HISTORY,WeatherCapture,weather


QUESTION='¿En el reglamento académico de Institutos Superiores, cuáles son las funciones del Rectorado?'
DIRECT_SOURCE='Las funciones del Rectorado de los Institutos Superiores son coordinar las actividades académicas y presentar informes.'
RELATED_SOURCE='La Secretaría Administrativa coordina la administración y asesora al Consejo Directivo y al Rector.'


def set_source(case,source):
    old=case.vectors.items[0].chunk
    chunk=replace(old,text=source,end=old.start+len(source))
    case.vectors.items=(Candidate(chunk=chunk,similarity=.99),)


@pytest.mark.parametrize('source,output,expected',[
    (DIRECT_SOURCE,DIRECT_SOURCE+' [F1]','FUNDAMENTADA'),
    (RELATED_SOURCE,RELATED_SOURCE+' [F1]','SIN_EVIDENCIA'),
    (DIRECT_SOURCE,RELATED_SOURCE+' [F1]','SIN_EVIDENCIA'),
    ('Los Institutos Superiores tienen sede. El Rectorado tiene funciones de coordinación.',DIRECT_SOURCE+' [F1]','SIN_EVIDENCIA'),
])
def test_grounding_requires_question_source_answer_alignment_not_just_valid_citation(source,output,expected):
    async def run():
        p,s,agent,catalog,direct,skills,provider,embedding,case=fixture()
        set_source(case,source)
        provider.output=GeneracionSalida(respuesta=output,finalizacion='completa')
        result=await case.execute(p,s.document_id,QUESTION)
        assert result.status==expected
        if expected=='SIN_EVIDENCIA':assert result.citations==() and result.finalization is None
        else:assert result.citations and result.answer==output
        if source==RELATED_SOURCE:assert provider.inputs==[]  # Ni score .99 basta.
    asyncio.run(run())


def test_model_rewrite_cannot_replace_documentary_subject():
    async def run():
        p,s,agent,catalog,direct,skills,provider,embedding,case=fixture()
        set_source(case,RELATED_SOURCE)
        class Planner:
            async def plan(self,payload):
                assert json.loads(payload)['pregunta_actual']==QUESTION
                return validate_proposal(json.dumps({'accion':'consultar_documentos_academicos','argumentos':{
                    'documento_id':str(s.document_id),'documento_solicitado':None,
                    'consulta':'¿Qué funciones tiene la Secretaría Administrativa?'}}))
        agent.planner=Planner()
        result=await agent.execute(p,QUESTION)
        assert result.status=='SIN_EVIDENCIA' and provider.inputs==[] and direct.calls==[]
    asyncio.run(run())


@pytest.mark.parametrize('question',['contame un chiste','escribí un poema','ayudame a redactar una invitación','contame una historia sobre Goya'])
@pytest.mark.parametrize('history',[WEATHER_HISTORY,ACADEMIC_HISTORY])
def test_unrelated_conversation_does_not_accept_stale_weather_proposal(question,history):
    async def run():
        p,s,agent,catalog,direct,skills,provider,embedding,case=fixture()
        calls=[]
        class WrongPlanner:
            async def plan(self,payload):
                data=json.loads(payload);calls.append(data)
                assert data['pregunta_actual']==question and data['historial_no_confiable']==[]
                return validate_proposal(json.dumps(weather()))
        agent.planner=WrongPlanner();agent.weather=WeatherCapture()
        result=await agent.execute(p,question,history=history)
        assert result.strategy=='LLM_DIRECTO' and len(direct.calls)==1
        assert agent.weather.calls==[] and provider.inputs==[] and embedding.calls==0 and len(calls)==1
    asyncio.run(run())


@pytest.mark.parametrize('question,history',[
    ('¿Cuál es el clima en Goya Corrientes Argentina hoy?',()),
    ('¿Y mañana?',WEATHER_HISTORY),
])
def test_explicit_weather_and_genuine_followup_still_use_tool(question,history):
    async def run():
        p,s,agent,catalog,direct,skills,provider,embedding,case=fixture()
        class Planner:
            async def plan(self,payload):return validate_proposal(json.dumps(weather(day='mañana' if history else 'hoy')))
        agent.planner=Planner();agent.weather=WeatherCapture()
        result=await agent.execute(p,question,history=history)
        assert result.tool=='consultar_clima' and result.status=='HERRAMIENTA'
        assert len(agent.weather.calls)==1 and direct.calls==[]
    asyncio.run(run())


def test_each_turn_plans_again_no_reuse_of_previous_action():
    async def run():
        p,s,agent,catalog,direct,skills,provider,embedding,case=fixture()
        inputs=[]
        class Planner:
            async def plan(self,payload):
                inputs.append(json.loads(payload)['pregunta_actual'])
                return validate_proposal(json.dumps(weather() if len(inputs)==1 else {'accion':'responder_llm_directo','argumentos':{}}))
        agent.planner=Planner();agent.weather=WeatherCapture()
        first=await agent.execute(p,'Clima en Goya Corrientes Argentina hoy')
        second=await agent.execute(p,'Contame una historia breve',history=WEATHER_HISTORY)
        assert first.strategy=='TOOL' and second.strategy=='LLM_DIRECTO'
        assert len(inputs)==2 and len(agent.weather.calls)==1 and len(direct.calls)==1
    asyncio.run(run())


def test_structural_followup_context_not_imposed_on_new_imperative():
    data=json.loads(planning_context('¿Y qué sucede cuando vence?',ACADEMIC_HISTORY,[],None))
    assert data['historial_no_confiable']
    data=json.loads(planning_context('Y escribí un cuento',ACADEMIC_HISTORY,[],None))
    assert data['historial_no_confiable']==[]
