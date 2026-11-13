"""Diagnostico explicito READ ONLY; dos embeddings de consulta, nunca Qwen ni escrituras."""
import asyncio
import json
from sqlalchemy import text
from app.infrastructure.configuration.database import load_database_config
from app.infrastructure.configuration.llm import LLMConfig, load_memory_guard
from app.infrastructure.persistence.database import build_engine
from app.infrastructure.rag.models import LocalModelGate
from app.infrastructure.rag.ollama import Embeddings, SPACE
from app.application.rag.relevance import AcademicRelevance, terms

QUESTIONS = (
    '\u00bfEn el reglamento acad\u00e9mico de Institutos Superiores, cu\u00e1les son las funciones del Rectorado?',
    'funciones del Rector',
)

async def main():
    config = load_database_config()
    assert (config.host, config.port, config.database) == ('127.0.0.1', 5434, 'usuarios_dev')
    engine = build_engine(config)
    embed = Embeddings(LLMConfig(enabled=True, environment='local-development',
        enforce_memory_guard=load_memory_guard(environment='local-development', testing=False)))
    lease = LocalModelGate().try_acquire()
    try:
        for question in QUESTIONS:
            vector = await embed.embed_query(question, space=SPACE)
            with engine.connect() as conn:
                conn.execute(text('SET TRANSACTION READ ONLY'))
                conn.execute(text("SET LOCAL statement_timeout='3s'"))
                assert conn.execute(text('SELECT current_database()')).scalar_one() == 'usuarios_dev'
                # Inspeccion administrativa del unico documento publicado; replica filtros
                # de integridad/estado/espacio y propietario activo del repositorio.
                rows = conn.execute(text('''SELECT f.identificador_estable AS id,
                    f.pagina_inicio AS page, f.offset_inicio AS start, f.texto AS content,
                    1-(e.embedding <=> CAST(:v AS public.vector)) AS score
                    FROM public.rag_fragmentos f JOIN public.rag_embeddings e ON e.fragmento_id=f.id
                    JOIN public.rag_versiones v ON v.id=f.version_id
                    JOIN public.rag_documentos d ON d.activa_version_id=v.id
                    JOIN public.usuarios u ON u.id=d.propietario_id
                    JOIN public.rag_espacios_embeddings s ON s.id=e.espacio_id
                    JOIN public.rag_paginas p ON p.version_id=v.id AND p.pagina_pdf=f.pagina_inicio
                    WHERE v.estado='LISTA' AND d.archivado_at IS NULL AND u.activo
                    AND s.fingerprint=:space AND s.dimension=768 AND e.dimension=768
                    AND f.pagina_inicio=f.pagina_fin
                    AND f.texto=substring(p.texto_extraido FROM f.offset_inicio+1 FOR f.offset_fin-f.offset_inicio)
                    ORDER BY e.embedding <=> CAST(:v AS public.vector),f.id'''),
                    {'v': json.dumps(vector), 'space': SPACE}).mappings().all()
                print(json.dumps({'question': question, 'eligible': len(rows), 'anchors': sorted(terms(question))}))
                for rank, row in enumerate(rows, 1):
                    if rank <= 12 or (row['page'] in (11,12) and ('Del Rectorado' in row['content'] or 'Funciones del Rector' in row['content'])):
                        accepted = row['score'] >= .60 and bool(tuple(AcademicRelevance().pertinent_units(question,row['content'])))
                        print(json.dumps({'rank':rank, 'id':row['id'], 'page':row['page'],
                            'start':row['start'], 'score':round(row['score'],6), 'accepted':accepted}))
                conn.rollback()
    finally:
        await embed.close()
        lease.release()
        engine.dispose()

if __name__ == '__main__':
    asyncio.run(main())
