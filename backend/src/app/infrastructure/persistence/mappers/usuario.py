from app.domain.usuarios.email import Email
from app.domain.usuarios.rol import Rol
from app.domain.usuarios.usuario import Usuario
from app.infrastructure.persistence.models.usuario import UsuarioModel


def to_domain(model: UsuarioModel) -> Usuario:
    return Usuario.reconstruir(
        id=model.id, nombre=model.nombre, apellido=model.apellido,
        email=Email(model.email), activo=model.activo, rol=Rol(model.rol),
        fecha_creacion=model.fecha_creacion,
    )


def to_model(usuario: Usuario) -> UsuarioModel:
    # Igual que el adaptador en memoria: validar y capturar un estado independiente.
    snapshot = Usuario.reconstruir(
        id=usuario.id, nombre=usuario.nombre, apellido=usuario.apellido,
        email=usuario.email, activo=usuario.activo, rol=usuario.rol,
        fecha_creacion=usuario.fecha_creacion,
    )
    return UsuarioModel(
        id=snapshot.id, nombre=snapshot.nombre, apellido=snapshot.apellido,
        email=str(snapshot.email), activo=snapshot.activo, rol=snapshot.rol.value,
        fecha_creacion=snapshot.fecha_creacion,
    )
