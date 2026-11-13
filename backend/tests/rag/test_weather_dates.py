import asyncio
from datetime import datetime, timezone, timedelta

import httpx
import pytest

from app.application.agent.tools import weather_arguments
from app.infrastructure.rag.weather import OpenMeteo
from tests.rag.test_agent import fixture
from tests.rag.test_tools_memory import meteo_handler


@pytest.mark.parametrize('suffix,day,explicit', [
    ('el día 08 de noviembre de 2026','fecha','2026-11-08'),
    ('el 08/11/2026','fecha','2026-11-08'),
    ('el 09/11/26','fecha','2026-11-09'),
    ('2026-11-08','fecha','2026-11-08'),
    ('mañana','mañana',None), ('pasado mañana','pasado mañana',None),
])
def test_location_separated_from_temporal_suffix(suffix,day,explicit):
    args=weather_arguments('¿Cómo estará el clima en Esquina, Corrientes, Argentina '+suffix+'?')
    assert (args.ciudad,args.region,args.pais,args.dia,args.fecha)==('Esquina','Corrientes','AR',day,explicit)


def test_relative_date_before_location():
    args=weather_arguments('¿Cómo estará el clima pasado mañana en Esquina, Corrientes, Argentina?')
    assert args.ciudad=='Esquina' and args.dia=='pasado mañana'


@pytest.mark.parametrize('question', ['¿y el 08/11/2026?', '¿y el 09/11/26?', '¿y el 8 de noviembre de 2026?', '¿y pasado mañana?'])
def test_followup_uses_location_and_actual_requested_day(question):
    async def run():
        p,s,agent,catalog,direct,skills,provider,embedding,case=fixture()
        def handler(request):
            response=meteo_handler(request)
            if request.url.host=='api.open-meteo.com':
                data=response.json()
                assert request.url.params['forecast_days']=='16'
                data['daily']={'time':[(datetime(2026,11,4).date()+timedelta(days=i)).isoformat() for i in range(16)],
                               'temperature_2m_min':[10]*16,'temperature_2m_max':[25]*16,'weather_code':[0]*16}
                return httpx.Response(200,json=data)
            return response
        agent.weather=OpenMeteo(transport=httpx.MockTransport(handler),clock=lambda:datetime(2026,11,5,1,tzinfo=timezone.utc))
        history=({'role':'assistant','strategy':'TOOL','tool':'consultar_clima','content':'Anterior',
                  'tool_context':{'ciudad':'Esquina','region':'Corrientes','pais':'AR','dia':'mañana'}},)
        try:
            result=await agent.execute(p,question,history=history)
            assert result.status=='HERRAMIENTA' and result.tool=='consultar_clima'
            expected='2026-11-06' if 'pasado' in question else ('2026-11-09' if '/26?' in question else '2026-11-08')
            assert expected in result.answer and '25' in result.answer
            assert result.tool_context['ciudad']=='Esquina'
            assert direct.calls==[] and provider.inputs==[]
        finally:await agent.weather.close()
    asyncio.run(run())


def test_regulation_failure_does_not_replace_weather_context_or_call_qwen_for_short_year():
    from app.application.ia.exceptions import IANoDisponible
    async def run():
        p,s,agent,catalog,direct,skills,provider,embedding,case=fixture()
        class UnavailableRAG:
            async def execute(self,*args,**kwargs):raise IANoDisponible()
        class NoPlanner:
            async def plan(self,*args):raise AssertionError('Qwen no debe decidir estos dos casos claros')
        class Weather:
            received=None
            async def execute(self,args,instructions):
                from app.application.agent.context import AgentResult
                self.received=args
                return AgentResult(strategy='TOOL',status='HERRAMIENTA',tool='consultar_clima',answer='Pronóstico de prueba')
        agent.rag=UnavailableRAG();agent.planner=None;agent.weather=Weather()
        history=({'role':'assistant','strategy':'TOOL','tool':'consultar_clima','content':'Anterior',
                  'tool_context':{'ciudad':'Esquina','region':'Corrientes','pais':'AR','dia':'fecha','fecha':'2026-11-08'}},)
        with pytest.raises(IANoDisponible):
            await agent.execute(p,'¿Podemos hablar del reglamento orgánico marco de Corrientes?',history=history)
        result=await agent.execute(p,'¿Y el 09/11/26?',history=history)
        assert result.tool=='consultar_clima'
        assert agent.weather.received.fecha=='2026-11-09' and agent.weather.received.ciudad=='Esquina'
        assert direct.calls==[] and provider.inputs==[]
    asyncio.run(run())


@pytest.mark.parametrize('suffix', ['el 31/11/2026','el 08/11/2026 o el 09/11/2026'])
def test_invalid_or_ambiguous_date_not_location_clarification(suffix):
    async def run():
        p,s,agent,*_=fixture()
        result=await agent.execute(p,'Clima en Esquina, Corrientes, Argentina '+suffix)
        assert result.status=='ACLARACION' and 'fecha válida' in result.answer
    asyncio.run(run())


@pytest.mark.parametrize('suffix', ['el 08/11/2025','el 08/11/2030','pasado mañana'])
def test_unavailable_horizon_or_missing_daily_has_no_invented_values(suffix):
    async def run():
        p,s,agent,*_=fixture()
        now=datetime.now(timezone.utc)
        agent.weather=OpenMeteo(transport=httpx.MockTransport(meteo_handler),clock=lambda:now)
        try:
            result=await agent.execute(p,'Clima en Esquina, Corrientes, Argentina '+suffix)
            assert result.status=='HERRAMIENTA' and 'pronóstico disponible' in result.answer
            assert 'mínima' not in result.answer
        finally:await agent.weather.close()
    asyncio.run(run())
