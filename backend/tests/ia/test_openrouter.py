"""Pruebas aisladas; ninguna solicitud real ni uso de créditos."""
import asyncio
from dataclasses import replace
import json

import httpx
import pytest

from app.application.ia.dto import GeneracionEntrada
from app.application.ia.exceptions import IANoDisponible, IATiempoAgotado, IARespuestaInvalida, PromptInvalido
from app.infrastructure.configuration.llm import LLMConfig, LLMConfigInvalida, apply_provider_settings
from app.infrastructure.llm.openrouter import OpenRouterProvider, OpenRouterGroundedProvider, OpenRouterPlanner
from app.infrastructure.llm.work_gate import MemoryModelWorkGate
from app.infrastructure.rag.models import CoordinatedDirectProvider
from app.application.rag.core import build_context, resolve_citations
from app.application.rag.relevance import AcademicRelevance
from app.application.rag.structured_output import supported_text
from app.infrastructure.rag.text import ConservativeCounter
from tests.rag.test_structured_output import evidence, QUESTION

CONFIG = LLMConfig(enabled=True, testing=True, environment='test', provider='openrouter', api_key='private-test-key')


def catalog(model=CONFIG.remote_model):
    return {'data': {'id': model, 'endpoints': [{'pricing': {'prompt':'0','completion':'0'},
        'supported_parameters':['response_format','structured_outputs','reasoning','max_tokens']}]}}


def completion(content, **kwargs):
    return {'model':CONFIG.remote_model.removesuffix(':free'), 'choices':[
        {'finish_reason':'stop','message':{'role':'assistant','content':content}}], **kwargs}


def test_configuration_isolation_and_explicit_switch(tmp_path, monkeypatch):
    env=tmp_path/'config.env'
    env.write_text('AGENT_LLM_PROVIDER=openrouter\nOPENROUTER_MODEL='+CONFIG.remote_model+'\n',encoding='utf-8')
    monkeypatch.setenv('OPENROUTER_API_KEY','private-test-key')
    selected=apply_provider_settings(LLMConfig(enabled=True,environment='local-development'),env_file=env)
    assert selected.provider=='openrouter' and selected.model=='qwen3:1.7b'
    assert 'private-test-key' not in repr(selected)
    monkeypatch.setenv('AGENT_LLM_PROVIDER','ollama')
    assert apply_provider_settings(selected,env_file=env).provider=='ollama'
    assert apply_provider_settings(LLMConfig(testing=True,environment='test'),env_file=env).provider=='ollama'
    monkeypatch.setenv('AGENT_LLM_PROVIDER','openrouter')
    monkeypatch.delenv('OPENROUTER_API_KEY')
    with pytest.raises(LLMConfigInvalida):
        apply_provider_settings(LLMConfig(enabled=True,environment='local-development'),env_file=env)


@pytest.mark.parametrize('changes',[{'provider':'unknown'},{'remote_model':'paid/model'},
    {'api_key':''},{'api_key':'header\r\ninjection'},{'remote_model':'../anything:free'}])
def test_invalid_configuration(changes):
    with pytest.raises(LLMConfigInvalida):replace(CONFIG,**changes)


def test_general_request_free_routing_and_no_secret_logging(caplog):
    calls=[]
    def handler(request):
        assert request.url.host=='openrouter.ai' and request.url.scheme=='https'
        calls.append(request)
        if request.method=='GET':
            assert 'authorization' not in request.headers
            return httpx.Response(200,json=catalog())
        body=json.loads(request.content)
        assert request.headers['authorization']=='Bearer private-test-key'
        assert 'private-test-key' not in request.content.decode()
        assert body['max_tokens']==256 and body['reasoning']=={'enabled':False}
        assert body['provider']['allow_fallbacks'] is False
        assert body['provider']['max_price']=={'prompt':0,'completion':0}
        assert len(body['messages'])==2
        return httpx.Response(200,json=completion('Una API REST permite intercambiar recursos.'))
    async def run():
        p=OpenRouterProvider(CONFIG,transport=httpx.MockTransport(handler))
        try:
            result=await p.generate(GeneracionEntrada(prompt='Qué es una API REST'))
            assert result.finalizacion=='completa'
        finally:await p.aclose()
    asyncio.run(run())
    assert len(calls)==2 and 'private-test-key' not in caplog.text
    assert 'intercambiar recursos' not in caplog.text


@pytest.mark.parametrize('status,error',[(401,IANoDisponible),(402,IANoDisponible),
    (429,IANoDisponible),(500,IANoDisponible),(503,IANoDisponible),(504,IATiempoAgotado),(400,IARespuestaInvalida)])
def test_http_errors_no_retry_or_fallback(status,error,caplog):
    calls=[]
    def handler(request):
        calls.append(str(request.url))
        return httpx.Response(200,json=catalog()) if request.method=='GET' else httpx.Response(status,text='private-test-key')
    async def run():
        p=OpenRouterProvider(CONFIG,transport=httpx.MockTransport(handler))
        try:
            with pytest.raises(error):await p.generate(GeneracionEntrada(prompt='Una pregunta'))
        finally:await p.aclose()
    asyncio.run(run())
    assert len(calls)==2 and all('127.0.0.1' not in url for url in calls)
    assert 'private-test-key' not in caplog.text


@pytest.mark.parametrize('failure,expected',[(httpx.ReadTimeout,IATiempoAgotado),(httpx.ConnectError,IANoDisponible)])
def test_network_and_timeout(failure,expected):
    def handler(request):raise failure('private-test-key',request=request)
    async def run():
        p=OpenRouterProvider(CONFIG,transport=httpx.MockTransport(handler))
        try:
            with pytest.raises(expected):await p.generate(GeneracionEntrada(prompt='Una pregunta'))
        finally:await p.aclose()
    asyncio.run(run())


@pytest.mark.parametrize('body',['{','{"model":"x","model":"y"}',json.dumps(completion('ok',model='different/model'))])
def test_invalid_envelope(body):
    def handler(request):
        return httpx.Response(200,json=catalog()) if request.method=='GET' else httpx.Response(200,text=body)
    async def run():
        p=OpenRouterProvider(CONFIG,transport=httpx.MockTransport(handler))
        try:
            with pytest.raises(IARespuestaInvalida):await p.generate(GeneracionEntrada(prompt='Una pregunta'))
        finally:await p.aclose()
    asyncio.run(run())


@pytest.mark.parametrize('literal,valid',[('{"claims":[]}',True),('{"claims":[],"claims":[]}',False),
    ('{"claims":[{"text":"Inventado","source_ids":["F99"]}]}',False),('{"claims":[',False)])
def test_grounded_json_strict(literal,valid):
    def handler(request):
        if request.method=='GET':return httpx.Response(200,json=catalog())
        body=json.loads(request.content)
        assert body['response_format']['json_schema']['strict'] is True
        assert body['response_format']['json_schema']['schema']['properties']['claims']['items']['properties']['source_ids']['items']['enum']==['F1']
        return httpx.Response(200,json=completion(literal))
    async def run():
        p=OpenRouterGroundedProvider(CONFIG,transport=httpx.MockTransport(handler))
        context=build_context(QUESTION,(evidence()[0].chunk,),ConservativeCounter())
        try:
            if valid:assert not (await p.generate_grounded(context)).claims
            else:
                with pytest.raises(IARespuestaInvalida):await p.generate_grounded(context)
        finally:await p.aclose()
    asyncio.run(run())


def test_grounded_support_and_citations_unchanged():
    claims={'claims':[{'text':'El Rectorado es la unidad de gestion institucional.','source_ids':['F1']},
                      {'text':'El Rectorado concede becas.','source_ids':['F1']}]}
    def handler(request):
        return httpx.Response(200,json=catalog()) if request.method=='GET' else httpx.Response(200,json=completion(json.dumps(claims)))
    async def run():
        p=OpenRouterGroundedProvider(CONFIG,transport=httpx.MockTransport(handler))
        context=build_context(QUESTION,(evidence()[0].chunk,),ConservativeCounter())
        try:
            result=await p.generate_grounded(context)
            text,partial=supported_text(result,QUESTION,context.evidence,AcademicRelevance())
            assert partial and 'becas' not in text.respuesta
            assert resolve_citations(text.respuesta,context.evidence)[0].citation=='F1'
        finally:await p.aclose()
    asyncio.run(run())


def test_planner_uses_existing_registry_and_remote_transport():
    proposal={'accion':'responder_llm_directo','argumentos':{}}
    def handler(request):
        return httpx.Response(200,json=catalog()) if request.method=='GET' else httpx.Response(200,json=completion(json.dumps(proposal)))
    async def idle():pass
    async def run():
        p=OpenRouterPlanner(CONFIG,MemoryModelWorkGate(),idle,transport=httpx.MockTransport(handler))
        try:assert (await p.plan('pregunta')).accion=='responder_llm_directo'
        finally:await p.aclose()
    asyncio.run(run())


def test_remote_not_subject_to_local_model_guard(monkeypatch):
    from app.infrastructure.rag import resources
    checked=[]
    monkeypatch.setattr(resources,'require_memory',lambda value:checked.append(value))
    def handler(request):
        return httpx.Response(200,json=catalog()) if request.method=='GET' else httpx.Response(200,json=completion('Respuesta'))
    async def run():
        p=OpenRouterProvider(CONFIG,transport=httpx.MockTransport(handler))
        # Cliente aislado ya construido con MockTransport; activar guardas operativas para comprobarlas.
        p._config=replace(CONFIG,testing=False,environment='local-development')
        direct=CoordinatedDirectProvider(p,MemoryModelWorkGate())
        try:await direct.generate(GeneracionEntrada(prompt='pregunta'))
        finally:await p.aclose()
    asyncio.run(run())
    assert checked==[.25]


def test_paid_catalog_never_receives_prompt():
    calls=[]
    def handler(request):
        calls.append(request.method)
        data=catalog();data['data']['endpoints'][0]['pricing']['prompt']='0.1'
        return httpx.Response(200,json=data)
    async def run():
        p=OpenRouterProvider(CONFIG,transport=httpx.MockTransport(handler))
        try:
            with pytest.raises(IARespuestaInvalida):await p.generate(GeneracionEntrada(prompt='pregunta'))
        finally:await p.aclose()
    asyncio.run(run())
    assert calls==['GET']


def test_sensitive_input_rejected_before_network():
    async def run():
        p=OpenRouterProvider(CONFIG,transport=httpx.MockTransport(lambda _:pytest.fail('No enviar secretos')))
        try:
            with pytest.raises(PromptInvalido):await p.generate(GeneracionEntrada(prompt='password=privado'))
        finally:await p.aclose()
    asyncio.run(run())


def test_embeddings_remain_local_and_keep_guard(monkeypatch):
    from app.infrastructure.rag.ollama import Embeddings
    from app.infrastructure.rag import resources
    checked=[]
    def low(value):checked.append(value);raise IANoDisponible()
    monkeypatch.setattr(resources,'require_memory',low)
    config=replace(CONFIG,testing=False,environment='local-development')
    async def run():
        p=Embeddings(config)
        try:
            assert str(p.client.base_url)=='http://127.0.0.1:11434'
            assert 'authorization' not in p.client.headers
            with pytest.raises(IANoDisponible):await p.embed_query('Prueba',space='invalid')
        finally:await p.close()
    asyncio.run(run())
    assert checked==[1.0]
