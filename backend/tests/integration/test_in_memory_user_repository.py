from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from threading import Barrier
from uuid import UUID, uuid4

import pytest

from app.application.usuarios.dto import EstadoUsuarios, ListarUsuariosDatos
from app.application.usuarios.ports.user_repository import (
    EmailDuplicadoRepositorio, IdentidadDuplicadaRepositorio, UserRepository, UsuarioAusenteRepositorio,
)
from app.domain.usuarios.email import Email
from app.domain.usuarios.rol import Rol
from app.domain.usuarios.usuario import Usuario
from app.infrastructure.persistence.repositories.in_memory_user_repository import InMemoryUserRepository


def nuevo(email="ana@ejemplo.com"):
    return Usuario.crear(nombre="Ana", apellido="Pérez", email=Email(email))


def test_contrato_es_abstracto_y_repo_vacio():
    with pytest.raises(TypeError):
        UserRepository()
    repo = InMemoryUserRepository()
    assert isinstance(repo, UserRepository)
    assert repo.obtener_por_id(uuid4()) is None
    assert repo.obtener_por_email(Email("a@ejemplo.com")) is None
    assert repo.listar(ListarUsuariosDatos()) == []


def test_copias_independientes_en_todas_las_fronteras():
    repo = InMemoryUserRepository()
    usuario = nuevo()
    repo.agregar(usuario)
    usuario.dar_de_baja()
    for recuperado in [repo.obtener_por_id(usuario.id), repo.obtener_por_email(usuario.email), repo.listar(ListarUsuariosDatos())[0]]:
        assert recuperado.activo
        recuperado.dar_de_baja()
        assert repo.obtener_por_id(usuario.id).activo
    repo.actualizar(usuario)
    usuario.reactivar()
    assert not repo.obtener_por_id(usuario.id).activo


@pytest.mark.parametrize("activo", [True, False])
def test_email_globalmente_unico_y_escritura_fallida_sin_cambios(activo):
    repo = InMemoryUserRepository()
    original = nuevo()
    if not activo:
        original.dar_de_baja()
    repo.agregar(original)
    with pytest.raises(EmailDuplicadoRepositorio) as captura:
        repo.agregar(nuevo("ANA@ejemplo.com"))
    assert captura.value.usuario_id == original.id and captura.value.activo is activo
    otro = nuevo("otro@ejemplo.com")
    repo.agregar(otro)
    otro.modificar_datos(nombre="Modificado", apellido="X", email=original.email)
    with pytest.raises(EmailDuplicadoRepositorio):
        repo.actualizar(otro)
    guardado = repo.obtener_por_id(otro.id)
    assert guardado.nombre == "Ana" and str(guardado.email) == "otro@ejemplo.com"
    assert len(repo.listar(ListarUsuariosDatos(estado=EstadoUsuarios.TODOS))) == 2


def test_identidad_duplicada_y_actualizacion_ausente_no_insertan():
    repo = InMemoryUserRepository()
    usuario = nuevo()
    with pytest.raises(UsuarioAusenteRepositorio):
        repo.actualizar(usuario)
    assert repo.listar(ListarUsuariosDatos()) == []
    repo.agregar(usuario)
    usuario.dar_de_baja()
    with pytest.raises(IdentidadDuplicadaRepositorio):
        repo.agregar(usuario)
    assert repo.obtener_por_id(usuario.id).activo


def test_actualizacion_libera_email_anterior_y_admite_email_propio():
    repo = InMemoryUserRepository()
    usuario = nuevo()
    repo.agregar(usuario)
    repo.actualizar(usuario)
    usuario.modificar_datos(nombre="Ana", apellido="P", email=Email("nuevo@ejemplo.com"))
    repo.actualizar(usuario)
    repo.agregar(nuevo())
    assert repo.obtener_por_email(Email("nuevo@ejemplo.com")).id == usuario.id


def test_filtra_antes_de_paginar_y_usa_orden_estable():
    repo = InMemoryUserRepository()
    fecha = datetime(2024, 1, 1, tzinfo=UTC)
    for numero in [4, 3, 2, 1]:
        repo.agregar(Usuario.reconstruir(id=UUID(int=numero), nombre="Ana", apellido="P",
            email=Email(f"a{numero}@ejemplo.com"), activo=numero % 2 == 0, rol=Rol.USUARIO, fecha_creacion=fecha))
    assert [u.id.int for u in repo.listar(ListarUsuariosDatos())] == [2, 4]
    assert [u.id.int for u in repo.listar(ListarUsuariosDatos(estado=EstadoUsuarios.INACTIVOS))] == [1, 3]
    assert [u.id.int for u in repo.listar(ListarUsuariosDatos(estado=EstadoUsuarios.TODOS, limite=2, desplazamiento=1))] == [2, 3]
    assert [u.id.int for u in repo.listar(ListarUsuariosDatos(limite=1, desplazamiento=1))] == [4]
    assert repo.listar(ListarUsuariosDatos(desplazamiento=10)) == []


@pytest.mark.parametrize("operacion", ["agregar", "actualizar"])
def test_escrituras_concurrentes_no_duplican_email(operacion):
    repo = InMemoryUserRepository()
    barrera = Barrier(8)
    usuarios = [nuevo(f"a{i}@ejemplo.com") for i in range(8)]
    if operacion == "actualizar":
        for usuario in usuarios:
            repo.agregar(usuario)

    def escribir(usuario):
        usuario.modificar_datos(nombre="Ana", apellido="P", email=Email("compartido@ejemplo.com"))
        barrera.wait(timeout=10)
        try:
            getattr(repo, operacion)(usuario)
            return True
        except EmailDuplicadoRepositorio:
            return False

    with ThreadPoolExecutor(max_workers=8) as pool:
        resultados = list(pool.map(escribir, usuarios))
    assert sum(resultados) == 1
    todos = repo.listar(ListarUsuariosDatos(estado=EstadoUsuarios.TODOS))
    assert len(todos) == (8 if operacion == "actualizar" else 1)
    assert sum(u.email == Email("compartido@ejemplo.com") for u in todos) == 1
