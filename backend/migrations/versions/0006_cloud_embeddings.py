"""Espacio cloud paralelo; no alterar tablas, vectores o punteros Nomic."""
from alembic import op

revision = '0006_cloud_embeddings'
down_revision = '0005_agent_memory'
branch_labels = None
depends_on = None

DDL = (
    """CREATE TABLE public.rag_cloud_espacios (
      id uuid PRIMARY KEY, fingerprint varchar(64) NOT NULL UNIQUE,
      identidad text NOT NULL, dimension integer NOT NULL CHECK(dimension=768),
      UNIQUE(id,dimension), CHECK(fingerprint ~ '^[0-9a-f]{64}$'))""",
    """CREATE TABLE public.rag_cloud_embeddings (
      fragmento_id uuid NOT NULL REFERENCES public.rag_fragmentos(id),
      espacio_id uuid NOT NULL, dimension integer NOT NULL DEFAULT 768 CHECK(dimension=768),
      embedding public.vector(768) NOT NULL CHECK(public.vector_norm(embedding)>0),
      hash_entrada varchar(64) NOT NULL CHECK(hash_entrada ~ '^[0-9a-f]{64}$'),
      PRIMARY KEY(fragmento_id,espacio_id),
      FOREIGN KEY(espacio_id,dimension) REFERENCES public.rag_cloud_espacios(id,dimension))""",
    """CREATE TABLE public.rag_cloud_ingestas (
      version_id uuid NOT NULL REFERENCES public.rag_versiones(id),
      espacio_id uuid NOT NULL REFERENCES public.rag_cloud_espacios(id),
      estado varchar(16) NOT NULL CHECK(estado IN ('PREPARANDO','VALIDADA')),
      PRIMARY KEY(version_id,espacio_id))""",
    """CREATE TABLE public.rag_cloud_activos (
      version_id uuid PRIMARY KEY,
      espacio_id uuid NOT NULL,
      FOREIGN KEY(version_id,espacio_id) REFERENCES public.rag_cloud_ingestas(version_id,espacio_id))""",
)


def upgrade():
    for statement in DDL:
        op.execute(statement)


def downgrade():
    raise RuntimeError('No eliminar embeddings cloud automáticamente; requiere plan de conservación.')
