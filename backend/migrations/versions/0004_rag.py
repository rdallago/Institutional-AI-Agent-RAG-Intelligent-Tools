"""Esquema documental RAG; vector se instala administrativamente por separado.

Revision ID: 0004_rag
Revises: 0003
"""
from alembic import op
import sqlalchemy as sa

revision = '0004_rag'
down_revision = '0003'
branch_labels = None
depends_on = None


DDL = (
    """CREATE TABLE public.rag_documentos (
      id uuid PRIMARY KEY,
      clave varchar(160) NOT NULL CHECK (length(btrim(clave)) BETWEEN 1 AND 160),
      titulo_publico varchar(300) NOT NULL CHECK (length(btrim(titulo_publico)) BETWEEN 1 AND 300),
      propietario_id uuid NOT NULL REFERENCES public.usuarios(id),
      visibilidad varchar(16) NOT NULL DEFAULT 'PRIVATE'
        CHECK (visibilidad IN ('PRIVATE','AUTHENTICATED')),
      activa_version_id uuid,
      creado_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
      archivado_at timestamptz,
      UNIQUE(propietario_id, clave)
    )""",
    """CREATE TABLE public.rag_documento_permisos (
      documento_id uuid NOT NULL REFERENCES public.rag_documentos(id),
      usuario_id uuid NOT NULL REFERENCES public.usuarios(id),
      puede_leer boolean NOT NULL DEFAULT false,
      puede_ingestar boolean NOT NULL DEFAULT false,
      concedido_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
      PRIMARY KEY(documento_id,usuario_id),
      CHECK (NOT puede_ingestar OR puede_leer)
    )""",
    """CREATE TABLE public.rag_versiones (
      id uuid PRIMARY KEY,
      documento_id uuid NOT NULL REFERENCES public.rag_documentos(id),
      numero integer NOT NULL CHECK(numero>=1),
      sha256 varchar(64) NOT NULL CHECK(sha256 ~ '^[0-9a-f]{64}$'),
      ruta_relativa_controlada varchar(500) NOT NULL
        CHECK (length(ruta_relativa_controlada)>0 AND ruta_relativa_controlada !~ '(^/|^[A-Za-z]:|(^|/)\\.\\.(/|$))'
          AND position(chr(92) in ruta_relativa_controlada)=0),
      bytes bigint NOT NULL CHECK(bytes>0),
      paginas integer NOT NULL CHECK(paginas>=1),
      fecha_normativa date,
      extractor_version varchar(160) NOT NULL CHECK(length(extractor_version)>0),
      pipeline_fingerprint varchar(64) NOT NULL CHECK(pipeline_fingerprint ~ '^[0-9a-f]{64}$'),
      estado varchar(16) NOT NULL DEFAULT 'PREPARANDO'
        CHECK(estado IN ('PREPARANDO','LISTA','FALLIDA','RETIRADA')),
      creado_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
      publicado_at timestamptz,
      UNIQUE(documento_id,numero), UNIQUE(documento_id,sha256,pipeline_fingerprint),
      UNIQUE(documento_id,id), CHECK(estado<>'LISTA' OR publicado_at IS NOT NULL)
    )""",
    """ALTER TABLE public.rag_documentos ADD CONSTRAINT fk_rag_version_activa
       FOREIGN KEY(id,activa_version_id) REFERENCES public.rag_versiones(documento_id,id)
       DEFERRABLE INITIALLY IMMEDIATE""",
    """CREATE TABLE public.rag_paginas (
      version_id uuid NOT NULL REFERENCES public.rag_versiones(id),
      pagina_pdf integer NOT NULL CHECK(pagina_pdf>=1),
      etiqueta_impresa varchar(80),
      texto_extraido text NOT NULL,
      hash_texto varchar(64) NOT NULL CHECK(hash_texto ~ '^[0-9a-f]{64}$'),
      PRIMARY KEY(version_id,pagina_pdf)
    )""",
    """CREATE TABLE public.rag_fragmentos (
      id uuid PRIMARY KEY,
      version_id uuid NOT NULL REFERENCES public.rag_versiones(id),
      identificador_estable varchar(64) NOT NULL CHECK(identificador_estable ~ '^[0-9a-f]{64}$'),
      ordinal integer NOT NULL CHECK(ordinal>=1),
      pagina_inicio integer NOT NULL CHECK(pagina_inicio>=1),
      pagina_fin integer NOT NULL CHECK(pagina_fin>=pagina_inicio),
      offset_inicio integer NOT NULL CHECK(offset_inicio>=0),
      offset_fin integer NOT NULL CHECK(offset_fin>offset_inicio),
      texto text NOT NULL CHECK(length(btrim(texto))>0),
      hash_texto varchar(64) NOT NULL CHECK(hash_texto ~ '^[0-9a-f]{64}$'),
      titulo_seccion varchar(300), articulo varchar(100),
      tokens_medidos integer NOT NULL CHECK(tokens_medidos BETWEEN 1 AND 400),
      pipeline_fingerprint varchar(64) NOT NULL CHECK(pipeline_fingerprint ~ '^[0-9a-f]{64}$'),
      UNIQUE(version_id,ordinal), UNIQUE(version_id,identificador_estable), UNIQUE(id,version_id),
      FOREIGN KEY(version_id,pagina_inicio) REFERENCES public.rag_paginas(version_id,pagina_pdf),
      FOREIGN KEY(version_id,pagina_fin) REFERENCES public.rag_paginas(version_id,pagina_pdf),
      CHECK(pagina_inicio<>pagina_fin OR offset_fin-offset_inicio=length(texto))
    )""",
    """CREATE TABLE public.rag_fragmento_paginas (
      fragmento_id uuid NOT NULL,
      pagina_pdf integer NOT NULL,
      version_id uuid NOT NULL,
      offset_inicio integer NOT NULL CHECK(offset_inicio>=0),
      offset_fin integer NOT NULL CHECK(offset_fin>offset_inicio),
      PRIMARY KEY(fragmento_id,pagina_pdf),
      FOREIGN KEY(fragmento_id,version_id) REFERENCES public.rag_fragmentos(id,version_id),
      FOREIGN KEY(version_id,pagina_pdf) REFERENCES public.rag_paginas(version_id,pagina_pdf)
    )""",
    """CREATE TABLE public.rag_espacios_embeddings (
      id uuid PRIMARY KEY,
      modelo_tag varchar(100) NOT NULL CHECK(modelo_tag='nomic-embed-text'),
      modelo_digest varchar(64) NOT NULL CHECK(modelo_digest ~ '^[0-9a-f]{64}$'),
      dimension integer NOT NULL DEFAULT 768 CHECK(dimension=768),
      metrica varchar(10) NOT NULL DEFAULT 'coseno' CHECK(metrica='coseno'),
      normalizacion varchar(160) NOT NULL CHECK(length(normalizacion)>0),
      prefijo_documento varchar(80) NOT NULL CHECK(prefijo_documento='search_document: '),
      prefijo_consulta varchar(80) NOT NULL CHECK(prefijo_consulta='search_query: '),
      tokenizador_version varchar(160) NOT NULL CHECK(length(tokenizador_version)>0),
      fingerprint varchar(64) NOT NULL UNIQUE CHECK(fingerprint ~ '^[0-9a-f]{64}$'),
      creado_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
      UNIQUE(id,dimension),
      UNIQUE(modelo_tag,modelo_digest,dimension,metrica,normalizacion,prefijo_documento,prefijo_consulta,tokenizador_version)
    )""",
    """CREATE TABLE public.rag_embeddings (
      fragmento_id uuid NOT NULL REFERENCES public.rag_fragmentos(id),
      espacio_id uuid NOT NULL,
      dimension integer NOT NULL DEFAULT 768 CHECK(dimension=768),
      embedding public.vector(768) NOT NULL CHECK(public.vector_norm(embedding)>0),
      hash_entrada varchar(64) NOT NULL CHECK(hash_entrada ~ '^[0-9a-f]{64}$'),
      creado_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
      PRIMARY KEY(fragmento_id,espacio_id),
      FOREIGN KEY(espacio_id,dimension) REFERENCES public.rag_espacios_embeddings(id,dimension)
    )""",
    """CREATE TABLE public.rag_ingestas (
      id uuid PRIMARY KEY,
      version_id uuid NOT NULL REFERENCES public.rag_versiones(id),
      espacio_id uuid NOT NULL REFERENCES public.rag_espacios_embeddings(id),
      estado varchar(16) NOT NULL DEFAULT 'PREPARANDO'
        CHECK(estado IN ('PREPARANDO','EMBEBIENDO','LISTA','FALLIDA','CANCELADA')),
      fragmentos_completos integer NOT NULL DEFAULT 0 CHECK(fragmentos_completos>=0),
      intento integer NOT NULL DEFAULT 1 CHECK(intento>=1),
      lease_until timestamptz,
      error_codigo varchar(32) CHECK(error_codigo IN ('EXTRACCION_INVALIDA','EMBEDDING_INVALIDO','PROVEEDOR_NO_DISPONIBLE','TIEMPO_AGOTADO','INTEGRIDAD_INVALIDA')),
      creado_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
      actualizado_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
    )""",
    'CREATE INDEX ix_rag_permisos_usuario ON public.rag_documento_permisos(usuario_id,documento_id)',
    'CREATE INDEX ix_rag_documentos_propietario ON public.rag_documentos(propietario_id)',
    'CREATE INDEX ix_rag_versiones_estado ON public.rag_versiones(documento_id,estado)',
    'CREATE INDEX ix_rag_fragmentos_version ON public.rag_fragmentos(version_id,pagina_inicio)',
    'CREATE INDEX ix_rag_embeddings_espacio ON public.rag_embeddings(espacio_id,fragmento_id)',
    "CREATE UNIQUE INDEX uq_rag_ingesta_activa ON public.rag_ingestas(version_id,espacio_id) WHERE estado IN ('PREPARANDO','EMBEBIENDO')",
)


def upgrade():
    bind = op.get_bind()
    if bind.execute(sa.text("SELECT extversion FROM pg_extension WHERE extname='vector' AND extnamespace='public'::regnamespace")).scalar_one_or_none() != '0.8.2':
        raise RuntimeError('Se requiere vector 0.8.2 administrado en public.')
    for statement in DDL:
        op.execute(sa.text(statement))


def downgrade():
    # Destructivo para documentos: no se ejecuta como rollback operativo 93E.
    raise RuntimeError('Reversion RAG requiere procedimiento explicito y respaldo; no se elimina contenido automaticamente.')
