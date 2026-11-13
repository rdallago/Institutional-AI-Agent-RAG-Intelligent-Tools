from app.application.auth.exceptions import PermisoDenegado
from app.application.usuarios.exceptions import UsuarioNoEncontrado
from app.domain.usuarios.rol import Rol


def authorize_profile(actor, action: str, target=None) -> None:
    if actor.rol is not Rol.ADMIN:
        if action != "obtener":
            raise PermisoDenegado()
        if target != actor.id:
            raise UsuarioNoEncontrado(target)
    if action == "baja" and target == actor.id:
        raise PermisoDenegado()
