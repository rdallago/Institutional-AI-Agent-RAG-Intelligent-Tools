import asyncio
import hashlib
import json
import re
import logging
from time import monotonic
from uuid import UUID, uuid4
from .diagnostics import execution_trace, request_identifier

from app.application.ia.dto import ConsultaDatos, validate_prompt
from app.application.ia.exceptions import PromptInvalido, IARespuestaInvalida
from .context import ConversationContext, conversation_memory_reference


def reject_secrets(text, *, output=False):
    # No se puede reconocer un secreto arbitrario sin contexto. Fallar cerrado
    # ante credenciales etiquetadas, Bearer, JWT y claves con formato conocido.
    if re.search(r'(?i)\b(?:bearer\s+\S+|eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+|'
                 r'(?:password|contrase[nñ]a|clave|api[_ -]?key|secret|token|jwt)\s*[:=]\s*\S+|'
                 r'(?:mi|tu|su|nuestra)\s+(?:password|contrase[nñ]a|clave|token|jwt)(?:\s+(?:nueva|actual))?\s+es\s+\S+|'
                 r'sk-[A-Za-z0-9]{16,})', text):
        raise IARespuestaInvalida() if output else PromptInvalido()


class Conversations:
    def __init__(self, *, authorizer, repository, agent):
        self.authorizer, self.repository, self.agent = authorizer, repository, agent

    async def create(self, principal, conversation=None):
        await self.authorizer.require_normal(principal)
        return await self.repository.create(principal, conversation) if conversation is not None else await self.repository.create(principal)

    async def list(self, principal):
        await self.authorizer.require_normal(principal)
        return await self.repository.list(principal)

    async def history(self, principal, conversation):
        await self.authorizer.require_normal(principal)
        messages = await self.repository.history(principal, conversation)
        # Revalidar cada documento antes de devolver contenido historico RAG.
        for message in messages:
            for ref in message.get('references', []):
                scope = await self.agent.documents.require_active(principal, UUID(ref['document']))
                if str(scope.version_id) != ref['version']:
                    from app.application.auth.exceptions import PermisoDenegado
                    raise PermisoDenegado()
        await self.authorizer.require_normal(principal)
        return messages

    async def turn(self, principal, conversation, key, question, mode, document):
        await self.authorizer.require_normal(principal)
        validate_prompt(ConsultaDatos(prompt=question)); reject_secrets(question)
        fingerprint = hashlib.sha256(json.dumps([question,mode,str(document)],ensure_ascii=True).encode()).hexdigest()
        reservation = await self.repository.reserve(principal, conversation, key, fingerprint)
        if reservation['replay'] is not None:
            # Misma autorizacion que historial; no entregar una respuesta RAG revocada.
            await self.history(principal, conversation)
            return reservation['replay']
        request_id = reservation['id']
        trace_token = execution_trace.set(uuid4().hex)
        request_token = request_identifier.set(str(key))
        started, stage = monotonic(), 'history'
        logger = logging.getLogger('app.agent')
        logger.warning('agent_turn trace=%s stage=start', execution_trace.get())
        try:
            history = await self.history(principal, conversation)
            context = ConversationContext(user_id=principal.usuario_id, conversation_id=conversation,
                question=question, history=tuple(history[-100:] if conversation_memory_reference(question) else history[-8:]))
            async with asyncio.timeout(65):
                stage = 'agent'
                result = await self.agent.execute(principal, context.question, mode=mode,
                    document_id=document, history=context.history)
            stage = 'output'
            reject_secrets(result.answer, output=True)
            refs = [{'id':e.citation,'pagina':e.chunk.page,'document':str(e.chunk.scope.document_id),
                     'version':str(e.chunk.scope.version_id)} for e in result.citations]
            public = {'respuesta':result.answer,'estado':result.status,'estrategia':result.strategy,
                'finalizacion':result.finalization,'fuentes':[{'id':r['id'],'pagina':r['pagina']} for r in refs]}
            payload = {'resultado':public,'herramienta':result.tool,'solicitud_id':str(key),'conversacion_id':str(conversation)}
            await self.authorizer.require_normal(principal)
            for ref in refs:
                await self.agent.documents.require_active(principal, UUID(ref['document']))
            stage = 'persist'
            await self.repository.complete(principal, conversation, request_id, question, result, refs, payload)
            logger.warning('agent_turn trace=%s stage=complete strategy=%s status=%s duration_ms=%d',
                execution_trace.get(), result.strategy, result.status, int((monotonic()-started)*1000))
            return payload
        except BaseException:
            logger.warning('agent_turn trace=%s stage=%s status=failed duration_ms=%d',
                execution_trace.get(), stage, int((monotonic()-started)*1000))
            # Sin mensajes parciales, sin almacenar excepciones ni contenido de fallos.
            await asyncio.shield(self.repository.fail(principal, conversation, request_id))
            raise
        finally:
            request_identifier.reset(request_token)
            execution_trace.reset(trace_token)
