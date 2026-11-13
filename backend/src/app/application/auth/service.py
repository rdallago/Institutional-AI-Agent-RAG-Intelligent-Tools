"""Políticas y operaciones de seguridad; cada operación compuesta usa una UoW."""

from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from app.application.auth.exceptions import (
    AprovisionamientoRechazado, AutenticacionRequerida, CredencialesInvalidas,
    PasswordInvalida,
    CambioPasswordRequerido,
    PasswordReutilizada,
    CredencialExistente, UsuarioInactivoNoAprovisionable,
)
from app.application.usuarios.dto import UsuarioResultado, CrearUsuarioDatos
from app.application.usuarios.use_cases.crear_usuario import CrearUsuario
from app.application.usuarios.use_cases.listar_usuarios import ListarUsuarios
from app.application.usuarios.use_cases.obtener_usuario import ObtenerUsuario
from app.application.usuarios.use_cases.modificar_usuario import ModificarUsuario
from app.application.usuarios.use_cases.dar_de_baja_usuario import DarDeBajaUsuario
from app.application.usuarios.use_cases.reactivar_usuario import ReactivarUsuario
from app.domain.auth.models import Credencial, Sesion
from app.domain.usuarios.email import Email
from app.domain.usuarios.rol import Rol
from app.application.auth.policies import authorize_profile
from app.application.auth.ports import PasswordHasher, TokenService, LoginAttemptLimiter
from app.application.auth import provisioning
from app.application.usuarios.exceptions import UsuarioNoEncontrado


def utc_now():
    return datetime.now(UTC)


def validate_password(password: str) -> None:
    # Sin truncar, normalizar o recortar; no se impone composición arbitraria.
    common = {"passwordpassword", "123456789012345", "contraseñacontraseña", "password123456789"}
    try:
        valid = isinstance(password, str) and 15 <= len(password) <= 128 and len(password.encode("utf-8")) <= 512
    except UnicodeError:
        valid = False
    if not valid or password.casefold() in common:
        raise PasswordInvalida("La contraseña no cumple la política de seguridad.")


@dataclass(frozen=True, slots=True)
class Principal:
    usuario_id: UUID
    sesion_id: UUID


@dataclass(frozen=True, slots=True)
class LoginResultado:
    access_token: str = field(repr=False)
    debe_cambiar_password: bool = field(kw_only=True)
    token_type: str = "bearer"
    expires_in: int = 900


@dataclass(frozen=True, slots=True)
class PerfilAuthResultado(UsuarioResultado):
    debe_cambiar_password: bool = field(default=False, init=False)


@dataclass(frozen=True, slots=True)
class CambioPasswordResultado:
    id: UUID
    debe_cambiar_password: bool = field(default=True, init=False)


class AuthService:
    def __init__(self, uow_factory, hasher: PasswordHasher, tokens: TokenService,
                 limiter: LoginAttemptLimiter, *, clock=utc_now, administrative_provisioning_gate=None):
        self.uow_factory, self.hasher, self.tokens, self.limiter = uow_factory, hasher, tokens, limiter
        self.clock = clock
        self._administrative_provisioning_gate = administrative_provisioning_gate
        # Preparado una vez; verifica trabajo equivalente para cuentas ausentes.
        self._dummy = hasher.hash(uuid4().hex + uuid4().hex)

    def _active(self, uow, principal: Principal):
        now = self.clock()
        session = uow.session(principal.sesion_id)
        if session is None or session.usuario_id != principal.usuario_id or session.revocada_at is not None or session.expira_at <= now:
            raise AutenticacionRequerida()
        user = uow.usuarios.obtener_por_id(principal.usuario_id)
        credential = uow.credential(user.id) if user else None
        if user is None or not user.activo or credential is None:
            raise AutenticacionRequerida()
        if session.restringida and not credential.debe_cambiar_password:
            raise AutenticacionRequerida()
        return user

    def _normal(self, uow, principal: Principal):
        user = self._active(uow, principal)
        if uow.credential(user.id).debe_cambiar_password or uow.session(principal.sesion_id).restringida:
            raise CambioPasswordRequerido()
        return user

    def authenticate(self, token: str) -> Principal:
        """Acceso normal por defecto; no autoriza una sesion pendiente."""
        user_id, session_id = self.tokens.verify(token)
        principal = Principal(user_id, session_id)
        with self.uow_factory() as uow:
            self._normal(uow, principal)
        return principal

    def require_normal_access(self, principal: Principal) -> None:
        """Revalidar un Principal mediante una UoW corta, sin permisos por rol nuevos."""
        with self.uow_factory() as uow:
            self._normal(uow, principal)

    def authenticate_session(self, token: str) -> Principal:
        """Solo para contexto y password; el servicio de negocio vuelve a validar."""
        user_id, session_id = self.tokens.verify(token)
        principal = Principal(user_id, session_id)
        with self.uow_factory() as uow:
            self._active(uow, principal)
        return principal

    def login(self, email: str, password: str, ip: str) -> LoginResultado:
        normalized = str(Email(email))
        attempted_at = self.clock()
        reservation = self.limiter.check(normalized, ip, attempted_at)
        with self.uow_factory() as uow:
            user = uow.usuarios.obtener_por_email(Email(normalized))
            credential = uow.credential(user.id) if user else None
        valid = self.hasher.verify(credential.password_hash if credential else self._dummy, password)
        if not valid or user is None or credential is None or not user.activo:
            self.limiter.failure(normalized, ip, self.clock())
            raise CredencialesInvalidas()
        replacement = self.hasher.hash(password) if self.hasher.needs_rehash(credential.password_hash) else None
        # Liberar antes de crear la sesion, fuera del lock de la UoW final.
        # Un fallo tecnico (incluso tras liberar) no debe dejar una sesion sin entregar.
        self.limiter.success(normalized, ip, attempted_at, reservation=reservation)
        now = self.clock()
        with self.uow_factory() as uow:
            current_user = uow.usuarios.obtener_por_id(user.id)
            current = uow.credential(user.id)
            if current_user is None or not current_user.activo or current is None or current.password_hash != credential.password_hash:
                raise CredencialesInvalidas()
            if replacement:
                uow.put_credential(replace(current, password_hash=replacement, actualizada_at=now))
            session = Sesion(uuid4(), user.id, now, now + timedelta(seconds=900),
                            restringida=current.debe_cambiar_password)
            uow.put_session(session)
            token = self.tokens.issue(session)
        return LoginResultado(token, debe_cambiar_password=session.restringida)

    def me(self, principal: Principal) -> PerfilAuthResultado | CambioPasswordResultado:
        with self.uow_factory() as uow:
            user = self._active(uow, principal)
            if uow.credential(user.id).debe_cambiar_password:
                return CambioPasswordResultado(user.id)
            return PerfilAuthResultado.desde_entidad(user)

    def logout(self, token: str) -> None:
        user_id, session_id = self.tokens.verify(token)
        with self.uow_factory() as uow:
            session = uow.session(session_id)
            if session and session.usuario_id == user_id and session.revocada_at is None:
                uow.put_session(replace(session, revocada_at=self.clock()))

    def change_password(self, principal: Principal, current_password: str, new_password: str,
                        *, ip: str = "unknown") -> None:
        with self.uow_factory() as uow:
            user = self._active(uow, principal)
            credential = uow.credential(user.id)
        attempted_at = self.clock()
        email = str(user.email)
        reservation = self.limiter.check(email, ip, attempted_at)
        if not self.hasher.verify(credential.password_hash, current_password):
            self.limiter.failure(email, ip, self.clock())
            raise CredencialesInvalidas()
        # Fuera de la UoW final: nunca esperar otra conexion bajo su advisory lock.
        self.limiter.success(email, ip, attempted_at, reservation=reservation)
        validate_password(new_password)
        if self.hasher.verify(credential.password_hash, new_password):
            raise PasswordReutilizada()
        if (credential.password_inicial_hash is not None
                and self.hasher.verify(credential.password_inicial_hash, new_password)):
            raise PasswordReutilizada()
        encoded = self.hasher.hash(new_password)
        with self.uow_factory() as uow:
            self._active(uow, principal)
            current = uow.credential(user.id)
            if current != credential:
                raise AutenticacionRequerida()
            now = self.clock()
            uow.put_credential(replace(current, password_hash=encoded, actualizada_at=now,
                                       debe_cambiar_password=False))
            uow.revoke(user.id, now)

    def manage(self, principal: Principal, action: str, *args):
        if action == "crear":
            return self.create_with_initial(principal, *args)
        cases = {"listar": ListarUsuarios, "obtener": ObtenerUsuario,
                 "modificar": ModificarUsuario, "baja": DarDeBajaUsuario, "reactivar": ReactivarUsuario}
        with self.uow_factory() as uow:
            actor = self._normal(uow, principal)
            authorize_profile(actor, action, args[0] if action in {"obtener", "modificar", "baja", "reactivar"} else None)
            result = cases[action](uow.usuarios).ejecutar(*args)
            if action == "baja":
                uow.revoke(args[0], self.clock())
            return result

    def _authorize_provisioning(self, uow, principal):
        actor = self._normal(uow, principal)
        authorize_profile(actor, "crear")
        gate = self._administrative_provisioning_gate
        if gate is None:
            provisioning.require_initial_provisioning_enabled()
        else:
            gate()

    def _insert_initial(self, uow, user_id, encoded):
        now = self.clock()
        uow.insert_initial_credential(Credencial(user_id, encoded, now, now,
            debe_cambiar_password=True, password_inicial_hash=encoded))

    def create_with_initial(self, principal: Principal, datos: CrearUsuarioDatos,
                            password_inicial: str | None = None) -> UsuarioResultado:
        with self.uow_factory() as uow:
            self._authorize_provisioning(uow, principal)
        validate_password(password_inicial)
        encoded = self.hasher.hash(password_inicial)
        with self.uow_factory() as uow:
            self._authorize_provisioning(uow, principal)
            result = CrearUsuario(uow.usuarios).ejecutar(datos)
            self._insert_initial(uow, result.id, encoded)
            return result

    def _initial_target(self, uow, user_id):
        user = uow.usuarios.obtener_por_id(user_id)
        if user is None:
            raise UsuarioNoEncontrado(user_id)
        if uow.credential(user_id) is not None:
            raise CredencialExistente()
        if not user.activo:
            raise UsuarioInactivoNoAprovisionable()
        return user

    def assign_initial_admin(self, principal: Principal, user_id: UUID, password_inicial: str) -> None:
        with self.uow_factory() as uow:
            self._authorize_provisioning(uow, principal)
            self._initial_target(uow, user_id)
        validate_password(password_inicial)
        encoded = self.hasher.hash(password_inicial)
        with self.uow_factory() as uow:
            self._authorize_provisioning(uow, principal)
            self._initial_target(uow, user_id)
            self._insert_initial(uow, user_id, encoded)
            uow.revoke(user_id, self.clock())

    def bootstrap(self, nombre: str, apellido: str, email: str, password: str) -> UUID:
        provisioning.require_initial_provisioning_enabled()
        validate_password(password)
        encoded = self.hasher.hash(password)
        with self.uow_factory() as uow:
            provisioning.require_initial_provisioning_enabled()
            # Cualquier ADMIN con credencial, incluso inactivo, cierra bootstrap.
            if uow.admin_provisioned():
                raise AprovisionamientoRechazado()
            normalized = Email(email)
            if uow.usuarios.obtener_por_email(normalized) is not None:
                raise AprovisionamientoRechazado()
            result = CrearUsuario(uow.usuarios).ejecutar(CrearUsuarioDatos(
                nombre=nombre, apellido=apellido, email=str(normalized), rol=Rol.ADMIN,
            ))
            self._insert_initial(uow, result.id, encoded)
            return result.id

    def assign_initial(self, user_id: UUID, password: str) -> None:
        provisioning.require_initial_provisioning_enabled()
        validate_password(password)
        encoded = self.hasher.hash(password)
        with self.uow_factory() as uow:
            provisioning.require_initial_provisioning_enabled()
            user = uow.usuarios.obtener_por_id(user_id)
            if user is None or not user.activo or uow.credential(user_id) is not None:
                raise AprovisionamientoRechazado()
            # No abrir una vía alternativa de creación ADMIN tras el bootstrap.
            if user.rol is Rol.ADMIN and uow.admin_provisioned():
                raise AprovisionamientoRechazado()
            self._insert_initial(uow, user_id, encoded)
