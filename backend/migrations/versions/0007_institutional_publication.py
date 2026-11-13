"""Explicit, version-bound institutional read publication; no automatic grants."""
from alembic import op

revision = '0007_institutional_publication'
down_revision = '0006_cloud_embeddings'
branch_labels = None
depends_on = None

DDL = '''CREATE TABLE public.rag_publicaciones_institucionales (
 documento_id uuid PRIMARY KEY REFERENCES public.rag_documentos(id),
 version_id uuid NOT NULL,
 publicado_por uuid NOT NULL REFERENCES public.usuarios(id),
 publicado_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
 revocado_por uuid REFERENCES public.usuarios(id),
 revocado_at timestamptz,
 FOREIGN KEY(documento_id,version_id) REFERENCES public.rag_versiones(documento_id,id),
 CHECK ((revocado_at IS NULL) = (revocado_por IS NULL)))'''


def upgrade():
    op.execute(DDL)


def downgrade():
    # Old application code must never interpret a residual AUTHENTICATED flag
    # as an unversioned grant after this registry is removed.
    op.execute("UPDATE public.rag_documentos SET visibilidad='PRIVATE' WHERE id IN "
               '(SELECT documento_id FROM public.rag_publicaciones_institucionales)')
    op.execute('DROP TABLE public.rag_publicaciones_institucionales')
