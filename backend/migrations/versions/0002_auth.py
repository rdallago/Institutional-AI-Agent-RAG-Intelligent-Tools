"""Credenciales, sesiones revocables y limitación de intentos; sin backfill.

Revision ID: 0002
Revises: 0001
"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("usuario_credenciales",
        sa.Column("usuario_id", sa.Uuid(), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("creada_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actualizada_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("usuario_id"),
        sa.ForeignKeyConstraint(["usuario_id"], ["public.usuarios.id"], ondelete="RESTRICT"),
        sa.CheckConstraint("actualizada_at >= creada_at", name="ck_credenciales_fechas"), schema="public")
    op.create_table("auth_sesiones",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("usuario_id", sa.Uuid(), nullable=False),
        sa.Column("creada_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expira_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revocada_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["usuario_id"], ["public.usuarios.id"], ondelete="RESTRICT"),
        sa.CheckConstraint("expira_at > creada_at", name="ck_sesiones_expiracion"),
        sa.CheckConstraint("revocada_at IS NULL OR revocada_at >= creada_at", name="ck_sesiones_revocacion"), schema="public")
    op.create_index("ix_sesiones_usuario", "auth_sesiones", ["usuario_id", "revocada_at"], schema="public")
    op.create_index("ix_sesiones_expiracion", "auth_sesiones", ["expira_at"], schema="public")
    op.create_table("auth_intentos",
        sa.Column("ambito", sa.String(16), nullable=False),
        sa.Column("clave", sa.LargeBinary(32), nullable=False),
        sa.Column("inicio", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expira_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("contador", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("ambito", "clave", "inicio"),
        sa.CheckConstraint("contador >= 0", name="ck_intentos_contador"),
        sa.CheckConstraint("octet_length(clave) = 32", name="ck_intentos_clave"),
        sa.CheckConstraint("ambito IN ('ip', 'email_ip')", name="ck_intentos_ambito"),
        sa.CheckConstraint("expira_at > inicio", name="ck_intentos_fechas"), schema="public")
    op.create_index("ix_intentos_expiracion", "auth_intentos", ["expira_at"], schema="public")


def downgrade():
    op.drop_index("ix_intentos_expiracion", table_name="auth_intentos", schema="public")
    op.drop_table("auth_intentos", schema="public")
    op.drop_index("ix_sesiones_expiracion", table_name="auth_sesiones", schema="public")
    op.drop_index("ix_sesiones_usuario", table_name="auth_sesiones", schema="public")
    op.drop_table("auth_sesiones", schema="public")
    op.drop_table("usuario_credenciales", schema="public")
