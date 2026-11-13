"""Contrato de persistencia; los adaptadores no deben exponer referencias vivas."""

from abc import ABC, abstractmethod
from uuid import UUID

from app.application.usuarios.dto import ListarUsuariosDatos
from app.domain.usuarios.email import Email
from app.domain.usuarios.usuario import Usuario


class EmailDuplicadoRepositorio(Exception):
    """Conflicto detectado al escribir; captura identidad y estado del propietario."""

    def __init__(self, usuario_id: UUID, activo: bool):
        self.usuario_id = usuario_id
        self.activo = activo
        super().__init__("Email duplicado en el repositorio.")


class IdentidadDuplicadaRepositorio(Exception):
    pass


class UsuarioAusenteRepositorio(Exception):
    pass


class UserRepository(ABC):
    @abstractmethod
    def obtener_por_id(self, id: UUID) -> Usuario | None:
        """Devolver una entidad independiente, activa o inactiva, o None."""

    @abstractmethod
    def obtener_por_email(self, email: Email) -> Usuario | None:
        """Buscar email normalizado entre todos los estados."""

    @abstractmethod
    def listar(self, consulta: ListarUsuariosDatos) -> list[Usuario]:
        """Filtrar, ordenar por fecha_creacion e id ascendente y luego paginar."""

    @abstractmethod
    def agregar(self, usuario: Usuario) -> None:
        """Insertar; rechazar identidad/email duplicados sin cambios parciales."""

    @abstractmethod
    def actualizar(self, usuario: Usuario) -> None:
        """Actualizar solo si existe; rechazar email ajeno sin cambios parciales."""
