from uuid import uuid4

import pytest

from app.application.usuarios.dto import ModificarUsuarioDatos
from app.application.usuarios.exceptions import EmailEnUso, UsuarioNoEncontrado
from app.application.usuarios.ports.user_repository import EmailDuplicadoRepositorio, UsuarioAusenteRepositorio
from app.application.usuarios.use_cases.modificar_usuario import ModificarUsuario
from app.domain.usuarios.email import Email
from app.domain.usuarios.exceptions import NombreInvalido
from app.domain.usuarios.usuario import Usuario


@pytest.mark.parametrize("activo", [True, False])
def test_modifica_email_propio_conservando_campos_protegidos(repositorio, usuario, activo):
    if not activo:
        usuario.dar_de_baja()
    repositorio.obtener_por_id.return_value = usuario
    repositorio.obtener_por_email.return_value = usuario
    resultado = ModificarUsuario(repositorio).ejecutar(usuario.id,
        ModificarUsuarioDatos(nombre="Beatriz", apellido="Díaz", email="ANA@ejemplo.com"))
    assert resultado.nombre == "Beatriz"
    assert (resultado.id, resultado.fecha_creacion, resultado.rol, resultado.activo) == (
        usuario.id, usuario.fecha_creacion, usuario.rol, activo)
    repositorio.actualizar.assert_called_once_with(usuario)
    repositorio.agregar.assert_not_called()


@pytest.mark.parametrize("activo", [True, False])
def test_email_ajeno_siempre_es_conflicto(repositorio, usuario, activo):
    otro = Usuario.crear(nombre="Otra", apellido="Persona", email=Email("otra@ejemplo.com"))
    if not activo:
        otro.dar_de_baja()
    repositorio.obtener_por_id.return_value = usuario
    repositorio.obtener_por_email.return_value = otro
    with pytest.raises(EmailEnUso):
        ModificarUsuario(repositorio).ejecutar(usuario.id,
            ModificarUsuarioDatos(nombre="Beatriz", apellido="Díaz", email=str(otro.email)))
    repositorio.actualizar.assert_not_called()


def test_modificacion_inexistente_no_escribe(repositorio):
    with pytest.raises(UsuarioNoEncontrado):
        ModificarUsuario(repositorio).ejecutar(uuid4(), ModificarUsuarioDatos(nombre="Ana", apellido="P", email="a@ejemplo.com"))
    repositorio.actualizar.assert_not_called()


def test_modificacion_invalida_no_escribe(repositorio, usuario):
    repositorio.obtener_por_id.return_value = usuario
    with pytest.raises(NombreInvalido):
        ModificarUsuario(repositorio).ejecutar(usuario.id, ModificarUsuarioDatos(nombre="", apellido="P", email="a@ejemplo.com"))
    repositorio.actualizar.assert_not_called()


@pytest.mark.parametrize("error,esperado", [
    (EmailDuplicadoRepositorio(uuid4(), False), EmailEnUso),
    (UsuarioAusenteRepositorio(), UsuarioNoEncontrado),
])
def test_traduce_conflictos_en_escritura(repositorio, usuario, error, esperado):
    repositorio.obtener_por_id.return_value = usuario
    repositorio.actualizar.side_effect = error
    with pytest.raises(esperado):
        ModificarUsuario(repositorio).ejecutar(usuario.id, ModificarUsuarioDatos(nombre="Ana", apellido="P", email="a@ejemplo.com"))
