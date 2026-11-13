from dataclasses import FrozenInstanceError

import pytest

from app.application.usuarios.dto import EstadoUsuarios, ListarUsuariosDatos
from app.application.usuarios.exceptions import FiltroEstadoInvalido, PaginacionInvalida
from app.application.usuarios.use_cases.listar_usuarios import ListarUsuarios


def test_listado_predeterminado_y_resultados_inmutables(repositorio, usuario):
    repositorio.listar.return_value = [usuario]
    resultado = ListarUsuarios(repositorio).ejecutar()
    repositorio.listar.assert_called_once_with(ListarUsuariosDatos())
    assert isinstance(resultado, tuple) and resultado[0].id == usuario.id
    with pytest.raises(FrozenInstanceError):
        resultado[0].activo = False
    usuario.dar_de_baja()
    assert resultado[0].activo is True


@pytest.mark.parametrize("estado", list(EstadoUsuarios))
def test_delega_filtro_y_pagina(repositorio, estado):
    consulta = ListarUsuariosDatos(estado=estado, limite=100, desplazamiento=2)
    assert ListarUsuarios(repositorio).ejecutar(consulta) == ()
    repositorio.listar.assert_called_once_with(consulta)


@pytest.mark.parametrize("campo,valor", [
    ("limite", 0), ("limite", 101), ("limite", -1), ("limite", True),
    ("limite", "20"), ("limite", 1.5), ("desplazamiento", -1),
    ("desplazamiento", False), ("desplazamiento", None), ("desplazamiento", 1.5),
])
def test_paginacion_invalida(campo, valor):
    with pytest.raises(PaginacionInvalida):
        ListarUsuariosDatos(**{campo: valor})


@pytest.mark.parametrize("estado", ["activos", "invalido", None, True])
def test_filtro_exige_enum(estado):
    with pytest.raises(FiltroEstadoInvalido):
        ListarUsuariosDatos(estado=estado)
