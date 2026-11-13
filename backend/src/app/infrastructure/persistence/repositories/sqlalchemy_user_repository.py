"""Adaptador síncrono: una sesión y transacción por operación."""

from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.application.usuarios.dto import EstadoUsuarios, ListarUsuariosDatos
from app.application.usuarios.ports.user_repository import (
    EmailDuplicadoRepositorio, IdentidadDuplicadaRepositorio,
    UserRepository, UsuarioAusenteRepositorio,
)
from app.domain.usuarios.email import Email
from app.domain.usuarios.usuario import Usuario
from app.infrastructure.persistence.mappers.usuario import to_domain, to_model
from app.infrastructure.persistence.models.usuario import UsuarioModel


class ErrorPersistencia(RuntimeError):
    """Fallo técnico saneado; no cambia el contrato de Application."""


def _reconstruir(model: UsuarioModel) -> Usuario:
    try:
        return to_domain(model)
    except (ValueError, TypeError):
        raise ErrorPersistencia("El estado almacenado no cumple las invariantes del dominio.") from None


class SQLAlchemyUserRepository(UserRepository):
    def __init__(self, session_factory: sessionmaker[Session]):
        self._sessions = session_factory

    def obtener_por_id(self, id: UUID) -> Usuario | None:
        return self._obtener(select(UsuarioModel).where(UsuarioModel.id == id))

    def obtener_por_email(self, email: Email) -> Usuario | None:
        return self._obtener(select(UsuarioModel).where(UsuarioModel.email == str(email)))

    def _obtener(self, statement) -> Usuario | None:
        try:
            with self._sessions() as session:
                model = session.scalar(statement)
                return _reconstruir(model) if model is not None else None
        except SQLAlchemyError:
            raise ErrorPersistencia("No se pudo consultar PostgreSQL.") from None

    def listar(self, consulta: ListarUsuariosDatos) -> list[Usuario]:
        statement = select(UsuarioModel)
        if consulta.estado is not EstadoUsuarios.TODOS:
            statement = statement.where(UsuarioModel.activo == (consulta.estado is EstadoUsuarios.ACTIVOS))
        statement = statement.order_by(UsuarioModel.fecha_creacion, UsuarioModel.id).offset(
            consulta.desplazamiento
        ).limit(consulta.limite)
        try:
            with self._sessions() as session:
                return [_reconstruir(model) for model in session.scalars(statement)]
        except SQLAlchemyError:
            raise ErrorPersistencia("No se pudo listar usuarios en PostgreSQL.") from None

    def agregar(self, usuario: Usuario) -> None:
        self._escribir(usuario, insertar=True)

    def actualizar(self, usuario: Usuario) -> None:
        self._escribir(usuario, insertar=False)

    def _escribir(self, usuario: Usuario, *, insertar: bool) -> None:
        snapshot = to_model(usuario)
        for _ in range(3):
            try:
                with self._sessions.begin() as session:
                    if insertar:
                        # Preservar prioridad del error de identidad del adaptador en memoria.
                        if session.get(UsuarioModel, snapshot.id) is not None:
                            raise IdentidadDuplicadaRepositorio("La identidad ya está registrada.")
                        # Instancia nueva en cada intento, sin estado ORM de la sesión fallida.
                        session.add(to_model(to_domain(snapshot)))
                    else:
                        result = session.execute(
                            update(UsuarioModel).where(UsuarioModel.id == snapshot.id).values(
                                nombre=snapshot.nombre, apellido=snapshot.apellido,
                                email=snapshot.email, activo=snapshot.activo, rol=snapshot.rol,
                                fecha_creacion=snapshot.fecha_creacion,
                            )
                        )
                        if result.rowcount == 0:
                            raise UsuarioAusenteRepositorio("No existe la identidad que se intenta actualizar.")
                return  # El commit ya ocurrió; el caso de uso puede capturar sus conflictos.
            except IntegrityError as error:
                # El context manager ya revirtió y cerró la transacción fallida.
                original = error.orig
                constraint = getattr(getattr(original, "diag", None), "constraint_name", None)
                if getattr(original, "sqlstate", None) != "23505":
                    raise ErrorPersistencia("Escritura rechazada por una restricción de integridad.") from None
                if constraint == "pk_usuarios":
                    raise IdentidadDuplicadaRepositorio("La identidad ya está registrada.") from None
                if constraint != "uq_usuarios_email":
                    raise ErrorPersistencia("Conflicto de integridad no reconocido.") from None
                owner = self.obtener_por_email(Email(snapshot.email))
                if owner is not None:
                    raise EmailDuplicadoRepositorio(owner.id, owner.activo) from None
                # El propietario liberó el email entre conflicto y consulta: reintentar acotadamente.
            except SQLAlchemyError:
                raise ErrorPersistencia("No se pudo escribir en PostgreSQL.") from None
        raise ErrorPersistencia("No se pudo resolver un conflicto concurrente de email.")
