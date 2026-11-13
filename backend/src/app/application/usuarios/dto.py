"""Entradas y resultados inmutables, independientes de Pydantic."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from app.application.usuarios.exceptions import FiltroEstadoInvalido, PaginacionInvalida
from app.domain.usuarios.rol import Rol
from app.domain.usuarios.usuario import Usuario


class EstadoUsuarios(StrEnum):
    ACTIVOS = "activos"
    INACTIVOS = "inactivos"
    TODOS = "todos"


@dataclass(frozen=True, slots=True, kw_only=True)
class CrearUsuarioDatos:
    nombre: str
    apellido: str
    email: str
    rol: Rol = Rol.USUARIO


@dataclass(frozen=True, slots=True, kw_only=True)
class ModificarUsuarioDatos:
    nombre: str
    apellido: str
    email: str


@dataclass(frozen=True, slots=True, kw_only=True)
class ListarUsuariosDatos:
    estado: EstadoUsuarios = EstadoUsuarios.ACTIVOS
    limite: int = 20
    desplazamiento: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.estado, EstadoUsuarios):
            raise FiltroEstadoInvalido("Se requiere un miembro de EstadoUsuarios.")
        if type(self.limite) is not int or not 1 <= self.limite <= 100:
            raise PaginacionInvalida("El límite debe ser un entero entre 1 y 100.")
        if type(self.desplazamiento) is not int or self.desplazamiento < 0:
            raise PaginacionInvalida("El desplazamiento debe ser un entero no negativo.")


@dataclass(frozen=True, slots=True)
class UsuarioResultado:
    id: UUID
    nombre: str
    apellido: str
    email: str
    activo: bool
    rol: Rol
    fecha_creacion: datetime

    @classmethod
    def desde_entidad(cls, usuario: Usuario) -> UsuarioResultado:
        return cls(usuario.id, usuario.nombre, usuario.apellido, str(usuario.email),
                   usuario.activo, usuario.rol, usuario.fecha_creacion)
