from uuid import UUID

from app.application.usuarios.dto import ModificarUsuarioDatos, UsuarioResultado
from app.application.usuarios.exceptions import EmailEnUso, UsuarioNoEncontrado
from app.application.usuarios.ports.user_repository import (
    EmailDuplicadoRepositorio, UserRepository, UsuarioAusenteRepositorio,
)
from app.application.usuarios.use_cases._comunes import obtener_existente
from app.domain.usuarios.email import Email


class ModificarUsuario:
    def __init__(self, repositorio: UserRepository):
        self._repositorio = repositorio

    def ejecutar(self, id: UUID, datos: ModificarUsuarioDatos) -> UsuarioResultado:
        usuario = obtener_existente(self._repositorio, id)
        email = Email(datos.email)
        usuario.modificar_datos(nombre=datos.nombre, apellido=datos.apellido, email=email)
        existente = self._repositorio.obtener_por_email(email)
        if existente is not None and existente.id != id:
            raise EmailEnUso()
        try:
            self._repositorio.actualizar(usuario)
        except EmailDuplicadoRepositorio as error:
            raise EmailEnUso() from error
        except UsuarioAusenteRepositorio as error:
            raise UsuarioNoEncontrado(id) from error
        return UsuarioResultado.desde_entidad(usuario)
