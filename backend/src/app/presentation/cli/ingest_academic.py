"""Ingesta administrativa local explicita, reanudable y sin contenido en stdout."""
import argparse
import asyncio
import hashlib
import logging

from sqlalchemy import text

from app.infrastructure.configuration.database import load_database_config
from app.infrastructure.configuration.llm import LLMConfig, load_memory_guard
from app.infrastructure.persistence.database import build_engine
from app.infrastructure.rag.models import LocalModelGate
from app.infrastructure.rag.ollama import Embeddings, SPACE
from app.infrastructure.rag.postgres import PostgresRAG
from app.infrastructure.rag.resources import available_gib, require_memory
from app.infrastructure.rag.text import extract_reference_pdf
from app.infrastructure.rag.article24_revision import REVISION


async def ingest(args):
    llm=LLMConfig(enabled=True,environment='local-development',
                  enforce_memory_guard=load_memory_guard(environment='local-development'))
    c=load_database_config()
    if (c.host,c.port,c.database)!=('127.0.0.1',5434,'usuarios_dev'):
        raise RuntimeError('Destino no permitido.')
    lease=LocalModelGate().try_acquire()
    engine=build_engine(c)
    embeddings=None
    try:
        with engine.connect() as conn:
            assert conn.execute(text('SELECT current_database()')).scalar_one()=='usuarios_dev'
            assert conn.execute(text('SELECT version_num FROM public.alembic_version')).scalar_one() in ('0004_rag','0005_agent_memory')
            # El operador autorizado elige explicitamente el unico administrador normal.
            owners=conn.execute(text("""SELECT u.id FROM public.usuarios u JOIN public.usuario_credenciales c
             ON c.usuario_id=u.id WHERE u.activo AND u.rol='ADMIN' AND NOT c.debe_cambiar_password""")).scalars().all()
            if len(owners)!=1:raise RuntimeError('Propietario no univoco; no ingerir.')
            owner=owners[0]
        logging.getLogger('pypdf').disabled=True
        path,pages=extract_reference_pdf()
        store=PostgresRAG(engine)
        scope,chunks=await asyncio.to_thread(store.stage,owner,pages,hashlib.sha256(path.read_bytes()).hexdigest(),path.stat().st_size,
                                            extraction_revision=REVISION)
        missing=await asyncio.to_thread(store.missing,scope)
        print(f'PREPARADO paginas={len(pages)} fragmentos={len(chunks)} pendientes={len(missing)}',flush=True)
        generated=0
        for item in missing:
            if generated>=args.max_chunks:break
            if llm.enforce_memory_guard and available_gib()<1.0:
                print('PAUSADO_MEMORIA checkpoints_conservados=true',flush=True)
                return
            if embeddings is None:embeddings=Embeddings(llm)
            if llm.enforce_memory_guard:require_memory(1.0)
            async with asyncio.timeout(60):
                vector=await embeddings.embed_document(item['texto'],space=SPACE)
            await asyncio.to_thread(store.checkpoint,scope,item['id'],vector)
            generated+=1
            print(f'PROGRESO nuevos={generated} pendientes={len(missing)-generated}',flush=True)
        remaining=await asyncio.to_thread(store.missing,scope)
        if not remaining:
            await asyncio.to_thread(store.publish,scope,len(chunks))
            print(f'PUBLICADO paginas={len(pages)} fragmentos={len(chunks)} embeddings={len(chunks)}',flush=True)
        else:print(f'PAUSADO_LOTE pendientes={len(remaining)} checkpoints_conservados=true',flush=True)
    finally:
        if embeddings is not None:await embeddings.close()
        engine.dispose();lease.release()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description='Ingesta local privada del reglamento; solo operador autorizado.')
    parser.add_argument('--confirm-local-administrative-ingest',action='store_true',required=True)
    parser.add_argument('--max-chunks',type=int,default=10)
    args=parser.parse_args()
    if not 1<=args.max_chunks<=10000:parser.error('Lote invalido')
    try:asyncio.run(ingest(args))
    except KeyboardInterrupt:print('INTERRUMPIDO checkpoints_conservados=true')
    except Exception:
        print('INGESTA_DETENIDA error_saneado=true checkpoints_conservados=true')
        raise SystemExit(1)
