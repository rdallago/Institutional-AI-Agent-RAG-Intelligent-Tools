"""Real ACL SQL in isolated in-memory SQLite; PG locks tested as SQL contracts.

No development/test PostgreSQL, API transports or real credentials are used.
"""
import asyncio
import hashlib
import importlib.util
import re
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

from app.application.auth.exceptions import PermisoDenegado
from app.application.auth.service import Principal
from app.application.ia.exceptions import IARespuestaInvalida, IANoDisponible
from app.application.rag.functions import literal_functions
from app.infrastructure.configuration.embeddings import EmbeddingConfig
from app.infrastructure.rag.cloud_postgres import CloudPostgresRAG
from app.infrastructure.rag.postgres import PostgresRAG, ACL


def migration():
    path=Path(__file__).resolve().parents[2]/'migrations/versions/0007_institutional_publication.py'
    spec=importlib.util.spec_from_file_location('publication_migration',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


class IsolatedSQL:
    def __init__(self):
        self.raw=create_engine('sqlite://',poolclass=StaticPool,connect_args={'check_same_thread':False})
        self.sql=[]
        with self.raw.begin() as c:
            c.execute(text('PRAGMA foreign_keys=ON'))
            c.execute(text("ATTACH DATABASE ':memory:' AS public"))
    @contextmanager
    def begin(self):
        with self.raw.begin() as c:yield self.connection(c)
    @contextmanager
    def connect(self):
        with self.raw.connect() as c:yield self.connection(c)
    def connection(self,c):
        outer=self
        class Connection:
            def execute(self,query,params=None):
                query=str(query);outer.sql.append(query)
                if query.startswith('SET LOCAL'):
                    return SimpleNamespace(rowcount=0)
                query=re.sub(r' FOR (?:UPDATE|SHARE) OF [a-z,]+','',query)
                query=query.replace('REFERENCES public.','REFERENCES ')
                return c.execute(text(query),{k:str(v) if isinstance(v,UUID) else v for k,v in (params or {}).items()})
        return Connection()
    def execute(self,query,params=None):
        with self.begin() as c:return c.execute(query,params)


@pytest.fixture
def db():
    db=IsolatedSQL()
    for ddl in (
        'CREATE TABLE public.usuarios(id uuid PRIMARY KEY,activo boolean NOT NULL,rol text NOT NULL)',
        '''CREATE TABLE public.rag_documentos(id uuid PRIMARY KEY,propietario_id uuid,
           visibilidad text DEFAULT 'PRIVATE',activa_version_id uuid,archivado_at text,titulo_publico text)''',
        '''CREATE TABLE public.rag_versiones(id uuid PRIMARY KEY,documento_id uuid,estado text,paginas integer,
           UNIQUE(documento_id,id))''',
        '''CREATE TABLE public.rag_documento_permisos(documento_id uuid,usuario_id uuid,
           puede_leer boolean,puede_ingestar boolean)''',
        'CREATE TABLE public.rag_cloud_activos(version_id uuid PRIMARY KEY,espacio_id uuid)',
        'CREATE TABLE public.rag_cloud_ingestas(version_id uuid,espacio_id uuid,estado text)',
        'CREATE TABLE public.rag_paginas(version_id uuid,pagina_pdf integer,texto_extraido text,hash_texto text)',
    ):db.execute(ddl)
    m=migration();m.op=SimpleNamespace(execute=db.execute);m.upgrade()
    owner=Principal(uuid4(),uuid4());reader=Principal(uuid4(),uuid4());other_admin=Principal(uuid4(),uuid4())
    document,version=uuid4(),uuid4();config=EmbeddingConfig(provider='jina',testing=True)
    for p,role in ((owner,'ADMIN'),(reader,'USUARIO'),(other_admin,'ADMIN')):
        db.execute('INSERT INTO public.usuarios VALUES(:id,true,:role)',{'id':p.usuario_id,'role':role})
    db.execute("INSERT INTO public.rag_documentos VALUES(:d,:u,'PRIVATE',:v,NULL,'Reglamento sintético')",
               {'d':document,'u':owner.usuario_id,'v':version})
    db.execute("INSERT INTO public.rag_versiones VALUES(:v,:d,'LISTA',3)",{'v':version,'d':document})
    store=CloudPostgresRAG(db,config)
    db.execute('INSERT INTO public.rag_cloud_activos VALUES(:v,:s)',{'v':version,'s':store.space_id})
    db.execute("INSERT INTO public.rag_cloud_ingestas VALUES(:v,:s,'VALIDADA')",{'v':version,'s':store.space_id})
    original=store.read
    def read(query,params):
        rows=original(query,params)
        return [dict(r,**({'version':UUID(r['version'])} if 'version' in r else {})) for r in rows]
    store.read=read
    yield SimpleNamespace(db=db,store=store,owner=owner,reader=reader,admin=other_admin,document=document,version=version,migration=m)
    db.raw.dispose()


def share(db):
    asyncio.run(db.store.set_institutional_publication(db.owner,db.document,db.version,publish=True))


def test_private_isolation_then_same_published_document_for_both_users(db):
    with pytest.raises(PermisoDenegado):asyncio.run(db.store.require_active(db.reader,db.document))
    with pytest.raises(PermisoDenegado):asyncio.run(db.store.require_active(db.admin,db.document))
    assert asyncio.run(db.store.list_documents(db.reader))==[]
    share(db)
    owner=asyncio.run(db.store.require_active(db.owner,db.document))
    assert asyncio.run(db.store.require_active(db.reader,db.document))==owner
    catalog=asyncio.run(db.store.list_documents(db.reader))
    assert len(catalog)==1 and str(catalog[0]['id'])==str(db.document)
    assert 'FOR UPDATE OF d,u' in '\n'.join(db.db.sql)
    assert 'FOR SHARE OF v,a,i' in '\n'.join(db.db.sql)


@pytest.mark.parametrize('who',['reader','admin'])
@pytest.mark.parametrize('publish',[True,False])
def test_non_owner_or_non_admin_cannot_publish_or_revoke(db,who,publish):
    with pytest.raises(PermisoDenegado):
        asyncio.run(db.store.set_institutional_publication(getattr(db,who),db.document,db.version,publish=publish))
    assert not any('INSERT INTO public.rag_publicaciones' in sql for sql in db.db.sql)


@pytest.mark.parametrize('state',['unpublished','revoked','archived','not_ready','no_version','new_version'])
def test_visibility_is_version_bound_and_fails_closed(db,state):
    share(db)
    if state=='unpublished':db.db.execute('DELETE FROM public.rag_publicaciones_institucionales')
    elif state=='revoked':
        asyncio.run(db.store.set_institutional_publication(db.owner,db.document,db.version,publish=False))
    elif state=='archived':db.db.execute("UPDATE public.rag_documentos SET archivado_at='now'")
    elif state=='not_ready':db.db.execute("UPDATE public.rag_versiones SET estado='PREPARANDO'")
    elif state=='no_version':db.db.execute('UPDATE public.rag_documentos SET activa_version_id=NULL')
    else:
        v=uuid4();db.db.execute("INSERT INTO public.rag_versiones VALUES(:v,:d,'LISTA',3)",{'v':v,'d':db.document})
        db.db.execute('UPDATE public.rag_documentos SET activa_version_id=:v',{'v':v})
    assert asyncio.run(db.store.list_documents(db.reader))==[]
    with pytest.raises(PermisoDenegado):asyncio.run(db.store.require_active(db.reader,db.document))


@pytest.mark.parametrize('state',['space','validation','version'])
def test_unvalidated_or_unpublished_index_cannot_be_shared(db,state):
    if state=='space':db.db.execute('DELETE FROM public.rag_cloud_activos')
    elif state=='validation':db.db.execute("UPDATE public.rag_cloud_ingestas SET estado='PREPARANDO'")
    else:db.db.execute("UPDATE public.rag_versiones SET estado='PREPARANDO'")
    with pytest.raises(IARespuestaInvalida):share(db)
    assert not any('INSERT INTO public.rag_publicaciones' in sql for sql in db.db.sql)


def test_cloud_pointer_revocation_hides_catalog_and_blocks_read(db):
    share(db);db.db.execute('DELETE FROM public.rag_cloud_activos')
    with pytest.raises(IANoDisponible):asyncio.run(db.store.require_active(db.reader,db.document))
    assert asyncio.run(db.store.list_documents(db.reader))==[]


def test_migration_isolated_upgrade_downgrade_and_no_automatic_grants(db):
    assert not db.db.execute('SELECT * FROM public.rag_publicaciones_institucionales').all()
    share(db);db.migration.downgrade()
    assert db.db.execute('SELECT visibilidad FROM public.rag_documentos').scalar()=='PRIVATE'
    db.migration.upgrade()
    assert not db.db.execute('SELECT * FROM public.rag_publicaciones_institucionales').all()
    assert db.migration.down_revision=='0006_cloud_embeddings'


def test_function_sources_and_pages_match_for_owner_and_reader(db):
    from tests.rag.test_literal_functions_12d import pages
    for n,content in pages():
        db.db.execute('INSERT INTO public.rag_paginas VALUES(:v,:p,:t,:h)',
            {'v':db.version,'p':n,'t':content,'h':hashlib.sha256(content.encode()).hexdigest()})
    share(db);outputs=[]
    for principal in (db.owner,db.reader):
        scope=asyncio.run(db.store.require_active(principal,db.document))
        result=asyncio.run(db.store.resolve_functions(principal,scope,'¿Cuáles son las funciones del Director?'))
        outputs.append(literal_functions('¿Cuáles son las funciones del Director?',result.chunks,scope))
    assert outputs[0]==outputs[1] and outputs[0] is not None
    assert [(e.citation,e.chunk.page) for e in outputs[1][1]]==[('F1',1),('F2',2),('F3',3)]


def test_requirement_enumeration_is_identical_for_both_readers_without_generation(db):
    from tests.rag.test_literal_requirements_12d import verified, QUESTION
    from tests.rag.test_core import setup
    from app.application.rag.dto import Candidate
    from app.application.rag.relevance import AcademicRelevance
    share(db);scope=asyncio.run(db.store.require_active(db.owner,db.document))
    seed,chunk=verified(scope)
    *_,case=setup();case.documents=db.store;case.relevance=AcademicRelevance()
    async def search(principal,current,vector,**kwargs):
        assert await db.store.require_active(principal,db.document)==current
        return (Candidate(chunk=seed,similarity=.9),)
    async def continuity(principal,current,chunks):
        assert await db.store.require_active(principal,db.document)==current
        return (chunk,)
    case.vectors=SimpleNamespace(search=search);case.continuity=continuity
    results=[asyncio.run(case.execute(p,db.document,QUESTION)) for p in (db.owner,db.reader)]
    assert results[0]==results[1] and results[0].status=='FUNDAMENTADA'
    assert results[0].answer.count('[F1]')==3 and results[0].citations[0].chunk.page==33
    assert not case.provider.inputs


def test_disabled_reader_has_no_institutional_access(db):
    share(db)
    db.db.execute('UPDATE public.usuarios SET activo=false WHERE id=:u',{'u':db.reader.usuario_id})
    with pytest.raises(PermisoDenegado):asyncio.run(db.store.require_active(db.reader,db.document))


def test_revocation_blocks_history_replay_and_other_users_conversations(db):
    from app.application.agent.conversations import Conversations
    from tests.rag.test_tools_memory import MemoryConversations
    from tests.rag.test_core import Authorizer
    share(db);repo=MemoryConversations()
    service=Conversations(authorizer=Authorizer(),repository=repo,agent=SimpleNamespace(documents=db.store))
    c=UUID(asyncio.run(service.create(db.reader))['id'])
    repo.rows[c]=[{'role':'assistant','content':'Texto sintético [F1].','references':[
        {'document':str(db.document),'version':str(db.version),'id':'F1','pagina':1}]}]
    assert asyncio.run(service.history(db.reader,c))
    with pytest.raises(PermisoDenegado):asyncio.run(service.history(db.owner,c))
    asyncio.run(db.store.set_institutional_publication(db.owner,db.document,db.version,publish=False))
    with pytest.raises(PermisoDenegado):asyncio.run(service.history(db.reader,c))
    key=uuid4()
    import json
    question='Pregunta sintética.'
    fingerprint=hashlib.sha256(json.dumps([question,'AUTO','None'],ensure_ascii=True).encode()).hexdigest()
    repo.requests[(c,key)]={'fp':fingerprint,'state':'COMPLETA','payload':{'resultado':'no entregar'}}
    with pytest.raises(PermisoDenegado):
        asyncio.run(service.turn(db.reader,c,key,question,'AUTO',None))


def test_same_acl_is_embedded_in_vector_search_and_continuity(db):
    share(db);scope=asyncio.run(db.store.require_active(db.reader,db.document));queries=[]
    original=db.store.read
    def read(query,params):
        if 'SELECT f.*' in query:
            queries.append(query);assert ACL in query and params['actor']==db.reader.usuario_id;return []
        return original(query,params)
    db.store.read=read
    asyncio.run(db.store.search(db.reader,scope,(1.,)+(0.,)*767,limit=12))
    asyncio.run(db.store.recover(db.reader,scope,(1.,)+(0.,)*767))
    from app.application.rag.dto import Chunk
    asyncio.run(db.store.article_context(db.reader,scope,(Chunk(id='x',scope=scope,page=1,
        start=0,end=12,text='Articulo 8. ',section=''),)))
    assert len(queries)==3


@pytest.mark.parametrize('action',['prepare_existing','validate_cloud','activate'])
def test_sharing_read_never_grants_cloud_write_capabilities(db,action):
    share(db);db.db.sql.clear()
    with pytest.raises(PermisoDenegado):getattr(db.store,action)(db.reader.usuario_id,db.version)
    assert not any(sql.lstrip().startswith(('INSERT','UPDATE','DELETE')) for sql in db.db.sql)


def test_revocation_retains_owner_and_separate_explicit_acl(db):
    share(db)
    db.db.execute('INSERT INTO public.rag_documento_permisos VALUES(:d,:u,true,false)',
                  {'d':db.document,'u':db.reader.usuario_id})
    asyncio.run(db.store.set_institutional_publication(db.owner,db.document,db.version,publish=False))
    assert asyncio.run(db.store.require_active(db.owner,db.document))
    assert asyncio.run(db.store.require_active(db.reader,db.document))
    # Revoking institutional publication does not silently delete independent ACLs.
    db.db.execute('DELETE FROM public.rag_documento_permisos')
    with pytest.raises(PermisoDenegado):asyncio.run(db.store.require_active(db.reader,db.document))


def test_migration_rejects_cross_document_version_and_inconsistent_revocation(db):
    from sqlalchemy.exc import IntegrityError
    other=uuid4();v=uuid4()
    db.db.execute("INSERT INTO public.rag_documentos VALUES(:d,:u,'PRIVATE',NULL,NULL,'Otro')",
                  {'d':other,'u':db.owner.usuario_id})
    db.db.execute("INSERT INTO public.rag_versiones VALUES(:v,:d,'LISTA',3)",{'v':v,'d':other})
    with pytest.raises(IntegrityError):
        db.db.execute('INSERT INTO public.rag_publicaciones_institucionales(documento_id,version_id,publicado_por) '
                      'VALUES(:d,:v,:u)',{'d':db.document,'v':v,'u':db.owner.usuario_id})
    share(db)
    with pytest.raises(IntegrityError):
        db.db.execute('UPDATE public.rag_publicaciones_institucionales SET revocado_por=:u',{'u':db.owner.usuario_id})


@pytest.mark.parametrize('admin',[True,False])
def test_http_authenticated_publication_and_no_client_role_escalation(db,admin):
    from fastapi.testclient import TestClient
    from tests.ia.test_http_ia import setup_app
    from app.domain.usuarios.rol import Rol
    app,_,_,principal,headers,_=setup_app(role=Rol.ADMIN if admin else Rol.USUARIO)
    db.db.execute('INSERT INTO public.usuarios VALUES(:id,true,:role)',
                  {'id':principal.usuario_id,'role':'ADMIN' if admin else 'USUARIO'})
    if admin:db.db.execute('UPDATE public.rag_documentos SET propietario_id=:u',{'u':principal.usuario_id})
    path=f'/api/v1/ia/documentos/{db.document}/publicacion'
    with TestClient(app) as client:
        app.state.rag_documents=db.store
        assert client.post(path,json={'version_id':str(db.version)}).status_code==401
        assert client.post(path,headers=headers,json={'version_id':str(db.version),'rol':'ADMIN'}).status_code==422
        response=client.post(path,headers=headers,json={'version_id':str(db.version)})
        assert response.status_code==(200 if admin else 403)
        if admin:
            assert response.json()['publicacion']=='PUBLICADA'
            response=client.request('DELETE',path,headers=headers,json={'version_id':str(db.version)})
            assert response.status_code==200 and response.json()['publicacion']=='REVOCADA'
        else:
            assert client.request('DELETE',path,headers=headers,json={'version_id':str(db.version)}).status_code==403
        # Sharing adds no public editing, deletion or activation endpoints.
        for route in app.routes:
            path=getattr(route,'path','')
            if path=='/api/v1/ia/documentos/{document}':
                assert not {'DELETE','PUT','PATCH'} & getattr(route,'methods',set())
            assert not path.startswith('/api/v1/ia/documentos/{document}/activate')
