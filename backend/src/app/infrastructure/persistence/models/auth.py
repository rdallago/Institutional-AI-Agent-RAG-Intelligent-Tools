from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, LargeBinary, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.persistence.models.base import Base


class CredencialModel(Base):
    __tablename__ = "usuario_credenciales"
    __table_args__ = (
        CheckConstraint("actualizada_at >= creada_at", name="ck_credenciales_fechas"),
        CheckConstraint("NOT debe_cambiar_password OR password_inicial_hash IS NOT NULL",
                        name="ck_credenciales_password_inicial"),
        {"schema": "public"})
    usuario_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("public.usuarios.id", ondelete="RESTRICT"), primary_key=True)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    creada_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    actualizada_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    debe_cambiar_password: Mapped[bool] = mapped_column(Boolean, nullable=False)
    password_inicial_hash: Mapped[str | None] = mapped_column(Text, nullable=True)


class SesionModel(Base):
    __tablename__ = "auth_sesiones"
    __table_args__ = (
        CheckConstraint("expira_at > creada_at", name="ck_sesiones_expiracion"),
        CheckConstraint("revocada_at IS NULL OR revocada_at >= creada_at", name="ck_sesiones_revocacion"),
        Index("ix_sesiones_usuario", "usuario_id", "revocada_at"),
        Index("ix_sesiones_expiracion", "expira_at"), {"schema": "public"})
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    usuario_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("public.usuarios.id", ondelete="RESTRICT"), nullable=False)
    creada_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expira_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revocada_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    restringida: Mapped[bool] = mapped_column(Boolean, nullable=False)


class IntentoModel(Base):
    __tablename__ = "auth_intentos"
    __table_args__ = (
        CheckConstraint("contador >= 0", name="ck_intentos_contador"),
        CheckConstraint("octet_length(clave) = 32", name="ck_intentos_clave"),
        CheckConstraint("ambito IN ('ip', 'email_ip')", name="ck_intentos_ambito"),
        CheckConstraint("expira_at > inicio", name="ck_intentos_fechas"),
        Index("ix_intentos_expiracion", "expira_at"), {"schema": "public"})
    ambito: Mapped[str] = mapped_column(String(16), primary_key=True)
    clave: Mapped[bytes] = mapped_column(LargeBinary(32), primary_key=True)
    inicio: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    expira_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    contador: Mapped[int] = mapped_column(Integer, nullable=False)
