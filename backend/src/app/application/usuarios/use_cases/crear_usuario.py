from app.application.usuarios.dto import CrearUsuarioDatos, UsuarioResultado
from app.application.usuarios.ports.user_repository import EmailDuplicadoRepositorio, UserRepository
from app.application.usuarios.use_cases._comunes import rechazar_alta_existente
from app.domain.usuarios.email import Email
from app.domain.usuarios.usuario import Usuario


class CrearUsuario:
    def __init__(self, repositorio: UserRepository):
        self._repositorio = repositorio

    def ejecutar(self, datos: CrearUsuarioDatos) -> UsuarioResultado:
        usuario = Usuario.crear(nombre=datos.nombre, apellido=datos.apellido,
                                email=Email(datos.email), rol=datos.rol)
        existente = self._repositorio.obtener_por_email(usuario.email)
        if existente is not None:
            rechazar_alta_existente(existente.id, existente.activo)
        try:
            self._repositorio.agregar(usuario)
        except EmailDuplicadoRepositorio as error:
            rechazar_alta_existente(error.usuario_id, error.activo)
        return UsuarioResultado.desde_entidad(usuario)
