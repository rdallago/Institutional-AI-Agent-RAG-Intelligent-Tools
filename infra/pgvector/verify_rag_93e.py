"""Comprobacion explicita de esquema real y fixtures RAG bajo ROLLBACK.

Solo usuarios_dev promovida. No lee ni altera usuarios_test. No ejecuta modelos.
"""
import hashlib
import json
from uuid import uuid4

import psycopg

from maintenance_93e import PRIVATE, IMAGE, VOLUME, config, docker, source_snapshot, snapshots_equal


TABLES = {
    'rag_documentos', 'rag_documento_permisos', 'rag_versiones', 'rag_paginas',
    'rag_fragmentos', 'rag_fragmento_paginas', 'rag_espacios_embeddings',
    'rag_embeddings', 'rag_ingestas',
}


def verify():
    state = json.loads(docker('inspect','api-usuarios-clean-postgres-1'))[0]
    assert state['Image'] == IMAGE and state['Mounts'][0]['Name'] == VOLUME
    baseline = json.loads((PRIVATE/'baseline.private.json').read_text())
    current = source_snapshot(expected_revision='0004_rag')
    assert set(current['records']) == set(baseline['records']) | TABLES
    assert all(current['records'][name]['count'] == 0 for name in TABLES)
    # Separar las tablas nuevas sin omitir controles sobre ninguna tabla original.
    original = dict(current)
    for key in ('columns','constraints','indexes','permissions'):
        original[key] = [row for row in current[key] if row[0] not in TABLES]
    original['records'] = {name:data for name,data in current['records'].items() if name not in TABLES}
    original['revision'] = baseline['revision']
    original['records']['alembic_version'] = baseline['records']['alembic_version']
    assert snapshots_equal(original,baseline)

    c = config()
    conn = psycopg.connect(host=c.host,port=c.port,dbname=c.database,user=c.username,
                          password=c.password,connect_timeout=5,
                          options='-c statement_timeout=10000 -c lock_timeout=2000')
    checks = []
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT current_database()'); assert cur.fetchone()[0] == 'usuarios_dev'
            cur.execute("SELECT extversion FROM pg_extension WHERE extname='vector'");assert cur.fetchone()[0]=='0.8.2'
            cur.execute("SELECT format_type(atttypid,atttypmod) FROM pg_attribute WHERE attrelid='public.rag_embeddings'::regclass AND attname='embedding'");assert cur.fetchone()[0]=='vector(768)'
            cur.execute("SELECT count(*) FROM pg_constraint k JOIN pg_class c ON c.oid=k.conrelid JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND c.relname LIKE 'rag_%' AND (NOT convalidated OR NOT conenforced)");assert cur.fetchone()[0]==0
            cur.execute("SELECT count(*) FROM pg_index i JOIN pg_class c ON c.oid=i.indrelid JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND c.relname LIKE 'rag_%' AND NOT i.indisvalid");assert cur.fetchone()[0]==0
            checks.extend(['extension','vector_768','constraints_validated','indexes_valid','legacy_data_identical'])
            cur.execute('SELECT id FROM public.usuarios LIMIT 1');row=cur.fetchone()
            if row is None: raise RuntimeError('Se requiere propietario existente para fixtures RAG reversibles.')
            owner = row[0]  # UUID solo en memoria; no se cambia ningun usuario.
            d1,d2,v1,v2,fragment,space = [uuid4() for _ in range(6)]
            for document in (d1,d2):
                cur.execute('INSERT INTO public.rag_documentos(id,clave,titulo_publico,propietario_id) VALUES (%s,%s,%s,%s)',(document,'fixture-'+str(document),'Documento sintetico 93E',owner))
            for document,version in ((d1,v1),(d2,v2)):
                cur.execute("INSERT INTO public.rag_versiones(id,documento_id,numero,sha256,ruta_relativa_controlada,bytes,paginas,extractor_version,pipeline_fingerprint) VALUES (%s,%s,1,%s,'fixture.pdf',100,1,'fixture-v1',%s)",(version,document,'a'*64,'b'*64))
                cur.execute('INSERT INTO public.rag_paginas(version_id,pagina_pdf,texto_extraido,hash_texto) VALUES (%s,1,%s,%s)',(version,'Norma.', 'c'*64))
            cur.execute('INSERT INTO public.rag_fragmentos(id,version_id,identificador_estable,ordinal,pagina_inicio,pagina_fin,offset_inicio,offset_fin,texto,hash_texto,tokens_medidos,pipeline_fingerprint) VALUES (%s,%s,%s,1,1,1,0,6,%s,%s,1,%s)',(fragment,v1,'d'*64,'Norma.','c'*64,'b'*64))
            cur.execute("INSERT INTO public.rag_espacios_embeddings(id,modelo_tag,modelo_digest,normalizacion,prefijo_documento,prefijo_consulta,tokenizador_version,fingerprint) VALUES (%s,'nomic-embed-text',%s,'fixture','search_document: ','search_query: ','fixture',%s)",(space,'e'*64,'f'*64))
            vector=[1.0]+[0.0]*767
            cur.execute('INSERT INTO public.rag_embeddings(fragmento_id,espacio_id,embedding,hash_entrada) VALUES (%s,%s,%s::real[]::vector,%s)',(fragment,space,vector,'a'*64))
            cur.execute('SELECT embedding <=> %s::real[]::vector FROM public.rag_embeddings WHERE fragmento_id=%s',(vector,fragment));assert abs(cur.fetchone()[0])<1e-6
            orthogonal=[0.0,1.0]+[0.0]*766
            cur.execute('SELECT embedding <=> %s::real[]::vector FROM public.rag_embeddings WHERE fragmento_id=%s',(orthogonal,fragment));assert abs(cur.fetchone()[0]-1)<1e-6
            checks.extend(['synthetic_insert_768','cosine_identity','cosine_orthogonal'])

            def rejected(name, query, params, expected):
                try:
                    with conn.transaction():
                        cur.execute(query,params)
                except psycopg.Error as error:
                    assert error.sqlstate==expected
                    checks.append(name)
                else: raise RuntimeError('Restriccion esperada no aplicada.')

            rejected('cross_document_active_version','UPDATE public.rag_documentos SET activa_version_id=%s WHERE id=%s',(v2,d1),'23503')
            rejected('cross_version_page','INSERT INTO public.rag_fragmento_paginas(fragmento_id,version_id,pagina_pdf,offset_inicio,offset_fin) VALUES (%s,%s,1,0,6)',(fragment,v2),'23503')
            rejected('permission_requires_read','INSERT INTO public.rag_documento_permisos(documento_id,usuario_id,puede_leer,puede_ingestar) VALUES (%s,%s,false,true)',(d1,owner),'23514')
            rejected('dimension_rejected','UPDATE public.rag_embeddings SET embedding=%s::real[]::vector WHERE fragmento_id=%s',([1.0,0.0],fragment),'22000')
            rejected('zero_vector_rejected','UPDATE public.rag_embeddings SET embedding=%s::real[]::vector WHERE fragmento_id=%s',([0.0]*768,fragment),'23514')
            rejected('embedding_space_dimension','UPDATE public.rag_espacios_embeddings SET dimension=767 WHERE id=%s',(space,),'23514')
            rejected('embedding_model_allowlist',"UPDATE public.rag_espacios_embeddings SET modelo_tag='arbitrary' WHERE id=%s",(space,),'23514')
            rejected('version_idempotency',"INSERT INTO public.rag_versiones(id,documento_id,numero,sha256,ruta_relativa_controlada,bytes,paginas,extractor_version,pipeline_fingerprint) VALUES (%s,%s,2,%s,'fixture.pdf',100,1,'fixture',%s)",(uuid4(),d1,'a'*64,'b'*64),'23505')
            cur.execute('INSERT INTO public.rag_ingestas(id,version_id,espacio_id) VALUES (%s,%s,%s)',(uuid4(),v1,space))
            rejected('duplicate_active_ingestion','INSERT INTO public.rag_ingestas(id,version_id,espacio_id) VALUES (%s,%s,%s)',(uuid4(),v1,space),'23505')
    finally:
        conn.rollback()
        conn.close()
    after=source_snapshot(expected_revision='0004_rag')
    assert snapshots_equal(current,after)
    (PRIVATE/'rag-schema-verification.json').write_text(json.dumps({'checks':checks,'rollback_verified':True}),encoding='utf-8')
    print('RAG_SCHEMA_APPROVED: '+str(len(checks))+' controles; fixtures revertidas; datos originales intactos; revision 0004_rag.')


if __name__ == '__main__':
    try:
        verify()
    except Exception:
        # No publicar excepciones con parametros/filas; detener fase.
        print('RAG_SCHEMA_FAILED: no reabrir escritores hasta revisar.')
        raise SystemExit(1)
