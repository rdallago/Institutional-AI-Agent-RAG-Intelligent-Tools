from uuid import UUID

from app.application.usuarios.dto import UsuarioResultado
from app.application.usuarios.ports.user_repository import UserRepository
from app.application.usuarios.use_cases._comunes import obtener_existente


class ObtenerUsuario:
    def __init__(self, repositorio: UserRepository):
        self._repositorio = repositorio

    def ejecutar(self, id: UUID) -> UsuarioResultado:
        return UsuarioResultado.desde_entidad(obtener_existente(self._repositorio, id))
