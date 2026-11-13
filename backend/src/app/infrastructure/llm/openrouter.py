"""HTTPS acotado, modelo gratuito fijo/configurado, sin reparación ni fallback."""
import asyncio
from contextlib import asynccontextmanager
from decimal import Decimal, InvalidOperation
import json
import logging
from time import monotonic

import httpx

from app.application.ia.dto import GeneracionSalida, validate_output
from app.application.ia.exceptions import IANoDisponible, IATiempoAgotado, IARespuestaInvalida, PromptInvalido
from app.infrastructure.configuration.llm import LLMConfigInvalida
from app.infrastructure.llm.ollama import (OllamaProvider, LLMRuntime, SYSTEM_INSTRUCTION,
    _object, _constant, _close, _validate_transport, _validate_observation)
from app.infrastructure.llm.admission import MemoryGenerationAdmission
from app.infrastructure.rag.ollama import GroundedProvider
from app.infrastructure.rag.planner import JSONPlanner

BASE = 'https://openrouter.ai/api/v1'
DOTS_MODEL = 'dots-studio/dots-3-note-preview:free'
logger = logging.getLogger('app.llm')


class OpenRouterProvider(OllamaProvider):
    def __init__(self, config, *, transport=None, observe=False):
        _validate_transport(config, transport)
        _validate_observation(config, observe)
        if not config.enabled or config.provider != 'openrouter' or not config.api_key:
            raise LLMConfigInvalida()
        self._config, self._observe, self._verified = config, observe, False
        self._client = httpx.AsyncClient(transport=transport, trust_env=False,
            follow_redirects=False, auth=None, timeout=httpx.Timeout(config.timeout_seconds, connect=3),
            limits=httpx.Limits(max_connections=1), headers={'Accept': 'application/json',
                'Accept-Encoding': 'identity'})

    async def _request(self, method, path, *, payload=None):
        response = None
        try:
            headers = {'Authorization': 'Bearer ' + self._config.api_key} if method == 'POST' else {}
            request = self._client.build_request(method, BASE + path, json=payload, headers=headers)
            request.headers.pop('cookie', None)
            response = await self._client.send(request, stream=True, follow_redirects=False)
            status = response.status_code
            if status != 200:
                logger.warning('llm_provider provider=openrouter http_status=%d classification=%s stage=%s', status,
                    'request_rejected' if status==400 else 'upstream_http_error',
                    'chat_completion' if method=='POST' and path=='/chat/completions' else 'metadata')
                if status in (408, 504):
                    raise IATiempoAgotado()
                if status in (401, 402, 403, 404, 429) or status >= 500:
                    raise IANoDisponible()
                raise IARespuestaInvalida()
            if response.headers.get('content-encoding', 'identity').lower() != 'identity':
                raise IARespuestaInvalida()
            body = bytearray()
            async for chunk in response.aiter_bytes():
                if len(body) + len(chunk) > 65536:
                    raise IARespuestaInvalida()
                body.extend(chunk)
            return json.loads(body.decode('utf-8'), object_pairs_hook=_object, parse_constant=_constant)
        except httpx.TimeoutException:
            raise IATiempoAgotado() from None
        except httpx.RequestError:
            raise IANoDisponible() from None
        except (ValueError, UnicodeError, TypeError, RecursionError):
            raise IARespuestaInvalida() from None
        finally:
            if response is not None:
                await _close(response)
            self._client.cookies.clear()

    async def verify_model(self):
        """Antes de enviar contenido: catálogo actual, precio cero y parámetros requeridos."""
        if self._verified:
            return
        data = await self._request('GET', '/models/' + self._config.remote_model + '/endpoints')
        try:
            model = data['data']
            endpoints = model['endpoints']
            def eligible(endpoint):
                price = endpoint['pricing']
                return ((self._config.remote_model != DOTS_MODEL
                         or endpoint.get('tag', '').split('/')[0] == 'atlas-cloud')
                    and Decimal(price['prompt']) == 0 and Decimal(price['completion']) == 0
                    and {'structured_outputs', 'response_format', 'reasoning', 'max_tokens'}
                    <= set(endpoint['supported_parameters']))
            if model['id'] != self._config.remote_model or not any(eligible(e) for e in endpoints):
                raise IARespuestaInvalida()
        except (KeyError, TypeError, InvalidOperation, ValueError):
            raise IARespuestaInvalida() from None
        self._verified = True

    async def _generate_validated(self, input, *, system=SYSTEM_INSTRUCTION, input_budget=None,
                                  output_format=None, temperature=None, timing_observer=None):
        started = monotonic()
        try:
            from app.application.agent.conversations import reject_secrets
            reject_secrets(input.prompt)
            # Un proveedor remoto no carga pesos locales; conserva una reserva para el proceso.
            if not self._config.testing:
                from app.infrastructure.rag.resources import require_memory
                require_memory(.25)
            if len(input.prompt.encode('utf-8')) + 256 > 4096:
                raise PromptInvalido()
            async with asyncio.timeout(self._config.timeout_seconds):
                await self.verify_model()
                payload = {'model': self._config.remote_model, 'stream': False,
                    'messages': [{'role': 'system', 'content': system}, {'role': 'user', 'content': input.prompt}],
                    'max_tokens': input.max_output_tokens, 'reasoning': {'enabled': False},
                    'provider': {'require_parameters': True, 'allow_fallbacks': False,
                                 'max_price': {'prompt': 0, 'completion': 0}, 'data_collection': 'deny'},
                    **({'temperature': temperature} if temperature is not None else {})}
                if self._config.remote_model == DOTS_MODEL:
                    payload['provider']['only'] = ['atlas-cloud']
                if output_format is not None:
                    payload['response_format'] = {'type': 'json_schema', 'json_schema': {
                        'name': 'agent_output', 'strict': True, 'schema': output_format}}
                data = await self._request('POST', '/chat/completions', payload=payload)
            if (not isinstance(data, dict) or data.get('error') is not None
                    or data.get('model') not in (self._config.remote_model, self._config.remote_model.removesuffix(':free'))
                    or type(data.get('choices')) is not list or len(data['choices']) != 1):
                raise IARespuestaInvalida()
            choice = data['choices'][0]
            message = choice.get('message', {})
            if (choice.get('finish_reason') not in ('stop', 'length') or message.get('role') != 'assistant'
                    or message.get('refusal') or message.get('tool_calls')
                    or not isinstance(message.get('content'), str)):
                raise IARespuestaInvalida()
            output = GeneracionSalida(respuesta=message['content'],
                finalizacion='completa' if choice['finish_reason'] == 'stop' else 'limite')
            validate_output(output)
            return output
        except TimeoutError:
            raise IATiempoAgotado() from None
        except (KeyError, TypeError, AttributeError):
            raise IARespuestaInvalida() from None
        finally:
            if timing_observer is not None:
                timing_observer({'request_s': max(0., monotonic() - started)})
            logger.warning('llm_provider provider=openrouter duration_ms=%d', int((monotonic()-started)*1000))


class OpenRouterGroundedProvider(GroundedProvider, OpenRouterProvider):
    """Misma construcción de contexto, parser estructurado y diagnóstico existentes."""


class OpenRouterPlanner(JSONPlanner, OpenRouterProvider):
    """Mismo prompt, registro cerrado y deadline; solo cambia el transporte."""


@asynccontextmanager
async def openrouter_runtime(config, *, transport=None, observe=False):
    provider = OpenRouterProvider(config, transport=transport, observe=observe)
    try:
        yield LLMRuntime(provider, MemoryGenerationAdmission(), config.timeout_seconds)
    finally:
        await provider.aclose()
