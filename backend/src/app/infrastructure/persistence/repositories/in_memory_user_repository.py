"""Adaptador temporal: copias independientes y unicidad bajo bloqueo local."""

from threading import RLock
from uuid import UUID

from app.application.usuarios.dto import EstadoUsuarios, ListarUsuariosDatos
from app.application.usuarios.ports.user_repository import (
    EmailDuplicadoRepositorio, IdentidadDuplicadaRepositorio,
    UserRepository, UsuarioAusenteRepositorio,
)
from app.domain.usuarios.email import Email
from app.domain.usuarios.usuario import Usuario


def _copiar(usuario: Usuario) -> Usuario:
    return Usuario.reconstruir(
        id=usuario.id, nombre=usuario.nombre, apellido=usuario.apellido,
        email=usuario.email, activo=usuario.activo, rol=usuario.rol,
        fecha_creacion=usuario.fecha_creacion,
    )


class InMemoryUserRepository(UserRepository):
    def __init__(self):
        self._usuarios: dict[UUID, Usuario] = {}
        self._lock = RLock()

    def obtener_por_id(self, id: UUID) -> Usuario | None:
        with self._lock:
            usuario = self._usuarios.get(id)
            return _copiar(usuario) if usuario is not None else None

    def obtener_por_email(self, email: Email) -> Usuario | None:
        with self._lock:
            for usuario in self._usuarios.values():
                if usuario.email == email:
                    return _copiar(usuario)
            return None

    def listar(self, consulta: ListarUsuariosDatos) -> list[Usuario]:
        with self._lock:
            usuarios = [u for u in self._usuarios.values() if (
                consulta.estado is EstadoUsuarios.TODOS
                or u.activo == (consulta.estado is EstadoUsuarios.ACTIVOS)
            )]
            usuarios.sort(key=lambda u: (u.fecha_creacion, u.id))
            pagina = usuarios[consulta.desplazamiento:consulta.desplazamiento + consulta.limite]
            return [_copiar(u) for u in pagina]

    def _verificar_email(self, usuario: Usuario) -> None:
        # Invocado exclusivamente mientras el bloqueo de escritura está tomado.
        for existente in self._usuarios.values():
            if existente.id != usuario.id and existente.email == usuario.email:
                raise EmailDuplicadoRepositorio(existente.id, existente.activo)

    def agregar(self, usuario: Usuario) -> None:
        copia = _copiar(usuario)
        with self._lock:
            if copia.id in self._usuarios:
                raise IdentidadDuplicadaRepositorio("La identidad ya está registrada.")
            self._verificar_email(copia)
            self._usuarios[copia.id] = copia

    def actualizar(self, usuario: Usuario) -> None:
        copia = _copiar(usuario)
        with self._lock:
            if copia.id not in self._usuarios:
                raise UsuarioAusenteRepositorio("No existe la identidad que se intenta actualizar.")
            self._verificar_email(copia)
            self._usuarios[copia.id] = copia
