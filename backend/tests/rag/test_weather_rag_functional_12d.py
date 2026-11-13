import asyncio
import httpx
import pytest

from app.application.agent.tools import weather_arguments, WeatherArgs
from app.application.ia.exceptions import IANoDisponible
from app.application.rag.diagnostics import generation
from app.application.rag.structured_output import Claim, StructuredGeneration, supported_text
from app.application.rag.relevance import AcademicRelevance
from app.application.ia.dto import GeneracionSalida
from app.infrastructure.rag.weather import OpenMeteo
from tests.rag.test_agent import fixture
from tests.rag.test_tools_memory import meteo_handler
from tests.rag.test_evidence_memory_12d import evidence


@pytest.mark.parametrize('city,region,admin',[
    ('Vera','Santa Fe','Provincia de Santa Fé'),
    ('Rosario','Santa Fe','Santa Fe Province'),
    ('Goya','Corrientes','Provincia de Corrientes'),
    ('Vera','Santa Fé','Santa Fe'),
])
def test_real_queries_select_only_explicit_location(city,region,admin):
    async def run():
        p,_,agent,_,direct,_,provider,embedding,_=fixture()
        query=f'¿Cómo está el clima hoy en la ciudad de {city}, {region}, Argentina?'
        args=weather_arguments(query)
        assert args.ciudad==city and args.pais=='AR' and args.region==region
        calls=[]
        def handler(request):
            calls.append(request.url.host)
            if request.url.host=='geocoding-api.open-meteo.com':
                assert request.url.params['name']==city
                assert request.url.params['countryCode']=='AR'
                return httpx.Response(200,json={'results':[
                    {'name':city,'admin1':'Otra provincia','country_code':'AR','latitude':3.,'longitude':4.},
                    {'name':city,'admin1':admin,'country_code':'ES','latitude':5.,'longitude':6.},
                    {'name':city,'admin1':admin,'country_code':'ar','latitude':1.,'longitude':2.}]})
            assert request.url.params['latitude']=='1.0' and request.url.params['longitude']=='2.0'
            return meteo_handler(request)
        agent.weather=OpenMeteo(transport=httpx.MockTransport(handler))
        try:
            result=await agent.execute(p,query)
            assert result.status=='HERRAMIENTA' and city in result.answer and '21.5' in result.answer
            assert len(calls)==2 and not direct.calls and not provider.inputs and not embedding.calls
        finally:await agent.weather.close()
    asyncio.run(run())


@pytest.mark.parametrize('kind',['empty','nonexistent','ambiguous','network'])
def test_geocoder_never_guesses_or_retries(kind):
    async def run():
        calls=[]
        def handler(request):
            calls.append(request.url.host)
            assert request.url.host=='geocoding-api.open-meteo.com'
            if kind=='network':raise httpx.ConnectError('PRIVATE_ERROR')
            row={'name':'Vera','admin1':'Santa Fe','country_code':'AR','latitude':1.,'longitude':2.}
            data={} if kind=='empty' else {'results':[]} if kind=='nonexistent' else {'results':[row,{**row,'latitude':3.}]}
            return httpx.Response(200,json=data)
        tool=OpenMeteo(transport=httpx.MockTransport(handler))
        try:
            if kind=='network':
                with pytest.raises(IANoDisponible):await tool._execute(WeatherArgs(ciudad='Vera',region='Santa Fe',pais='AR'))
            else:
                result=await tool._execute(WeatherArgs(ciudad='Vera',region='Santa Fe',pais='AR'))
                assert result.status=='ACLARACION'
            assert len(calls)==1
        finally:await tool.close()
    asyncio.run(run())


def test_safe_rag_diagnostics_default_off_then_only_counts(monkeypatch,caplog):
    claim='El artículo 24 establece que el Rector entrega PRIVATE_BECAS.'
    e=evidence();policy=AcademicRelevance();output=StructuredGeneration((Claim(claim,('F1',)),))
    monkeypatch.delenv('AGENT_RAG_SAFE_DIAGNOSTICS',raising=False)
    supported_text(output,'Articulo 24',e,policy)
    assert 'rag_safe_diagnostic' not in caplog.text
    caplog.clear();monkeypatch.setenv('AGENT_RAG_SAFE_DIAGNOSTICS','true')
    result,_=supported_text(output,'Articulo 24',e,policy)
    assert result.respuesta=='SIN_EVIDENCIA'
    assert 'lexical_gap' in caplog.text and 'missing_count' in caplog.text
    assert 'PRIVATE_BECAS' not in caplog.text and claim not in caplog.text
    assert 'asistencia' not in caplog.text


def test_polarity_and_parser_diagnostic_do_not_capture_body(monkeypatch,caplog):
    monkeypatch.setenv('AGENT_RAG_SAFE_DIAGNOSTICS','true')
    e=evidence()
    supported_text(StructuredGeneration((Claim('La asistencia no es obligatoria.',('F1',)),)),
                   'Articulo 24',e,AcademicRelevance())
    assert 'polarity_mismatch' in caplog.text and 'polarity_matches' in caplog.text
    generation(GeneracionSalida(respuesta='PRIVATE_BODY',finalizacion='completa'),e,False)
    assert 'structured_contract_rejected' in caplog.text and 'PRIVATE_BODY' not in caplog.text
