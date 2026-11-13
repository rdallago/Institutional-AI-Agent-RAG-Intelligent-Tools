from uuid import uuid4

import pytest

from app.application.usuarios.dto import UsuarioResultado
from app.application.usuarios.exceptions import UsuarioNoEncontrado
from app.application.usuarios.ports.user_repository import UsuarioAusenteRepositorio
from app.application.usuarios.use_cases.dar_de_baja_usuario import DarDeBajaUsuario
from app.application.usuarios.use_cases.reactivar_usuario import ReactivarUsuario


@pytest.mark.parametrize("caso,estado", [(DarDeBajaUsuario, False), (ReactivarUsuario, True)])
@pytest.mark.parametrize("inicial", [True, False])
def test_transicion_idempotencia_y_conservacion(repositorio, usuario, caso, estado, inicial):
    if not inicial:
        usuario.dar_de_baja()
    antes = UsuarioResultado.desde_entidad(usuario)
    repositorio.obtener_por_id.return_value = usuario
    operacion = caso(repositorio)
    resultado = operacion.ejecutar(usuario.id)
    assert resultado.activo is estado
    assert (resultado.id, resultado.email, resultado.fecha_creacion, resultado.nombre, resultado.apellido, resultado.rol) == (
        antes.id, antes.email, antes.fecha_creacion, antes.nombre, antes.apellido, antes.rol)
    assert repositorio.actualizar.call_count == int(inicial != estado)
    operacion.ejecutar(usuario.id)
    assert repositorio.actualizar.call_count == int(inicial != estado)
    repositorio.agregar.assert_not_called()


@pytest.mark.parametrize("caso", [DarDeBajaUsuario, ReactivarUsuario])
def test_transicion_inexistente(repositorio, caso):
    with pytest.raises(UsuarioNoEncontrado):
        caso(repositorio).ejecutar(uuid4())
    repositorio.actualizar.assert_not_called()
    repositorio.agregar.assert_not_called()


@pytest.mark.parametrize("caso", [DarDeBajaUsuario, ReactivarUsuario])
def test_traduce_ausencia_en_escritura(repositorio, usuario, caso):
    if caso is ReactivarUsuario:
        usuario.dar_de_baja()
    repositorio.obtener_por_id.return_value = usuario
    repositorio.actualizar.side_effect = UsuarioAusenteRepositorio()
    with pytest.raises(UsuarioNoEncontrado):
        caso(repositorio).ejecutar(usuario.id)
