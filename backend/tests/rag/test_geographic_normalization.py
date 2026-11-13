import asyncio
import json

import httpx
import pytest

from app.application.agent.geography import country_code,explicit_countries,normalize_geography
from app.application.agent.planning import WeatherArguments,validate_proposal
from app.infrastructure.rag.weather import OpenMeteo
from app.infrastructure.rag.skills import PackagedSkillLoader
from tests.rag.test_tools_memory import meteo_handler


def proposed(city='Goya',region='Corrientes',country='AU'):
    return WeatherArguments(ciudad=city,provincia=region,pais=country,fecha='hoy')


@pytest.mark.parametrize('value,code',[('Argentina','AR'),('arg','AR'),('ar','AR'),('Australia','AU'),
    ('España','ES'),('Germany','DE'),('Estados Unidos','US'),('ZZ',None)])
def test_general_iso_country_names_and_codes(value,code):assert country_code(value)==code


@pytest.mark.parametrize('question', ['Clima en Goya Corrientes Argentina hoy','Clima en Goya, Corrientes, AR hoy'])
def test_explicit_country_overrides_wrong_proposal_without_mutating_it(question):
    original=proposed()
    result=normalize_geography(original,question)
    assert original.pais=='AU' and result.args.pais=='AR' and result.country_changed
    assert result.reason=='requires_geocoding'


def test_country_correct_unchanged_and_model_name_accepted_for_normalization():
    for value in ('AR','Argentina'):
        result=normalize_geography(proposed(country=value),'Clima en Goya Corrientes Argentina hoy')
        assert result.args.pais=='AR' and not result.country_changed


def test_missing_country_does_not_trust_model_guess_and_followup_uses_validated_context():
    assert normalize_geography(proposed(),'Clima en Goya Corrientes hoy').reason=='missing_country'
    result=normalize_geography(proposed(),'¿Y hoy?',{'ciudad':'Goya','region':'Corrientes','pais':'AR'})
    assert result.args.pais=='AR'


def test_multiple_explicit_countries_and_new_hallucinated_city_require_clarification():
    assert normalize_geography(proposed(),'Goya Corrientes Argentina o Australia').args is None
    assert normalize_geography(proposed(),'Clima en Esquina Corrientes Argentina').reason=='ungrounded_city'
    assert explicit_countries('clima en Goya de noche')==set()


@pytest.mark.parametrize('kind',['corrected','correct','cross_country','incompatible','ambiguous'])
def test_geocoding_validates_before_any_forecast(kind):
    async def run():
        question='Clima en Goya Corrientes Argentina hoy'
        proposal=proposed(country='AR' if kind=='correct' else 'AU')
        candidate=normalize_geography(proposal,question)
        forecasts=[];events=[]
        row={'name':'Goya','admin1':'Corrientes','country_code':'AR','latitude':-29.14,'longitude':-59.26}
        def handler(request):
            if request.url.host=='geocoding-api.open-meteo.com':
                assert request.url.params['countryCode']=='AR'
                if kind=='cross_country':rows=[{**row,'country_code':'AU'},row]
                elif kind=='incompatible':rows=[{**row,'admin1':'New South Wales','country_code':'AU'}]
                elif kind=='ambiguous':rows=[row,{**row,'latitude':-28.0}]
                else:rows=[row]
                return httpx.Response(200,json={'results':rows})
            forecasts.append(1)
            return meteo_handler(request)
        service=OpenMeteo(transport=httpx.MockTransport(handler),observe_geography=events.append)
        try:
            result=await service.execute(candidate.args,PackagedSkillLoader().load('weather').instructions)
            if kind in ('ambiguous','incompatible'):
                assert result.status=='ACLARACION' and forecasts==[] and result.tool_context=={}
            else:
                assert result.status=='HERRAMIENTA' and len(forecasts)==1 and result.tool_context['pais']=='AR'
            assert events[0]['match_count']==(2 if kind=='ambiguous' else 0 if kind=='incompatible' else 1)
        finally:await service.close()
    asyncio.run(run())


def test_agent_preserves_model_action_but_validates_normalized_geography():
    from tests.rag.test_agent import fixture
    async def run():
        p,s,agent,catalog,direct,skills,provider,embedding,case=fixture()
        class Planner:
            async def plan(self,payload):
                return validate_proposal(json.dumps({'accion':'consultar_clima','argumentos':{
                    'ciudad':'Goya','provincia':'Corrientes','pais':'AU','fecha':'hoy'}}))
        class Tool:
            async def execute(self,args,instructions):
                from app.application.agent.context import AgentResult
                assert args.pais=='AR'
                return AgentResult(strategy='TOOL',status='HERRAMIENTA',tool='consultar_clima',answer='Dato sintético')
        agent.planner=Planner();agent.weather=Tool()
        result=await agent.execute(p,'¿Cuál es el clima en Goya Corrientes Argentina hoy?')
        assert result.tool=='consultar_clima' and direct.calls==[] and embedding.calls==0
    asyncio.run(run())
