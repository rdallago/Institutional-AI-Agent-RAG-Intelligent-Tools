from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, DateTime, Index, PrimaryKeyConstraint, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.persistence.models.base import Base


class UsuarioModel(Base):
    __tablename__ = "usuarios"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_usuarios"),
        UniqueConstraint("email", name="uq_usuarios_email"),
        CheckConstraint("char_length(nombre) BETWEEN 1 AND 100", name="ck_usuarios_nombre_longitud"),
        CheckConstraint("char_length(apellido) BETWEEN 1 AND 100", name="ck_usuarios_apellido_longitud"),
        CheckConstraint("email = lower(email) AND email = btrim(email) AND char_length(email) > 0", name="ck_usuarios_email_normalizado"),
        CheckConstraint("rol IN ('ADMIN', 'USUARIO')", name="ck_usuarios_rol"),
        Index("ix_usuarios_fecha_id", "fecha_creacion", "id"),
        Index("ix_usuarios_activo_fecha_id", "activo", "fecha_creacion", "id"),
        {"schema": "public"},
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    apellido: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(254, collation="C"), nullable=False)
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False)
    rol: Mapped[str] = mapped_column(String(7), nullable=False)
    fecha_creacion: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
