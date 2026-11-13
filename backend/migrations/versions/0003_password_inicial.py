"""Estado de credencial y alcance de sesion; sin activar flujos nuevos.

Revision ID: 0003
Revises: 0002
"""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("usuario_credenciales", sa.Column(
        "debe_cambiar_password", sa.Boolean(), nullable=False,
        server_default=sa.false()), schema="public")
    op.add_column("usuario_credenciales", sa.Column(
        "password_inicial_hash", sa.Text(), nullable=True), schema="public")
    op.add_column("auth_sesiones", sa.Column(
        "restringida", sa.Boolean(), nullable=False,
        server_default=sa.false()), schema="public")
    op.create_check_constraint(
        "ck_credenciales_password_inicial", "usuario_credenciales",
        "NOT debe_cambiar_password OR password_inicial_hash IS NOT NULL", schema="public")
    op.alter_column("usuario_credenciales", "debe_cambiar_password",
                    server_default=None, schema="public")
    op.alter_column("auth_sesiones", "restringida",
                    server_default=None, schema="public")


def downgrade():
    op.drop_constraint("ck_credenciales_password_inicial", "usuario_credenciales",
                       type_="check", schema="public")
    op.drop_column("auth_sesiones", "restringida", schema="public")
    op.drop_column("usuario_credenciales", "password_inicial_hash", schema="public")
    op.drop_column("usuario_credenciales", "debe_cambiar_password", schema="public")
