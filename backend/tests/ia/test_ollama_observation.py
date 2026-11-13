import asyncio
from contextlib import asynccontextmanager
import json
from unittest.mock import Mock

import httpx
import pytest
from fastapi.testclient import TestClient

from auth_support import memory_auth, bootstrap_login
from app.bootstrap import create_app
from app.application.ia.dto import GeneracionEntrada
from app.application.ia.exceptions import IARespuestaInvalida, IATiempoAgotado
from app.infrastructure.configuration.llm import LLMConfig, LLMConfigInvalida
from app.infrastructure.llm.ollama import ollama_runtime

CONFIG = LLMConfig(enabled=True, testing=True, environment='test')
SECRET = 'FICTIONAL_SENSITIVE_SENTINEL'
FIELDS = {'http_status','model_matches','done_valid','done_reason','think_requested',
          'thinking_present','duration_seconds','response_bytes'}


def valid(**changes):
    return {'model':'qwen3:1.7b','done':True,'done_reason':'stop','response':SECRET,**changes}


@pytest.mark.parametrize('observe', [False, True])
def test_default_silent_and_explicit_metadata_only(observe, capsys, monkeypatch):
    ticks = iter([10.0, 12.5])
    monkeypatch.setattr('app.infrastructure.llm.ollama.monotonic', lambda: next(ticks))
    body = json.dumps(valid(thinking=SECRET)).encode()
    calls = []
    async def scenario():
        def handler(request):
            calls.append(request)
            assert json.loads(request.content)['think'] is False
            return httpx.Response(200, content=body, headers={'Set-Cookie':SECRET})
        async with ollama_runtime(CONFIG, transport=httpx.MockTransport(handler), observe=observe) as runtime:
            result = await runtime.provider.generate(GeneracionEntrada(prompt=SECRET))
            assert result.respuesta == SECRET and result.finalizacion == 'completa'
            assert not runtime.provider._client.cookies
        assert runtime.provider._client.is_closed
    asyncio.run(scenario())
    assert len(calls) == 1
    output = capsys.readouterr()
    assert not output.err and SECRET not in output.out
    if not observe:
        assert not output.out
    else:
        event = json.loads(output.out)
        assert set(event) == FIELDS
        assert event == dict(http_status=200,model_matches=True,done_valid=True,done_reason='stop',
            think_requested=False,thinking_present=True,duration_seconds=2.5,response_bytes=len(body))


@pytest.mark.parametrize('reason', ['stop','length',None,SECRET,[],42])
@pytest.mark.parametrize('thinking', [None,'',SECRET])
def test_reason_normalized_and_thinking_never_exposed(reason, thinking, capsys):
    data = valid(done_reason=reason)
    if thinking is not None: data['thinking'] = thinking
    if reason is None: data.pop('done_reason')
    async def scenario():
        async with ollama_runtime(CONFIG,transport=httpx.MockTransport(lambda r:httpx.Response(200,json=data)),observe=True) as runtime:
            if reason in ('stop','length'):
                result = await runtime.provider.generate(GeneracionEntrada(prompt=SECRET))
                assert result.finalizacion == ('completa' if reason == 'stop' else 'limite')
            else:
                with pytest.raises(IARespuestaInvalida):
                    await runtime.provider.generate(GeneracionEntrada(prompt=SECRET))
    asyncio.run(scenario())
    output = capsys.readouterr().out
    event = json.loads(output)
    assert SECRET not in output and set(event) == FIELDS
    assert event['done_reason'] == (reason if reason in ('stop','length') else 'invalid')
    assert event['thinking_present'] is bool(thinking)


@pytest.mark.parametrize('data', [valid(model=SECRET,done=1),[],None])
def test_invalid_model_done_and_json_shape_emit_safe_defaults(data, capsys):
    async def scenario():
        async with ollama_runtime(CONFIG,transport=httpx.MockTransport(lambda r:httpx.Response(200,json=data)),observe=True) as runtime:
            with pytest.raises(IARespuestaInvalida):
                await runtime.provider.generate(GeneracionEntrada(prompt=SECRET))
    asyncio.run(scenario())
    event = json.loads(capsys.readouterr().out)
    assert event['model_matches'] is False and event['done_valid'] is False


@pytest.mark.parametrize('mode', ['timeout','cancel'])
def test_timeout_cancel_emit_once_close_and_do_not_expose_exception(mode, capsys):
    async def scenario():
        entered = asyncio.Event()
        class Stream(httpx.AsyncByteStream):
            closed = False
            async def __aiter__(self):
                yield b'partial'
                entered.set()
                if mode == 'timeout': raise httpx.ReadTimeout(SECRET)
                await asyncio.Event().wait()
            async def aclose(self): self.closed = True
        stream = Stream()
        async with ollama_runtime(CONFIG,transport=httpx.MockTransport(lambda r:httpx.Response(200,stream=stream)),observe=True) as runtime:
            task = asyncio.create_task(runtime.provider.generate(GeneracionEntrada(prompt=SECRET)))
            await entered.wait()
            if mode == 'cancel': task.cancel()
            with pytest.raises(IATiempoAgotado if mode == 'timeout' else asyncio.CancelledError): await task
            assert stream.closed
        assert runtime.provider._client.is_closed
    asyncio.run(scenario())
    output = capsys.readouterr().out
    event = json.loads(output)
    assert SECRET not in output
    assert event['http_status'] == 200 and event['response_bytes'] == 7
    assert event['done_reason'] == 'invalid'


def test_connection_timeout_has_no_invented_http_status(capsys):
    def fail(request): raise httpx.ConnectTimeout(SECRET)
    async def scenario():
        async with ollama_runtime(CONFIG,transport=httpx.MockTransport(fail),observe=True) as runtime:
            with pytest.raises(IATiempoAgotado): await runtime.provider.generate(GeneracionEntrada(prompt=SECRET))
    asyncio.run(scenario())
    event = json.loads(capsys.readouterr().out)
    assert event['http_status'] is None and event['response_bytes'] == 0


@pytest.mark.parametrize('status,body', [(401,b'secret-error-body'),(200,b'not-json'),(200,b'x'*65537)],
                         ids=['http-error','invalid-json','oversize'])
def test_error_bodies_not_exposed_and_received_bytes_counted(status, body, capsys):
    async def scenario():
        async with ollama_runtime(CONFIG,transport=httpx.MockTransport(lambda r:httpx.Response(status,content=body)),observe=True) as runtime:
            with pytest.raises(IARespuestaInvalida):
                await runtime.provider.generate(GeneracionEntrada(prompt=SECRET))
    asyncio.run(scenario())
    output = capsys.readouterr().out
    event = json.loads(output)
    assert event['http_status'] == status and event['response_bytes'] == len(body)
    assert event['done_reason'] == 'invalid' and 'secret-error-body' not in output


@pytest.mark.parametrize('observe', ['true',1,True])
def test_disabled_or_invalid_observation_rejected(observe):
    async def scenario():
        with pytest.raises(LLMConfigInvalida):
            async with ollama_runtime(LLMConfig(),observe=observe): pass
    asyncio.run(scenario())


def test_emitter_failure_does_not_change_generation(monkeypatch):
    async def scenario():
        async with ollama_runtime(CONFIG,transport=httpx.MockTransport(lambda r:httpx.Response(200,json=valid())),observe=True) as runtime:
            monkeypatch.setattr('builtins.print', Mock(side_effect=RuntimeError(SECRET)))
            assert (await runtime.provider.generate(GeneracionEntrada(prompt=SECRET))).respuesta == SECRET
    asyncio.run(scenario())


def test_lifespan_routes_same_generation_observer_without_public_contract_change(capsys):
    store, auth, _ = memory_auth()
    _, token = bootstrap_login(auth)
    calls = []
    def handler(request): calls.append(request); return httpx.Response(200,json=valid())
    @asynccontextmanager
    async def factory(config, **kwargs):
        assert kwargs == {'observe': True}
        async with ollama_runtime(config,transport=httpx.MockTransport(handler),**kwargs) as runtime:
            yield runtime
        assert runtime.provider._client.is_closed
    app = create_app(repository=store.users,auth_service=auth,llm_config=CONFIG,llm_runtime_factory=factory,llm_observe=True)
    with TestClient(app) as client:
        response = client.post('/api/v1/ia/consultas',json={'prompt':SECRET},headers={'Authorization':'Bearer '+token})
        assert response.status_code == 200
        assert response.json() == {'respuesta':SECRET,'finalizacion':'completa'}
    output = capsys.readouterr().out
    assert len(calls) == 1 and SECRET not in output and token not in output
    assert set(json.loads(output)) == FIELDS
    assert not hasattr(app.state, 'llm_runtime')


@pytest.mark.parametrize('config', [LLMConfig(), LLMConfig(enabled=True,environment='local-development')])
def test_observer_cannot_bypass_enabled_config_or_real_local_context(config, monkeypatch):
    forbidden = Mock(side_effect=AssertionError('No database'))
    monkeypatch.setattr('app.bootstrap.crear_persistencia_postgresql', forbidden)
    with pytest.raises(LLMConfigInvalida):
        with TestClient(create_app(llm_config=config,llm_observe=True)): pass
    forbidden.assert_not_called()
