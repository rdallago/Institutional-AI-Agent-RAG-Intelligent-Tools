from dataclasses import replace

import pytest

from app.application.usuarios.dto import CrearUsuarioDatos, EstadoUsuarios, ListarUsuariosDatos, ModificarUsuarioDatos
from app.application.usuarios.exceptions import EmailEnUso, UsuarioActivoExistente, UsuarioInactivoReactivable
from app.application.usuarios.use_cases.crear_usuario import CrearUsuario
from app.application.usuarios.use_cases.dar_de_baja_usuario import DarDeBajaUsuario
from app.application.usuarios.use_cases.listar_usuarios import ListarUsuarios
from app.application.usuarios.use_cases.modificar_usuario import ModificarUsuario
from app.application.usuarios.use_cases.obtener_usuario import ObtenerUsuario
from app.application.usuarios.use_cases.reactivar_usuario import ReactivarUsuario
from app.domain.usuarios.exceptions import ApellidoInvalido
from app.infrastructure.persistence.repositories.in_memory_user_repository import InMemoryUserRepository


def test_ciclo_completo_y_reactivacion_explicita():
    repo = InMemoryUserRepository()
    crear, consultar, listar = CrearUsuario(repo), ObtenerUsuario(repo), ListarUsuarios(repo)
    ana = crear.ejecutar(CrearUsuarioDatos(nombre="Ana", apellido="Pérez", email="ANA@ejemplo.com"))
    assert consultar.ejecutar(ana.id) == ana
    with pytest.raises(UsuarioActivoExistente):
        crear.ejecutar(CrearUsuarioDatos(nombre="Otra", apellido="Persona", email=ana.email))
    modificado = ModificarUsuario(repo).ejecutar(ana.id,
        ModificarUsuarioDatos(nombre="Ana", apellido="Díaz", email=ana.email))
    inactivo = DarDeBajaUsuario(repo).ejecutar(ana.id)
    assert inactivo == replace(modificado, activo=False)
    assert DarDeBajaUsuario(repo).ejecutar(ana.id) == inactivo
    assert listar.ejecutar() == ()
    assert listar.ejecutar(ListarUsuariosDatos(estado=EstadoUsuarios.INACTIVOS)) == (inactivo,)
    with pytest.raises(UsuarioInactivoReactivable) as captura:
        crear.ejecutar(CrearUsuarioDatos(nombre="No reemplazar", apellido="Datos", email=ana.email))
    assert captura.value.usuario_id == ana.id
    assert consultar.ejecutar(ana.id) == inactivo
    assert ReactivarUsuario(repo).ejecutar(ana.id) == modificado
    assert ReactivarUsuario(repo).ejecutar(ana.id) == modificado
    assert listar.ejecutar(ListarUsuariosDatos(estado=EstadoUsuarios.TODOS)) == (modificado,)
    assert modificado.id == ana.id and modificado.fecha_creacion == ana.fecha_creacion


def test_errores_de_modificacion_no_cambian_datos_persistidos():
    repo = InMemoryUserRepository()
    crear = CrearUsuario(repo)
    ana = crear.ejecutar(CrearUsuarioDatos(nombre="Ana", apellido="P", email="ana@ejemplo.com"))
    otro = crear.ejecutar(CrearUsuarioDatos(nombre="Otra", apellido="P", email="otra@ejemplo.com"))
    DarDeBajaUsuario(repo).ejecutar(otro.id)
    modificar = ModificarUsuario(repo)
    with pytest.raises(EmailEnUso):
        modificar.ejecutar(ana.id, ModificarUsuarioDatos(nombre="Cambio", apellido="P", email=otro.email))
    assert ObtenerUsuario(repo).ejecutar(ana.id) == ana
    with pytest.raises(ApellidoInvalido):
        modificar.ejecutar(ana.id, ModificarUsuarioDatos(nombre="Cambio", apellido="", email=ana.email))
    assert ObtenerUsuario(repo).ejecutar(ana.id) == ana
