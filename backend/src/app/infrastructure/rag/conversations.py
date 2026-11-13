"""Memoria definitiva en PostgreSQL, ACL en cada operacion, transacciones cortas."""
import asyncio
import json
import logging
from uuid import uuid4

from sqlalchemy import text

from app.application.auth.exceptions import PermisoDenegado
from app.application.ia.exceptions import IAOcupada, PromptInvalido, IARespuestaInvalida


EXTENDED_RECORD = 'Respuesta documental extensa: contenido íntegro conservado en el resultado de este turno.'


def message_record(result, payload):
    """Keep the existing message CHECK; full literal text lives in the atomic result."""
    answer = result.answer
    if len(answer) <= 4096 and len(answer.encode()) <= 16384:
        return answer
    if (result.strategy != 'RAG' or result.status != 'FUNDAMENTADA' or result.finalization != 'completa'
            or not result.citations or len(answer)>8192 or len(answer.encode())>32768
            or payload.get('resultado',{}).get('respuesta') != answer):
        raise IARespuestaInvalida()
    return EXTENDED_RECORD


def restore_record(row):
    row = dict(row)
    payload = row.pop('turn_result', None)
    if row['role']=='assistant' and row['content']==EXTENDED_RECORD:
        public = payload.get('resultado',{}) if isinstance(payload,dict) else {}
        answer = public.get('respuesta')
        if (row['strategy']!='RAG' or row['status']!='FUNDAMENTADA'
                or public.get('estrategia')!='RAG' or public.get('estado')!='FUNDAMENTADA'
                or public.get('finalizacion')!='completa' or not row['references']
                or not isinstance(answer,str) or not 4096<len(answer)<=8192
                or len(answer.encode())>32768 or '\x00' in answer):
            raise IARespuestaInvalida()
        row['content']=answer
    return row


class PostgresConversations:
    def __init__(self, engine): self.engine = engine

    def owned(self, conn, principal, conversation, *, lock=False):
        row = conn.execute(text('''SELECT c.id FROM public.agent_conversaciones c
          JOIN public.usuarios u ON u.id=c.propietario_id WHERE c.id=:c AND c.propietario_id=:u AND u.activo'''
          + (' FOR UPDATE OF c' if lock else '')), {'c':conversation,'u':principal.usuario_id}).first()
        if row is None: raise PermisoDenegado()

    async def create(self, principal, conversation=None): return await asyncio.to_thread(self._create,principal,conversation)
    def _create(self, principal, conversation=None):
        id = conversation or uuid4()
        with self.engine.begin() as c:
            c.execute(text('SELECT pg_advisory_xact_lock(hashtextextended(:owner,0))'),{'owner':str(principal.usuario_id)})
            if c.execute(text('SELECT id FROM public.agent_conversaciones WHERE id=:id'),{'id':id}).first():
                self.owned(c,principal,id)
                return {'id':str(id)}
            if c.execute(text('SELECT count(*) FROM public.agent_conversaciones WHERE propietario_id=:u'),{'u':principal.usuario_id}).scalar_one()>=50:
                raise PromptInvalido()
            c.execute(text('''INSERT INTO public.agent_conversaciones(id,propietario_id)
              SELECT :id,id FROM public.usuarios WHERE id=:u AND activo'''),{'id':id,'u':principal.usuario_id})
            self.owned(c,principal,id)
        return {'id':str(id)}

    async def list(self, principal):
        def read():
            with self.engine.connect() as c:
                return [dict(r) for r in c.execute(text('''SELECT c.id,c.creado_at,c.actualizado_at
                FROM public.agent_conversaciones c JOIN public.usuarios u ON u.id=c.propietario_id
                WHERE c.propietario_id=:u AND u.activo ORDER BY c.actualizado_at DESC LIMIT 50'''),{'u':principal.usuario_id}).mappings()]
        return await asyncio.to_thread(read)

    async def history(self, principal, conversation):
        def read():
            with self.engine.connect() as c:
                self.owned(c,principal,conversation)
                rows = c.execute(text('''SELECT m.id,m.rol AS role,m.contenido AS content,m.estrategia AS strategy,
                  m.estado AS status,m.referencias AS "references",m.herramienta AS tool,m.contexto_tool AS tool_context,m.creado_at,
                  CASE WHEN m.contenido=:extended AND m.rol='assistant' THEN s.resultado ELSE NULL END AS turn_result
                  FROM public.agent_mensajes m JOIN public.agent_solicitudes s
                  ON s.id=m.solicitud_id AND s.conversacion_id=m.conversacion_id
                  WHERE m.conversacion_id=:c ORDER BY m.id DESC LIMIT 100'''),
                  {'c':conversation,'extended':EXTENDED_RECORD}).mappings().all()
                return [restore_record(r) for r in reversed(rows)]
        return await asyncio.to_thread(read)

    async def reserve(self, principal, conversation, key, fingerprint):
        def write():
            with self.engine.begin() as c:
                self.owned(c,principal,conversation,lock=True)
                row = c.execute(text('''SELECT id,fingerprint,estado,resultado FROM public.agent_solicitudes
                WHERE conversacion_id=:c AND clave=:k'''),{'c':conversation,'k':key}).mappings().first()
                if row:
                    if row['fingerprint'] != fingerprint: raise PromptInvalido()
                    if row['estado']!='COMPLETA':
                        logging.getLogger('app.agent').warning('agent_reservation reason=%s',
                            'failed_key' if row['estado']=='FALLIDA' else 'pending_key')
                        raise IAOcupada(retry_after=1)
                    return {'id':row['id'],'replay':row['resultado']}
                # No permitir dos turnos concurrentes sobre una misma conversacion.
                if c.execute(text("SELECT 1 FROM public.agent_solicitudes WHERE conversacion_id=:c AND estado='PENDIENTE'"),{'c':conversation}).first():
                    logging.getLogger('app.agent').warning('agent_reservation reason=pending_turn')
                    raise IAOcupada(retry_after=1)
                if c.execute(text('SELECT count(*) FROM public.agent_mensajes WHERE conversacion_id=:c'),{'c':conversation}).scalar_one()>=100:
                    raise PromptInvalido()
                id = uuid4()
                c.execute(text('''INSERT INTO public.agent_solicitudes(id,conversacion_id,clave,fingerprint,estado)
                VALUES(:id,:c,:k,:f,'PENDIENTE')'''),{'id':id,'c':conversation,'k':key,'f':fingerprint})
                return {'id':id,'replay':None}
        return await asyncio.to_thread(write)

    async def complete(self, principal, conversation, request_id, question, result, refs, payload):
        recorded = message_record(result, payload)
        def write():
            with self.engine.begin() as c:
                self.owned(c,principal,conversation,lock=True)
                changed = c.execute(text('''UPDATE public.agent_solicitudes SET estado='COMPLETA',resultado=CAST(:p AS jsonb)
                  WHERE id=:id AND conversacion_id=:c AND estado='PENDIENTE' '''),{'id':request_id,'c':conversation,'p':json.dumps(payload)}).rowcount
                if changed!=1: raise IAOcupada(retry_after=1)
                for role,content in [('user',question),('assistant',recorded)]:
                    c.execute(text('''INSERT INTO public.agent_mensajes(conversacion_id,solicitud_id,rol,contenido,estrategia,estado,referencias,herramienta,contexto_tool)
                    VALUES(:c,:id,:r,:t,:s,:e,CAST(:refs AS jsonb),:tool,CAST(:ctx AS jsonb))'''),
                    {'c':conversation,'id':request_id,'r':role,'t':content,'s':result.strategy,'e':result.status,
                     'refs':json.dumps(refs) if role=='assistant' else '[]','tool':result.tool,
                     'ctx':json.dumps(result.tool_context) if role=='assistant' else '{}'})
                c.execute(text('UPDATE public.agent_conversaciones SET actualizado_at=CURRENT_TIMESTAMP WHERE id=:c'),{'c':conversation})
        await asyncio.to_thread(write)

    async def fail(self, principal, conversation, request_id):
        def write():
            with self.engine.begin() as c:
                self.owned(c,principal,conversation)
                c.execute(text("UPDATE public.agent_solicitudes SET estado='FALLIDA' WHERE id=:id AND conversacion_id=:c AND estado='PENDIENTE'"),{'id':request_id,'c':conversation})
        await asyncio.to_thread(write)
