from uuid import uuid4

import pytest

from app.application.usuarios.exceptions import UsuarioNoEncontrado
from app.application.usuarios.use_cases.obtener_usuario import ObtenerUsuario
from app.domain.usuarios.exceptions import IdentificadorUsuarioInvalido


@pytest.mark.parametrize("activo", [True, False])
def test_consulta_ambos_estados(repositorio, usuario, activo):
    if not activo:
        usuario.dar_de_baja()
    repositorio.obtener_por_id.return_value = usuario
    resultado = ObtenerUsuario(repositorio).ejecutar(usuario.id)
    assert resultado.id == usuario.id and resultado.activo is activo
    repositorio.agregar.assert_not_called()
    repositorio.actualizar.assert_not_called()


def test_consulta_inexistente(repositorio):
    id = uuid4()
    with pytest.raises(UsuarioNoEncontrado) as captura:
        ObtenerUsuario(repositorio).ejecutar(id)
    assert captura.value.usuario_id == id
    repositorio.actualizar.assert_not_called()


@pytest.mark.parametrize("id", [None, "no-uuid", 1])
def test_identificador_invalido_no_consulta(repositorio, id):
    with pytest.raises(IdentificadorUsuarioInvalido):
        ObtenerUsuario(repositorio).ejecutar(id)
    assert repositorio.mock_calls == []
