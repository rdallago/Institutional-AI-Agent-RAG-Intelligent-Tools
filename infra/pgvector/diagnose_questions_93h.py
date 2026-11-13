"""Dos embeddings de consulta con guardas normales; SQL READ ONLY; nunca Qwen."""
import asyncio
import json
from pathlib import Path
from uuid import uuid4
from sqlalchemy import create_engine,text
from app.application.auth.service import Principal
from app.application.rag.relevance import AcademicRelevance,terms
from app.infrastructure.configuration.database import load_database_config
from app.infrastructure.configuration.llm import LLMConfig,load_memory_guard
from app.infrastructure.rag.postgres import PostgresRAG
from app.infrastructure.rag.ollama import Embeddings
from app.infrastructure.rag.models import LocalModelGate

QUESTIONS=('¿Cuáles son las funciones del Rectorado según el Reglamento Orgánico Marco?',
           '¿Cuáles son los requisitos para acceder al concurso de coordinación de carrera?')

async def main():
    config=load_database_config()
    assert(config.host,config.port,config.database)==('127.0.0.1',5434,'usuarios_dev')
    engine=create_engine(config.url(),hide_parameters=True,connect_args={'connect_timeout':3,
        'options':'-c default_transaction_read_only=on -c statement_timeout=3000'})
    store=PostgresRAG(engine)
    # Cuenta indicada previamente por el responsable, no asumir acceso de cualquier ADMIN.
    rows=store.read('SELECT id FROM usuarios WHERE email=:email AND activo',{'email':'rdallago@gmail.com'})
    assert len(rows)==1
    actor=Principal(usuario_id=rows[0]['id'],sesion_id=uuid4())
    report={'scope':'administrative_read_only_not_http_login','documents':[], 'queries':[]}
    catalog=await store.list_documents(actor)
    inventory=store.read('''SELECT d.id,d.titulo_publico,d.visibilidad,v.estado,v.numero,
        v.ruta_relativa_controlada,v.paginas,
        (SELECT count(*) FROM rag_fragmentos f WHERE f.version_id=v.id) AS chunks,
        (SELECT count(*) FROM rag_embeddings e JOIN rag_fragmentos f ON f.id=e.fragmento_id WHERE f.version_id=v.id) AS embeddings
        FROM rag_documentos d LEFT JOIN rag_versiones v ON v.documento_id=d.id ORDER BY d.id,v.numero''',{})
    for row in inventory:
        report['documents'].append({**dict(row),'id':str(row['id']),
            'accessible':any(str(row['id'])==r['id'] for r in catalog)})
    cfg=LLMConfig(enabled=True,environment='local-development',
        enforce_memory_guard=load_memory_guard(environment='local-development',testing=False))
    embeddings=Embeddings(cfg);lease=LocalModelGate().try_acquire()
    try:
        for entry in catalog:
            scope=await store.require_active(actor,__import__('uuid').UUID(entry['id']))
            hits=store.read('''SELECT identificador_estable AS id,pagina_inicio AS page,texto
                FROM rag_fragmentos WHERE version_id=:version AND
                (texto ~* :pattern) ORDER BY pagina_inicio,offset_inicio''',
                {'version':scope.version_id,'pattern':r'rector|coordinaci[oó6]n|coordinador|concurso'})
            report['text_hits']=[{'id':r['id'],'page':r['page'],'excerpt':r['texto'][:100]} for r in hits]
            for question in QUESTIONS:
                vector=await embeddings.embed_query(question,space=scope.space)
                candidates=await store._search(actor,scope,vector,limit=48)
                policy=AcademicRelevance()
                result={'question':question,'document':entry,'anchors':sorted(terms(policy.focus(question))),
                    'top12':[], 'expanded_accepted':[]}
                for rank,c in enumerate(candidates,1):
                    relevant=bool(policy.select(question,(c.chunk,)))
                    reason='accepted' if c.similarity>=.60 and relevant else ('below_cosine_threshold' if c.similarity<.60 else 'lexical_or_subject_mismatch')
                    item={'rank':rank,'id':c.chunk.id,'page':c.chunk.page,'score':round(c.similarity,6),
                          'reason':reason,'missing_anchors':sorted(terms(policy.focus(question))-terms(c.chunk.text))}
                    if rank<=12:result['top12'].append(item)
                    if reason=='accepted':result['expanded_accepted'].append(item)
                report['queries'].append(result)
        Path('docs/93h-retrieval-diagnostic.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(report,ensure_ascii=True,default=str))
    finally:
        await embeddings.close();lease.release();engine.dispose()

if __name__=='__main__':asyncio.run(main())
