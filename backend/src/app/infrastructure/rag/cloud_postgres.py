"""Coexistencia cloud/Nomic sin mutar las versiones textuales existentes."""
import hashlib
import json
from uuid import UUID
from sqlalchemy import text
from app.application.auth.exceptions import PermisoDenegado
from app.application.ia.exceptions import IARespuestaInvalida, IANoDisponible
from app.application.rag.core import validate_vector
from .postgres import PostgresRAG, ACL


class CloudPostgresRAG(PostgresRAG):
    def __init__(self, engine, config):
        super().__init__(engine)
        self.space, self.identity = config.space, config.identity
        self.space_id = UUID(self.space[:32])

    def read(self, query, params):
        # Reutilizar exactamente SQL de recuperación/ACL/integridad de PostgresRAG.
        # Solo se redirigen las dos tablas del almacenamiento vectorial.
        query = query.replace('public.rag_embeddings ', 'public.rag_cloud_embeddings ')
        query = query.replace('public.rag_espacios_embeddings ', 'public.rag_cloud_espacios ')
        return super().read(query, params)

    async def require_active(self, principal, document_id):
        scope = await super().require_active(principal, document_id)
        import asyncio
        rows = await asyncio.to_thread(self.read, '''SELECT a.espacio_id FROM public.rag_cloud_activos a
            JOIN public.rag_cloud_ingestas i USING(version_id,espacio_id)
            WHERE a.version_id=:v AND a.espacio_id=:s AND i.estado='VALIDADA' ''',
            {'v': scope.version_id, 's': self.space_id})
        if not rows:
            raise IANoDisponible()  # Nunca caer silenciosamente al espacio Nomic.
        return scope

    async def list_documents(self, principal):
        import asyncio
        rows = await asyncio.to_thread(self.read, '''SELECT d.id,d.titulo_publico
            FROM public.rag_documentos d JOIN public.rag_versiones v ON v.id=d.activa_version_id
            JOIN public.usuarios u ON u.id=:actor WHERE v.estado='LISTA' AND '''+ACL+'''
            AND EXISTS(SELECT 1 FROM public.rag_cloud_activos a JOIN public.rag_cloud_ingestas i
              ON i.version_id=a.version_id AND i.espacio_id=a.espacio_id
              WHERE a.version_id=v.id AND a.espacio_id=:space AND i.estado='VALIDADA')
            ORDER BY d.id LIMIT 50''',{'actor':principal.usuario_id,'space':self.space_id})
        return [{'id':str(r['id']),'titulo':r['titulo_publico']} for r in rows]

    async def set_institutional_publication(self, principal, document_id, version_id, *, publish):
        import asyncio
        if type(publish) is not bool:
            raise IARespuestaInvalida()
        await asyncio.to_thread(self._institutional_publication, principal.usuario_id,
                                document_id, version_id, publish)

    def _institutional_publication(self, actor, document, version, publish):
        """Only the active ADMIN owner; sharing grants no ingestion/admin capability."""
        with self.engine.begin() as conn:
            conn.execute(text("SET LOCAL lock_timeout='2s'"))
            conn.execute(text("SET LOCAL statement_timeout='10s'"))
            permitted = conn.execute(text('''SELECT d.id FROM public.rag_documentos d
                JOIN public.usuarios u ON u.id=:actor
                WHERE d.id=:document AND d.propietario_id=u.id AND u.activo AND u.rol='ADMIN'
                FOR UPDATE OF d,u'''),
                {'actor':actor,'document':document}).first()
            if permitted is None:
                raise PermisoDenegado()
            if publish:
                ready = conn.execute(text('''SELECT v.id FROM public.rag_versiones v
                    JOIN public.rag_documentos d ON d.id=v.documento_id
                    JOIN public.rag_cloud_activos a ON a.version_id=v.id
                    JOIN public.rag_cloud_ingestas i ON i.version_id=a.version_id AND i.espacio_id=a.espacio_id
                    WHERE d.id=:document AND v.id=:version AND d.activa_version_id=v.id
                    AND d.archivado_at IS NULL AND v.estado='LISTA'
                    AND a.espacio_id=:space AND i.estado='VALIDADA'
                    FOR SHARE OF v,a,i'''),
                    {'document':document,'version':version,'space':self.space_id}).first()
                if ready is None:
                    raise IARespuestaInvalida()
                conn.execute(text('''INSERT INTO public.rag_publicaciones_institucionales
                    (documento_id,version_id,publicado_por) VALUES(:document,:version,:actor)
                    ON CONFLICT(documento_id) DO UPDATE SET version_id=EXCLUDED.version_id,
                    publicado_por=EXCLUDED.publicado_por,publicado_at=CURRENT_TIMESTAMP,
                    revocado_por=NULL,revocado_at=NULL'''),
                    {'document':document,'version':version,'actor':actor})
                visibility = 'AUTHENTICATED'
            else:
                revoked = conn.execute(text('''UPDATE public.rag_publicaciones_institucionales
                    SET revocado_por=:actor,revocado_at=CURRENT_TIMESTAMP
                    WHERE documento_id=:document AND version_id=:version'''),
                    {'document':document,'version':version,'actor':actor}).rowcount
                if revoked != 1:
                    raise IARespuestaInvalida()
                visibility = 'PRIVATE'
            conn.execute(text('UPDATE public.rag_documentos SET visibilidad=:visibility WHERE id=:document'),
                         {'visibility':visibility,'document':document})

    async def _search(self, principal, scope, vector, *, limit):
        if await self.require_active(principal, scope.document_id) != scope:
            raise PermisoDenegado()
        result = await super()._search(principal, scope, vector, limit=limit)
        if await self.require_active(principal, scope.document_id) != scope:
            raise PermisoDenegado()
        return result

    def stage(self, *args, **kwargs):
        raise RuntimeError('Usar prepare_existing; no extraer ni duplicar fragmentos.')

    def publish(self, *args, **kwargs):
        raise RuntimeError('Usar activate explícitamente; no publicación automática.')

    def _guard(self, conn, actor, version):
        row = conn.execute(text('''SELECT v.documento_id FROM public.rag_versiones v
            JOIN public.rag_documentos d ON d.id=v.documento_id
            JOIN public.usuarios u ON u.id=:actor
            WHERE v.id=:v AND d.activa_version_id=v.id AND v.estado='LISTA'
            AND u.activo AND u.rol='ADMIN' AND d.propietario_id=u.id AND d.archivado_at IS NULL
            FOR UPDATE OF d'''), {'actor': actor, 'v': version}).first()
        if row is None:
            raise PermisoDenegado()

    def prepare_existing(self, actor, version):
        with self.engine.begin() as conn:
            self._guard(conn, actor, version)
            conn.execute(text('''INSERT INTO public.rag_cloud_espacios(id,fingerprint,identidad,dimension)
                VALUES(:s,:fp,:identity,768) ON CONFLICT DO NOTHING'''),
                {'s': self.space_id, 'fp': self.space, 'identity': self.identity})
            existing = conn.execute(text('SELECT identidad FROM public.rag_cloud_espacios WHERE id=:s AND fingerprint=:fp'),
                                    {'s': self.space_id, 'fp': self.space}).scalar_one()
            if existing != self.identity:
                raise IARespuestaInvalida()
            conn.execute(text('''INSERT INTO public.rag_cloud_ingestas(version_id,espacio_id,estado)
                VALUES(:v,:s,'PREPARANDO') ON CONFLICT DO NOTHING'''), {'v': version, 's': self.space_id})

    def missing_cloud(self, version):
        return self.read('''SELECT f.id,f.texto,f.hash_texto,p.texto_extraido,p.hash_texto AS page_hash,
            f.pagina_inicio=f.pagina_fin AND f.texto=substring(p.texto_extraido
            FROM f.offset_inicio+1 FOR f.offset_fin-f.offset_inicio) AS intact FROM public.rag_fragmentos f
            JOIN public.rag_paginas p ON p.version_id=f.version_id AND p.pagina_pdf=f.pagina_inicio
            LEFT JOIN public.rag_cloud_embeddings e ON e.fragmento_id=f.id AND e.espacio_id=:s
            WHERE f.version_id=:v AND e.fragmento_id IS NULL ORDER BY f.ordinal''',
            {'v': version, 's': self.space_id})

    def export_manifest(self, actor, version, document):
        """Lectura autorizada de identidad/integridad, antes de preparar escrituras."""
        from .document_export import DOCUMENT, VERSION, OWNER, SPACE
        if (actor, version, document, self.space) != (OWNER, VERSION, DOCUMENT, SPACE):
            raise PermisoDenegado()
        with self.engine.connect() as conn:
            rows = conn.execute(text('''SELECT f.id,f.texto,f.hash_texto,p.texto_extraido,
                p.hash_texto AS page_hash,f.offset_inicio,f.offset_fin,
                f.pagina_inicio,f.pagina_fin FROM public.rag_documentos d
                JOIN public.rag_versiones v ON v.id=d.activa_version_id AND v.documento_id=d.id
                JOIN public.usuarios u ON u.id=d.propietario_id
                JOIN public.rag_fragmentos f ON f.version_id=v.id
                JOIN public.rag_paginas p ON p.version_id=v.id AND p.pagina_pdf=f.pagina_inicio
                WHERE d.id=:d AND v.id=:v AND u.id=:actor AND u.activo AND u.rol='ADMIN'
                AND v.estado='LISTA' AND d.archivado_at IS NULL ORDER BY f.ordinal'''),
                {'d': document, 'v': version, 'actor': actor}).mappings().all()
        manifest = {}
        for r in rows:
            if (r['pagina_inicio'] != r['pagina_fin'] or r['offset_inicio'] < 0
                    or r['offset_fin'] <= r['offset_inicio']
                    or r['texto_extraido'][r['offset_inicio']:r['offset_fin']] != r['texto']
                    or hashlib.sha256(r['texto'].encode()).hexdigest() != r['hash_texto']
                    or hashlib.sha256(r['texto_extraido'].encode()).hexdigest() != r['page_hash']
                    or r['id'] in manifest):
                raise IARespuestaInvalida()
            manifest[r['id']] = r['hash_texto']
        if len(manifest) != 432:
            raise IARespuestaInvalida()
        return manifest

    def checkpoint_cloud(self, actor, version, fragment, vector):
        validate_vector(vector)
        import math
        if abs(math.hypot(*vector)-1) > .01:
            raise IARespuestaInvalida()
        with self.engine.begin() as conn:
            self._guard(conn, actor, version)
            row = conn.execute(text('''SELECT f.texto,f.hash_texto,p.texto_extraido,p.hash_texto AS page_hash,
                f.texto=substring(p.texto_extraido FROM f.offset_inicio+1 FOR f.offset_fin-f.offset_inicio) AS intact
                FROM public.rag_fragmentos f JOIN public.rag_paginas p
                ON p.version_id=f.version_id AND p.pagina_pdf=f.pagina_inicio
                WHERE f.id=:f AND f.version_id=:v AND f.pagina_inicio=f.pagina_fin'''),
                {'f': fragment, 'v': version}).mappings().one()
            if (not row['intact'] or hashlib.sha256(row['texto'].encode()).hexdigest() != row['hash_texto']
                    or hashlib.sha256(row['texto_extraido'].encode()).hexdigest() != row['page_hash']):
                raise IARespuestaInvalida()
            conn.execute(text('''INSERT INTO public.rag_cloud_embeddings(fragmento_id,espacio_id,embedding,hash_entrada)
                VALUES(:f,:s,CAST(:vec AS public.vector),:hash) ON CONFLICT DO NOTHING'''),
                {'f': fragment, 's': self.space_id, 'vec': json.dumps(vector), 'hash': row['hash_texto']})
            valid = conn.execute(text('''SELECT embedding=CAST(:vec AS public.vector) AND hash_entrada=:hash
                FROM public.rag_cloud_embeddings WHERE fragmento_id=:f AND espacio_id=:s'''),
                {'f': fragment, 's': self.space_id, 'vec': json.dumps(vector), 'hash': row['hash_texto']}).scalar_one()
            if not valid:
                raise IARespuestaInvalida()

    def validate_cloud(self, actor, version, expected=432):
        with self.engine.begin() as conn:
            return self._validate_connection(conn, actor, version, expected)

    def _validate_connection(self, conn, actor, version, expected):
        self._guard(conn, actor, version)
        rows = conn.execute(text('''SELECT f.*,p.texto_extraido,p.hash_texto AS page_hash,e.embedding::text AS vector,e.hash_entrada
            FROM public.rag_fragmentos f JOIN public.rag_paginas p
            ON p.version_id=f.version_id AND p.pagina_pdf=f.pagina_inicio
            LEFT JOIN public.rag_cloud_embeddings e ON e.fragmento_id=f.id AND e.espacio_id=:s
            WHERE f.version_id=:v ORDER BY f.ordinal'''), {'s': self.space_id, 'v': version}).mappings().all()
        if len(rows) != expected:
            raise IARespuestaInvalida()
        for r in rows:
            if (r['vector'] is None or r['pagina_inicio'] != r['pagina_fin']
                    or r['offset_inicio'] < 0 or r['offset_fin'] <= r['offset_inicio']
                    or r['texto'] != r['texto_extraido'][r['offset_inicio']:r['offset_fin']]
                    or hashlib.sha256(r['texto'].encode()).hexdigest() != r['hash_texto']
                    or hashlib.sha256(r['texto_extraido'].encode()).hexdigest() != r['page_hash']
                    or r['hash_entrada'] != r['hash_texto']):
                raise IARespuestaInvalida()
            vector = tuple(json.loads(r['vector']))
            validate_vector(vector)
            import math
            if abs(math.hypot(*vector)-1) > .01:
                raise IARespuestaInvalida()
        conn.execute(text("UPDATE public.rag_cloud_ingestas SET estado='VALIDADA' WHERE version_id=:v AND espacio_id=:s"),
                     {'v': version, 's': self.space_id})
        return len(rows)

    def activate(self, actor, version):
        with self.engine.begin() as conn:
            self._validate_connection(conn, actor, version, 432)
            conn.execute(text('''INSERT INTO public.rag_cloud_activos(version_id,espacio_id)
                VALUES(:v,:s) ON CONFLICT(version_id) DO UPDATE SET espacio_id=EXCLUDED.espacio_id'''),
                {'v': version, 's': self.space_id})
