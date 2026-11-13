"""Coordina lotes CLI sin reintentos; requiere autorización externa previa."""
import argparse
import json
import subprocess
import sys
import psycopg
from app.infrastructure.configuration.database import load_database_config
from app.infrastructure.configuration.embeddings import load_embedding_config
from app.infrastructure.rag.document_export import DOCUMENT, VERSION, OWNER, SPACE


def progress():
    """Solo lectura: scope, integridad de checkpoints e históricos; nunca crea engine."""
    c=load_database_config()
    if (c.host,c.port,c.database)!=('127.0.0.1',5434,'usuarios_dev'):
        raise RuntimeError('Destino incorrecto')
    with psycopg.connect(host=c.host,port=c.port,dbname=c.database,user=c.username,password=c.password,
            connect_timeout=10,options='-c default_transaction_read_only=on -c statement_timeout=10000') as conn:
        if conn.execute('SHOW transaction_read_only').fetchone()[0]!='on':
            raise RuntimeError('Lectura no protegida')
        if conn.execute('SELECT version_num FROM alembic_version').fetchone()[0]!='0006_cloud_embeddings':
            raise RuntimeError('Revisión incorrecta')
        valid=conn.execute("""SELECT 1 FROM rag_documentos d JOIN usuarios u ON u.id=d.propietario_id
            JOIN rag_versiones v ON v.id=d.activa_version_id AND v.documento_id=d.id
            WHERE d.id=%s AND v.id=%s AND u.id=%s AND u.activo AND u.rol='ADMIN'
            AND v.estado='LISTA' AND d.archivado_at IS NULL""",(DOCUMENT,VERSION,OWNER)).fetchone()
        if not valid:raise RuntimeError('ACL o versión cambiada')
        if conn.execute('SELECT count(*) FROM rag_fragmentos WHERE version_id=%s',(VERSION,)).fetchone()[0]!=432:
            raise RuntimeError('Cantidad de fragmentos incorrecta')
        if conn.execute('SELECT count(*) FROM rag_embeddings').fetchone()[0]!=864:
            raise RuntimeError('Cantidad histórica incorrecta')
        if conn.execute('SELECT count(*) FROM rag_cloud_activos').fetchone()[0]!=0:
            raise RuntimeError('Índice ya activado: detener')
        rows=conn.execute('''SELECT f.id,f.hash_texto,e.hash_entrada,e.embedding::text
            FROM rag_fragmentos f JOIN rag_cloud_embeddings e ON e.fragmento_id=f.id
            JOIN rag_cloud_espacios s ON s.id=e.espacio_id
            WHERE f.version_id=%s AND s.fingerprint=%s''',(VERSION,SPACE)).fetchall()
        from app.application.rag.core import validate_vector
        import math
        for _,h,eh,raw in rows:
            vec=tuple(json.loads(raw));validate_vector(vec)
            if h!=eh or abs(math.hypot(*vec)-1)>.01:raise RuntimeError('Checkpoint inválido')
        conn.rollback()
    return len(rows)


def execute_batch(limit):
    args=[sys.executable,'-B','-m','app.presentation.cli.reindex_jina','--action','index',
          '--owner',str(OWNER),'--version',str(VERSION),'--max-chunks',str(limit),
          '--approve-document-export','--confirm-free-usage','--confirm-data-policy']
    # Solo stdout/err genéricos del CLI; nunca propagar cuerpos/secretos de errores no controlados.
    p=subprocess.run(args,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=660)
    return p.returncode


def coordinate(read_progress=progress, batch=execute_batch):
    count=read_progress()
    if type(count) is not int or not 0<=count<=432:raise RuntimeError('Progreso inválido')
    batches=0
    while count<432:
        limit=min(10,432-count)
        code=batch(limit)
        if code!=0:raise RuntimeError('Lote fallido; conservar checkpoints, sin reintento')
        updated=read_progress()
        if type(updated) is not int or updated!=count+limit:
            raise RuntimeError('Progreso inesperado; no iniciar otro lote')
        count=updated;batches+=1
        print(json.dumps({'confirmados':count,'pendientes':432-count,'lotes':batches,'activo':False}))
    return count


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('execute','approve-document-export','confirm-free-usage','confirm-data-policy'):
        p.add_argument('--'+name,action='store_true')
    a=p.parse_args(argv)
    if not all((a.execute,a.approve_document_export,a.confirm_free_usage,a.confirm_data_policy)):
        print('BLOQUEADO: falta autorización/confirmación explícita; no se accedió a servicios.')
        return 2
    try:
        e=load_embedding_config()
        if e.provider!='jina' or e.space!=SPACE or not e.api_key.strip():raise RuntimeError('Configuración incompleta')
        coordinate()
        print('432 checkpoints confirmados. Sin validación de estado ni activación automática.')
        return 0
    except (Exception,KeyboardInterrupt):
        print('DETENIDO: revisar checkpoints y llamadas inciertas antes de autorizar reanudación. Sin reintentos.')
        return 2


if __name__=='__main__':raise SystemExit(main())
