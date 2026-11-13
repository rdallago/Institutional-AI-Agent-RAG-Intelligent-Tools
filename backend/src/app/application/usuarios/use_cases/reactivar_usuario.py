from uuid import UUID

from app.application.usuarios.dto import UsuarioResultado
from app.application.usuarios.exceptions import UsuarioNoEncontrado
from app.application.usuarios.ports.user_repository import UserRepository, UsuarioAusenteRepositorio
from app.application.usuarios.use_cases._comunes import obtener_existente


class ReactivarUsuario:
    def __init__(self, repositorio: UserRepository):
        self._repositorio = repositorio

    def ejecutar(self, id: UUID) -> UsuarioResultado:
        usuario = obtener_existente(self._repositorio, id)
        if not usuario.activo:
            usuario.reactivar()
            try:
                self._repositorio.actualizar(usuario)
            except UsuarioAusenteRepositorio as error:
                raise UsuarioNoEncontrado(id) from error
        return UsuarioResultado.desde_entidad(usuario)
