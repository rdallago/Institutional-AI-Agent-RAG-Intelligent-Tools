import asyncio
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timezone, timedelta
from uuid import uuid4

import httpx
import pytest

from app.application.agent.admission import ScopedAdmission
from app.application.agent.context import AgentResult, effective_question, direct_context
from app.application.agent.conversations import Conversations, reject_secrets
from app.application.agent.tools import ToolRegistry, WeatherArgs, weather_arguments
from app.application.agent.skills.registry import SkillRegistry
from app.infrastructure.rag.skills import PackagedSkillLoader
from app.infrastructure.rag.weather import OpenMeteo
from app.infrastructure.rag.planner import JSONPlanner
from app.application.ia.exceptions import IARespuestaInvalida, IANoDisponible, IATiempoAgotado, IAOcupada, PromptInvalido
from app.application.auth.exceptions import PermisoDenegado
from tests.rag.test_agent import fixture
from tests.rag.test_adapters import CONFIG


def meteo_handler(request):
    if request.url.host=='geocoding-api.open-meteo.com':
        assert request.url.params['countryCode']=='AR'
        return httpx.Response(200,json={'results':[{'name':'Esquina','admin1':'Provincia de Corrientes','country_code':'AR','latitude':-30.01,'longitude':-59.53}]})
    assert request.url.host=='api.open-meteo.com' and request.url.path=='/v1/forecast'
    today=datetime.now(timezone(timedelta(hours=-3)))
    return httpx.Response(200,json={'utc_offset_seconds':-10800,'timezone':'America/Argentina/Cordoba',
      'current':{'time':today.isoformat(timespec='minutes'),'temperature_2m':21.5,'weather_code':2},
      'current_units':{'temperature_2m':'°C'},'daily_units':{'temperature_2m_min':'°C','temperature_2m_max':'°C'},
      'daily':{'time':[today.date().isoformat(),(today.date()+timedelta(days=1)).isoformat()],
               'temperature_2m_min':[10,11],'temperature_2m_max':[22,23],'weather_code':[1,3]}})


def test_weather_skill_applied_with_fixed_destinations_current_and_followup():
    async def run():
        p,s,agent,catalog,direct,skills,provider,embedding,case=fixture()
        agent.weather=OpenMeteo(transport=httpx.MockTransport(meteo_handler))
        try:
            result=await agent.execute(p,'¿Cómo está el clima en Esquina, Corrientes, Argentina?')
            assert result.strategy=='TOOL' and result.tool=='consultar_clima' and '21.5' in result.answer
            assert 'Open-Meteo' in result.answer and 'Referencia:' in result.answer
            history=({'role':'assistant','strategy':'TOOL','content':result.answer,'tool_context':result.tool_context},)
            tomorrow=await agent.execute(p,'¿Y mañana?',history=history)
            assert 'mínima 11' in tomorrow.answer and 'máxima 23' in tomorrow.answer
            assert skills.selected==['weather','weather'] and provider.inputs==[] and direct.calls==[]
        finally: await agent.weather.close()
    asyncio.run(run())


def test_weather_ambiguous_city_does_not_guess_or_call_forecast():
    async def run():
        count=[]
        def handler(request):
            count.append(request.url.host)
            return httpx.Response(200,json={'results':[
                {'name':'Paris','country_code':'US','admin1':'Texas'},
                {'name':'Paris','country_code':'US','admin1':'Ohio'}]})
        tool=OpenMeteo(transport=httpx.MockTransport(handler))
        try:
            skill=SkillRegistry(PackagedSkillLoader()).load('weather')
            result=await tool.execute(WeatherArgs(ciudad='Paris',pais='US'),skill.instructions)
            assert result.status=='ACLARACION' and len(count)==1
        finally: await tool.close()
    asyncio.run(run())


@pytest.mark.parametrize('mode',['network','contract','timeout','error_body'])
def test_weather_real_errors_not_abstention(mode):
    async def run():
        def handler(request):
            if mode=='network':raise httpx.ConnectError('PRIVATE')
            if mode=='timeout':raise httpx.ReadTimeout('PRIVATE')
            if mode=='error_body':return httpx.Response(200,json={'error':True,'reason':'PRIVATE'})
            return httpx.Response(200,json={'results':'PRIVATE'})
        tool=OpenMeteo(transport=httpx.MockTransport(handler))
        try:
            with pytest.raises({'network':IANoDisponible,'timeout':IATiempoAgotado}.get(mode,IARespuestaInvalida)):
                await tool.execute(WeatherArgs(ciudad='Esquina',pais='AR'),SkillRegistry(PackagedSkillLoader()).load('weather').instructions)
        finally:await tool.close()
    asyncio.run(run())


@pytest.mark.parametrize('raw',[
    '{"capacidad":"shell","argumentos":{}}',
    '{"capacidad":"weather","argumentos":{"ciudad":"http://127.0.0.1","pais":"AR"}}',
    '{"capacidad":"academic-rag","argumentos":{"sql":"SELECT 1"}}',
    '{"capacidad":"llm-directo","capacidad":"weather","argumentos":{}}',
    '[{"capacidad":"weather"},{"capacidad":"weather"}]',
])
def test_tool_allowlist_arguments_duplicates_cycles_rejected(raw):
    with pytest.raises(IARespuestaInvalida):ToolRegistry().validate(raw)


def test_planner_actual_adapter_schema_and_agent_dispatch_once():
    import json
    async def run():
        p,s,agent,catalog,direct,skills,provider,embedding,case=fixture()
        calls=[]
        async def idle():pass
        def handler(request):
            body=json.loads(request.content);calls.append(body)
            assert body['format']['discriminator']['propertyName']=='accion'
            assert body['think'] is False and body['keep_alive']==0
            return httpx.Response(200,json={'model':'qwen3:1.7b','done':True,'done_reason':'stop',
                'response':'{"accion":"responder_llm_directo","argumentos":{}}','prompt_eval_count':100})
        agent.planner=JSONPlanner(CONFIG,case.gate,idle,transport=httpx.MockTransport(handler))
        try:
            result=await agent.execute(p,'¿Qué me recomendás?')
            assert result.strategy=='LLM_DIRECTO' and len(calls)==1 and len(direct.calls)==1
        finally:await agent.planner.aclose()
    asyncio.run(run())


def test_followup_rag_resolves_topic_but_never_uses_old_answer_as_evidence():
    history=({'role':'user','content':'¿Cuánto dura la regularidad de una unidad curricular?','strategy':'RAG'},
             {'role':'assistant','content':'OLD_ANSWER_NOT_EVIDENCE','strategy':'RAG'})
    text,weather=effective_question('¿Y qué sucede cuando vence?',history)
    assert 'regularidad' in text and 'vence' in text and weather is None
    assert 'OLD_ANSWER' not in text and 'OLD_ANSWER' not in direct_context('Otra pregunta',history)
    assert len(direct_context('x'*1000,history))==1000


class MemoryConversations:
    def __init__(self):self.owners={};self.rows={};self.requests={}
    def owned(self,p,c):
        if self.owners.get(c)!=p.usuario_id:raise PermisoDenegado()
    async def create(self,p,conversation=None):
        c=conversation or uuid4()
        if c in self.owners:self.owned(p,c);return {'id':str(c)}
        self.owners[c]=p.usuario_id;self.rows[c]=[];return {'id':str(c)}
    async def list(self,p):return [{'id':c} for c,u in self.owners.items() if u==p.usuario_id]
    async def history(self,p,c):self.owned(p,c);return deepcopy(self.rows[c])
    async def reserve(self,p,c,k,f):
        self.owned(p,c);key=(c,k)
        if key in self.requests:
            r=self.requests[key]
            if r['fp']!=f:raise PromptInvalido()
            if r['state']!='COMPLETA':raise IAOcupada(1)
            return {'id':k,'replay':r['payload']}
        self.requests[key]={'fp':f,'state':'PENDIENTE'};return {'id':k,'replay':None}
    async def complete(self,p,c,k,q,result,refs,payload):
        self.owned(p,c)
        for role,content in [('user',q),('assistant',result.answer)]:
            self.rows[c].append({'id':len(self.rows[c])+1,'role':role,'content':content,
                'strategy':result.strategy,'status':result.status,'references':refs if role=='assistant' else [],
                'tool':result.tool,'tool_context':result.tool_context,'creado_at':'2026-11-04T00:00:00Z'})
        self.requests[(c,k)].update(state='COMPLETA',payload=payload)
    async def fail(self,p,c,k):
        self.owned(p,c);self.requests[(c,k)]['state']='FALLIDA'


def test_persistent_service_replay_owner_isolation_and_reload():
    async def run():
        p,s,agent,catalog,direct,skills,provider,embedding,case=fixture()
        repository=MemoryConversations()
        service=Conversations(authorizer=agent.authorizer,repository=repository,agent=agent)
        from uuid import UUID
        c=UUID((await service.create(p))['id']);key=uuid4()
        first=await service.turn(p,c,key,'¿Qué es una API REST?','AUTO',None)
        assert first['resultado']['estrategia']=='LLM_DIRECTO'
        assert await service.turn(p,c,key,'¿Qué es una API REST?','AUTO',None)==first
        assert len(direct.calls)==1 and len(await service.history(p,c))==2
        restored=Conversations(authorizer=agent.authorizer,repository=repository,agent=agent)
        assert len(await restored.history(replace(p,sesion_id=uuid4()),c))==2
        with pytest.raises(PermisoDenegado):await service.history(replace(p,usuario_id=uuid4()),c)
        with pytest.raises(PromptInvalido):await service.turn(p,c,key,'Pregunta diferente','AUTO',None)
    asyncio.run(run())


@pytest.mark.parametrize('value',['Bearer private','mi contraseña es privada123','token=secreto','eyJaaaa.bbbb.cccc'])
def test_secrets_rejected_before_persistence(value):
    with pytest.raises(PromptInvalido):reject_secrets(value)


def test_general_definition_of_tokens_is_not_mistaken_for_a_secret():
    reject_secrets('Un token es una unidad de texto.',output=True)
    reject_secrets('Una contraseña es una forma de autenticación.',output=True)


def test_scoped_admission_one_lease_for_planning_and_execution():
    class Delegate:
        calls=0;released=0
        def try_acquire(self,p):
            self.calls+=1;outer=self
            class Lease:
                def release(self,**kwargs):outer.released+=1
            return Lease()
    delegate=Delegate();admission=ScopedAdmission(delegate)
    with admission.scope('user'):
        admission.try_acquire('user').release()
        admission.try_acquire('user').release()
    assert delegate.calls==1 and delegate.released==1


def test_conversation_failure_is_not_persisted_as_success_or_reexecuted():
    from uuid import UUID
    async def run():
        p,s,agent,catalog,direct,skills,provider,embedding,case=fixture()
        class Broken:
            async def ejecutar(self,*args):raise IANoDisponible()
        agent.direct=Broken()
        repo=MemoryConversations();service=Conversations(authorizer=agent.authorizer,repository=repo,agent=agent)
        c=UUID((await service.create(p))['id']);key=uuid4()
        with pytest.raises(IANoDisponible):await service.turn(p,c,key,'General','AUTO',None)
        assert repo.rows[c]==[] and repo.requests[(c,key)]['state']=='FALLIDA'
        with pytest.raises(IAOcupada):await service.turn(p,c,key,'General','AUTO',None)
        with pytest.raises(PromptInvalido):await service.turn(p,c,uuid4(),'password=PRIVATE','AUTO',None)
        assert len(repo.requests)==1
    asyncio.run(run())


def test_conversation_followup_retrieves_again_and_revocation_blocks_history():
    from uuid import UUID
    async def run():
        p,s,agent,catalog,direct,skills,provider,embedding,case=fixture()
        chunk=case.vectors.items[0].chunk
        content='La regularidad de una unidad curricular dura dos ciclos y su vencimiento exige nuevo examen.'
        from app.application.rag.dto import Candidate
        case.vectors.items=(Candidate(chunk=replace(chunk,text=content,end=len(content)),similarity=.95),)
        repo=MemoryConversations();service=Conversations(authorizer=agent.authorizer,repository=repo,agent=agent)
        c=UUID((await service.create(p))['id'])
        await service.turn(p,c,uuid4(),'¿Cuánto dura la regularidad de una unidad curricular?','AUTO',None)
        result=await service.turn(p,c,uuid4(),'¿Y qué sucede cuando vence?','AUTO',None)
        assert result['resultado']['estrategia']=='RAG' and embedding.calls==2 and len(provider.inputs)==2
        assert 'regularidad' in provider.inputs[-1].question and 'vence' in provider.inputs[-1].question
        catalog.documents.revoked=True
        with pytest.raises(PermissionError):await service.history(p,c)
    asyncio.run(run())


def test_conversations_http_auth_contracts_and_ownership():
    from contextlib import asynccontextmanager
    from auth_support import memory_auth, bootstrap_login
    from fastapi.testclient import TestClient
    from app.bootstrap import create_app
    from app.infrastructure.llm.admission import MemoryGenerationAdmission
    from app.infrastructure.llm.ollama import LLMRuntime
    from ia_support import FakeLLMProvider
    from app.infrastructure.llm.authorization import AuthServiceNormalAccessAuthorizer
    store,auth,_=memory_auth();_,token=bootstrap_login(auth)
    @asynccontextmanager
    async def runtime(config):yield LLMRuntime(FakeLLMProvider(),MemoryGenerationAdmission(),60)
    app=create_app(repository=store.users,auth_service=auth,llm_config=CONFIG,llm_runtime_factory=runtime)
    repo=MemoryConversations()
    with TestClient(app) as client:
        app.state.conversations=Conversations(authorizer=AuthServiceNormalAccessAuthorizer(auth),repository=repo,agent=app.state.ia_agent)
        headers={'Authorization':'Bearer '+token};url='/api/v1/ia/conversaciones'
        assert client.get(url).status_code==401
        created=client.post(url,headers=headers,json={'conversacion_id':str(uuid4())})
        assert created.status_code==200 and created.headers['Cache-Control']=='no-store'
        c=created.json()['id'];key=str(uuid4())
        response=client.post(f'{url}/{c}/mensajes',headers=headers,json={'prompt':'¿Qué es una API REST?','solicitud_id':key})
        assert response.status_code==200 and response.json()['resultado']['estrategia']=='LLM_DIRECTO'
        assert len(client.get(f'{url}/{c}/mensajes',headers=headers).json())==2
        assert client.get(f'{url}/{uuid4()}/mensajes',headers=headers).status_code==403
        assert client.post(f'{url}/{c}/mensajes',headers=headers,json={'prompt':'x'*20000,'solicitud_id':str(uuid4())}).status_code==413


def test_planning_and_direct_execution_use_one_admission():
    from app.application.agent.planning import DirectProposal, EmptyArguments
    from app.application.ia.use_cases.generar_respuesta import GenerarRespuesta
    from ia_support import FakeLLMProvider
    async def run():
        p,s,agent,*_=fixture()
        class Delegate:
            calls=0;released=0
            def try_acquire(self,principal):
                self.calls+=1;outer=self
                class Lease:
                    def release(self,**kwargs):outer.released+=1
                return Lease()
        class Planner:
            async def plan(self,question):return DirectProposal(accion='responder_llm_directo',argumentos=EmptyArguments())
        delegate=Delegate();admission=ScopedAdmission(delegate)
        agent.admission=admission;agent.planner=Planner()
        agent.direct=GenerarRespuesta(FakeLLMProvider(),agent.authorizer,admission)
        result=await agent.execute(p,'¿Qué me recomendás?')
        assert result.strategy=='LLM_DIRECTO' and delegate.calls==1 and delegate.released==1
    asyncio.run(run())


@pytest.mark.parametrize('question,intent',[
    ('¿Qué es el clima?','general'),
    ('¿Lloverá mañana en Esquina, Argentina?','weather'),
    ('Según el reglamento, se suspenden clases por lluvia?','documentary'),
])
def test_intention_relations_not_only_weather_keyword(question,intent):
    from app.application.agent.router import AgentRouter
    assert AgentRouter().intent(question)==intent
