"""Orquestación/modelo simulado: no acredita interpretación del Qwen real."""
import asyncio
import json
from uuid import uuid4

import httpx
import pytest

from app.application.agent.context import AgentResult
from app.application.agent.planning import validate_proposal, planning_context
from app.application.ia.exceptions import IANoDisponible, IARespuestaInvalida
from app.infrastructure.rag.planner import JSONPlanner
from app.infrastructure.rag.weather import OpenMeteo
from tests.rag.test_agent import fixture
from tests.rag.test_adapters import CONFIG
from tests.rag.test_tools_memory import meteo_handler


WEATHER_HISTORY=({'role':'user','content':'Clima en Goya Corrientes Argentina hoy','strategy':'TOOL'},
    {'role':'assistant','content':'PRIVATE_RESPONSE_NOT_FOR_PLANNER','strategy':'TOOL','tool':'consultar_clima',
     'tool_context':{'ciudad':'Goya','region':'Corrientes','pais':'AR','dia':'hoy','fecha':None}})
ACADEMIC_HISTORY=WEATHER_HISTORY+({'role':'user','content':'Regularidad curricular','strategy':'RAG'},
    {'role':'assistant','content':'OLD_RAG_NOT_EVIDENCE','strategy':'RAG','tool_context':{'topic':'regularidad'}})


def weather(city='Goya',day='hoy'):
    return {'accion':'consultar_clima','argumentos':{'ciudad':city,'provincia':'Corrientes','pais':'AR','fecha':day}}


class WeatherCapture:
    def __init__(self):self.calls=[]
    async def execute(self,args,instructions):
        self.calls.append(args)
        return AgentResult(strategy='TOOL',status='HERRAMIENTA',tool='consultar_clima',
                           answer='Pronóstico simulado, no dato meteorológico real.',tool_context=args.model_dump())


def attach(agent,case,output,observed):
    async def idle():pass
    def handler(request):
        body=json.loads(request.content)
        assert body['format']['discriminator']['propertyName']=='accion'
        assert body['think'] is False and body['keep_alive']==0
        observed.append(json.loads(body['prompt']))
        return httpx.Response(200,json={'model':'qwen3:1.7b','done':True,'done_reason':'stop',
            'response':json.dumps(output,ensure_ascii=False),'prompt_eval_count':120})
    agent.planner=JSONPlanner(CONFIG,case.gate,idle,transport=httpx.MockTransport(handler))


@pytest.mark.parametrize('question,history,proposal,city,day',[
    ('¿Cuál es el clima en Goya Corrientes Argentina hoy?',(),weather(),'Goya','hoy'),
    ('¿Cómo estará el tiempo mañana en Esquina?',WEATHER_HISTORY,weather('Esquina','mañana'),'Esquina','mañana'),
    ('¿Cómo está el clima en Goya?',ACADEMIC_HISTORY,weather(),'Goya','hoy'),
    ('¿Y cómo está el clima en Goya?',ACADEMIC_HISTORY,weather(),'Goya','hoy'),
])
def test_semantic_model_output_extracts_and_switches_without_regex(question,history,proposal,city,day,caplog):
    async def run():
        p,s,agent,catalog,direct,skills,provider,embedding,case=fixture()
        observed=[];attach(agent,case,proposal,observed);agent.weather=WeatherCapture()
        try:
            result=await agent.execute(p,question,history=history)
            assert result.strategy=='TOOL' and len(agent.weather.calls)==1 and len(observed)==1
            args=agent.weather.calls[0]
            assert (args.ciudad,args.region,args.pais,args.dia)==(city,'Corrientes','AR',day)
            assert observed[0]['pregunta_actual']==question  # No se impone tema anterior.
            assert 'PRIVATE_RESPONSE' not in json.dumps(observed) and 'OLD_RAG' not in json.dumps(observed)
            assert direct.calls==[] and provider.inputs==[]
        finally:await agent.planner.aclose()
    asyncio.run(run())
    assert 'source=qwen action=consultar_clima' in caplog.text
    assert question not in caplog.text


def test_complete_weather_followup_uses_rules_without_planner(caplog):
    async def run():
        p, s, agent, *_ = fixture()
        class NoPlanner:
            async def plan(self, payload):
                raise AssertionError('Complete weather followup must use rules')
        agent.planner = NoPlanner()
        agent.weather = WeatherCapture()
        result = await agent.execute(p, '¿Y pasado mañana?', history=WEATHER_HISTORY)
        assert result.tool == 'consultar_clima'
        assert len(agent.weather.calls) == 1
        args = agent.weather.calls[0]
        assert (args.ciudad, args.region, args.pais, args.dia) == ('Goya', 'Corrientes', 'AR', 'pasado mañana')
    asyncio.run(run())
    assert 'source=rules intent=weather' in caplog.text


def test_semantic_weather_to_general_and_academic_rag():
    async def run():
        p,s,agent,catalog,direct,skills,provider,embedding,case=fixture()
        observed=[];attach(agent,case,{'accion':'responder_llm_directo','argumentos':{}},observed)
        try:
            result=await agent.execute(p,'¿Qué es una API REST?',history=WEATHER_HISTORY)
            assert result.strategy=='LLM_DIRECTO' and len(direct.calls)==1
        finally:await agent.planner.aclose()
        question='¿Cuánto dura la regularidad de una unidad curricular?'
        attach(agent,case,{'accion':'consultar_documentos_academicos','argumentos':{
            'documento_id':str(s.document_id),'documento_solicitado':None,'consulta':question}},observed)
        try:
            result=await agent.execute(p,question,history=WEATHER_HISTORY)
            assert result.strategy=='RAG' and result.status=='FUNDAMENTADA' and result.citations
            assert 'regularidad' in provider.inputs[0].question
        finally:await agent.planner.aclose()
    asyncio.run(run())


@pytest.mark.parametrize('selected_id',['catalog','none'])
def test_requested_rom_unavailable_never_substitutes_academic_document(selected_id):
    async def run():
        p,s,agent,catalog,direct,skills,provider,embedding,case=fixture()
        observed=[]
        question='¿Podés hablarme de las coordinaciones contempladas en el ROM RM 1455/14 de Corrientes?'
        attach(agent,case,{'accion':'consultar_documentos_academicos','argumentos':{
            'documento_id':str(s.document_id) if selected_id=='catalog' else None,
            'documento_solicitado':'ROM RM 1455/14 de Corrientes','consulta':question}},observed)
        try:
            result=await agent.execute(p,question,history=WEATHER_HISTORY)
            assert result.status=='SIN_EVIDENCIA' and 'ese documento' in result.answer
            assert direct.calls==[] and embedding.calls==0 and provider.inputs==[] and result.citations==()
        finally:await agent.planner.aclose()
    asyncio.run(run())


def test_model_document_id_cannot_bypass_authorized_catalog():
    async def run():
        p,s,agent,catalog,direct,skills,provider,embedding,case=fixture()
        attach(agent,case,{'accion':'consultar_documentos_academicos','argumentos':{
            'documento_id':str(uuid4()),'documento_solicitado':None,'consulta':'Regularidad curricular'}},[])
        try:
            with pytest.raises(IARespuestaInvalida):await agent.execute(p,'Regularidad curricular')
            assert embedding.calls==0
        finally:await agent.planner.aclose()
    asyncio.run(run())


@pytest.mark.parametrize('kind',['ambiguous','unavailable'])
def test_semantic_weather_still_validates_geocoding_and_real_provider_errors(kind):
    async def run():
        p,s,agent,catalog,direct,skills,provider,embedding,case=fixture()
        attach(agent,case,weather('Paris'),[])
        def handler(request):
            if kind=='unavailable':raise httpx.ConnectError('PRIVATE')
            return httpx.Response(200,json={'results':[{'name':'Paris','country_code':'AR','admin1':'Corrientes'},
                                                      {'name':'Paris','country_code':'AR','admin1':'Corrientes'}]})
        agent.weather=OpenMeteo(transport=httpx.MockTransport(handler))
        try:
            if kind=='unavailable':
                with pytest.raises(IANoDisponible):await agent.execute(p,'¿Qué clima hace en Paris, Corrientes, Argentina?')
            else:
                result=await agent.execute(p,'¿Qué clima hace en Paris, Corrientes, Argentina?')
                assert result.status=='ACLARACION'
        finally:await agent.planner.aclose();await agent.weather.close()
    asyncio.run(run())


def test_memory_blocked_planner_never_calls_transport_or_guesses_unknown_entities(monkeypatch):
    from dataclasses import replace
    import app.infrastructure.rag.planner as module
    async def run():
        p,s,agent,catalog,direct,skills,provider,embedding,case=fixture()
        calls=[]
        def blocked(minimum):raise IANoDisponible()
        monkeypatch.setattr(module,'require_memory',blocked)
        async def idle():pass
        agent.planner=JSONPlanner(replace(CONFIG,testing=False,environment='local-development'),case.gate,idle)
        async def forbidden(*args,**kwargs):calls.append(1);raise AssertionError('No cargar modelo')
        monkeypatch.setattr(agent.planner,'_generate_validated',forbidden)
        try:
            with pytest.raises(IANoDisponible):await agent.execute(p,'¿Cuál es el clima en Goya Corrientes Argentina hoy?')
            assert calls==[] and direct.calls==[]
        finally:await agent.planner.aclose()
    asyncio.run(run())


@pytest.mark.parametrize('proposal',[
    {'accion':'shell','argumentos':{}},
    {'accion':'consultar_clima','argumentos':{'ciudad':'http://evil','provincia':None,'pais':'AR','fecha':'hoy'}},
    {'accion':'consultar_clima','argumentos':{'ciudad':'Goya','provincia':None,'pais':'AR','fecha':'2026-02-31'}},
    {'accion':'responder_llm_directo','argumentos':{'sql':'SELECT 1'}},
    {'accion':'responder_llm_directo','argumentos':{},'next':{'accion':'shell'}},
])
def test_semantic_proposals_strictly_reject_invalid_arguments_and_cycles(proposal):
    with pytest.raises(IARespuestaInvalida):validate_proposal(json.dumps(proposal))


def test_duplicate_keys_in_semantic_plan_are_rejected():
    with pytest.raises(IARespuestaInvalida):
        validate_proposal('{"accion":"shell","accion":"responder_llm_directo","argumentos":{}}')


def test_semantic_context_is_bounded_and_does_not_include_private_rag_responses():
    data=json.loads(planning_context('Consulta',ACADEMIC_HISTORY,[{'id':str(uuid4()),'titulo':'Documento'}],None))
    assert data['ubicacion_previa']['ciudad']=='Goya'
    assert 'OLD_RAG' not in json.dumps(data) and data['historial_no_confiable']==[]


def test_unavailable_planner_only_allows_complete_deterministic_weather_not_new_entity_guess():
    async def run():
        p,s,agent,catalog,direct,skills,provider,embedding,case=fixture()
        class Blocked:
            async def plan(self,payload):raise IANoDisponible()
        agent.planner=Blocked();agent.weather=WeatherCapture()
        result=await agent.execute(p,'Clima en Esquina, Corrientes, Argentina hoy')
        assert result.strategy=='TOOL' and len(agent.weather.calls)==1
        with pytest.raises(IANoDisponible):await agent.execute(p,'Clima en Goya Corrientes Argentina hoy')
        assert len(agent.weather.calls)==1
    asyncio.run(run())


def test_safe_public_errors_distinguish_weather_planner_and_memory():
    from app.application.agent.errors import ClimaNoDisponible, PlanificadorNoDisponible, MemoriaPlanificadorInsuficiente
    from app.presentation.http.errors import PUBLIC_ERRORS
    assert PUBLIC_ERRORS[ClimaNoDisponible][:2]==(503,'CLIMA_NO_DISPONIBLE')
    assert PUBLIC_ERRORS[PlanificadorNoDisponible][:2]==(503,'IA_PLANIFICADOR_NO_DISPONIBLE')
    assert PUBLIC_ERRORS[MemoriaPlanificadorInsuficiente][:2]==(503,'IA_MEMORIA_INSUFICIENTE')
