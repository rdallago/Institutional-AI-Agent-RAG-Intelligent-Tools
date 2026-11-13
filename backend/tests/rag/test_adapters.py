import asyncio
from contextlib import asynccontextmanager
import json
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient

from auth_support import memory_auth, bootstrap_login
from ia_support import FakeLLMProvider
from app.bootstrap import create_app
from app.application.ia.exceptions import IARespuestaInvalida, IAOcupada, IATiempoAgotado, IANoDisponible
from app.application.rag.core import build_context
from app.application.rag.dto import Chunk, Scope, RAGResult
from app.infrastructure.configuration.llm import LLMConfig
from app.infrastructure.llm.admission import MemoryGenerationAdmission
from app.infrastructure.llm.ollama import LLMRuntime
from app.infrastructure.rag.ollama import Embeddings, GroundedProvider, SPACE, DIGEST
from app.infrastructure.rag.text import ConservativeCounter
from app.infrastructure.rag.models import LocalModelGate


CONFIG=LLMConfig(enabled=True,testing=True,environment='test')


class EmptyCatalog:
    async def require_active(self, principal, document):
        return None  # Solo doble del contrato; ACL real se prueba por separado.
    async def list_documents(self, principal):
        return []


@pytest.mark.parametrize('document',[True,False])
def test_embedding_payload_and_identity(document):
    async def scenario():
        def handler(request):
            if request.url.path=='/api/ps':return httpx.Response(200,json={'models':[]})
            if request.url.path=='/api/tags':return httpx.Response(200,json={'models':[{'name':'nomic-embed-text:latest','digest':DIGEST}]})
            body=json.loads(request.content)
            assert body=={'model':'nomic-embed-text','input':('search_document: ' if document else 'search_query: ')+'Sintetico',
                'truncate':False,'keep_alive':0,'options':{'num_ctx':2048}}
            assert 'authorization' not in request.headers and 'cookie' not in request.headers
            return httpx.Response(200,json={'model':'nomic-embed-text:latest','embeddings':[[1.]+[0.]*767],'prompt_eval_count':8})
        adapter=Embeddings(CONFIG,transport=httpx.MockTransport(handler))
        try:
            method=adapter.embed_document if document else adapter.embed_query
            result=await method('Sintetico',space=SPACE)
            assert len(result)==768
        finally:await adapter.close()
        assert adapter.client.is_closed
    asyncio.run(scenario())


@pytest.mark.parametrize('mode',['digest','dimensions','zero','tokens','timeout'])
def test_embedding_invalid_and_timeout(mode):
    async def scenario():
        def handler(request):
            if request.url.path=='/api/ps':return httpx.Response(200,json={'models':[]})
            if request.url.path=='/api/tags':return httpx.Response(200,json={'models':[{'name':'nomic-embed-text:latest','digest':DIGEST}]})
            if mode=='timeout':raise httpx.ReadTimeout('private sentinel')
            return httpx.Response(200,json={'model':'wrong' if mode=='digest' else 'nomic-embed-text',
                'embeddings':[[1.]*2 if mode=='dimensions' else [0.]*768 if mode=='zero' else [1.]*768],
                'prompt_eval_count':99999 if mode=='tokens' else 2})
        adapter=Embeddings(CONFIG,transport=httpx.MockTransport(handler))
        try:
            with pytest.raises(IATiempoAgotado if mode=='timeout' else IARespuestaInvalida):
                await adapter.embed_query('Sintetico',space=SPACE)
        finally:await adapter.close()
    asyncio.run(scenario())


@pytest.mark.parametrize('reason',['stop','length','unknown',None])
def test_grounded_payload_and_strict_reason(reason):
    async def scenario():
        scope=Scope(document_id=uuid4(),version_id=uuid4(),space=SPACE)
        chunk=Chunk(id='fixture',scope=scope,page=4,start=0,end=6,text='Norma.',section='')
        input=build_context('Pregunta',(chunk,),ConservativeCounter())
        def handler(request):
            body=json.loads(request.content)
            assert body['think'] is False and body['stream'] is False and body['keep_alive']==0
            assert body['prompt']==input.rendered and body['options']=={'num_predict':256,'num_ctx':4096}
            return httpx.Response(200,json={'model':'qwen3:1.7b','done':True,'done_reason':reason,
                'response':'Norma [F1].','prompt_eval_count':100})
        adapter=GroundedProvider(CONFIG,transport=httpx.MockTransport(handler))
        try:
            if reason in ('stop','length'):assert (await adapter.generate_grounded(input)).respuesta=='Norma [F1].'
            else:
                with pytest.raises(IARespuestaInvalida):await adapter.generate_grounded(input)
        finally:await adapter.aclose()
    asyncio.run(scenario())


def test_cross_instance_model_exclusion(tmp_path):
    a,b=LocalModelGate(tmp_path/'lock'),LocalModelGate(tmp_path/'lock')
    lease=a.try_acquire()
    with pytest.raises(IAOcupada):b.try_acquire()
    lease.release();new=b.try_acquire();lease.release()
    with pytest.raises(IAOcupada):a.try_acquire()
    new.release()


def test_direct_idle_barrier_and_gate_cleanup(tmp_path):
    from app.infrastructure.rag.models import CoordinatedDirectProvider
    from app.application.ia.dto import GeneracionEntrada
    from app.application.ia.exceptions import IANoDisponible
    async def scenario():
        gate=LocalModelGate(tmp_path/'gate')
        underlying=FakeLLMProvider()
        provider=CoordinatedDirectProvider(underlying,gate)
        async def busy():raise IANoDisponible()
        provider.idle=busy
        with pytest.raises(IANoDisponible):await provider.generate(GeneracionEntrada(prompt='Pregunta'))
        assert not underlying.inputs
        gate.try_acquire().release()
    asyncio.run(scenario())


def test_new_http_modes_and_privacy():
    store,auth,_=memory_auth();_,token=bootstrap_login(auth)
    @asynccontextmanager
    async def runtime(config):yield LLMRuntime(FakeLLMProvider(),MemoryGenerationAdmission(),60)
    app=create_app(repository=store.users,auth_service=auth,llm_config=CONFIG,llm_runtime_factory=runtime)
    class FakeRAG:
        async def execute(self,principal,document,question,**kwargs):
            return RAGResult(status='SIN_EVIDENCIA',answer='No hay evidencia suficiente.')
    with TestClient(app) as client:
        app.state.ia_agent.rag=FakeRAG()
        app.state.ia_agent.documents=EmptyCatalog()
        headers={'Authorization':'Bearer '+token}
        url='/api/v1/ia/respuestas'
        assert client.post(url,json={'modo':'RAG','prompt':'x','documento_id':str(uuid4())}).status_code==401
        response=client.post(url,headers=headers,json={'modo':'RAG','prompt':'x','documento_id':str(uuid4())})
        assert response.status_code==200 and response.headers['Cache-Control']=='no-store'
        assert response.json()=={'respuesta':'No hay evidencia suficiente.','finalizacion':None,'estado':'SIN_EVIDENCIA','estrategia':'RAG','fuentes':[]}
        assert client.post(url,headers=headers,json={'modo':'RAG','prompt':'x'}).status_code==422
        assert client.post(url,headers=headers,json={'modo':'LLM_DIRECTO','prompt':'x','documento_id':str(uuid4())}).status_code==422
        assert client.post(url,headers=headers,json={'modo':'LLM_DIRECTO','prompt':'x'}).json()['estrategia']=='LLM_DIRECTO'
        assert client.post(url,headers=headers,json={'modo':'RAG','prompt':'x'*20000,'documento_id':str(uuid4())}).status_code==413


def test_real_pdf_reader_fictitious_page(tmp_path):
    from pypdf import PdfWriter
    from pypdf.generic import DictionaryObject,NameObject,DecodedStreamObject
    from app.infrastructure.rag.text import _extract_pages
    writer=PdfWriter()
    for number in (1,2):
        page=writer.add_blank_page(width=200,height=200)
        font=DictionaryObject({NameObject('/Type'):NameObject('/Font'),NameObject('/Subtype'):NameObject('/Type1'),NameObject('/BaseFont'):NameObject('/Helvetica')})
        page[NameObject('/Resources')]=DictionaryObject({NameObject('/Font'):DictionaryObject({NameObject('/F1'):writer._add_object(font)})})
        stream=DecodedStreamObject();stream.set_data(f'BT /F1 12 Tf 20 100 Td (Synthetic page {number}) Tj ET'.encode())
        page[NameObject('/Contents')]=writer._add_object(stream)
    path=tmp_path/'synthetic.pdf'
    writer.write(path)
    pages=_extract_pages(path)
    assert [p.number for p in pages]==[1,2]
    assert 'Synthetic page 1' in pages[0].text and 'Synthetic page 2' in pages[1].text
    assert ConservativeCounter().count('á🙂')==6


@pytest.mark.parametrize('question,strategy', [
    ('Que es una API REST', 'LLM_DIRECTO'),
    ('Requisitos para mantener regularidad de unidad curricular', 'RAG'),
])
def test_auto_http_routes_one_case(question,strategy):
    store,auth,_=memory_auth();_,token=bootstrap_login(auth)
    direct=FakeLLMProvider();calls=[]
    @asynccontextmanager
    async def runtime(config):yield LLMRuntime(direct,MemoryGenerationAdmission(),60)
    app=create_app(repository=store.users,auth_service=auth,llm_config=CONFIG,llm_runtime_factory=runtime)
    class FakeRAG:
        async def execute(self,principal,document,question,**kwargs):
            calls.append(document)
            return RAGResult(status='SIN_EVIDENCIA',answer='Sin evidencia.')
    with TestClient(app) as client:
        app.state.ia_agent.rag=FakeRAG()
        app.state.ia_agent.documents=EmptyCatalog()
        headers={'Authorization':'Bearer '+token}
        doc=str(uuid4())
        response=client.post('/api/v1/ia/respuestas',headers=headers,json={
            'modo':'AUTO','prompt':question,'documento_id':doc})
        assert response.status_code==200 and response.json()['estrategia']==strategy
        assert len(calls)==(1 if strategy=='RAG' else 0)
        assert len(direct.inputs)==(1 if strategy=='LLM_DIRECTO' else 0)
        missing=client.post('/api/v1/ia/respuestas',headers=headers,json={
            'modo':'AUTO','prompt':'Regularidad curricular'})
        assert missing.status_code==200 and missing.json()['estado']=='SIN_EVIDENCIA'


@pytest.mark.parametrize('error,status', [(IARespuestaInvalida(),502),
    (IANoDisponible(),503)])
def test_rag_http_technical_failure_is_not_success(error,status):
    store,auth,_=memory_auth();_,token=bootstrap_login(auth)
    @asynccontextmanager
    async def runtime(config):yield LLMRuntime(FakeLLMProvider(),MemoryGenerationAdmission(),60)
    app=create_app(repository=store.users,auth_service=auth,llm_config=CONFIG,llm_runtime_factory=runtime)
    class Broken:
        async def execute(self,*args,**kwargs):raise error
    with TestClient(app) as client:
        app.state.ia_agent.rag=Broken()
        app.state.ia_agent.documents=EmptyCatalog()
        result=client.post('/api/v1/ia/respuestas',headers={'Authorization':'Bearer '+token},
            json={'modo':'RAG','prompt':'Regularidad','documento_id':str(uuid4())})
        assert result.status_code==status and 'estado' not in result.json()
