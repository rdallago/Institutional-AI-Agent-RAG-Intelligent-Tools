"""Entidad Usuario: identidad estable y cambios explícitos de negocio."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.domain.usuarios.email import Email
from app.domain.usuarios.exceptions import (
    ApellidoInvalido,
    EmailInvalido,
    EstadoUsuarioInvalido,
    FechaCreacionInvalida,
    IdentificadorUsuarioInvalido,
    NombreInvalido,
    RolInvalido,
)
from app.domain.usuarios.rol import Rol


def _validar_nombre(valor: str) -> str:
    if not isinstance(valor, str) or not 1 <= len(valor.strip()) <= 100:
        raise NombreInvalido("El nombre debe contener entre 1 y 100 caracteres.")
    return valor.strip()


def _validar_apellido(valor: str) -> str:
    if not isinstance(valor, str) or not 1 <= len(valor.strip()) <= 100:
        raise ApellidoInvalido("El apellido debe contener entre 1 y 100 caracteres.")
    return valor.strip()


def _validar_email(valor: Email) -> Email:
    if not isinstance(valor, Email):
        raise EmailInvalido("Se requiere un objeto de valor Email.")
    return valor


class Usuario:
    """Usar crear para altas y reconstruir para datos previamente persistidos.

    Las propiedades no tienen setters. Los atributos internos siguen la
    convención de encapsulación de Python; no son una barrera de seguridad.
    """

    __slots__ = ("_id", "_nombre", "_apellido", "_email", "_activo", "_rol", "_fecha_creacion")

    def __init__(
        self, *, id: UUID, nombre: str, apellido: str, email: Email,
        activo: bool, rol: Rol, fecha_creacion: datetime,
    ) -> None:
        if not isinstance(id, UUID):
            raise IdentificadorUsuarioInvalido("El identificador debe ser UUID.")
        if not isinstance(activo, bool):
            raise EstadoUsuarioInvalido("El estado activo debe ser booleano.")
        if not isinstance(rol, Rol):
            raise RolInvalido("El rol debe ser ADMIN o USUARIO de la enumeración Rol.")
        if not isinstance(fecha_creacion, datetime) or fecha_creacion.utcoffset() is None:
            raise FechaCreacionInvalida("La fecha de creación debe incluir zona horaria.")
        self._nombre = _validar_nombre(nombre)
        self._apellido = _validar_apellido(apellido)
        self._email = _validar_email(email)
        self._id = id
        self._activo = activo
        self._rol = rol
        self._fecha_creacion = fecha_creacion.astimezone(UTC)

    @classmethod
    def crear(
        cls, *, nombre: str, apellido: str, email: Email, rol: Rol = Rol.USUARIO,
    ) -> Usuario:
        """Dar de alta con identidad y fecha nuevas, siempre activo."""
        return cls(
            id=uuid4(), nombre=nombre, apellido=apellido, email=email,
            activo=True, rol=rol, fecha_creacion=datetime.now(UTC),
        )

    @classmethod
    def reconstruir(
        cls, *, id: UUID, nombre: str, apellido: str, email: Email,
        activo: bool, rol: Rol, fecha_creacion: datetime,
    ) -> Usuario:
        """Recuperar un estado existente sin generar identidad ni fecha nuevas."""
        return cls(
            id=id, nombre=nombre, apellido=apellido, email=email,
            activo=activo, rol=rol, fecha_creacion=fecha_creacion,
        )

    @property
    def id(self) -> UUID:
        return self._id

    @property
    def nombre(self) -> str:
        return self._nombre

    @property
    def apellido(self) -> str:
        return self._apellido

    @property
    def email(self) -> Email:
        return self._email

    @property
    def activo(self) -> bool:
        return self._activo

    @property
    def rol(self) -> Rol:
        return self._rol

    @property
    def fecha_creacion(self) -> datetime:
        return self._fecha_creacion

    def modificar_datos(self, *, nombre: str, apellido: str, email: Email) -> None:
        """Validar todo antes de asignar; no modifica rol, identidad ni estado."""
        nuevo_nombre = _validar_nombre(nombre)
        nuevo_apellido = _validar_apellido(apellido)
        nuevo_email = _validar_email(email)
        self._nombre = nuevo_nombre
        self._apellido = nuevo_apellido
        self._email = nuevo_email

    def dar_de_baja(self) -> None:
        """Baja lógica idempotente; conservar los demás atributos."""
        self._activo = False

    def reactivar(self) -> None:
        """Reactivación idempotente; conservar los demás atributos."""
        self._activo = True
