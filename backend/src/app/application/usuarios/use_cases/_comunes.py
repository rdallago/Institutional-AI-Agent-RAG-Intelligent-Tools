from uuid import UUID

from app.application.usuarios.exceptions import (
    UsuarioActivoExistente, UsuarioInactivoReactivable, UsuarioNoEncontrado,
)
from app.application.usuarios.ports.user_repository import UserRepository
from app.domain.usuarios.exceptions import IdentificadorUsuarioInvalido
from app.domain.usuarios.usuario import Usuario


def obtener_existente(repositorio: UserRepository, id: UUID) -> Usuario:
    if not isinstance(id, UUID):
        raise IdentificadorUsuarioInvalido("El identificador debe ser UUID.")
    usuario = repositorio.obtener_por_id(id)
    if usuario is None:
        raise UsuarioNoEncontrado(id)
    return usuario


def rechazar_alta_existente(id: UUID, activo: bool) -> None:
    if activo:
        raise UsuarioActivoExistente()
    raise UsuarioInactivoReactivable(id)
