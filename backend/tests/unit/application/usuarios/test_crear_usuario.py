import pytest

from app.application.usuarios.dto import CrearUsuarioDatos
from app.application.usuarios.exceptions import UsuarioActivoExistente, UsuarioInactivoReactivable
from app.application.usuarios.ports.user_repository import EmailDuplicadoRepositorio
from app.application.usuarios.use_cases.crear_usuario import CrearUsuario
from app.domain.usuarios.email import Email
from app.domain.usuarios.exceptions import NombreInvalido, EmailInvalido, RolInvalido
from app.domain.usuarios.rol import Rol


def test_crear_normaliza_y_guarda_entidad(repositorio):
    resultado = CrearUsuario(repositorio).ejecutar(
        CrearUsuarioDatos(nombre=" Ana ", apellido="Pérez", email=" ANA@ejemplo.com ", rol=Rol.ADMIN))
    guardado = repositorio.agregar.call_args.args[0]
    assert resultado.id == guardado.id
    assert resultado.nombre == "Ana"
    assert resultado.email == "ana@ejemplo.com"
    assert resultado.activo is True and resultado.rol is Rol.ADMIN
    repositorio.obtener_por_email.assert_called_once_with(Email(resultado.email))
    repositorio.actualizar.assert_not_called()


@pytest.mark.parametrize("activo,error", [(True, UsuarioActivoExistente), (False, UsuarioInactivoReactivable)])
def test_alta_existente_no_escribe(repositorio, usuario, activo, error):
    if not activo:
        usuario.dar_de_baja()
    repositorio.obtener_por_email.return_value = usuario
    with pytest.raises(error) as captura:
        CrearUsuario(repositorio).ejecutar(CrearUsuarioDatos(nombre="Otra", apellido="Persona", email="ANA@ejemplo.com"))
    if not activo:
        assert captura.value.usuario_id == usuario.id
        assert captura.value.codigo == "USUARIO_INACTIVO_REACTIVABLE"
    assert usuario.activo is activo
    assert usuario.nombre == "Ana"
    repositorio.agregar.assert_not_called()
    repositorio.actualizar.assert_not_called()


@pytest.mark.parametrize("activo,error", [(True, UsuarioActivoExistente), (False, UsuarioInactivoReactivable)])
def test_traduce_conflicto_de_email_detectado_durante_insercion(repositorio, usuario, activo, error):
    repositorio.agregar.side_effect = EmailDuplicadoRepositorio(usuario.id, activo)
    with pytest.raises(error) as captura:
        CrearUsuario(repositorio).ejecutar(CrearUsuarioDatos(nombre="Ana", apellido="Pérez", email="ana@ejemplo.com"))
    if not activo:
        assert captura.value.usuario_id == usuario.id
    repositorio.actualizar.assert_not_called()


@pytest.mark.parametrize("cambios,error", [
    ({"nombre": ""}, NombreInvalido), ({"email": "mal"}, EmailInvalido), ({"rol": "ADMIN"}, RolInvalido),
])
def test_alta_invalida_no_accede_al_repositorio(repositorio, cambios, error):
    datos = dict(nombre="Ana", apellido="Pérez", email="ana@ejemplo.com") | cambios
    with pytest.raises(error):
        CrearUsuario(repositorio).ejecutar(CrearUsuarioDatos(**datos))
    assert repositorio.mock_calls == []
