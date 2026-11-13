"""Ollama HTTP local. Sin composicion FastAPI ni operaciones de administracion."""
import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass
import json
import logging
from time import monotonic

import httpx

from app.application.ia.dto import ConsultaDatos, GeneracionEntrada, GeneracionSalida, validate_prompt, validate_output
from app.application.ia.exceptions import IANoDisponible, IATiempoAgotado, IARespuestaInvalida, PromptInvalido
from app.application.ia.ports import LLMProvider
from app.infrastructure.configuration.llm import LLMConfig, LLMConfigInvalida
from app.infrastructure.llm.admission import MemoryGenerationAdmission
from app.infrastructure.llm.observation import GenerationMetadata


SYSTEM_INSTRUCTION = ('Responde en espanol con informacion breve y clara. No operas sistemas ni ejecutas acciones. '
                      'Si no sabes la respuesta o faltan datos, reconoce la incertidumbre y pide aclaracion; no inventes.')
MAX_UPSTREAM_BYTES = 65536
_logger = logging.getLogger('app.llm')


async def _close(resource):
    task = asyncio.create_task(resource.aclose())
    cancelled = False
    while not task.done():
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError:
            cancelled = True
        except Exception:
            break
    if cancelled:
        # Recuperar cualquier excepcion del cierre sin filtrar su mensaje.
        if not task.cancelled():
            task.exception()
        raise asyncio.CancelledError()
    try:
        task.result()
    except Exception:
        raise IARespuestaInvalida() from None


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError()
        result[key] = value
    return result


def _constant(_):
    raise ValueError()


class DisabledLLMProvider:
    async def generate(self, input: GeneracionEntrada) -> GeneracionSalida:
        raise IANoDisponible()


class OllamaProvider:
    def __init__(self, config: LLMConfig, *, transport: httpx.MockTransport | None = None, observe: bool = False):
        _validate_transport(config, transport)
        _validate_observation(config, observe)
        if not config.enabled:
            raise LLMConfigInvalida()
        self._config = config
        self._observe = observe
        self._client = httpx.AsyncClient(trust_env=False, follow_redirects=False, auth=None,
            transport=transport, timeout=httpx.Timeout(connect=2, write=5, read=55, pool=1),
            limits=httpx.Limits(max_connections=1, max_keepalive_connections=1),
            headers={'Accept': 'application/json', 'Accept-Encoding': 'identity'})

    async def aclose(self):
        await _close(self._client)

    async def generate(self, input: GeneracionEntrada) -> GeneracionSalida:
        if not self._config.enabled or self._client.is_closed:
            raise IANoDisponible()
        if not isinstance(input, GeneracionEntrada):
            raise PromptInvalido()
        validate_prompt(ConsultaDatos(prompt=input.prompt))
        return await self._generate_validated(input)

    async def _generate_validated(self, input, *, system=SYSTEM_INSTRUCTION, input_budget=None, output_format=None,
                                  temperature=None, timing_observer=None):
        """Transporte/parser comun; solo llamadores internos con validacion propia."""
        response = None
        started = monotonic()
        native = {key: None for key in ('native_load_s','native_prompt_eval_s','native_generation_s','native_total_s')}
        status, received = None, 0
        model_matches, done_valid, thinking_present, reason = False, False, False, 'invalid'
        try:
            request = self._client.build_request('POST', self._config.base_url + '/api/generate', json={
                'model': self._config.model, 'prompt': input.prompt, 'stream': False, 'think': False,
                'options': {'num_predict': input.max_output_tokens, 'num_ctx': input.context_tokens,
                            **({'temperature':temperature} if temperature is not None else {})}, 'keep_alive': 0,
                'system': system,
                **({'format': output_format} if output_format is not None else {}),
            })
            # Un Set-Cookie upstream nunca se convierte en identidad de otra consulta.
            request.headers.pop('cookie', None)
            request.headers.pop('authorization', None)
            response = await self._client.send(request, stream=True, auth=None, follow_redirects=False)
            status = response.status_code
            if response.is_stream_consumed:
                received = len(response.content)
            if response.status_code in (408, 504):
                raise IATiempoAgotado()
            if response.status_code in (404, 429, 500, 502, 503):
                raise IANoDisponible()
            if response.status_code != 200:
                raise IARespuestaInvalida()
            if response.headers.get('content-encoding', 'identity').lower() != 'identity':
                raise IARespuestaInvalida()
            body = bytearray()
            if response.is_stream_consumed:
                # MockTransport puede entregar respuestas precargadas; la red real usa stream=True.
                received = len(response.content)
                if received > MAX_UPSTREAM_BYTES:
                    raise IARespuestaInvalida()
                body.extend(response.content)
            else:
                async for chunk in response.aiter_raw():
                    received += len(chunk)
                    if len(body) + len(chunk) > MAX_UPSTREAM_BYTES:
                        raise IARespuestaInvalida()
                    body.extend(chunk)
            data = json.loads(body.decode('utf-8'), object_pairs_hook=_object, parse_constant=_constant)
            if type(data) is dict:
                for source,target in (('load_duration','native_load_s'),('prompt_eval_duration','native_prompt_eval_s'),
                                      ('eval_duration','native_generation_s'),('total_duration','native_total_s')):
                    value=data.get(source)
                    if type(value) is int and 0<=value<=86_400_000_000_000:
                        native[target]=value/1_000_000_000
                model_matches = data.get('model') == self._config.model
                done_valid = data.get('done') is True
                reason = data.get('done_reason') if data.get('done_reason') in ('stop', 'length') else 'invalid'
                thinking_present = isinstance(data.get('thinking'), str) and len(data['thinking']) > 0
            if (type(data) is not dict or data.get('model') != self._config.model
                    or data.get('done') is not True or data.get('done_reason') not in ('stop', 'length')):
                raise IARespuestaInvalida()
            result = GeneracionSalida(respuesta=data.get('response'),
                finalizacion='completa' if data['done_reason'] == 'stop' else 'limite')
            if input_budget is not None and (type(data.get('prompt_eval_count')) is not int
                    or not 0 <= data['prompt_eval_count'] <= input_budget):
                raise IARespuestaInvalida()
            validate_output(result)
            return result
        except httpx.TimeoutException as error:
            category = next((name for kind, name in (
                (httpx.ConnectTimeout, 'connect'), (httpx.ReadTimeout, 'read'),
                (httpx.WriteTimeout, 'write'), (httpx.PoolTimeout, 'pool'))
                if isinstance(error, kind)), 'other')
            _logger.warning('llm_timeout category=%s stage=transport duration_s=%.6f',
                            category, monotonic() - started)
            raise IATiempoAgotado() from None
        except httpx.NetworkError:
            raise IANoDisponible() from None
        except (IANoDisponible, IATiempoAgotado, IARespuestaInvalida):
            raise
        except Exception:
            raise IARespuestaInvalida() from None
        finally:
            try:
                if response is not None:
                    await _close(response)
            finally:
                self._client.cookies.clear()
                if self._observe:
                    GenerationMetadata(status, model_matches, done_valid, reason, False, thinking_present,
                        max(0.0, monotonic() - started), received).emit()
                if timing_observer is not None:
                    timing_observer({**native,'request_s':max(0.0,monotonic()-started)})


@dataclass(frozen=True, slots=True)
class LLMRuntime:
    provider: LLMProvider
    admission: MemoryGenerationAdmission
    timeout_seconds: float


def _validate_transport(config, transport):
    if not isinstance(config, LLMConfig):
        raise LLMConfigInvalida()
    if config.testing and config.enabled and not isinstance(transport, httpx.MockTransport):
        raise LLMConfigInvalida()
    if transport is not None and (not config.testing or not isinstance(transport, httpx.MockTransport)):
        raise LLMConfigInvalida()


def _validate_observation(config, observe):
    if type(observe) is not bool or (observe and (not config.enabled or
            config.environment != ('test' if config.testing else 'local-development'))):
        raise LLMConfigInvalida()


@asynccontextmanager
async def ollama_runtime(config: LLMConfig, *, transport: httpx.MockTransport | None = None, observe: bool = False):
    """Una instancia compartida por lifespan futuro. No abre red al construir."""
    _validate_transport(config, transport)
    _validate_observation(config, observe)
    admission = MemoryGenerationAdmission()
    if not config.enabled:
        yield LLMRuntime(DisabledLLMProvider(), admission, config.timeout_seconds)
        return
    provider = OllamaProvider(config, transport=transport, observe=observe)
    try:
        yield LLMRuntime(provider, admission, config.timeout_seconds)
    finally:
        await provider.aclose()
