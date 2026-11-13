"""Preparado, no autorizado para exportar documentos hasta revisar privacidad."""
import argparse
import asyncio
import hashlib
from uuid import UUID
from sqlalchemy import text
from app.infrastructure.configuration.database import load_database_config
from app.infrastructure.configuration.embeddings import load_embedding_config
from app.infrastructure.persistence.database import build_engine
from app.infrastructure.rag.cloud_postgres import CloudPostgresRAG
from app.infrastructure.rag.jina import JinaEmbeddings, DOCUMENT_EXPORT_APPROVED
from app.infrastructure.rag.models import LocalModelGate
from app.infrastructure.rag.document_export import DOCUMENT, VERSION, OWNER, SPACE, require_cli_entry, issue_permit


async def run(args):
    # La autorización de exportación nunca concede validate/activate.
    if (getattr(args, 'action', None) != 'index' or not getattr(args, 'approve_document_export', False)
            or not getattr(args, 'confirm_free_usage', False)
            or not getattr(args, 'confirm_data_policy', False)):
        raise RuntimeError('Exportación documental bloqueada: privacidad Jina pendiente.')
    require_cli_entry()
    if ((args.owner, args.version) != (OWNER, VERSION)
            or type(args.max_chunks) is not int or not 1 <= args.max_chunks <= 10):
        raise RuntimeError('Alcance de indexación no autorizado.')
    c = load_database_config()
    if (c.host, c.port, c.database) != ('127.0.0.1', 5434, 'usuarios_dev'):
        raise RuntimeError('Destino no autorizado.')
    config = load_embedding_config()
    if config.provider != 'jina' or config.space != SPACE or not config.api_key.strip():
        raise RuntimeError('Proveedor incorrecto.')
    engine = build_engine(c)
    lease = None
    embeddings = None
    permit = None
    try:
        lease = LocalModelGate().try_acquire()  # Exclusión de trabajo; no carga modelos.
        with engine.connect() as conn:
            if conn.execute(text('SELECT version_num FROM alembic_version')).scalar_one() != '0006_cloud_embeddings':
                raise RuntimeError('Migración no aplicada.')
        store = CloudPostgresRAG(engine, config)
        manifest = store.export_manifest(args.owner, args.version, DOCUMENT)
        embeddings = JinaEmbeddings(config)
        permit = issue_permit(adapter=embeddings, owner=args.owner, version=args.version,
                              document=DOCUMENT, space=config.space, manifest=manifest, limit=args.max_chunks)
        store.prepare_existing(args.owner, args.version)
        missing = store.missing_cloud(args.version)
        for item in missing[:args.max_chunks]:
            if (manifest.get(item['id']) != item['hash_texto']
                    or not item['intact'] or hashlib.sha256(item['texto'].encode()).hexdigest() != item['hash_texto']
                    or hashlib.sha256(item['texto_extraido'].encode()).hexdigest() != item['page_hash']):
                raise RuntimeError('Integridad inválida antes de transporte.')
            # Revalidar ACL, versión activa y manifiesto justo antes de cada envío.
            if store.export_manifest(args.owner, args.version, DOCUMENT) != manifest:
                raise RuntimeError('Manifiesto documental modificado.')
            vector = await embeddings.embed_document(item['texto'], space=config.space,
                                                     authorization=permit, fragment_id=item['id'])
            store.checkpoint_cloud(args.owner, args.version, item['id'], vector)
        print('PENDIENTES', len(store.missing_cloud(args.version)), 'publicacion_automatica=false')
    finally:
        if permit is not None:
            permit.close()
        try:
            if embeddings is not None:
                await embeddings.close()
        finally:
            try:
                engine.dispose()
            finally:
                if lease is not None:
                    lease.release()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--action', choices=('index', 'validate', 'activate'), required=True)
    p.add_argument('--owner', type=UUID, required=True)
    p.add_argument('--version', type=UUID, required=True)
    p.add_argument('--max-chunks', type=int, default=10)
    p.add_argument('--approve-document-export', action='store_true', help='Solo tras autorización externa expresa de esta versión.')
    p.add_argument('--confirm-free-usage', action='store_true', help='El operador confirmó saldo/condiciones sin cargos.')
    p.add_argument('--confirm-data-policy', action='store_true', help='El operador confirmó derechos y tratamiento de datos.')
    args = p.parse_args()
    if not 1 <= args.max_chunks <= 10:
        p.error('Lotes de 1 a 10.')
    try:
        asyncio.run(run(args))
    except (Exception, KeyboardInterrupt):
        print('BLOQUEADO/DETENIDO: sin reintentos; checkpoints conservados; revisar privacidad y precondiciones.')
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
