"""Autorización acotada sin red, secretos o SQL real."""
import asyncio
import hashlib
import os
from types import SimpleNamespace
from uuid import uuid4
import httpx
import pytest
from app.infrastructure.rag import document_export as scope
from app.infrastructure.rag.jina import JinaEmbeddings, DOCUMENT_EXPORT_APPROVED
from app.infrastructure.configuration.embeddings import EmbeddingConfig
from app.application.ia.exceptions import IANoDisponible, IARespuestaInvalida
from app.presentation.cli import reindex_jina as cli

TEXT='Texto sintetico de prueba'
HASH=hashlib.sha256(TEXT.encode()).hexdigest()

def manifest():return {uuid4():HASH for _ in range(432)}

def issue(adapter,rows=None,**changes):
    params=dict(adapter=adapter,owner=scope.OWNER,version=scope.VERSION,document=scope.DOCUMENT,
                space=scope.SPACE,manifest=rows if rows is not None else manifest(),limit=1)
    params.update(changes)
    return scope.issue_permit(**params)

@pytest.mark.parametrize('field',['owner','version','document','space','limit','manifest'])
def test_wrong_scope_denied(monkeypatch,field):
    monkeypatch.setattr(scope,'require_cli_entry',lambda:None)
    async def run():
        value={'owner':uuid4(),'version':uuid4(),'document':uuid4(),'space':'0'*64,'limit':11,'manifest':{}}[field]
        with pytest.raises(RuntimeError):issue(object(),**{field:value})
    asyncio.run(run())

def test_fastapi_cannot_issue_permit():
    assert DOCUMENT_EXPORT_APPROVED is False
    async def run():
        with pytest.raises(RuntimeError,match='CLI'):issue(object())
    asyncio.run(run())

@pytest.mark.parametrize('failure',['text','fragment','space','adapter','pid','task','expired','closed','reuse'])
def test_permit_cannot_escape_or_repeat(monkeypatch,failure):
    monkeypatch.setattr(scope,'require_cli_entry',lambda:None)
    async def run():
        a=object();rows=manifest();fid=next(iter(rows));p=issue(a,rows)
        args=[a,fid,TEXT,scope.SPACE]
        if failure=='text':args[2]='Inventado'
        if failure=='fragment':args[1]=uuid4()
        if failure=='space':args[3]='0'*64
        if failure=='adapter':args[0]=object()
        if failure=='pid':monkeypatch.setattr(scope.os,'getpid',lambda:p._pid+1)
        if failure=='expired':monkeypatch.setattr(scope.time,'monotonic',lambda:p._expires+1)
        if failure=='closed':p.close()
        if failure=='reuse':p.consume(*args)
        if failure=='task':
            async def other():
                with pytest.raises(RuntimeError):p.consume(*args)
            await asyncio.create_task(other());return
        with pytest.raises(RuntimeError):p.consume(*args)
    asyncio.run(run())

def test_production_adapter_needs_capability_even_if_global_flag_true(monkeypatch):
    import app.infrastructure.rag.jina as jina
    monkeypatch.setattr(jina,'DOCUMENT_EXPORT_APPROVED',True)
    async def run():
        cfg=EmbeddingConfig(provider='jina',testing=True,api_key='synthetic')
        a=JinaEmbeddings(cfg,transport=httpx.MockTransport(lambda _:pytest.fail('No HTTP')))
        from dataclasses import replace
        a.config=replace(cfg,testing=False)
        try:
            with pytest.raises(IANoDisponible):await a.embed_document(TEXT,space=scope.SPACE)
        finally:await a.close()
    asyncio.run(run())

@pytest.mark.parametrize('change',[{'action':'activate'},{'action':'validate'},
    {'approve_document_export':False},{'confirm_free_usage':False},{'confirm_data_policy':False},
    {'max_chunks':11},{'version':uuid4()},{'owner':uuid4()}])
def test_cli_denies_before_clients_or_sql(monkeypatch,change):
    monkeypatch.setattr(cli,'require_cli_entry',lambda:None)
    monkeypatch.setattr(cli,'load_database_config',lambda:pytest.fail('No SQL/config'))
    args=dict(action='index',owner=scope.OWNER,version=scope.VERSION,max_chunks=1,
              approve_document_export=True,confirm_free_usage=True,confirm_data_policy=True)
    args.update(change)
    with pytest.raises(RuntimeError):asyncio.run(cli.run(SimpleNamespace(**args)))

def test_manifest_checks_real_repository_read_guard(monkeypatch):
    from app.infrastructure.rag.cloud_postgres import CloudPostgresRAG
    from contextlib import contextmanager
    rows=[dict(id=uuid4(),texto=TEXT,hash_texto=HASH,texto_extraido=TEXT,page_hash=HASH,
               offset_inicio=0,offset_fin=len(TEXT),pagina_inicio=11,pagina_fin=11) for _ in range(432)]
    class Result:
        def mappings(self):return self
        def all(self):return rows
    class Conn:
        def execute(self,query,params):
            q=str(query);assert "u.rol='ADMIN'" in q and 'u.activo' in q and 'v.documento_id=d.id' in q
            assert 'd.activa_version_id' in q and "v.estado='LISTA'" in q
            assert params=={'d':scope.DOCUMENT,'v':scope.VERSION,'actor':scope.OWNER}
            return Result()
    class Engine:
        @contextmanager
        def connect(self):yield Conn()
    store=CloudPostgresRAG(Engine(),EmbeddingConfig(provider='jina',testing=True))
    assert len(store.export_manifest(scope.OWNER,scope.VERSION,scope.DOCUMENT))==432
    rows[0]['texto']='Texto alterado'
    with pytest.raises(IARespuestaInvalida):store.export_manifest(scope.OWNER,scope.VERSION,scope.DOCUMENT)

@pytest.mark.parametrize('change',[{'api_key':''},{'provider':'ollama'},{'space':'0'*64}])
def test_missing_runtime_conditions_before_engine(monkeypatch,change):
    monkeypatch.setattr(cli,'require_cli_entry',lambda:None)
    monkeypatch.setattr(cli,'load_database_config',lambda:SimpleNamespace(host='127.0.0.1',port=5434,database='usuarios_dev'))
    config=dict(provider='jina',space=scope.SPACE,api_key='synthetic')
    config.update(change)
    monkeypatch.setattr(cli,'load_embedding_config',lambda:SimpleNamespace(**config))
    monkeypatch.setattr(cli,'build_engine',lambda *_:pytest.fail('No engine'))
    args=SimpleNamespace(action='index',owner=scope.OWNER,version=scope.VERSION,max_chunks=1,
                         approve_document_export=True,confirm_free_usage=True,confirm_data_policy=True)
    with pytest.raises(RuntimeError):asyncio.run(cli.run(args))

def test_permit_ten_distinct_fragments_no_eleventh(monkeypatch):
    monkeypatch.setattr(scope,'require_cli_entry',lambda:None)
    async def run():
        a=object();rows=manifest();p=issue(a,rows,limit=10)
        ids=list(rows)
        for fid in ids[:10]:p.consume(a,fid,TEXT,scope.SPACE)
        with pytest.raises(RuntimeError):p.consume(a,ids[10],TEXT,scope.SPACE)
    asyncio.run(run())
