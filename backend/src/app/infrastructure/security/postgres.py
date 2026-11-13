"""UoW PostgreSQL: savepoints de repositorio y una única confirmación externa."""
from contextlib import contextmanager

from sqlalchemy import select, update, text, delete, func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.application.auth.ports import SecurityUnitOfWork
from app.application.auth.exceptions import AprovisionamientoRechazado
from app.domain.auth.models import Credencial, Sesion
from app.domain.usuarios.rol import Rol
from app.infrastructure.persistence.models.auth import CredencialModel, SesionModel, IntentoModel
from app.infrastructure.persistence.models.usuario import UsuarioModel
from app.infrastructure.persistence.repositories.sqlalchemy_user_repository import SQLAlchemyUserRepository, ErrorPersistencia


class _SessionScope:
    def __init__(self, session):
        self.session = session

    @contextmanager
    def __call__(self):
        yield self.session

    @contextmanager
    def begin(self):
        with self.session.begin_nested():
            yield self.session


class PostgresSecurityUnitOfWork(SecurityUnitOfWork):
    def __init__(self, sessions):
        self.sessions = sessions

    def __enter__(self):
        self.db = self.sessions()
        try:
            self.db.begin()
            # Serialización conservadora para este backend local. Todos los caminos
            # de seguridad usan el mismo lock transaccional, incluido bootstrap.
            self.db.execute(text("SELECT pg_advisory_xact_lock(715070001)"))
            self.usuarios = SQLAlchemyUserRepository(_SessionScope(self.db))
            return self
        except SQLAlchemyError:
            self.db.rollback()
            self.db.close()
            raise ErrorPersistencia("No se pudo iniciar la transacción de seguridad.") from None

    def __exit__(self, exc_type, exc, tb):
        try:
            if exc_type:
                self.db.rollback()
            else:
                self.db.commit()
        except SQLAlchemyError:
            self.db.rollback()
            raise ErrorPersistencia("No se pudo confirmar la transacción de seguridad.") from None
        finally:
            self.db.close()
        if isinstance(exc, SQLAlchemyError):
            raise ErrorPersistencia("Falló una operación de persistencia de seguridad.") from None

    def credential(self, user_id):
        model = self.db.get(CredencialModel, user_id)
        return Credencial(model.usuario_id, model.password_hash, model.creada_at, model.actualizada_at,
            debe_cambiar_password=model.debe_cambiar_password,
            password_inicial_hash=model.password_inicial_hash) if model else None

    def put_credential(self, credential):
        self.db.merge(CredencialModel(usuario_id=credential.usuario_id, password_hash=credential.password_hash,
            creada_at=credential.creada_at, actualizada_at=credential.actualizada_at,
            debe_cambiar_password=credential.debe_cambiar_password,
            password_inicial_hash=credential.password_inicial_hash))
        self.db.flush()

    def insert_initial_credential(self, credential):
        try:
            with self.db.begin_nested():
                self.db.add(CredencialModel(
                    usuario_id=credential.usuario_id, password_hash=credential.password_hash,
                    creada_at=credential.creada_at, actualizada_at=credential.actualizada_at,
                    debe_cambiar_password=credential.debe_cambiar_password,
                    password_inicial_hash=credential.password_inicial_hash))
                self.db.flush()
        except IntegrityError as error:
            if getattr(error.orig, "sqlstate", None) == "23505":
                raise AprovisionamientoRechazado() from None
            raise ErrorPersistencia("No se pudo insertar la credencial inicial.") from None

    def session(self, session_id):
        model = self.db.get(SesionModel, session_id)
        return Sesion(model.id, model.usuario_id, model.creada_at, model.expira_at, model.revocada_at,
            restringida=model.restringida) if model else None

    def put_session(self, session):
        self.db.merge(SesionModel(id=session.id, usuario_id=session.usuario_id, creada_at=session.creada_at,
            expira_at=session.expira_at, revocada_at=session.revocada_at,
            restringida=session.restringida))
        self.db.flush()

    def revoke(self, user_id, now):
        self.db.execute(update(SesionModel).where(SesionModel.usuario_id == user_id, SesionModel.revocada_at.is_(None)).values(revocada_at=now))

    def admin_provisioned(self):
        return self.db.scalar(select(CredencialModel.usuario_id).join(UsuarioModel).where(UsuarioModel.rol == Rol.ADMIN.value).limit(1)) is not None

    def consume(self, scope, digest, start, expires, limit):
        # Bajo el advisory lock de esta UoW; no contar reservas rechazadas.
        existing = self.db.get(IntentoModel, (scope, digest, start))
        if existing is not None and existing.contador >= limit:
            return limit + 1
        statement = insert(IntentoModel).values(ambito=scope, clave=digest, inicio=start, expira_at=expires, contador=1)
        statement = statement.on_conflict_do_update(index_elements=["ambito", "clave", "inicio"],
            set_={"contador": func.least(IntentoModel.contador + 1, limit + 1)}).returning(IntentoModel.contador)
        return self.db.scalar(statement)

    def release_attempt(self, scope, digest, start):
        self.db.execute(update(IntentoModel).where(IntentoModel.ambito == scope, IntentoModel.clave == digest, IntentoModel.inicio == start)
            .values(contador=func.greatest(IntentoModel.contador - 1, 0)))

    def cleanup_attempts(self, now, limit=1000):
        keys = select(IntentoModel.ambito, IntentoModel.clave, IntentoModel.inicio).where(IntentoModel.expira_at <= now).limit(limit)
        from sqlalchemy import tuple_
        return self.db.execute(delete(IntentoModel).where(tuple_(IntentoModel.ambito, IntentoModel.clave, IntentoModel.inicio).in_(keys))).rowcount
