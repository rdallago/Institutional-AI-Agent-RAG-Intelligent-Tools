"""Memoria conversacional privada y requests idempotentes; solo DDL aditivo."""
from alembic import op
import sqlalchemy as sa

revision = '0005_agent_memory'
down_revision = '0004_rag'
branch_labels = None
depends_on = None

DDL = (
    """CREATE TABLE public.agent_conversaciones (
      id uuid PRIMARY KEY, propietario_id uuid NOT NULL REFERENCES public.usuarios(id),
      creado_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
      actualizado_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP)""",
    "CREATE INDEX ix_agent_conv_owner ON public.agent_conversaciones(propietario_id,actualizado_at DESC)",
    """CREATE TABLE public.agent_solicitudes (
      id uuid PRIMARY KEY, conversacion_id uuid NOT NULL REFERENCES public.agent_conversaciones(id),
      clave uuid NOT NULL, fingerprint varchar(64) NOT NULL CHECK(length(fingerprint)=64),
      estado varchar(12) NOT NULL CHECK(estado IN ('PENDIENTE','COMPLETA','FALLIDA')),
      resultado jsonb, creado_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
      UNIQUE(conversacion_id,clave), UNIQUE(conversacion_id,id),
      CHECK((estado='COMPLETA')=(resultado IS NOT NULL)))""",
    """CREATE TABLE public.agent_mensajes (
      id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
      conversacion_id uuid NOT NULL REFERENCES public.agent_conversaciones(id),
      solicitud_id uuid NOT NULL, rol varchar(12) NOT NULL CHECK(rol IN ('user','assistant')),
      contenido text NOT NULL CHECK(length(contenido) BETWEEN 1 AND 4096 AND octet_length(contenido)<=16384),
      estrategia varchar(16) NOT NULL CHECK(estrategia IN ('RAG','LLM_DIRECTO','TOOL')),
      estado varchar(24) NOT NULL, referencias jsonb NOT NULL DEFAULT '[]'::jsonb,
      herramienta varchar(40), contexto_tool jsonb NOT NULL DEFAULT '{}'::jsonb,
      creado_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY(conversacion_id,solicitud_id) REFERENCES public.agent_solicitudes(conversacion_id,id),
      UNIQUE(solicitud_id,rol))""",
    "CREATE INDEX ix_agent_msg_conv ON public.agent_mensajes(conversacion_id,id DESC)",
)


def upgrade():
    op.execute(sa.text("SET LOCAL lock_timeout='1s'"))
    op.execute(sa.text("SET LOCAL statement_timeout='10s'"))
    for ddl in DDL: op.execute(sa.text(ddl))


def downgrade():
    raise RuntimeError('Reversion de historial requiere respaldo y autorizacion; no se elimina automaticamente.')
