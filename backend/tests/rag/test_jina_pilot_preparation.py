"""Piloto CLI sintético: ningún socket, SQL real o documento real."""
import asyncio
from contextlib import contextmanager
from types import SimpleNamespace
from uuid import uuid4
import hashlib
import httpx
import pytest
from app.infrastructure.configuration.embeddings import EmbeddingConfig
from app.infrastructure.rag.jina import JinaEmbeddings
from app.infrastructure.rag.cloud_postgres import CloudPostgresRAG
from app.application.ia.exceptions import IARespuestaInvalida
from app.presentation.cli import reindex_jina as cli

@pytest.mark.parametrize('failure', [None,401,402,403,429,500,'timeout','sql'])
def test_single_pilot_cli_checkpoint_and_stop(monkeypatch, failure):
    cfg=EmbeddingConfig(provider='jina',testing=True,api_key='synthetic-only')
    from app.infrastructure.rag import document_export as exports
    owner,version,fragment=exports.OWNER,exports.VERSION,uuid4()
    text='Fragmento completamente sintetico.'
    digest=hashlib.sha256(text.encode()).hexdigest()
    manifest={uuid4():digest for _ in range(431)}
    manifest[fragment]=digest
    item=dict(id=fragment,texto=text,hash_texto=digest,texto_extraido=text,page_hash=digest,intact=True)
    calls=[];saved=[];events=[]
    def handler(request):
        calls.append(request)
        import json
        body=json.loads(request.content)
        assert body['task']=='retrieval.passage' and body['input']==[text]
        if failure=='timeout': raise httpx.ReadTimeout('synthetic timeout',request=request)
        return httpx.Response(failure if isinstance(failure,int) else 200,json={
            'model':cfg.model,'data':[{'index':0,'embedding':[1.]+[0.]*767}]})
    class Connection:
        def execute(self,*a):return SimpleNamespace(scalar_one=lambda:'0006_cloud_embeddings')
        def __enter__(self):return self
        def __exit__(self,*a):pass
    class Engine:
        def connect(self):return Connection()
        def dispose(self):events.append('dispose')
    class Store:
        def __init__(self,*a):pass
        def export_manifest(self,*a):return manifest
        def prepare_existing(self,*a):events.append('prepare')
        def missing_cloud(self,*a):return [] if saved else [item]
        def checkpoint_cloud(self,a,v,f,vector):
            assert (a,v,f)==(owner,version,fragment)
            assert len(vector)==768 and vector[0]==1
            if failure=='sql':raise RuntimeError('synthetic SQL failure')
            saved.append((f,cfg.space,digest,vector))
        def activate(self,*a):pytest.fail('No activation')
    monkeypatch.setattr(exports,'require_cli_entry',lambda:None)
    monkeypatch.setattr(cli,'require_cli_entry',lambda:None) # Only the isolated synthetic CLI process identity.
    monkeypatch.setattr(cli,'load_database_config',lambda:SimpleNamespace(host='127.0.0.1',port=5434,database='usuarios_dev'))
    monkeypatch.setattr(cli,'load_embedding_config',lambda:cfg)
    monkeypatch.setattr(cli,'build_engine',lambda c:Engine())
    monkeypatch.setattr(cli,'CloudPostgresRAG',Store)
    monkeypatch.setattr(cli,'LocalModelGate',lambda:SimpleNamespace(try_acquire=lambda:SimpleNamespace(release=lambda:events.append('release'))))
    monkeypatch.setattr(cli,'JinaEmbeddings',lambda _:JinaEmbeddings(cfg,transport=httpx.MockTransport(handler)))
    monkeypatch.setattr(httpx,'AsyncHTTPTransport',lambda *a,**k:pytest.fail('No real transport'))
    monkeypatch.setattr('app.infrastructure.rag.ollama.Embeddings',lambda *a,**k:pytest.fail('No Ollama'))
    args=SimpleNamespace(action='index',owner=owner,version=version,max_chunks=1,
                         approve_document_export=True,confirm_free_usage=True,confirm_data_policy=True)
    if failure is None:asyncio.run(cli.run(args))
    else:
        with pytest.raises(Exception):asyncio.run(cli.run(args))
    assert len(calls)==1 and len(saved)==(1 if failure is None else 0)
    assert events[-2:]==['dispose','release']

@pytest.mark.parametrize('action',['validate_cloud','activate'])
def test_one_of_432_cannot_validate_or_activate(action):
    queries=[]
    class Result:
        def first(self):return (uuid4(),)
        def mappings(self):return self
        def all(self):return [{}] # Only one row: rejected before any status/pointer write.
    class Conn:
        def execute(self,q,*a):queries.append(str(q));return Result()
    class Engine:
        @contextmanager
        def begin(self):yield Conn()
    store=CloudPostgresRAG(Engine(),EmbeddingConfig(provider='jina',testing=True))
    with pytest.raises(IARespuestaInvalida):getattr(store,action)(uuid4(),uuid4())
    assert not any('UPDATE public.rag_cloud_ingestas' in q or 'INSERT INTO public.rag_cloud_activos' in q for q in queries)
