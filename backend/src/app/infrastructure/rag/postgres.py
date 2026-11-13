"""SQL parametrizado, transacciones cortas y ACL antes de top-k."""
import asyncio
import hashlib
import json
import re
from uuid import UUID, uuid4, uuid5, NAMESPACE_URL

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.application.auth.exceptions import PermisoDenegado
from app.application.ia.exceptions import IANoDisponible, IARespuestaInvalida
from app.application.rag.core import prepare_pages, ChunkPolicy, validate_vector
from app.application.rag.dto import Scope, Chunk, Candidate
from app.infrastructure.rag.ollama import SPACE, MODEL, DIGEST
from app.infrastructure.rag.text import ConservativeCounter


SPACE_ID=UUID(SPACE[:32])
ACL="""u.activo AND d.archivado_at IS NULL AND
 (d.propietario_id=:actor OR (d.visibilidad='AUTHENTICATED' AND EXISTS
 (SELECT 1 FROM public.rag_publicaciones_institucionales pub
 WHERE pub.documento_id=d.id AND pub.version_id=v.id AND pub.revocado_at IS NULL)) OR EXISTS
 (SELECT 1 FROM public.rag_documento_permisos a WHERE a.documento_id=d.id
 AND a.usuario_id=:actor AND a.puede_leer))"""


def verified_cover_titles(content):
    titles=[]
    for match in re.finditer(r'\bREGLAMENTO\s+[A-ZÁÉÍÓÚÜÑ]+(?:\s+[A-ZÁÉÍÓÚÜÑ]+){1,3}',content):
        title=re.split(r'\s+(?:PARA|DE|DEL)\b',match.group(),maxsplit=1)[0]
        titles.append(' '.join(title.split()))
    return tuple(dict.fromkeys(titles))


class PostgresRAG:
    def __init__(self,engine):
        self.engine=engine
        self.space=SPACE

    def read(self,query,params):
        try:
            with self.engine.connect() as conn:
                return conn.execute(text(query),params).mappings().all()
        except SQLAlchemyError:raise IANoDisponible() from None

    async def require_active(self,principal,document_id):
        rows=await asyncio.to_thread(self.read,"""SELECT d.id,v.id AS version
          FROM public.rag_documentos d JOIN public.rag_versiones v ON v.id=d.activa_version_id
          JOIN public.usuarios u ON u.id=:actor
          WHERE d.id=:document AND v.estado='LISTA' AND """+ACL,
          {'actor':principal.usuario_id,'document':document_id})
        if not rows:raise PermisoDenegado()
        return Scope(document_id=document_id,version_id=rows[0]['version'],space=self.space)

    async def list_documents(self,principal):
        rows=await asyncio.to_thread(self.read,"""SELECT d.id,d.titulo_publico FROM public.rag_documentos d
         JOIN public.rag_versiones v ON v.id=d.activa_version_id JOIN public.usuarios u ON u.id=:actor
         WHERE v.estado='LISTA' AND """+ACL+' ORDER BY d.id LIMIT 50',{'actor':principal.usuario_id})
        return [{'id':str(r['id']),'titulo':r['titulo_publico']} for r in rows]

    async def list_sources(self,principal):
        """Titulos internos comprobados en portada; no cambiar el contrato publico."""
        catalog=await self.list_documents(principal)
        for row in catalog:
            scope=await self.require_active(principal,UUID(row['id']))
            pages=await asyncio.to_thread(self.read,
                'SELECT texto_extraido FROM rag_paginas WHERE version_id=:v AND pagina_pdf<=3 ORDER BY pagina_pdf',
                {'v':scope.version_id})
            aliases=[]
            for page in pages:
                aliases.extend(verified_cover_titles(page['texto_extraido']))
            if await self.require_active(principal,UUID(row['id'])) != scope:
                raise PermisoDenegado()
            row['aliases']=list(dict.fromkeys(aliases))
        return catalog

    async def search(self,principal,scope,vector,*,limit):
        if not 1<=limit<=12:raise IARespuestaInvalida()
        return await self._search(principal,scope,vector,limit=limit)

    async def explicit_article(self, principal, scope, number):
        return (await self.resolve_article(principal, scope, number)).chunks

    async def resolve_article(self, principal, scope, number, question=''):
        return await self._resolve_verified(principal, scope, number, question)

    async def resolve_functions(self, principal, scope, question):
        return await self._resolve_verified(principal, scope, 1, question, functions=True)

    async def _resolve_verified(self, principal, scope, number, question, *, functions=False):
        from app.application.rag.articles import resolve_article, ArticleResolution
        if type(number) is not int or number < 1 or scope.space != self.space:
            raise IARespuestaInvalida()
        if await self.require_active(principal, scope.document_id) != scope:
            raise PermisoDenegado()
        rows = await asyncio.to_thread(self.read, '''SELECT p.pagina_pdf,p.texto_extraido,p.hash_texto,v.paginas AS total_pages
          FROM public.rag_paginas p JOIN public.rag_versiones v ON v.id=p.version_id
          JOIN public.rag_documentos d ON d.id=v.documento_id JOIN public.usuarios u ON u.id=:actor
          WHERE d.id=:document AND v.id=:version AND d.activa_version_id=v.id
          AND v.estado='LISTA' AND ''' + ACL + ' ORDER BY p.pagina_pdf LIMIT 101',
          {'actor':principal.usuario_id,'document':scope.document_id,'version':scope.version_id})
        if len(rows)>100:
            return ArticleResolution(reason='document_bound')
        for row in rows:
            if hashlib.sha256(row['texto_extraido'].encode()).hexdigest()!=row['hash_texto']:
                raise IARespuestaInvalida()
        complete=bool(rows and rows[0]['pagina_pdf']==1 and
            all(r.get('total_pages')==len(rows) for r in rows) and rows[-1]['pagina_pdf']==len(rows))
        pages=tuple((r['pagina_pdf'],r['texto_extraido']) for r in rows)
        if functions:
            from app.application.rag.functions import resolve_functions, bind_functions
            result=bind_functions(resolve_functions(pages,scope,question,complete_document=complete))
        else:
            result=resolve_article(pages,scope,number,question,complete_document=complete)
        if await self.require_active(principal,scope.document_id)!=scope:
            raise PermisoDenegado()
        return result

    async def recover(self,principal,scope,vector):
        """Ventana ampliada unica; mismos filtros ACL/integridad/espacio."""
        return await self._search(principal,scope,vector,limit=48)

    async def article_context(self, principal, scope, seeds):
        """Lectura acotada de chunks contiguos; sin acceso implicito por ADMIN."""
        from app.application.rag.continuity import complete_article, requirement_section
        if scope.space != self.space:
            raise IARespuestaInvalida()
        if any(seed.scope != scope for seed in seeds):
            raise IARespuestaInvalida()
        if len(seeds)>3:
            return ()
        if await self.require_active(principal, scope.document_id) != scope:
            raise PermisoDenegado()
        result = {}
        for seed in seeds:
            rows = await asyncio.to_thread(self.read, """SELECT f.*,length(p.texto_extraido) AS page_length,
             f.pagina_inicio=f.pagina_fin AND f.texto=substring(p.texto_extraido
                FROM f.offset_inicio+1 FOR f.offset_fin-f.offset_inicio) AS intact
             FROM public.rag_fragmentos f JOIN public.rag_versiones v ON v.id=f.version_id
             JOIN public.rag_documentos d ON d.id=v.documento_id
             JOIN public.rag_paginas p ON p.version_id=v.id AND p.pagina_pdf=f.pagina_inicio
             JOIN public.usuarios u ON u.id=:actor
             WHERE d.id=:document AND v.id=:version AND d.activa_version_id=v.id
             AND v.estado='LISTA' AND f.pagina_inicio BETWEEN :first AND :last AND """ + ACL +
             " ORDER BY f.pagina_inicio,f.offset_inicio,f.identificador_estable LIMIT 65",
             {'actor':principal.usuario_id,'document':scope.document_id,'version':scope.version_id,
                'first':max(1,seed.page-2),'last':seed.page+2})
            if len(rows)>64:
                return ()
            if any(not row['intact'] for row in rows):
                raise IARespuestaInvalida()
            chunks = tuple((Chunk(id=r['identificador_estable'],scope=scope,page=r['pagina_inicio'],
                start=r['offset_inicio'],end=r['offset_fin'],text=r['texto'],section=r['titulo_seccion'] or ''),
                r['page_length']) for r in rows)
            expanded = complete_article(seed, chunks)
            if not expanded:
                return ()
            expanded = requirement_section(seed, expanded) or expanded
            for chunk in expanded:
                result[(chunk.page,chunk.start,chunk.end)] = chunk
        if await self.require_active(principal, scope.document_id) != scope:
            raise PermisoDenegado()
        return tuple(result[key] for key in sorted(result))

    async def _search(self,principal,scope,vector,*,limit):
        validate_vector(vector)
        if scope.space!=self.space or not 1<=limit<=48:raise IARespuestaInvalida()
        rows=await asyncio.to_thread(self.read,"""SELECT f.*,v.documento_id,
         greatest(-1.0,least(1.0,1-(e.embedding <=> CAST(:vector AS public.vector)))) AS similarity
         FROM public.rag_embeddings e JOIN public.rag_fragmentos f ON f.id=e.fragmento_id
         JOIN public.rag_versiones v ON v.id=f.version_id
         JOIN public.rag_documentos d ON d.id=v.documento_id
         JOIN public.rag_espacios_embeddings s ON s.id=e.espacio_id
         JOIN public.rag_paginas p ON p.version_id=v.id AND p.pagina_pdf=f.pagina_inicio
         JOIN public.usuarios u ON u.id=:actor
         WHERE d.id=:document AND v.id=:version AND d.activa_version_id=v.id AND v.estado='LISTA'
         AND s.fingerprint=:space AND s.dimension=768 AND e.dimension=768
         AND f.pagina_inicio=f.pagina_fin AND f.texto=substring(p.texto_extraido FROM f.offset_inicio+1 FOR f.offset_fin-f.offset_inicio)
         AND """+ACL+" ORDER BY e.embedding <=> CAST(:vector AS public.vector),f.id LIMIT :limit",
         {'vector':json.dumps(vector),'document':scope.document_id,'version':scope.version_id,
          'actor':principal.usuario_id,'space':self.space,'limit':limit})
        return tuple(Candidate(chunk=Chunk(id=r['identificador_estable'],scope=scope,page=r['pagina_inicio'],
            start=r['offset_inicio'],end=r['offset_fin'],text=r['texto'],section=r['titulo_seccion'] or '',
            ordinal=r.get('ordinal')),
            similarity=float(r['similarity'])) for r in rows)

    def stage(self,owner,pages,file_hash,size,*,extraction_revision=None):
        """Solo CLI administrativo explicito; no se invoca desde HTTP."""
        document=uuid5(owner,'reglamento_academico.pdf')
        from .article24_revision import pipeline_identity, verify_corrected_pages
        pipeline, extractor = pipeline_identity(extraction_revision)
        if extraction_revision is not None:
            verify_corrected_pages(pages,file_hash)
        version=uuid5(document,file_hash+pipeline)
        scope=Scope(document_id=document,version_id=version,space=SPACE)
        key,chunks=prepare_pages(pages,scope,ConservativeCounter(),ChunkPolicy())
        with self.engine.begin() as conn:
            permitted=conn.execute(text("SELECT id FROM public.usuarios WHERE id=:owner AND activo AND rol='ADMIN'"),{'owner':owner}).first()
            if not permitted:raise PermisoDenegado()
            conn.execute(text("""INSERT INTO public.rag_documentos(id,clave,titulo_publico,propietario_id)
             VALUES (:id,'reglamento-academico','Reglamento académico',:owner) ON CONFLICT DO NOTHING"""),{'id':document,'owner':owner})
            conn.execute(text('SELECT id FROM public.rag_documentos WHERE id=:id FOR UPDATE'),{'id':document})
            conn.execute(text("""INSERT INTO public.rag_espacios_embeddings(id,modelo_tag,modelo_digest,normalizacion,
             prefijo_documento,prefijo_consulta,tokenizador_version,fingerprint) VALUES (:id,:model,:digest,
             'ollama-unit-v1','search_document: ','search_query: ','utf8-upper-bound-v1',:fp) ON CONFLICT DO NOTHING"""),
             {'id':SPACE_ID,'model':MODEL,'digest':DIGEST,'fp':SPACE})
            conn.execute(text("""INSERT INTO public.rag_versiones(id,documento_id,numero,sha256,ruta_relativa_controlada,
             bytes,paginas,extractor_version,pipeline_fingerprint) SELECT :v,:d,
             coalesce((SELECT max(numero) FROM public.rag_versiones WHERE documento_id=:d),0)+1,
             :hash,'reglamento_academico.pdf',:bytes,:pages,:extractor,:pipeline ON CONFLICT DO NOTHING"""),
             {'v':version,'d':document,'hash':file_hash,'bytes':size,'pages':len(pages),'pipeline':pipeline,
              'extractor':extractor})
            for page in pages:
                conn.execute(text("""INSERT INTO public.rag_paginas(version_id,pagina_pdf,texto_extraido,hash_texto)
                 VALUES (:v,:p,:t,:h) ON CONFLICT DO NOTHING"""),{'v':version,'p':page.number,'t':page.text,'h':hashlib.sha256(page.text.encode()).hexdigest()})
            for ordinal,c in enumerate(chunks,1):
                fragment=uuid5(version,c.id)
                conn.execute(text("""INSERT INTO public.rag_fragmentos(id,version_id,identificador_estable,ordinal,
                 pagina_inicio,pagina_fin,offset_inicio,offset_fin,texto,hash_texto,titulo_seccion,tokens_medidos,pipeline_fingerprint)
                 VALUES (:id,:v,:stable,:ordinal,:p,:p,:start,:end,:t,:h,:section,:tokens,:fp) ON CONFLICT DO NOTHING"""),
                 {'id':fragment,'v':version,'stable':c.id,'ordinal':ordinal,'p':c.page,'start':c.start,'end':c.end,
                  't':c.text,'h':hashlib.sha256(c.text.encode()).hexdigest(),'section':c.section,'tokens':len(c.text.encode()),'fp':pipeline})
                conn.execute(text("""INSERT INTO public.rag_fragmento_paginas(fragmento_id,pagina_pdf,version_id,offset_inicio,offset_fin)
                 VALUES (:id,:p,:v,:start,:end) ON CONFLICT DO NOTHING"""),{'id':fragment,'p':c.page,'v':version,'start':c.start,'end':c.end})
            conn.execute(text("""INSERT INTO public.rag_ingestas(id,version_id,espacio_id,estado)
             VALUES (:id,:v,:s,'PREPARANDO') ON CONFLICT DO NOTHING"""),{'id':uuid5(version,SPACE),'v':version,'s':SPACE_ID})
        return scope,chunks

    def missing(self,scope):
        return self.read("""SELECT f.id,f.texto FROM public.rag_fragmentos f LEFT JOIN public.rag_embeddings e
         ON e.fragmento_id=f.id AND e.espacio_id=:s WHERE f.version_id=:v AND e.fragmento_id IS NULL ORDER BY f.ordinal""",
         {'v':scope.version_id,'s':SPACE_ID})

    def checkpoint(self,scope,fragment,vector):
        validate_vector(vector)
        with self.engine.begin() as conn:
            conn.execute(text("""INSERT INTO public.rag_embeddings(fragmento_id,espacio_id,embedding,hash_entrada)
             SELECT id,:s,CAST(:vector AS public.vector),hash_texto FROM public.rag_fragmentos
             WHERE id=:id AND version_id=:v ON CONFLICT DO NOTHING"""),
             {'id':fragment,'v':scope.version_id,'s':SPACE_ID,'vector':json.dumps(vector)})
            valid=conn.execute(text("""SELECT e.embedding=CAST(:vector AS public.vector)
             AND e.hash_entrada=f.hash_texto FROM public.rag_embeddings e JOIN public.rag_fragmentos f
             ON f.id=e.fragmento_id WHERE f.id=:id AND f.version_id=:v AND e.espacio_id=:s"""),
             {'id':fragment,'v':scope.version_id,'s':SPACE_ID,'vector':json.dumps(vector)}).scalar_one_or_none()
            if valid is not True:raise IARespuestaInvalida()
            conn.execute(text("""UPDATE public.rag_ingestas SET estado='EMBEBIENDO',
             fragmentos_completos=(SELECT count(*) FROM public.rag_embeddings e JOIN public.rag_fragmentos f
             ON f.id=e.fragmento_id WHERE f.version_id=:v AND e.espacio_id=:s),actualizado_at=now()
             WHERE version_id=:v AND espacio_id=:s"""),{'v':scope.version_id,'s':SPACE_ID})

    def publish(self,scope,expected):
        with self.engine.begin() as conn:
            conn.execute(text('SELECT id FROM public.rag_documentos WHERE id=:d FOR UPDATE'),{'d':scope.document_id})
            count=conn.execute(text("""SELECT count(*) FROM public.rag_fragmentos f JOIN public.rag_embeddings e
             ON e.fragmento_id=f.id AND e.espacio_id=:s JOIN public.rag_paginas p
             ON p.version_id=f.version_id AND p.pagina_pdf=f.pagina_inicio
             WHERE f.version_id=:v AND f.texto=substring(p.texto_extraido FROM f.offset_inicio+1 FOR f.offset_fin-f.offset_inicio)
             AND vector_dims(e.embedding)=768 AND vector_norm(e.embedding)>0"""),{'v':scope.version_id,'s':SPACE_ID}).scalar_one()
            total=conn.execute(text('SELECT count(*) FROM public.rag_fragmentos WHERE version_id=:v'),{'v':scope.version_id}).scalar_one()
            if count!=expected or total!=expected or expected<1:raise IARespuestaInvalida()
            pages_valid=conn.execute(text("""SELECT v.paginas=(SELECT count(*) FROM public.rag_paginas p WHERE p.version_id=v.id)
             AND u.activo FROM public.rag_versiones v JOIN public.rag_documentos d ON d.id=v.documento_id
             JOIN public.usuarios u ON u.id=d.propietario_id WHERE v.id=:v AND d.id=:d"""),
             {'v':scope.version_id,'d':scope.document_id}).scalar_one()
            if pages_valid is not True:raise IARespuestaInvalida()
            conn.execute(text("UPDATE public.rag_versiones SET estado='LISTA',publicado_at=coalesce(publicado_at,now()) WHERE id=:v"),{'v':scope.version_id})
            conn.execute(text('UPDATE public.rag_documentos SET activa_version_id=:v WHERE id=:d'),{'v':scope.version_id,'d':scope.document_id})
            conn.execute(text("UPDATE public.rag_ingestas SET estado='LISTA',actualizado_at=now() WHERE version_id=:v AND espacio_id=:s"),{'v':scope.version_id,'s':SPACE_ID})
