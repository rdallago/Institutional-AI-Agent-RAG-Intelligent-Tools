from app.application.usuarios.dto import ListarUsuariosDatos, UsuarioResultado
from app.application.usuarios.ports.user_repository import UserRepository


class ListarUsuarios:
    def __init__(self, repositorio: UserRepository):
        self._repositorio = repositorio

    def ejecutar(self, consulta: ListarUsuariosDatos | None = None) -> tuple[UsuarioResultado, ...]:
        consulta = consulta if consulta is not None else ListarUsuariosDatos()
        return tuple(UsuarioResultado.desde_entidad(u) for u in self._repositorio.listar(consulta))
