from app.application.usuarios.dto import CrearUsuarioDatos, ModificarUsuarioDatos, UsuarioResultado
from app.presentation.http.usuarios.schemas import CrearUsuarioSolicitud, ModificarUsuarioSolicitud, UsuarioRespuesta


def crear_datos(body: CrearUsuarioSolicitud) -> CrearUsuarioDatos:
    return CrearUsuarioDatos(nombre=body.nombre, apellido=body.apellido, email=body.email, rol=body.rol)


def modificar_datos(body: ModificarUsuarioSolicitud) -> ModificarUsuarioDatos:
    return ModificarUsuarioDatos(nombre=body.nombre, apellido=body.apellido, email=body.email)


def usuario_respuesta(result: UsuarioResultado) -> UsuarioRespuesta:
    return UsuarioRespuesta(
        id=result.id, nombre=result.nombre, apellido=result.apellido, email=result.email,
        activo=result.activo, rol=result.rol, fecha_creacion=result.fecha_creacion,
    )
