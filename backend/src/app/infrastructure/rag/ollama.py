import asyncio
import hashlib
import json
import math

import httpx

from app.application.ia.dto import ConsultaDatos, GeneracionEntrada, validate_prompt
from app.application.ia.exceptions import IANoDisponible, IARespuestaInvalida, IATiempoAgotado
from app.application.rag.core import render, SYSTEM, validate_vector
from app.infrastructure.llm.ollama import OllamaProvider, _object, _constant, _close, _validate_transport
from app.infrastructure.rag.text import ConservativeCounter


MODEL='nomic-embed-text'
DIGEST='0a109f422b47e3a30ba2b10eca18548e944e8a23073ee3f3e947efcf3c45e59f'
SPACE=hashlib.sha256((MODEL+DIGEST+'768:coseno:search_document: :search_query: :utf8-upper-bound-v1').encode()).hexdigest()


class Embeddings:
    def __init__(self,config,*,transport=None):
        _validate_transport(config,transport)
        if not config.enabled:raise IANoDisponible()
        self.testing=config.testing
        self.enforce_memory_guard=config.enforce_memory_guard
        self.client=httpx.AsyncClient(base_url=config.base_url,trust_env=False,follow_redirects=False,
            transport=transport,timeout=httpx.Timeout(55,connect=2),headers={'Accept-Encoding':'identity'},
            limits=httpx.Limits(max_connections=1))
        self.verified=False

    async def close(self):await _close(self.client)

    async def request(self,method,path,**kwargs):
        response=None
        try:
            request=self.client.build_request(method,path,**kwargs)
            request.headers.pop('cookie',None);request.headers.pop('authorization',None)
            response=await self.client.send(request,stream=True,follow_redirects=False)
            if response.status_code in (408,504):raise IATiempoAgotado()
            if response.status_code in (404,429,500,502,503):raise IANoDisponible()
            if response.status_code!=200 or response.headers.get('content-encoding','identity')!='identity':raise IARespuestaInvalida()
            body=bytearray()
            async for chunk in response.aiter_bytes():
                if len(body)+len(chunk)>65536:raise IARespuestaInvalida()
                body.extend(chunk)
            return json.loads(body.decode('utf-8'),object_pairs_hook=_object,parse_constant=_constant)
        except httpx.TimeoutException:raise IATiempoAgotado() from None
        except httpx.NetworkError:raise IANoDisponible() from None
        except (IANoDisponible,IATiempoAgotado,IARespuestaInvalida):raise
        except Exception:raise IARespuestaInvalida() from None
        finally:
            if response is not None:await _close(response)
            self.client.cookies.clear()

    async def idle(self):
        # No admite solapar modelos, incluso si un keep_alive=0 aun esta descargando.
        for _ in range(6):
            data=await self.request('GET','/api/ps')
            if type(data) is not dict or type(data.get('models')) is not list:raise IARespuestaInvalida()
            if not data['models']:return
            await asyncio.sleep(.2)
        raise IANoDisponible()

    async def embed(self,text,prefix,space):
        if not self.testing and self.enforce_memory_guard:
            from app.infrastructure.rag.resources import require_memory
            require_memory(1.0)
        if space!=SPACE:raise IARespuestaInvalida()
        if not self.verified:
            tags=await self.request('GET','/api/tags')
            if not any(x.get('name')==MODEL+':latest' and x.get('digest')==DIGEST for x in tags.get('models',[])):
                raise IANoDisponible()
            self.verified=True
        content=prefix+text
        budget=len(content.encode('utf-8'))+16
        if budget>2048:raise IARespuestaInvalida()
        await self.idle()
        data=await self.request('POST','/api/embed',json={'model':MODEL,'input':content,'truncate':False,
            'keep_alive':0,'options':{'num_ctx':2048}})
        if (data.get('model') not in (MODEL,MODEL+':latest') or type(data.get('embeddings')) is not list
                or len(data['embeddings'])!=1 or type(data.get('prompt_eval_count')) is not int
                or not 0<=data['prompt_eval_count']<=budget):raise IARespuestaInvalida()
        vector=tuple(data['embeddings'][0]);validate_vector(vector)
        if abs(math.hypot(*vector)-1)>0.01:raise IARespuestaInvalida()
        await self.idle()
        return vector

    async def embed_query(self,text,*,space):return await self.embed(text,'search_query: ',space)
    async def embed_document(self,text,*,space):return await self.embed(text,'search_document: ',space)


class GroundedProvider(OllamaProvider):
    async def generate_grounded(self,input):
        if self._config.provider == 'ollama' and not self._config.testing and self._config.enforce_memory_guard:
            from app.infrastructure.rag.resources import require_memory
            require_memory(1.5)
        validate_prompt(ConsultaDatos(prompt=input.question))
        if (not input.evidence or len(input.evidence)>3 or input.rendered!=render(input.question,input.evidence,input.instructions)
                or ConservativeCounter().count(input.rendered)+256+512>4096):raise IARespuestaInvalida()
        structured=(self._config.provider == 'openrouter' or (self._config.environment=='local-development' and not self._config.testing
                    and self._config.model=='qwen2.5:1.5b'))
        from app.application.rag.structured_output import schema, parse
        result=await self._generate_validated(GeneracionEntrada(prompt=input.rendered),system=SYSTEM,
            input_budget=min(3840,ConservativeCounter().count(input.rendered)+512),
            output_format=schema(input.evidence) if structured else None)
        if structured:
            from app.application.rag.diagnostics import generation
            try:
                parsed = parse(result,input.evidence)
            except IARespuestaInvalida:
                generation(result, input.evidence, False)
                raise
            generation(result, input.evidence, True, len(parsed.claims))
            return parsed
        return result
