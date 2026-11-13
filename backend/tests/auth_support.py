import secrets

from app.application.auth.service import AuthService
from app.infrastructure.configuration.auth import AuthConfig
from app.infrastructure.security.crypto import Argon2Hasher, JWTService
from app.infrastructure.security.limiter import LoginLimiter
from app.infrastructure.security.memory import MemorySecurityStore


PASSWORD = "test-password-with-at-least-15-chars"


def auth_config():
    return AuthConfig({"test-key": secrets.token_bytes(32)}, "test-key", secrets.token_bytes(32))


def memory_auth(users=None, *, clock=None):
    store = MemorySecurityStore(users)
    config = auth_config()
    service = build_auth(store.uow, config, clock=clock)
    return store, service, config


def build_auth(factory, config, *, clock=None):
    kwargs = {"clock": clock} if clock else {}
    tokens = JWTService(config, **kwargs)
    return AuthService(factory, Argon2Hasher(memory_cost=1024, time_cost=1), tokens,
                       LoginLimiter(factory, config.limiter_key), **kwargs)


def bootstrap_login(service):
    # Fixture historica: no abrir la barrera operativa ni forzar cambio retroactivo.
    from app.application.usuarios.dto import CrearUsuarioDatos
    from app.application.usuarios.use_cases.crear_usuario import CrearUsuario
    from app.domain.usuarios.rol import Rol
    with service.uow_factory() as uow:
        result = CrearUsuario(uow.usuarios).ejecutar(CrearUsuarioDatos(
            nombre="Operador", apellido="Pruebas", email="operator@example.com", rol=Rol.ADMIN))
    user_id = result.id
    seed_legacy_credential(service, user_id)
    token = service.login("operator@example.com", PASSWORD, "127.0.0.1").access_token
    return user_id, token


def seed_legacy_credential(service, user_id, password=PASSWORD):
    from app.domain.auth.models import Credencial
    now = service.clock()
    encoded = service.hasher.hash(password)
    with service.uow_factory() as uow:
        uow.put_credential(Credencial(user_id, encoded, now, now,
            debe_cambiar_password=False, password_inicial_hash=None))
