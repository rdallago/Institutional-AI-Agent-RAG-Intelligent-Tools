"""Todo transporte de esta batería usa MockTransport, sin API real."""
import asyncio
from dataclasses import replace
import hashlib
import json
from types import SimpleNamespace
from uuid import uuid4
from contextlib import contextmanager
from unittest.mock import Mock

import httpx
import pytest
from app.infrastructure.configuration.embeddings import EmbeddingConfig, load_embedding_config
from app.infrastructure.rag.jina import JinaEmbeddings
from app.infrastructure.rag.cloud_postgres import CloudPostgresRAG
from app.infrastructure.rag.postgres import PostgresRAG
from app.infrastructure.rag.ollama import SPACE
from app.application.ia.exceptions import IANoDisponible, IATiempoAgotado, IARespuestaInvalida, PromptInvalido
from app.application.auth.exceptions import PermisoDenegado
from app.application.rag.dto import Scope

CONFIG = EmbeddingConfig(provider='jina', api_key='synthetic-secret', testing=True)
VECTOR = [1.] + [0.] * 767


def response():
    return {'model': CONFIG.model, 'data': [{'index': 0, 'embedding': VECTOR}]}


@pytest.mark.parametrize('document', [False, True])
def test_contract_and_tasks(document, caplog):
    calls = []
    def handler(request):
        calls.append(request)
        assert str(request.url) == 'https://api.jina.ai/v1/embeddings'
        assert request.headers['authorization'] == 'Bearer synthetic-secret'
        assert json.loads(request.content) == {'model': CONFIG.model,
            'task': 'retrieval.passage' if document else 'retrieval.query',
            'dimensions': 768, 'normalized': True, 'embedding_type': 'float', 'input': ['Dato sintetico']}
        return httpx.Response(200, json=response())
    async def run():
        p = JinaEmbeddings(CONFIG, transport=httpx.MockTransport(handler))
        try:
            method = p.embed_document if document else p.embed_query
            assert await method('Dato sintetico', space=CONFIG.space) == tuple(VECTOR)
        finally:
            await p.close()
    asyncio.run(run())
    assert len(calls) == 1
    assert 'synthetic-secret' not in caplog.text
    assert 'Dato sintetico' not in caplog.text


@pytest.mark.parametrize('status,error', [(401, IANoDisponible), (402, IANoDisponible),
    (403, IANoDisponible), (429, IANoDisponible), (500, IANoDisponible),
    (503, IANoDisponible), (504, IATiempoAgotado), (422, IARespuestaInvalida), (302, IARespuestaInvalida)])
def test_http_errors_without_retry(status, error):
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(status, text='synthetic-secret', headers={'location': 'https://other.invalid'})
    async def run():
        p = JinaEmbeddings(CONFIG, transport=httpx.MockTransport(handler))
        try:
            with pytest.raises(error):
                await p.embed_query('Dato', space=CONFIG.space)
        finally:
            await p.close()
    asyncio.run(run())
    assert len(calls) == 1


@pytest.mark.parametrize('mutation', ['dimension', 'nan', 'bool', 'norm', 'index', 'count', 'model', 'error'])
def test_invalid_vectors_and_envelopes(mutation):
    body = response()
    if mutation == 'dimension': body['data'][0]['embedding'] = [1.]
    if mutation == 'nan': body['data'][0]['embedding'] = [float('nan')] + [0.] * 767
    if mutation == 'bool': body['data'][0]['embedding'] = [True] + [0.] * 767
    if mutation == 'norm': body['data'][0]['embedding'] = [2.] + [0.] * 767
    if mutation == 'index': body['data'][0]['index'] = True
    if mutation == 'count': body['data'].append(body['data'][0])
    if mutation == 'model': body['model'] = 'other'
    if mutation == 'error': body['error'] = {'message': 'synthetic-secret'}
    async def run():
        # Texto crudo para probar también NaN, sin serialización HTTPX estricta.
        p = JinaEmbeddings(CONFIG, transport=httpx.MockTransport(
            lambda _: httpx.Response(200, text=json.dumps(body))))
        try:
            with pytest.raises(IARespuestaInvalida):
                await p.embed_query('Dato', space=CONFIG.space)
        finally:
            await p.close()
    asyncio.run(run())


@pytest.mark.parametrize('raw', ['{', '{"data":[],"data":[]}', 'x' * 65537], ids=['truncated', 'duplicates', 'oversize'])
def test_bounded_strict_json(raw):
    async def run():
        p = JinaEmbeddings(CONFIG, transport=httpx.MockTransport(lambda _: httpx.Response(200, text=raw)))
        try:
            with pytest.raises(IARespuestaInvalida):
                await p.embed_query('Dato', space=CONFIG.space)
        finally:
            await p.close()
    asyncio.run(run())


@pytest.mark.parametrize('failure,expected', [(httpx.ConnectError, IANoDisponible), (httpx.ReadTimeout, IATiempoAgotado)])
def test_network_failures(failure, expected):
    calls = []
    def handler(request):
        calls.append(request)
        raise failure('synthetic-secret', request=request)
    async def run():
        p = JinaEmbeddings(CONFIG, transport=httpx.MockTransport(handler))
        try:
            with pytest.raises(expected) as e:
                await p.embed_query('Dato', space=CONFIG.space)
            assert 'synthetic-secret' not in str(e.value)
        finally:
            await p.close()
    asyncio.run(run())
    assert len(calls) == 1


def test_fail_before_transport_and_document_privacy_gate():
    async def run():
        p = JinaEmbeddings(CONFIG, transport=httpx.MockTransport(lambda _: pytest.fail('No HTTP')))
        try:
            with pytest.raises(IARespuestaInvalida): await p.embed_query('Dato', space=SPACE)
            with pytest.raises(PromptInvalido): await p.embed_query('password=secret', space=CONFIG.space)
            with pytest.raises(PromptInvalido): await p.embed_query('x' * 8193, space=CONFIG.space)
            p.config = replace(CONFIG, testing=False)
            with pytest.raises(IANoDisponible): await p.embed_document('Documento', space=CONFIG.space)
        finally:
            await p.close()
    asyncio.run(run())


def test_configuration_isolation_and_identity(tmp_path, monkeypatch):
    path = tmp_path / 'settings.env'
    path.write_text('EMBEDDING_PROVIDER=jina\nJINA_API_KEY=never-load-this\n')
    monkeypatch.delenv('JINA_API_KEY', raising=False)
    monkeypatch.delenv('EMBEDDING_PROVIDER', raising=False)
    c = load_embedding_config(env_file=path)
    assert c.provider == 'jina' and not c.api_key
    assert c.space != SPACE and c.space == CONFIG.space
    assert load_embedding_config(testing=True, env_file=path).provider == 'ollama'
    assert 'synthetic-secret' not in repr(CONFIG)
    for changes in ({'dimensions': 1024}, {'timeout': float('nan')}, {'api_key': 'x\r\ny'}):
        with pytest.raises(ValueError): replace(CONFIG, **changes)
    with pytest.raises(ValueError): JinaEmbeddings(CONFIG)


def test_cloud_sql_reuses_acl_and_never_reads_nomic_vectors(monkeypatch):
    queries = []
    def read(self, query, params):
        queries.append((query, params))
        return []
    monkeypatch.setattr(PostgresRAG, 'read', read)
    store = CloudPostgresRAG(None, CONFIG)
    store.read('SELECT * FROM public.rag_embeddings e JOIN public.rag_espacios_embeddings s ON s.id=e.espacio_id', {})
    assert 'public.rag_cloud_embeddings' in queries[0][0]
    assert 'public.rag_cloud_espacios' in queries[0][0]
    principal = SimpleNamespace(usuario_id=uuid4())
    scope = Scope(document_id=uuid4(), version_id=uuid4(), space=CONFIG.space)
    async def active(*_): return scope
    monkeypatch.setattr(store, 'require_active', active)
    asyncio.run(store.search(principal, scope, tuple(VECTOR), limit=12))
    sql, params = queries[-1]
    assert 'puede_leer' in sql and "v.estado='LISTA'" in sql
    assert 'substring(p.texto_extraido' in sql and 's.fingerprint=:space' in sql
    assert params['space'] == CONFIG.space and params['actor'] == principal.usuario_id
    with pytest.raises(PermisoDenegado):
        asyncio.run(store.search(principal, replace(scope, space=SPACE), tuple(VECTOR), limit=12))


def test_unpublished_cloud_fails_closed(monkeypatch):
    version, document = uuid4(), uuid4()
    def read(self, query, params):
        return [{'version': version}] if 'AS version' in query else []
    monkeypatch.setattr(PostgresRAG, 'read', read)
    store = CloudPostgresRAG(None, CONFIG)
    with pytest.raises(IANoDisponible):
        asyncio.run(store.require_active(SimpleNamespace(usuario_id=uuid4()), document))


def test_publication_checks_all_rows_before_pointer():
    events = []
    class Result:
        def mappings(self): return self
        def all(self): return []  # Incompleto.
        def first(self): return (uuid4(),)
    class Conn:
        def execute(self, query, params):
            events.append(str(query))
            return Result()
    class Engine:
        @contextmanager
        def begin(self): yield Conn()
    store = CloudPostgresRAG(Engine(), CONFIG)
    with pytest.raises(IARespuestaInvalida): store.activate(uuid4(), uuid4())
    assert not any('INSERT INTO public.rag_cloud_activos' in q for q in events)
    assert any('FOR UPDATE OF d' in q for q in events)


def test_publication_transaction_validates_hash_and_vector():
    events = []
    value = 'Dato sintetico'
    digest = hashlib.sha256(value.encode()).hexdigest()
    row = dict(texto=value, texto_extraido=value, offset_inicio=0, offset_fin=len(value),
        pagina_inicio=11, pagina_fin=11, hash_texto=digest, page_hash=digest, hash_entrada=digest, vector=json.dumps(VECTOR))
    class Result:
        def mappings(self): return self
        def all(self): return [row] * 432
        def first(self): return (uuid4(),)
    class Conn:
        def execute(self, query, params): events.append(str(query)); return Result()
    class Engine:
        @contextmanager
        def begin(self): yield Conn()
    store = CloudPostgresRAG(Engine(), CONFIG)
    store.activate(uuid4(), uuid4())
    assert 'rag_cloud_activos' in events[-1]
    events.clear(); row['hash_entrada'] = '0' * 64
    with pytest.raises(IARespuestaInvalida): store.activate(uuid4(), uuid4())
    assert not any('INSERT INTO public.rag_cloud_activos' in q for q in events)


def test_cli_privacy_block_before_database(monkeypatch):
    from app.presentation.cli import reindex_jina
    monkeypatch.setattr(reindex_jina, 'load_database_config', lambda: pytest.fail('No SQL'))
    with pytest.raises(RuntimeError, match='privacidad'):
        asyncio.run(reindex_jina.run(SimpleNamespace()))


def test_cloud_lifespan_never_constructs_ollama_embeddings(monkeypatch):
    from contextlib import asynccontextmanager
    from auth_support import memory_auth
    from fastapi.testclient import TestClient
    from app.bootstrap import create_app
    from app.infrastructure.configuration.llm import LLMConfig
    from app.infrastructure.llm.ollama import LLMRuntime
    from app.infrastructure.llm.admission import MemoryGenerationAdmission
    import app.bootstrap as bootstrap
    users, auth, _ = memory_auth()
    engine = Mock()
    monkeypatch.setattr(bootstrap, 'crear_persistencia_postgresql', lambda *_: (engine, users.users))
    monkeypatch.setattr('app.infrastructure.configuration.llm_local.require_local_runtime', lambda *_: None)
    monkeypatch.setattr('app.infrastructure.configuration.embeddings.load_embedding_config', lambda: CONFIG)
    def forbidden(*_a, **_k): pytest.fail('No construir embeddings Ollama')
    monkeypatch.setattr('app.infrastructure.rag.ollama.Embeddings', forbidden)
    real_constructor = JinaEmbeddings
    held = []
    def jina(config):
        p = real_constructor(config, transport=httpx.MockTransport(lambda _: pytest.fail('Sin HTTP')))
        held.append(p)
        return p
    monkeypatch.setattr('app.infrastructure.rag.jina.JinaEmbeddings', jina)
    @asynccontextmanager
    async def runtime(*_a, **_k):
        yield LLMRuntime(Mock(), MemoryGenerationAdmission(), 60)
    monkeypatch.setattr('app.infrastructure.llm.openrouter.openrouter_runtime', runtime)
    cfg = LLMConfig(enabled=True, environment='local-development', provider='openrouter', api_key='synthetic')
    with TestClient(create_app(auth_service=auth, llm_config=cfg)) as client:
        assert client.get('/openapi.json').status_code == 200
        assert isinstance(client.app.state.rag_documents, CloudPostgresRAG)
        assert client.app.state.rag_service.embeddings is held[0]
    assert held[0].client.is_closed


def test_migration_is_additive_and_never_activates(monkeypatch):
    import importlib.util
    from pathlib import Path
    path = Path(__file__).resolve().parents[2] / 'migrations' / 'versions' / '0006_cloud_embeddings.py'
    spec = importlib.util.spec_from_file_location('cloud_migration_test', path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    statements = []
    monkeypatch.setattr(migration.op, 'execute', statements.append)
    migration.upgrade()
    assert len(statements) == 4
    assert all(q.startswith('CREATE TABLE public.rag_cloud_') for q in statements)
    assert not any('INSERT' in q or 'UPDATE' in q or 'ALTER' in q for q in statements)
    assert migration.down_revision == '0005_agent_memory'
    with pytest.raises(RuntimeError): migration.downgrade()
