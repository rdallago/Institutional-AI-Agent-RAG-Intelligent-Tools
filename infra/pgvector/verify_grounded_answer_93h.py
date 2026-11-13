"""Comprobacion administrativa explicita, READ ONLY, un embedding y una generacion.

No es login ni prueba HTTP. Usa propietario existente del PDF con ACL real.
No persiste preguntas/respuestas y no usa cuentas de prueba.
"""
import asyncio
import hashlib
import json
import logging
from pathlib import Path
from time import monotonic
from uuid import uuid4
from sqlalchemy import create_engine, text
from app.application.auth.service import Principal
from app.application.rag.use_cases import ResponderConDocumento
from app.application.rag.relevance import AcademicRelevance
from app.infrastructure.configuration.database import load_database_config
from app.infrastructure.configuration.llm import LLMConfig, load_memory_guard
from app.infrastructure.rag.postgres import PostgresRAG
from app.infrastructure.rag.ollama import Embeddings, GroundedProvider
from app.infrastructure.rag.models import LocalModelGate
from app.infrastructure.rag.text import ConservativeCounter
from app.infrastructure.llm.admission import MemoryGenerationAdmission
from infra.pgvector.diagnose_questions_93h import QUESTIONS
from app.application.rag.core import resolve_citations

async def main():
    db=load_database_config()
    assert (db.host,db.port,db.database)==('127.0.0.1',5434,'usuarios_dev')
    engine=create_engine(db.url(),hide_parameters=True,connect_args={'connect_timeout':3,
        'options':'-c default_transaction_read_only=on -c statement_timeout=3000'})
    store=PostgresRAG(engine)
    digest=hashlib.sha256(Path('backend/data/documents/reglamento_academico.pdf').read_bytes()).hexdigest()
    with engine.connect() as conn:
        assert conn.execute(text('SHOW transaction_read_only')).scalar_one()=='on'
        rows=conn.execute(text("""SELECT d.id,d.propietario_id FROM public.rag_documentos d
            JOIN public.rag_versiones v ON v.id=d.activa_version_id
            JOIN public.usuarios u ON u.id=d.propietario_id
            WHERE v.sha256=:hash AND v.estado='LISTA' AND u.activo AND d.archivado_at IS NULL"""),{'hash':digest}).all()
        assert len(rows)==1
        document,owner=rows[0]
        conn.rollback()
    # Identidad de propietario para ACL documental; no representa sesion HTTP autenticada.
    principal=Principal(usuario_id=owner,sesion_id=uuid4())
    class DocumentAuthorization:
        async def require_normal(self,p):
            assert p.usuario_id==owner
            await store.require_active(p,document)
    config=LLMConfig(enabled=True,environment='local-development',
        enforce_memory_guard=load_memory_guard(environment='local-development',testing=False))
    embeddings=Embeddings(config)
    actual=GroundedProvider(config)
    policy=AcademicRelevance()
    comparisons=[]
    class Capture:
        async def generate_grounded(self,input):
            print(json.dumps({'generator_sources':[{'id':e.chunk.id,'page':e.chunk.page} for e in input.evidence]}))
            result=await actual.generate_grounded(input)
            diagnostic={'question':input.question,'answer':result.respuesta,
                        'evidence':[{'page':e.chunk.page,'text':e.chunk.text} for e in input.evidence]}
            if result.respuesta!='SIN_EVIDENCIA':
                diagnostic['validation']=policy.explain_answer(input.question,result.respuesta,
                    resolve_citations(result.respuesta,input.evidence))
            comparisons.append(diagnostic)
            validation=diagnostic.get('validation',{})
            print(json.dumps({'finalization':result.finalizacion,
                'supported':validation.get('supported'),
                'claims':len(validation.get('claims',[])),
                'rejected_claims':sum(not c['supported'] for c in validation.get('claims',[]))}))
            return result
    case=ResponderConDocumento(authorizer=DocumentAuthorization(),documents=store,vectors=store,
        embeddings=embeddings,provider=Capture(),counter=ConservativeCounter(),gate=LocalModelGate(),
        admission=MemoryGenerationAdmission(),threshold=.60,relevance=policy,recovery=store.recover)
    try:
        for index,question in enumerate(QUESTIONS,1):
            start=monotonic()
            try:
                result=await case.execute(principal,document,question)
                print(json.dumps({'test':index,'status':result.status,
                    'pages':[e.chunk.page for e in result.citations],'seconds':round(monotonic()-start,3)}))
            except Exception as error:
                print(json.dumps({'test':index,'error_type':type(error).__name__,
                    'seconds':round(monotonic()-start,3)}))
        # Solo con destino solicitado explicitamente: nunca logs de la aplicacion.
        import os
        destination=os.environ.get('RAG_PRIVATE_DIAGNOSTIC_PATH')
        if destination:
            with Path(destination).open('x',encoding='utf-8') as output:
                json.dump(comparisons,output,ensure_ascii=False,indent=2)
    finally:
        await embeddings.close()
        await actual.aclose()
        engine.dispose()

if __name__=='__main__':
    logging.basicConfig(level=logging.WARNING)
    asyncio.run(main())
