import asyncio
import json
from uuid import uuid4
import httpx
import pytest

from app.application.agent.router import AgentRouter
from app.application.ia.exceptions import IARespuestaInvalida
from app.application.ia.exceptions import IANoDisponible
from app.infrastructure.llm.openrouter import OpenRouterPlanner, DOTS_MODEL
from app.infrastructure.llm.work_gate import MemoryModelWorkGate
from tests.ia.test_dots_openrouter import CONFIG_DOTS
from tests.ia.test_openrouter import catalog
from tests.rag.test_agent import fixture


QUESTION='¿Cuáles son los requisitos para acceder a concursos de Coordinaciones de Carreras?'


@pytest.mark.parametrize('kind',['authorized_no_evidence','no_documents','multiple_documents'])
def test_procedural_academic_query_bypasses_planner_with_catalog_guards(kind):
    p,s,agent,documents,direct,_,provider,embedding,case=fixture()
    class NoPlanner:
        async def plan(self,*args):raise AssertionError('Explicit procedural intent must not plan')
    agent.planner=NoPlanner()
    if kind=='no_documents':documents.empty=True
    if kind=='multiple_documents':
        async def listing(principal):
            return [{'id':str(s.document_id),'titulo':'Documento A'}, {'id':str(uuid4()),'titulo':'Documento B'}]
        documents.list_documents=listing
    result=asyncio.run(agent.execute(p,QUESTION))
    assert result.strategy=='RAG' and not direct.calls and not provider.inputs
    if kind=='authorized_no_evidence':
        assert embedding.calls==1 and result.status=='SIN_EVIDENCIA'
        assert documents.documents.calls>=2
    else:
        assert embedding.calls==0
        assert result.status==('ACLARACION' if kind=='multiple_documents' else 'SIN_EVIDENCIA')


@pytest.mark.parametrize('question',[
    '¿Qué es un concurso de programación?',
    'Requisitos de Python para concursos de programación',
    '¿Cómo está el clima en Goya, Corrientes, Argentina?',
    '¿De qué te estuve preguntando?',
    'Requisitos para concursos de Coordinaciones de Carreras según el Reglamento Electoral',
])
def test_narrow_rule_does_not_claim_other_capabilities_or_named_instruments(question):
    assert not AgentRouter().institutional_requirements(question)


def test_http400_planner_request_is_technical_and_safe(caplog):
    calls=[]
    def handler(request):
        calls.append(request.method)
        if request.method=='GET':
            data=catalog(DOTS_MODEL);data['data']['endpoints'][0]['tag']='atlas-cloud/fp8'
            return httpx.Response(200,json=data)
        assert str(request.url)=='https://openrouter.ai/api/v1/chat/completions'
        payload=json.loads(request.content)
        assert payload['model']==DOTS_MODEL and payload['stream'] is False
        assert [m['role'] for m in payload['messages']]==['system','user']
        assert payload['max_tokens']==256 and payload['temperature']==0
        assert payload['response_format']['type']=='json_schema'
        assert payload['response_format']['json_schema']['strict'] is True
        assert payload['provider']['only']==['atlas-cloud']
        assert payload['provider']['data_collection']=='deny'
        assert payload['provider']['allow_fallbacks'] is False
        assert payload['provider']['max_price']=={'prompt':0,'completion':0}
        return httpx.Response(400,json={'error':{'message':'PRIVATE_UPSTREAM_BODY','code':400}})
    async def idle():pass
    async def run():
        provider=OpenRouterPlanner(CONFIG_DOTS,MemoryModelWorkGate(),idle,transport=httpx.MockTransport(handler))
        try:
            with pytest.raises(IARespuestaInvalida):await provider.plan('PRIVATE_SYNTHETIC_PROMPT')
        finally:await provider.aclose()
    asyncio.run(run())
    assert calls==['GET','POST']
    assert 'classification=request_rejected' in caplog.text and 'stage=chat_completion' in caplog.text
    assert 'PRIVATE_UPSTREAM_BODY' not in caplog.text and 'PRIVATE_SYNTHETIC_PROMPT' not in caplog.text


@pytest.mark.parametrize('status',[200,503])
def test_transient_weather_error_is_not_ambiguous_location(status):
    from app.infrastructure.rag.weather import OpenMeteo
    from app.application.agent.tools import WeatherArgs
    calls=[]
    def handler(request):
        calls.append(request.method)
        return httpx.Response(status,json={} if status==200 else {'reason':'PRIVATE_PROVIDER_BODY'})
    async def run():
        tool=OpenMeteo(transport=httpx.MockTransport(handler))
        try:
            if status==503:
                with pytest.raises(IANoDisponible):await tool._execute(WeatherArgs(ciudad='Vera',region='Santa Fe',pais='AR'))
            else:
                result=await tool._execute(WeatherArgs(ciudad='Vera',region='Santa Fe',pais='AR'))
                assert result.status=='ACLARACION'
        finally:await tool.close()
    asyncio.run(run())
    assert calls==['GET']
