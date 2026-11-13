"""Un input por llamada, sin reintentos, redirecciones, cookies ni proxies."""
import asyncio
import json
import math
import httpx
from app.application.ia.exceptions import IANoDisponible, IATiempoAgotado, IARespuestaInvalida, PromptInvalido
from app.application.agent.conversations import reject_secrets
from app.application.rag.core import validate_vector
from app.infrastructure.llm.ollama import _object, _constant

URL = 'https://api.jina.ai/v1/embeddings'
# Denegación global conservada; la CLI solo puede usar una capacidad acotada explícita.
DOCUMENT_EXPORT_APPROVED = False


class JinaEmbeddings:
    def __init__(self, config, *, transport=None):
        if (config.provider != 'jina' or not config.api_key.strip()
                or (config.testing and not isinstance(transport, httpx.MockTransport))
                or (not config.testing and transport is not None)):
            raise ValueError('Configuración Jina no autorizada.')
        self.config = config
        self.client = httpx.AsyncClient(transport=transport or httpx.AsyncHTTPTransport(retries=0),
            trust_env=False, follow_redirects=False, timeout=httpx.Timeout(config.timeout, connect=3),
            limits=httpx.Limits(max_connections=1))

    async def close(self):
        await self.client.aclose()

    async def embed_query(self, text, *, space):
        return await self._embed(text, 'retrieval.query', space)

    async def embed_document(self, text, *, space, authorization=None, fragment_id=None):
        if authorization is not None:
            from .document_export import DocumentExportPermit
            if type(authorization) is not DocumentExportPermit:
                raise IANoDisponible()
            authorization.consume(self, fragment_id, text, space)
        elif not self.config.testing:
            # La bandera histórica no otorga permisos globales; FastAPI no tiene capacidad CLI.
            raise IANoDisponible()
        return await self._embed(text, 'retrieval.passage', space)

    async def _embed(self, value, task, space):
        if space != self.config.space:
            raise IARespuestaInvalida()
        try:
            if not isinstance(value, str) or not value.strip() or '\x00' in value:
                raise PromptInvalido()
            if len(value.encode('utf-8')) > self.config.max_input_bytes:
                raise PromptInvalido()
        except UnicodeError:
            raise PromptInvalido() from None
        reject_secrets(value)
        if not self.config.testing:
            from .resources import require_memory
            require_memory(.25)
        payload = {'model': self.config.model, 'task': task, 'dimensions': 768,
                   'normalized': True, 'embedding_type': 'float', 'input': [value]}
        try:
            async with asyncio.timeout(self.config.timeout):
                async with self.client.stream('POST', URL, json=payload, headers={
                        'Authorization': 'Bearer ' + self.config.api_key,
                        'Accept': 'application/json', 'Accept-Encoding': 'identity'}) as response:
                    if response.status_code in (408, 504):
                        raise IATiempoAgotado()
                    if response.status_code in (401, 402, 403, 429) or response.status_code >= 500:
                        raise IANoDisponible()
                    if response.status_code != 200 or response.headers.get('content-encoding', 'identity') != 'identity':
                        raise IARespuestaInvalida()
                    raw = bytearray()
                    async for chunk in response.aiter_bytes():
                        if len(raw) + len(chunk) > self.config.max_response_bytes:
                            raise IARespuestaInvalida()
                        raw.extend(chunk)
                    body = json.loads(raw.decode('utf-8'), object_pairs_hook=_object, parse_constant=_constant)
            if (type(body) is not dict or body.get('error') is not None
                    or body.get('model') != self.config.model or type(body.get('data')) is not list
                    or len(body['data']) != 1):
                raise IARespuestaInvalida()
            item = body['data'][0]
            if type(item) is not dict or type(item.get('index')) is not int or item['index'] != 0 or type(item.get('embedding')) is not list:
                raise IARespuestaInvalida()
            vector = tuple(item['embedding'])
            validate_vector(vector)
            if abs(math.hypot(*vector) - 1) > .01:
                raise IARespuestaInvalida()
            return vector
        except (TimeoutError, httpx.TimeoutException):
            raise IATiempoAgotado() from None
        except httpx.RequestError:
            raise IANoDisponible() from None
        except (ValueError, TypeError, KeyError, UnicodeError, RecursionError):
            raise IARespuestaInvalida() from None
        finally:
            self.client.cookies.clear()
