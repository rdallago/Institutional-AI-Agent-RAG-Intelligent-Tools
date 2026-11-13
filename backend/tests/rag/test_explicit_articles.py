import asyncio,hashlib
from uuid import uuid4
import pytest
from app.infrastructure.rag.postgres import PostgresRAG
from app.application.rag.dto import Scope
from app.application.rag.continuity import requested_article
from app.application.auth.exceptions import PermisoDenegado

@pytest.mark.parametrize('word',['Artículo','ARTÍCULO','Art.','articulo'])
@pytest.mark.parametrize('number',[24,52])
def test_exact_article(word,number):
 scope=Scope(document_id=uuid4(),version_id=uuid4(),space='test')
 store=PostgresRAG(None);store.space='test'
 async def active(*args):return scope
 store.require_active=active
 content=f'Artículo 2. Otro.\n{word} {number}. Regla sintética.\nArtículo 124. Otra regla.'
 # Fragmentación original no afecta los slices de página autorizados.
 def read(sql,params):
  assert params['document']==scope.document_id and params['version']==scope.version_id
  assert 'propietario_id=:actor' in sql
  return [{'pagina_pdf':58,'texto_extraido':content,'hash_texto':hashlib.sha256(content.encode()).hexdigest()}]
 store.read=read
 chunks=asyncio.run(store.explicit_article(type('P',(),{'usuario_id':uuid4()})(),scope,number))
 assert len(chunks)==1 and chunks[0].page==58 and 'Regla sintética' in chunks[0].text
 assert 'Otra regla' not in chunks[0].text and chunks[0].scope==scope
 assert requested_article(f'¿Qué establece el {word} {number}?')==number

@pytest.mark.parametrize('kind',['missing','denied','version'])
def test_unavailable(kind):
 scope=Scope(document_id=uuid4(),version_id=uuid4(),space='test')
 store=PostgresRAG(None);store.space='test'
 async def active(*args):
  if kind=='denied':raise PermisoDenegado()
  if kind=='version':return Scope(document_id=scope.document_id,version_id=uuid4(),space='test')
  return scope
 store.require_active=active
 store.read=lambda *args:[]
 if kind=='missing':assert asyncio.run(store.explicit_article(type('P',(),{'usuario_id':uuid4()})(),scope,24))==()
 else:
  with pytest.raises(PermisoDenegado):asyncio.run(store.explicit_article(None,scope,24))

def test_general_and_multiple_refs():
 assert requested_article('Funciones del Rectorado') is None
 assert requested_article('Artículo 24 y Art. 52') is None


def test_complete_article_across_pages():
 from app.application.rag.continuity import complete_article
 from app.application.rag.dto import Chunk
 scope=Scope(document_id=uuid4(),version_id=uuid4(),space='test')
 first='Articulo 24. Inicio del cuerpo.'
 second='Continuacion del cuerpo.\nArticulo 25. No incluir.'
 a=Chunk(id='a',scope=scope,page=58,start=0,end=len(first),text=first,section='')
 b=Chunk(id='b',scope=scope,page=59,start=0,end=len(second),text=second,section='')
 result=complete_article(a,((a,len(first)),(b,len(second))))
 assert [r.page for r in result]==[58,59]
 assert 'No incluir' not in ''.join(r.text for r in result)


def test_use_case_exact_article_without_embedding_or_semantic_search():
 from tests.rag.test_core import setup
 from dataclasses import replace
 from app.application.ia.dto import GeneracionSalida
 p,s,chunks,documents,provider,gate,vectors,embeddings,auth,case=setup()
 content='Articulo 24. La asistencia es obligatoria.\n'
 chunk=replace(chunks[0],text=content,end=chunks[0].start+len(content))
 async def exact(principal,scope,number):
  assert number==24 and scope==s
  return (chunk,)
 vectors.explicit_article=exact
 provider.output=GeneracionSalida(respuesta='La asistencia es obligatoria [F1].',finalizacion='completa')
 result=asyncio.run(case.execute(p,s.document_id,'?Qu? establece el articulo 24?'))
 assert result.status=='FUNDAMENTADA' and result.citations[0].chunk.page==chunk.page
 assert embeddings.calls==0


def test_duplicate_number_and_unclosed_article_abstain():
 scope=Scope(document_id=uuid4(),version_id=uuid4(),space='test')
 store=PostgresRAG(None);store.space='test'
 async def active(*args):return scope
 store.require_active=active
 principal=type('P',(),{'usuario_id':uuid4()})()
 for content in ('Articulo 24. Primero.\nArticulo 24. Segundo.\nArticulo 25. Otro.', 'Articulo 24. Sin limite demostrado.'):
  store.read=lambda *args:[{'pagina_pdf':58,'texto_extraido':content,'hash_texto':hashlib.sha256(content.encode()).hexdigest()}]
  assert asyncio.run(store.explicit_article(principal,scope,24))==()
