"""Base nueva desechable solamente; nunca usuarios_dev ni usuarios_test."""
import asyncio
import hashlib
import json
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from jina_disposable_support import disposable_engine, disposable_config
from app.infrastructure.configuration.embeddings import EmbeddingConfig
from app.infrastructure.rag.cloud_postgres import CloudPostgresRAG
from app.application.auth.exceptions import PermisoDenegado
from app.application.ia.exceptions import IARespuestaInvalida, IANoDisponible

pytestmark = pytest.mark.postgres


@pytest.fixture(scope='module')
def cloud_disposable_resources():
    # Sin autorizacion no se crea motor ni se ejecuta SQL.
    import os
    if not os.environ.get('JINA_TEST_ALLOW_SCHEMA'):
        pytest.skip('Base desechable pendiente de creacion/autorizacion explicita.')
    disposable_config()
    with disposable_engine() as resources:
        yield resources


def test_parallel_space_checkpoints_publication_and_acl(cloud_disposable_resources):
    config, engine = cloud_disposable_resources
    with engine.begin() as conn:
        actor, stranger, document, version = (uuid4() for _ in range(4))
        for user in (actor, stranger):
            conn.execute(text('''INSERT INTO usuarios(id,nombre,apellido,email,activo,rol,fecha_creacion)
                VALUES(:u,'Cloud','Fixture',:email,true,'ADMIN',now())'''),
                {'u': user, 'email': str(user)+'@example.invalid'})
        conn.execute(text('''INSERT INTO rag_documentos(id,clave,titulo_publico,propietario_id)
            VALUES(:d,'fixture-cloud','Fixture cloud',:u)'''), {'d': document, 'u': actor})
        conn.execute(text('''INSERT INTO rag_versiones(id,documento_id,numero,sha256,ruta_relativa_controlada,
            bytes,paginas,extractor_version,pipeline_fingerprint,estado,publicado_at)
            VALUES(:v,:d,1,:h,'fixture.pdf',1,1,'fixture',:h,'LISTA',now())'''),
            {'v': version, 'd': document, 'h': 'a'*64})
        conn.execute(text('UPDATE rag_documentos SET activa_version_id=:v WHERE id=:d'), {'v': version, 'd': document})
        digest = hashlib.sha256(b'a').hexdigest()
        conn.execute(text('INSERT INTO rag_paginas VALUES(:v,1,NULL,\'a\',:h)'), {'v': version, 'h': digest})
        fragments = [uuid4() for _ in range(432)]
        conn.execute(text('''INSERT INTO rag_fragmentos(id,version_id,identificador_estable,ordinal,
            pagina_inicio,pagina_fin,offset_inicio,offset_fin,texto,hash_texto,tokens_medidos,pipeline_fingerprint)
            VALUES(:id,:v,:stable,:n,1,1,0,1,'a',:h,1,:h)'''),
            [{'id': f, 'v': version, 'stable': hashlib.sha256(str(f).encode()).hexdigest(),
              'n': n, 'h': digest} for n, f in enumerate(fragments, 1)])
        from app.infrastructure.rag.postgres import SPACE_ID, SPACE, DIGEST
        conn.execute(text('''INSERT INTO rag_espacios_embeddings(id,modelo_tag,modelo_digest,
            normalizacion,prefijo_documento,prefijo_consulta,tokenizador_version,fingerprint)
            VALUES(:s,'nomic-embed-text',:digest,'fixture','search_document: ',
            'search_query: ','fixture',:fp)'''), {'s': SPACE_ID, 'digest': DIGEST, 'fp': SPACE})
        historical = (0., 1.) + (0.,)*766
        conn.execute(text('''INSERT INTO rag_embeddings(fragmento_id,espacio_id,embedding,hash_entrada)
            VALUES(:f,:s,CAST(:vec AS public.vector),:h)'''),
            {'f': fragments[0], 's': SPACE_ID, 'vec': json.dumps(historical), 'h': digest})

    store = CloudPostgresRAG(engine, EmbeddingConfig(provider='jina'))
    vector = (1.,) + (0.,)*767
    store.prepare_existing(actor, version)
    assert len(store.missing_cloud(version)) == 432
    with pytest.raises(IANoDisponible):
        asyncio.run(store.require_active(SimpleNamespace(usuario_id=actor), document))
    store.checkpoint_cloud(actor, version, fragments[0], vector)
    store.checkpoint_cloud(actor, version, fragments[0], vector)
    engine.dispose()  # Abrir conexiones nuevas: comprobar checkpoints confirmados.
    resumed = CloudPostgresRAG(engine, EmbeddingConfig(provider='jina'))
    assert len(resumed.missing_cloud(version)) == 431
    with pytest.raises(IARespuestaInvalida):
        resumed.checkpoint_cloud(actor, version, fragments[0], historical)
    invalid_vectors = [[1., 0.], [float('nan')] + [0.]*767, [float('inf')] + [0.]*767]
    for invalid in invalid_vectors:
        with pytest.raises(SQLAlchemyError):
            with engine.begin() as conn:
                conn.execute(text('''INSERT INTO rag_cloud_embeddings(fragmento_id,espacio_id,embedding,hash_entrada)
                    VALUES(:f,:s,CAST(:vec AS public.vector),:h)'''),
                    {'f': fragments[1], 's': store.space_id, 'vec': json.dumps(invalid), 'h': digest})
    for fragment in (fragments[0], uuid4()):  # PK duplicada / FK inexistente.
        with pytest.raises(SQLAlchemyError):
            with engine.begin() as conn:
                conn.execute(text('''INSERT INTO rag_cloud_embeddings(fragmento_id,espacio_id,embedding,hash_entrada)
                    VALUES(:f,:s,CAST(:vec AS public.vector),:h)'''),
                    {'f': fragment, 's': store.space_id, 'vec': json.dumps(vector), 'h': digest})
    with pytest.raises(IARespuestaInvalida): store.activate(actor, version)
    with engine.connect() as check:
        assert check.execute(text('SELECT count(*) FROM rag_cloud_activos WHERE version_id=:v'), {'v': version}).scalar_one() == 0
    for fragment in fragments[1:]: store.checkpoint_cloud(actor, version, fragment, historical)
    assert store.validate_cloud(actor, version) == 432
    store.activate(actor, version)
    scope = asyncio.run(store.require_active(SimpleNamespace(usuario_id=actor), document))
    found = asyncio.run(store.search(SimpleNamespace(usuario_id=actor), scope, vector, limit=12))
    assert len(found) == 12 and found[0].similarity == pytest.approx(1)
    assert found[1].similarity == pytest.approx(0)
    assert found[0].chunk.id == hashlib.sha256(str(fragments[0]).encode()).hexdigest()
    with pytest.raises(PermisoDenegado):
        asyncio.run(store.require_active(SimpleNamespace(usuario_id=stranger), document))
    with engine.connect() as check:
        assert check.execute(text('SELECT activa_version_id FROM rag_documentos WHERE id=:d'), {'d': document}).scalar_one() == version
        assert check.execute(text('SELECT count(*) FROM rag_embeddings')).scalar_one() == 1
        assert check.execute(text('SELECT embedding=CAST(:vec AS public.vector) FROM rag_embeddings'),
                             {'vec': json.dumps(historical)}).scalar_one()

