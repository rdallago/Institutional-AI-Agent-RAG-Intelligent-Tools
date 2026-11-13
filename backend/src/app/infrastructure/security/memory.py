from copy import deepcopy
from dataclasses import replace
from threading import RLock

from app.application.auth.ports import SecurityUnitOfWork
from app.application.auth.exceptions import AprovisionamientoRechazado
from app.domain.usuarios.rol import Rol
from app.infrastructure.persistence.repositories.in_memory_user_repository import InMemoryUserRepository


class MemorySecurityStore:
    def __init__(self, users=None):
        self.users = users if users is not None else InMemoryUserRepository()
        self.credentials, self.sessions, self.attempts = {}, {}, {}
        self.lock = RLock()

    def uow(self):
        return MemorySecurityUnitOfWork(self)


class MemorySecurityUnitOfWork(SecurityUnitOfWork):
    def __init__(self, store):
        self.store = store
        self.usuarios = store.users

    def __enter__(self):
        self.store.lock.acquire()
        self.usuarios._lock.acquire()
        self.snapshot = deepcopy((self.usuarios._usuarios, self.store.credentials, self.store.sessions, self.store.attempts))
        return self

    def __exit__(self, exc_type, exc, tb):
        try:
            if exc_type:
                self.usuarios._usuarios, self.store.credentials, self.store.sessions, self.store.attempts = self.snapshot
        finally:
            self.usuarios._lock.release()
            self.store.lock.release()

    def credential(self, user_id):
        return self.store.credentials.get(user_id)

    def put_credential(self, credential):
        self.store.credentials[credential.usuario_id] = credential

    def insert_initial_credential(self, credential):
        if credential.usuario_id in self.store.credentials:
            raise AprovisionamientoRechazado()
        self.store.credentials[credential.usuario_id] = credential

    def session(self, session_id):
        return self.store.sessions.get(session_id)

    def put_session(self, session):
        self.store.sessions[session.id] = session

    def revoke(self, user_id, now):
        for key, session in list(self.store.sessions.items()):
            if session.usuario_id == user_id and session.revocada_at is None:
                self.store.sessions[key] = replace(session, revocada_at=now)

    def admin_provisioned(self):
        return any(self.usuarios.obtener_por_id(key).rol is Rol.ADMIN for key in self.store.credentials
                   if self.usuarios.obtener_por_id(key) is not None)

    def consume(self, scope, digest, start, expires, limit):
        key = (scope, digest, start)
        previous = self.store.attempts.get(key, (0, expires))[0]
        if previous >= limit:
            return limit + 1
        count = previous + 1
        self.store.attempts[key] = (count, expires)
        return count

    def release_attempt(self, scope, digest, start):
        key = (scope, digest, start)
        if key in self.store.attempts:
            count, expires = self.store.attempts[key]
            self.store.attempts[key] = (max(count - 1, 0), expires)

    def cleanup_attempts(self, now, limit=1000):
        keys = [k for k, (_, expiry) in self.store.attempts.items() if expiry <= now][:limit]
        for key in keys:
            del self.store.attempts[key]
        return len(keys)
