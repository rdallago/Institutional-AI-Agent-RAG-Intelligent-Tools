import asyncio
import json
import traceback
from uuid import uuid4

import httpx
import pytest

from ia_support import FakeAuthorizer, SENSITIVE
from app.application.auth.service import Principal
from app.application.ia.dto import GeneracionEntrada, ConsultaDatos
from app.application.ia.exceptions import IANoDisponible, IATiempoAgotado, IARespuestaInvalida, IAOcupada
from app.application.ia.use_cases.generar_respuesta import GenerarRespuesta
from app.infrastructure.configuration.llm import LLMConfig
from app.infrastructure.llm.ollama import ollama_runtime, SYSTEM_INSTRUCTION


CONFIG=LLMConfig(enabled=True,testing=True,environment='test')


def valid(**changes):
    return {'model':'qwen3:1.7b','done':True,'response':'Respuesta ficticia.','done_reason':'stop',**changes}


class Stream(httpx.AsyncByteStream):
    def __init__(self,chunks,*,blocked=False,close_error=False):
        self.chunks=chunks
        self.closed=False
        self.read_count=0
        self.blocked=blocked
        self.started=asyncio.Event()
        self.resume=asyncio.Event()
        self.close_error=close_error
    async def __aiter__(self):
        self.started.set()
        if self.blocked: await self.resume.wait()
        for chunk in self.chunks:
            self.read_count+=1
            yield chunk
    async def aclose(self):
        self.closed=True
        if self.close_error: raise RuntimeError(SENSITIVE)


class Transport(httpx.MockTransport):
    def __init__(self,handler):
        super().__init__(handler)
        self.closed=False
    async def aclose(self): self.closed=True


def test_payload_fixed_target_no_identity_and_shared_client(monkeypatch):
    monkeypatch.setenv('HTTP_PROXY','http://secret@external.invalid')
    monkeypatch.setenv('OLLAMA_HOST','http://external.invalid')
    seen=[]
    def handle(request):
        seen.append(request)
        assert str(request.url)=='http://127.0.0.1:11434/api/generate' and request.method=='POST'
        assert 'authorization' not in request.headers and 'cookie' not in request.headers
        assert request.headers['accept-encoding']=='identity'
        assert json.loads(request.content)=={'model':'qwen3:1.7b','prompt':SENSITIVE,'stream':False,'think':False,
            'system':SYSTEM_INSTRUCTION,'options':{'num_predict':256,'num_ctx':4096},'keep_alive':0}
        assert request.extensions['timeout']=={'connect':2,'read':55,'write':5,'pool':1}
        return httpx.Response(200,json=valid(),headers={'Set-Cookie':'secret=not-forwarded'})
    transport=Transport(handle)
    async def scenario():
        async with ollama_runtime(CONFIG,transport=transport) as runtime:
            provider=runtime.provider
            client=provider._client
            assert not client.trust_env and not client.follow_redirects and client.auth is None
            for _ in range(2): assert (await provider.generate(GeneracionEntrada(prompt=SENSITIVE))).finalizacion=='completa'
            assert runtime.provider is provider and not client.is_closed
        assert client.is_closed and transport.closed
        with pytest.raises(IANoDisponible): await provider.generate(GeneracionEntrada(prompt='valid'))
    asyncio.run(scenario())
    assert len(seen)==2


@pytest.mark.parametrize('reason,finish',[('stop','completa'),('length','limite')])
def test_success_and_limit(reason,finish):
    async def scenario():
        async with ollama_runtime(CONFIG,transport=Transport(lambda r:httpx.Response(200,json=valid(done_reason=reason)))) as runtime:
            output=await runtime.provider.generate(GeneracionEntrada(prompt='valid'))
            assert output.finalizacion==finish and output.respuesta=='Respuesta ficticia.'
    asyncio.run(scenario())


@pytest.mark.parametrize('text', ['', 'Respuesta ficticia.'])
def test_thinking_is_never_used_as_answer_or_returned(text):
    async def scenario():
        data = valid(response=text, thinking=SENSITIVE)
        async with ollama_runtime(CONFIG,transport=Transport(lambda r:httpx.Response(200,json=data))) as runtime:
            if not text:
                with pytest.raises(IARespuestaInvalida):
                    await runtime.provider.generate(GeneracionEntrada(prompt='valid'))
            else:
                result = await runtime.provider.generate(GeneracionEntrada(prompt='valid'))
                assert result.respuesta == text and SENSITIVE not in repr(result)
                assert not hasattr(result, 'thinking')
    asyncio.run(scenario())


def test_previously_allowed_model_is_rejected_in_provider_response():
    async def scenario():
        async with ollama_runtime(CONFIG,transport=Transport(lambda r:httpx.Response(200,json=valid(model='qwen2.5:1.5b')))) as runtime:
            with pytest.raises(IARespuestaInvalida):
                await runtime.provider.generate(GeneracionEntrada(prompt='valid'))
    asyncio.run(scenario())


@pytest.mark.parametrize('reason',[None,'','load','unload',[],42])
def test_missing_or_unrecognized_reason_does_not_invent_normal_completion(reason):
    data=valid()
    if reason is None:
        data.pop('done_reason')
    else:
        data['done_reason']=reason
    async def scenario():
        async with ollama_runtime(CONFIG,transport=Transport(lambda r:httpx.Response(200,json=data))) as runtime:
            with pytest.raises(IARespuestaInvalida):
                await runtime.provider.generate(GeneracionEntrada(prompt='valid'))
    asyncio.run(scenario())


@pytest.mark.parametrize('data',[valid(model='other'),valid(done=False),valid(done=1),valid(response=''),
    valid(response=' \n'),valid(response=None),valid(response=42),valid(response='a'*4097),
    valid(response='nul\x00'),valid(response='\ud800'),valid(done_reason='unknown'),
    {'model':'qwen3:1.7b','done':True,'response':'text'},[],None,42])
def test_invalid_protocol(data):
    async def scenario():
        async with ollama_runtime(CONFIG,transport=Transport(lambda r:httpx.Response(200,json=data))) as runtime:
            with pytest.raises(IARespuestaInvalida): await runtime.provider.generate(GeneracionEntrada(prompt='valid'))
    asyncio.run(scenario())


@pytest.mark.parametrize('body',[b'not json',b'{} trailing',b'\xff',b'{"model":NaN}',
    b'{"model":"qwen3:1.7b","model":"qwen3:1.7b"}'])
def test_invalid_json_and_duplicate_fields(body):
    async def scenario():
        async with ollama_runtime(CONFIG,transport=Transport(lambda r:httpx.Response(200,content=body))) as runtime:
            with pytest.raises(IARespuestaInvalida): await runtime.provider.generate(GeneracionEntrada(prompt='valid'))
    asyncio.run(scenario())


@pytest.mark.parametrize('status,error',[(301,IARespuestaInvalida),(307,IARespuestaInvalida),
    (201,IARespuestaInvalida),(401,IARespuestaInvalida),(403,IARespuestaInvalida),
    (404,IANoDisponible),(429,IANoDisponible),(500,IANoDisponible),(503,IANoDisponible),
    (408,IATiempoAgotado),(504,IATiempoAgotado)])
def test_status_mapping_without_redirect_or_upstream_auth_leak(status,error):
    calls=[]
    def handle(r):
        calls.append(r)
        return httpx.Response(status,content=SENSITIVE,headers={'Location':'http://external.invalid'})
    async def scenario():
        async with ollama_runtime(CONFIG,transport=Transport(handle)) as runtime:
            with pytest.raises(error) as caught: await runtime.provider.generate(GeneracionEntrada(prompt='valid'))
            assert SENSITIVE not in str(caught.value)
    asyncio.run(scenario())
    assert len(calls)==1


@pytest.mark.parametrize('exception,error',[(httpx.ConnectError,IANoDisponible),(httpx.ReadError,IANoDisponible),
    (httpx.ConnectTimeout,IATiempoAgotado),(httpx.ReadTimeout,IATiempoAgotado),
    (httpx.WriteTimeout,IATiempoAgotado),(httpx.PoolTimeout,IATiempoAgotado),
    (httpx.RemoteProtocolError,IARespuestaInvalida),(RuntimeError,IARespuestaInvalida)])
def test_transport_errors_are_sanitized(exception,error,caplog):
    def handle(r): raise exception(SENSITIVE)
    transport=Transport(handle)
    async def scenario():
        async with ollama_runtime(CONFIG,transport=transport) as runtime:
            with pytest.raises(error) as caught: await runtime.provider.generate(GeneracionEntrada(prompt=SENSITIVE))
            assert SENSITIVE not in str(caught.value)+repr(caught.value)+''.join(traceback.format_exception(caught.value))+caplog.text
        assert transport.closed
    asyncio.run(scenario())


@pytest.mark.parametrize('declared',[None,'1','999999'])
def test_fragmented_size_limit_ignores_content_length_and_stops_early(declared):
    stream=Stream([b'x'*32768,b'x'*32768,b'x',b'never read'])
    headers={} if declared is None else {'Content-Length':declared}
    async def scenario():
        async with ollama_runtime(CONFIG,transport=Transport(lambda r:httpx.Response(200,stream=stream,headers=headers))) as runtime:
            with pytest.raises(IARespuestaInvalida): await runtime.provider.generate(GeneracionEntrada(prompt='valid'))
        assert stream.closed and stream.read_count==3
    asyncio.run(scenario())


def test_exact_64k_body_accepted_and_fragmented_utf8_preserved():
    body=json.dumps(valid(response='Hola \U0001f600'),ensure_ascii=False).encode()
    body+=b' '*(65536-len(body))
    stream=Stream([body[i:i+3] for i in range(0,len(body),3)])
    async def scenario():
        async with ollama_runtime(CONFIG,transport=Transport(lambda r:httpx.Response(200,stream=stream))) as runtime:
            assert (await runtime.provider.generate(GeneracionEntrada(prompt='valid'))).respuesta=='Hola \U0001f600'
        assert stream.closed
    asyncio.run(scenario())


def test_preloaded_oversize_and_compressed_response_rejected():
    async def scenario():
        for response in [httpx.Response(200,content=b'x'*65537),httpx.Response(200,stream=Stream([b'x']),headers={'Content-Encoding':'gzip'})]:
            async with ollama_runtime(CONFIG,transport=Transport(lambda r:response)) as runtime:
                with pytest.raises(IARespuestaInvalida): await runtime.provider.generate(GeneracionEntrada(prompt='valid'))
    asyncio.run(scenario())


@pytest.mark.parametrize('mode',['cancel','deadline'])
def test_cancellation_and_case_deadline_close_resources_and_release_slot(mode):
    async def scenario():
        stream=Stream([],blocked=True)
        transport=Transport(lambda r:httpx.Response(200,stream=stream))
        async def work():
            async with ollama_runtime(CONFIG,transport=transport) as runtime:
                holder.append(runtime)
                case=GenerarRespuesta(runtime.provider,FakeAuthorizer(),runtime.admission,
                    timeout_seconds=0.01 if mode=='deadline' else runtime.timeout_seconds)
                await case.ejecutar(Principal(uuid4(),uuid4()),ConsultaDatos(prompt='valid'))
        holder=[]
        task=asyncio.create_task(work())
        await stream.started.wait()
        if mode=='cancel': task.cancel()
        with pytest.raises(asyncio.CancelledError if mode=='cancel' else IATiempoAgotado): await task
        assert stream.closed and transport.closed and holder[0].provider._client.is_closed
        if mode=='deadline':
            with pytest.raises(IAOcupada): holder[0].admission.try_acquire(Principal(uuid4(),uuid4()))
        else: holder[0].admission.try_acquire(Principal(uuid4(),uuid4())).release()
    asyncio.run(scenario())


def test_close_failure_sanitized_and_client_still_closed():
    async def scenario():
        stream=Stream([json.dumps(valid()).encode()],close_error=True)
        transport=Transport(lambda r:httpx.Response(200,stream=stream))
        async with ollama_runtime(CONFIG,transport=transport) as runtime:
            with pytest.raises(IARespuestaInvalida) as caught: await runtime.provider.generate(GeneracionEntrada(prompt='valid'))
            assert SENSITIVE not in ''.join(traceback.format_exception(caught.value))
        assert stream.closed and transport.closed
    asyncio.run(scenario())


def test_scope_error_closes_client_and_preserves_original_failure():
    async def scenario():
        transport=Transport(lambda r:httpx.Response(200,json=valid()))
        with pytest.raises(ValueError):
            async with ollama_runtime(CONFIG,transport=transport) as runtime:
                raise ValueError('fictitious application setup failure')
        assert transport.closed and runtime.provider._client.is_closed
    asyncio.run(scenario())


def test_case_use_success_and_single_connection_configuration(monkeypatch):
    actual=httpx.AsyncClient
    arguments=[]
    def client(**kwargs):
        arguments.append(kwargs)
        return actual(**kwargs)
    monkeypatch.setattr(httpx,'AsyncClient',client)
    async def scenario():
        async with ollama_runtime(CONFIG,transport=Transport(lambda r:httpx.Response(200,json=valid()))) as runtime:
            auth=FakeAuthorizer()
            case=GenerarRespuesta(runtime.provider,auth,runtime.admission,timeout_seconds=runtime.timeout_seconds)
            result=await case.ejecutar(Principal(uuid4(),uuid4()),ConsultaDatos(prompt='valid'))
            assert result.respuesta=='Respuesta ficticia.' and auth.calls==2
        assert len(arguments)==1
        assert arguments[0]['limits'].max_connections==1
        assert arguments[0]['limits'].max_keepalive_connections==1
        assert arguments[0]['trust_env'] is False and arguments[0]['follow_redirects'] is False
    asyncio.run(scenario())


def test_repeated_cancellation_during_scope_cleanup_still_closes_transport():
    async def scenario():
        closing,resume=asyncio.Event(),asyncio.Event()
        class BlockingCloseTransport(Transport):
            async def aclose(self):
                closing.set()
                await resume.wait()
                self.closed=True
        transport=BlockingCloseTransport(lambda r:httpx.Response(200,json=valid()))
        async def work():
            async with ollama_runtime(CONFIG,transport=transport): pass
        task=asyncio.create_task(work())
        await closing.wait()
        task.cancel()
        # Permitir que el primer cancel llegue al shield antes de repetirlo.
        await asyncio.sleep(0)
        task.cancel()
        resume.set()
        with pytest.raises(asyncio.CancelledError): await task
        assert transport.closed
    asyncio.run(scenario())
