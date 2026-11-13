"""Crear usuarios con identidad estable y email globalmente único.

Revision ID: 0001
Revises: ninguna
"""

from alembic import op
import sqlalchemy as sa


revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "usuarios",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("nombre", sa.String(100), nullable=False),
        sa.Column("apellido", sa.String(100), nullable=False),
        sa.Column("email", sa.String(254, collation="C"), nullable=False),
        sa.Column("activo", sa.Boolean(), nullable=False),
        sa.Column("rol", sa.String(7), nullable=False),
        sa.Column("fecha_creacion", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_usuarios"),
        sa.UniqueConstraint("email", name="uq_usuarios_email"),
        sa.CheckConstraint("char_length(nombre) BETWEEN 1 AND 100", name="ck_usuarios_nombre_longitud"),
        sa.CheckConstraint("char_length(apellido) BETWEEN 1 AND 100", name="ck_usuarios_apellido_longitud"),
        sa.CheckConstraint("email = lower(email) AND email = btrim(email) AND char_length(email) > 0", name="ck_usuarios_email_normalizado"),
        sa.CheckConstraint("rol IN ('ADMIN', 'USUARIO')", name="ck_usuarios_rol"),
        schema="public",
    )
    op.create_index("ix_usuarios_fecha_id", "usuarios", ["fecha_creacion", "id"], schema="public")
    op.create_index("ix_usuarios_activo_fecha_id", "usuarios", ["activo", "fecha_creacion", "id"], schema="public")


def downgrade() -> None:
    op.drop_index("ix_usuarios_activo_fecha_id", table_name="usuarios", schema="public")
    op.drop_index("ix_usuarios_fecha_id", table_name="usuarios", schema="public")
    op.drop_table("usuarios", schema="public")
