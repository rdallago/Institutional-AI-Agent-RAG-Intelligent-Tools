from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictStr, SecretStr

from app.domain.usuarios.rol import Rol


class CrearUsuarioSolicitud(BaseModel):
    model_config = ConfigDict(extra="forbid", json_schema_extra={"examples": [{
        "nombre": "Ana", "apellido": "Pérez", "email": "ana@example.com", "rol": "USUARIO",
    }]})
    nombre: StrictStr = Field(description="Nombre; el dominio elimina espacios externos y valida su longitud.")
    apellido: StrictStr
    email: StrictStr = Field(description="Email según la política ASCII del dominio; se normaliza a minúsculas.")
    rol: Rol = Rol.USUARIO
    password_inicial: SecretStr = Field(min_length=15, max_length=128,
        description="Secreto inicial manual; debe cambiarse antes de obtener acceso normal. Aprovisionamiento operativo deshabilitado.")


class CredencialInicialSolicitud(BaseModel):
    model_config = ConfigDict(extra="forbid")
    password_inicial: SecretStr = Field(min_length=15, max_length=128)


class ModificarUsuarioSolicitud(BaseModel):
    model_config = ConfigDict(extra="forbid", json_schema_extra={"examples": [{
        "nombre": "Ana", "apellido": "Díaz", "email": "ana.diaz@example.com",
    }]})
    nombre: StrictStr
    apellido: StrictStr
    email: StrictStr


class OperacionEstadoSolicitud(BaseModel):
    """Una operación de estado no admite campos de negocio."""
    model_config = ConfigDict(extra="forbid")


class UsuarioRespuesta(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{
        "id": "550e8400-e29b-41d4-a716-446655440000", "nombre": "Ana", "apellido": "Pérez",
        "email": "ana@example.com", "activo": True, "rol": "USUARIO",
        "fecha_creacion": "2026-10-29T12:00:00Z",
    }]})
    id: UUID
    nombre: str
    apellido: str
    email: str
    activo: bool
    rol: Rol
    fecha_creacion: datetime
