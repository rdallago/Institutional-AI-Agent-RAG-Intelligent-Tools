"""Integracion real del repositorio en usuarios_dev con fixtures y ROLLBACK.

Nunca usuarios_test ni datos del PDF. No ejecuta modelos. Invocacion explicita.
"""
import asyncio
from contextlib import contextmanager
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import text

from app.application.auth.service import Principal
from app.application.auth.exceptions import PermisoDenegado
from app.application.rag.dto import Page
from app.infrastructure.configuration.database import load_database_config
from app.infrastructure.persistence.database import build_engine
from app.infrastructure.rag.postgres import PostgresRAG


async def verify():
    c=load_database_config()
    assert (c.host,c.port,c.database)==('127.0.0.1',5434,'usuarios_dev')
    engine=build_engine(c)
    try:
        with engine.connect() as conn:
            transaction=conn.begin()
            try:
                assert conn.execute(text('SELECT current_database()')).scalar_one()=='usuarios_dev'
                assert conn.execute(text('SELECT version_num FROM public.alembic_version')).scalar_one()=='0004_rag'
                before=conn.execute(text('SELECT count(*) FROM public.rag_documentos')).scalar_one()
                class TransactionEngine:
                    # Las operaciones del repositorio usan transacciones reales anidadas
                    # sobre la fixture aislada; outer ROLLBACK elimina todos los cambios.
                    @contextmanager
                    def connect(self):yield conn
                    @contextmanager
                    def begin(self):
                        with conn.begin_nested():yield conn
                store=PostgresRAG(TransactionEngine())
                # Evitar compartir una conexion entre hilos: en este ensayo read es
                # ejecutado por to_thread sin operaciones simultaneas del hilo principal.
                owner,other=uuid4(),uuid4()
                for uid,role in [(owner,'ADMIN'),(other,'USUARIO')]:
                    conn.execute(text("""INSERT INTO public.usuarios(id,nombre,apellido,email,activo,rol,fecha_creacion)
                     VALUES (:id,'Fixture','RAG',:email,true,:role,:created)"""),
                     {'id':uid,'email':str(uid)+'@fixture.invalid','role':role,'created':datetime.now(timezone.utc)})
                page=Page(number=1,text='Regla academica sintetica.')
                scope,chunks=store.stage(owner,(page,),'a'*64,100)
                again,repeated=store.stage(owner,(page,),'a'*64,100)
                assert again==scope and repeated==chunks
                assert len(store.missing(scope))==len(chunks)
                for chunk in store.missing(scope):store.checkpoint(scope,chunk['id'],(1.,)+(0.,)*767)
                assert store.missing(scope)==[]
                store.publish(scope,len(chunks))
                principal=Principal(usuario_id=owner,sesion_id=uuid4())
                assert await store.require_active(principal,scope.document_id)==scope
                result=await store.search(principal,scope,(1.,)+(0.,)*767,limit=3)
                assert result and result[0].chunk.text==page.text and result[0].chunk.page==1
                assert abs(result[0].similarity-1)<1e-6
                outsider=Principal(usuario_id=other,sesion_id=uuid4())
                assert await store.list_documents(outsider)==[]
                assert await store.search(outsider,scope,(1.,)+(0.,)*767,limit=3)==()
                try:await store.require_active(outsider,scope.document_id)
                except PermisoDenegado:pass
                else:raise RuntimeError('ACL no aplicada')
                conn.execute(text('INSERT INTO public.rag_documento_permisos(documento_id,usuario_id,puede_leer) VALUES (:d,:u,true)'),{'d':scope.document_id,'u':other})
                assert await store.require_active(outsider,scope.document_id)==scope
                conn.execute(text('UPDATE public.rag_documento_permisos SET puede_leer=false WHERE documento_id=:d AND usuario_id=:u'),{'d':scope.document_id,'u':other})
                try:await store.require_active(outsider,scope.document_id)
                except PermisoDenegado:pass
                else:raise RuntimeError('Revocacion no aplicada')
            finally:transaction.rollback()
            assert conn.execute(text('SELECT count(*) FROM public.rag_documentos')).scalar_one()==before
            conn.rollback()
        print('POSTGRES_REPOSITORY_OK idempotencia checkpoints coseno ACL concesion revocacion procedencia rollback')
    finally:engine.dispose()


if __name__=='__main__':
    try:asyncio.run(verify())
    except Exception:
        print('POSTGRES_REPOSITORY_FAILED datos_sinteticos_revertidos=true')
        raise SystemExit(1)
