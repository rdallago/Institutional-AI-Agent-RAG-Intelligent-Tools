"""Ensayo SQL secuencial de memoria en usuarios_dev; fixtures y DDL con ROLLBACK.

No crea usuarios, sesiones, modelos o vectores. Nunca usuarios_test.
"""
import asyncio
from contextlib import contextmanager
import importlib.util
from pathlib import Path
from uuid import uuid4, UUID

from sqlalchemy import text

from app.application.agent.context import AgentResult
from app.application.auth.service import Principal
from app.application.auth.exceptions import PermisoDenegado
from app.application.ia.exceptions import PromptInvalido
from app.infrastructure.configuration.database import load_database_config
from app.infrastructure.persistence.database import build_engine
from app.infrastructure.rag.conversations import PostgresConversations


async def verify():
    config=load_database_config()
    assert (config.host,config.port,config.database)==('127.0.0.1',5434,'usuarios_dev')
    engine=build_engine(config)
    try:
        with engine.connect() as conn:
            transaction=conn.begin()
            try:
                assert conn.execute(text('SELECT current_database()')).scalar_one()=='usuarios_dev'
                revision=conn.execute(text('SELECT version_num FROM alembic_version')).scalar_one()
                assert revision in ('0004_rag','0005_agent_memory')
                conn.execute(text("SET LOCAL lock_timeout='1s'"))
                conn.execute(text("SET LOCAL statement_timeout='10s'"))
                before=conn.execute(text('SELECT count(*) FROM rag_embeddings')).scalar_one()
                if revision=='0004_rag':
                    assert conn.execute(text("SELECT to_regclass('public.agent_conversaciones')")).scalar_one() is None
                    path=Path(__file__).resolve().parents[2]/'backend/migrations/versions/0005_agent_memory.py'
                    spec=importlib.util.spec_from_file_location('memory_revision',path)
                    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
                    for ddl in module.DDL:conn.execute(text(ddl))
                owner=conn.execute(text('SELECT id FROM usuarios WHERE activo ORDER BY id LIMIT 1')).scalar_one()
                principal=Principal(usuario_id=owner,sesion_id=uuid4())
                outsider=Principal(usuario_id=uuid4(),sesion_id=uuid4())
                class TransactionEngine:
                    @contextmanager
                    def connect(self):yield conn
                    @contextmanager
                    def begin(self):
                        with conn.begin_nested():yield conn
                store=PostgresConversations(TransactionEngine())
                conversation=UUID((await store.create(principal))['id'])
                assert (await store.create(principal,conversation))['id']==str(conversation)
                assert (await store.list(principal)) and await store.history(principal,conversation)==[]
                try:await store.history(outsider,conversation)
                except PermisoDenegado:pass
                else:raise RuntimeError('ACL no aplicada')
                key=uuid4();reservation=await store.reserve(principal,conversation,key,'a'*64)
                result=AgentResult(strategy='LLM_DIRECTO',status='GENERADA',answer='Respuesta sintetica.')
                payload={'sintetico':True}
                await store.complete(principal,conversation,reservation['id'],'Pregunta sintetica.',result,[],payload)
                assert (await store.reserve(principal,conversation,key,'a'*64))['replay']==payload
                assert len(await store.history(principal,conversation))==2
                assert len(await store.history(Principal(usuario_id=owner,sesion_id=uuid4()),conversation))==2
                try:await store.reserve(principal,conversation,key,'b'*64)
                except PromptInvalido:pass
                else:raise RuntimeError('Idempotencia no aplicada')
                assert conn.execute(text('SELECT count(*) FROM rag_embeddings')).scalar_one()==before
                print('MEMORY_SCHEMA_ACL_REPLAY_RELOGIN_OK rollback=true')
            finally:transaction.rollback()
    finally:engine.dispose()


if __name__=='__main__':
    try:asyncio.run(verify())
    except Exception as error:
        print('MEMORY_CHECK_FAILED type='+type(error).__name__)
        raise SystemExit(1)
