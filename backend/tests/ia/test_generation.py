import asyncio
from dataclasses import FrozenInstanceError
import traceback
from uuid import uuid4

import pytest

from ia_support import FakeLLMProvider, FakeAuthorizer, ControlledClock, SENSITIVE
from app.application.auth.exceptions import AutenticacionRequerida, CambioPasswordRequerido
from app.application.auth.service import Principal
from app.application.ia.dto import ConsultaDatos, GeneracionEntrada, GeneracionSalida
from app.application.ia.exceptions import PromptInvalido, IAOcupada, IATiempoAgotado, IANoDisponible, IARespuestaInvalida
from app.application.ia.use_cases.generar_respuesta import GenerarRespuesta
from app.infrastructure.llm.admission import MemoryGenerationAdmission


def principal(): return Principal(uuid4(),uuid4())


def test_success_keeps_exact_prompt_and_internal_limits_hidden():
    async def scenario():
        provider, auth, admission = FakeLLMProvider(), FakeAuthorizer(), MemoryGenerationAdmission()
        case=GenerarRespuesta(provider,auth,admission)
        original='  consulta e\u0301 con espacios \U0001f600  '
        result=await case.ejecutar(principal(),ConsultaDatos(prompt=original))
        assert result.respuesta=='Respuesta ficticia.' and auth.calls==2
        assert provider.inputs[0].prompt==original
        assert provider.inputs[0].max_output_tokens==256 and provider.inputs[0].context_tokens==4096
        admission.try_acquire(principal()).release()
    asyncio.run(scenario())


@pytest.mark.parametrize('prompt', ['', ' \t\r\n', None, 123, 'a'*1001, '\U0001f600'*751,
    '\ud800', '\udfff', 'nul\x00inside'])
def test_invalid_prompt_never_calls_provider_or_consumes_quota(prompt):
    async def scenario():
        provider, admission=FakeLLMProvider(),MemoryGenerationAdmission()
        case=GenerarRespuesta(provider,FakeAuthorizer(),admission)
        actor=principal()
        with pytest.raises(PromptInvalido): await case.ejecutar(actor,ConsultaDatos(prompt=prompt))
        assert not provider.inputs
        for _ in range(5): admission.try_acquire(actor).release()
    asyncio.run(scenario())


@pytest.mark.parametrize('prompt', ['a','a'*1000,'\u20ac'*1000,'\U0001f600'*750,'\U0001f600'*500+'a'*500])
def test_prompt_unicode_and_byte_boundaries(prompt):
    async def scenario():
        provider=FakeLLMProvider()
        await GenerarRespuesta(provider,FakeAuthorizer(),MemoryGenerationAdmission()).ejecutar(principal(),ConsultaDatos(prompt=prompt))
        assert provider.inputs[0].prompt==prompt
    asyncio.run(scenario())


@pytest.mark.parametrize('error', [AutenticacionRequerida,CambioPasswordRequerido])
def test_authorization_failure_never_calls_provider(error):
    async def scenario():
        provider, admission=FakeLLMProvider(),MemoryGenerationAdmission()
        with pytest.raises(error):
            await GenerarRespuesta(provider,FakeAuthorizer(error=error),admission).ejecutar(principal(),ConsultaDatos(prompt='valid'))
        assert not provider.inputs
        admission.try_acquire(principal()).release()
    asyncio.run(scenario())


@pytest.mark.parametrize('output', [object(),None,GeneracionSalida(respuesta='',finalizacion='completa'),
    GeneracionSalida(respuesta=' \n',finalizacion='completa'),GeneracionSalida(respuesta=42,finalizacion='completa'),
    GeneracionSalida(respuesta='a'*4097,finalizacion='completa'),GeneracionSalida(respuesta='\ud800',finalizacion='completa'),
    GeneracionSalida(respuesta='a\x00b',finalizacion='completa'),GeneracionSalida(respuesta='valid',finalizacion=SENSITIVE)])
def test_untrusted_output_rejected_and_slot_released(output):
    async def scenario():
        provider=FakeLLMProvider()
        provider.output=output
        admission=MemoryGenerationAdmission()
        with pytest.raises(IARespuestaInvalida):
            await GenerarRespuesta(provider,FakeAuthorizer(),admission).ejecutar(principal(),ConsultaDatos(prompt='valid'))
        admission.try_acquire(principal()).release()
    asyncio.run(scenario())


@pytest.mark.parametrize('finish',['completa','limite'])
def test_output_limits_and_termination(finish):
    async def scenario():
        output=GeneracionSalida(respuesta='\U0001f600'*4096,finalizacion=finish)
        result=await GenerarRespuesta(FakeLLMProvider(output=output),FakeAuthorizer(),MemoryGenerationAdmission()).ejecutar(principal(),ConsultaDatos(prompt='valid'))
        assert result is output
    asyncio.run(scenario())


@pytest.mark.parametrize('mode,error',[('unavailable',IANoDisponible),('invalid',IARespuestaInvalida),('unexpected',IARespuestaInvalida),('timeout',IATiempoAgotado)])
def test_errors_sanitized_and_resources_released(mode,error,caplog):
    async def scenario():
        clock=ControlledClock()
        admission=MemoryGenerationAdmission(clock=clock)
        with pytest.raises(error) as captured:
            await GenerarRespuesta(FakeLLMProvider(mode=mode),FakeAuthorizer(),admission).ejecutar(principal(),ConsultaDatos(prompt=SENSITIVE))
        assert SENSITIVE not in str(captured.value)+repr(captured.value)+''.join(traceback.format_exception(captured.value))+caplog.text
        if mode=='timeout':
            with pytest.raises(IAOcupada) as busy: admission.try_acquire(principal())
            assert busy.value.retry_after==30
            clock.now=30
        admission.try_acquire(principal()).release()
    asyncio.run(scenario())


def test_concurrent_request_rejected_without_provider_call_then_recovers():
    async def scenario():
        provider=FakeLLMProvider(blocked=True)
        admission=MemoryGenerationAdmission()
        case=GenerarRespuesta(provider,FakeAuthorizer(),admission)
        first=asyncio.create_task(case.ejecutar(principal(),ConsultaDatos(prompt='first')))
        await provider.started.wait()
        with pytest.raises(IAOcupada): await case.ejecutar(principal(),ConsultaDatos(prompt='second'))
        assert len(provider.inputs)==1
        provider.resume.set()
        await first
        await case.ejecutar(principal(),ConsultaDatos(prompt='third'))
        assert len(provider.inputs)==2
    asyncio.run(scenario())


def test_external_cancellation_is_propagated_and_slot_reusable():
    async def scenario():
        provider,admission=FakeLLMProvider(blocked=True),MemoryGenerationAdmission()
        task=asyncio.create_task(GenerarRespuesta(provider,FakeAuthorizer(),admission).ejecutar(principal(),ConsultaDatos(prompt='valid')))
        await provider.started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError): await task
        assert provider.cancelled
        admission.try_acquire(principal()).release()
    asyncio.run(scenario())


def test_real_deadline_cancels_blocked_provider_and_starts_cooldown():
    async def scenario():
        clock=ControlledClock()
        provider,admission=FakeLLMProvider(blocked=True),MemoryGenerationAdmission(clock=clock)
        with pytest.raises(IATiempoAgotado):
            await GenerarRespuesta(provider,FakeAuthorizer(),admission,timeout_seconds=0.01).ejecutar(principal(),ConsultaDatos(prompt='valid'))
        assert provider.cancelled
        with pytest.raises(IAOcupada): admission.try_acquire(principal())
        clock.now=30
        admission.try_acquire(principal()).release()
    asyncio.run(scenario())


def test_provider_cancel_and_post_authorization_cancel_release_slot():
    async def scenario():
        for mode in ['cancel','success']:
            admission,provider=MemoryGenerationAdmission(),FakeLLMProvider(mode=mode)
            class Authorizer(FakeAuthorizer):
                async def require_normal(self,actor):
                    await super().require_normal(actor)
                    if self.calls==2: raise asyncio.CancelledError()
            with pytest.raises(asyncio.CancelledError):
                await GenerarRespuesta(provider,Authorizer(),admission).ejecutar(principal(),ConsultaDatos(prompt='valid'))
            admission.try_acquire(principal()).release()
    asyncio.run(scenario())


def test_sensitive_dto_repr_and_no_user_model_options():
    for dto in [ConsultaDatos(prompt=SENSITIVE),GeneracionEntrada(prompt=SENSITIVE),GeneracionSalida(respuesta=SENSITIVE,finalizacion=SENSITIVE)]:
        assert SENSITIVE not in repr(dto)
        field='respuesta' if isinstance(dto,GeneracionSalida) else 'prompt'
        with pytest.raises(FrozenInstanceError): setattr(dto,field,'value')
    for key in ['model','url','tools','max_output_tokens','context_tokens']:
        with pytest.raises(TypeError): ConsultaDatos(prompt='valid',**{key:'forbidden'})
    with pytest.raises(TypeError): GeneracionEntrada(prompt='valid',max_output_tokens=9999)


@pytest.mark.parametrize('timeout',[0,-1,61,float('inf'),float('nan'),True,'60'])
def test_deadline_config_cannot_disable_or_expand_limit(timeout):
    with pytest.raises(ValueError): GenerarRespuesta(FakeLLMProvider(),FakeAuthorizer(),MemoryGenerationAdmission(),timeout_seconds=timeout)


def test_failed_provider_calls_keep_their_own_consumed_quota():
    async def scenario():
        from app.application.ia.exceptions import IALimiteIntentos
        provider,admission=FakeLLMProvider(mode='unavailable'),MemoryGenerationAdmission(clock=ControlledClock())
        case=GenerarRespuesta(provider,FakeAuthorizer(),admission)
        actor=principal()
        for _ in range(5):
            with pytest.raises(IANoDisponible): await case.ejecutar(actor,ConsultaDatos(prompt='valid'))
        with pytest.raises(IALimiteIntentos): await case.ejecutar(actor,ConsultaDatos(prompt='valid'))
        assert len(provider.inputs)==5
    asyncio.run(scenario())
