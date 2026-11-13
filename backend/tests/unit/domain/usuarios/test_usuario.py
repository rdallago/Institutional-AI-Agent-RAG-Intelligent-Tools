from datetime import UTC, datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest

from app.domain.usuarios.email import Email
from app.domain.usuarios.exceptions import (
    ApellidoInvalido, EmailInvalido, EstadoUsuarioInvalido,
    FechaCreacionInvalida, IdentificadorUsuarioInvalido, NombreInvalido, RolInvalido,
)
from app.domain.usuarios.rol import Rol
from app.domain.usuarios.usuario import Usuario


@pytest.fixture
def usuario():
    return Usuario.crear(nombre=" Ana María ", apellido=" O'Connor-Pérez ", email=Email("ana@ejemplo.com"))


def estado(usuario):
    return (
        usuario.id, usuario.nombre, usuario.apellido, usuario.email,
        usuario.activo, usuario.rol, usuario.fecha_creacion,
    )


def test_alta_normaliza_datos_y_establece_valores_iniciales():
    antes = datetime.now(UTC)
    usuario = Usuario.crear(nombre=" Ana María ", apellido=" O'Connor-Pérez ", email=Email("ANA@ejemplo.com"))
    despues = datetime.now(UTC)
    assert isinstance(usuario.id, UUID)
    assert usuario.id.version == 4
    assert usuario.activo is True
    assert usuario.rol is Rol.USUARIO
    assert usuario.nombre == "Ana María"
    assert usuario.apellido == "O'Connor-Pérez"
    assert usuario.email == Email("ana@ejemplo.com")
    assert antes <= usuario.fecha_creacion <= despues
    assert usuario.fecha_creacion.tzinfo is UTC


def test_cada_alta_genera_identidad_nueva(usuario):
    otro = Usuario.crear(nombre=usuario.nombre, apellido=usuario.apellido, email=usuario.email)
    assert otro.id != usuario.id


@pytest.mark.parametrize("rol", list(Rol))
def test_admite_ambos_roles(rol):
    usuario = Usuario.crear(nombre="Ana", apellido="Pérez", email=Email("a@ejemplo.com"), rol=rol)
    assert usuario.rol is rol


@pytest.mark.parametrize("campo,error", [("nombre", NombreInvalido), ("apellido", ApellidoInvalido)])
@pytest.mark.parametrize("valor", [None, 1, True, "", " \t\n ", "a" * 101])
def test_rechaza_datos_personales_invalidos(campo, error, valor):
    datos = dict(nombre="Ana", apellido="Pérez", email=Email("a@ejemplo.com"))
    datos[campo] = valor
    with pytest.raises(error):
        Usuario.crear(**datos)


def test_admite_limites_de_nombre_y_apellido():
    usuario = Usuario.crear(nombre=" a ", apellido=" " + "b" * 100 + " ", email=Email("a@ejemplo.com"))
    assert usuario.nombre == "a"
    assert usuario.apellido == "b" * 100


@pytest.mark.parametrize("rol", ["ADMIN", "USUARIO", "OTRO", None, 1])
def test_rechaza_roles_sin_tipo_enum(rol):
    with pytest.raises(RolInvalido):
        Usuario.crear(nombre="Ana", apellido="Pérez", email=Email("a@ejemplo.com"), rol=rol)


@pytest.mark.parametrize("email", [None, "a@ejemplo.com", 1])
def test_exige_objeto_email(email):
    with pytest.raises(EmailInvalido):
        Usuario.crear(nombre="Ana", apellido="Pérez", email=email)


@pytest.mark.parametrize("activo", [True, False])
def test_reconstruccion_conserva_datos_y_normaliza_instante_a_utc(activo):
    identificador = uuid4()
    fecha = datetime(2024, 1, 2, 10, tzinfo=timezone(timedelta(hours=-3)))
    usuario = Usuario.reconstruir(
        id=identificador, nombre="Ana", apellido="Pérez", email=Email("a@ejemplo.com"),
        activo=activo, rol=Rol.ADMIN, fecha_creacion=fecha,
    )
    assert estado(usuario) == (identificador, "Ana", "Pérez", Email("a@ejemplo.com"), activo, Rol.ADMIN, fecha)
    assert usuario.fecha_creacion.tzinfo is UTC


@pytest.mark.parametrize("campo,valor,error", [
    ("id", "123", IdentificadorUsuarioInvalido),
    ("id", None, IdentificadorUsuarioInvalido),
    ("activo", 0, EstadoUsuarioInvalido),
    ("activo", 1, EstadoUsuarioInvalido),
    ("activo", "false", EstadoUsuarioInvalido),
    ("activo", None, EstadoUsuarioInvalido),
    ("fecha_creacion", datetime(2024, 1, 1), FechaCreacionInvalida),
    ("fecha_creacion", "2024-01-01", FechaCreacionInvalida),
    ("fecha_creacion", None, FechaCreacionInvalida),
    ("nombre", "", NombreInvalido),
    ("apellido", "", ApellidoInvalido),
    ("email", "a@ejemplo.com", EmailInvalido),
    ("rol", "ADMIN", RolInvalido),
])
def test_reconstruccion_valida_invariantes(campo, valor, error):
    datos = dict(id=uuid4(), nombre="Ana", apellido="Pérez", email=Email("a@ejemplo.com"),
                 activo=False, rol=Rol.USUARIO, fecha_creacion=datetime.now(UTC))
    datos[campo] = valor
    with pytest.raises(error):
        Usuario.reconstruir(**datos)


@pytest.mark.parametrize("activo", [True, False])
def test_modificacion_preserva_identidad_fecha_rol_y_estado(usuario, activo):
    if not activo:
        usuario.dar_de_baja()
    antes = estado(usuario)
    usuario.modificar_datos(nombre=" Beatriz ", apellido=" Díaz ", email=Email("B@ejemplo.com"))
    assert (usuario.nombre, usuario.apellido, str(usuario.email)) == ("Beatriz", "Díaz", "b@ejemplo.com")
    assert (usuario.id, usuario.activo, usuario.rol, usuario.fecha_creacion) == (antes[0], antes[4], antes[5], antes[6])


@pytest.mark.parametrize("campo,valor,error", [
    ("nombre", "", NombreInvalido),
    ("apellido", "", ApellidoInvalido),
    ("email", "invalido", EmailInvalido),
])
def test_modificacion_invalida_no_deja_cambios_parciales(usuario, campo, valor, error):
    antes = estado(usuario)
    datos = dict(nombre="Beatriz", apellido="Díaz", email=Email("b@ejemplo.com"))
    datos[campo] = valor
    with pytest.raises(error):
        usuario.modificar_datos(**datos)
    assert estado(usuario) == antes


@pytest.mark.parametrize("rol", list(Rol))
def test_baja_y_reactivacion_idempotentes_conservan_demas_atributos(rol):
    usuario = Usuario.crear(nombre="Ana", apellido="Pérez", email=Email("a@ejemplo.com"), rol=rol)
    antes = estado(usuario)
    for operacion, esperado in [(usuario.dar_de_baja, False), (usuario.dar_de_baja, False),
                                (usuario.reactivar, True), (usuario.reactivar, True)]:
        operacion()
        actual = estado(usuario)
        assert actual[4] is esperado
        assert actual[:4] == antes[:4]
        assert actual[5:] == antes[5:]


@pytest.mark.parametrize("atributo", ["id", "nombre", "apellido", "email", "activo", "rol", "fecha_creacion"])
def test_propiedades_sin_setter(usuario, atributo):
    antes = estado(usuario)
    with pytest.raises(AttributeError):
        setattr(usuario, atributo, None)
    assert estado(usuario) == antes


@pytest.mark.parametrize("campo,valor", [("activo", False), ("rol", Rol.ADMIN), ("id", uuid4()),
                                        ("fecha_creacion", datetime.now(UTC))])
def test_modificacion_no_admite_campos_protegidos(usuario, campo, valor):
    antes = estado(usuario)
    with pytest.raises(TypeError):
        usuario.modificar_datos(nombre="Beatriz", apellido="Díaz", email=Email("b@ejemplo.com"), **{campo: valor})
    assert estado(usuario) == antes
