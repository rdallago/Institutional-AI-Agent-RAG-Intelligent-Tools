r"""Ejecutar desde backend: .\.venv\Scripts\python.exe examples\usuarios_en_memoria.py"""

from app.application.usuarios.dto import CrearUsuarioDatos, ModificarUsuarioDatos
from app.application.usuarios.exceptions import UsuarioInactivoReactivable
from app.application.usuarios.use_cases.crear_usuario import CrearUsuario
from app.application.usuarios.use_cases.dar_de_baja_usuario import DarDeBajaUsuario
from app.application.usuarios.use_cases.listar_usuarios import ListarUsuarios
from app.application.usuarios.use_cases.modificar_usuario import ModificarUsuario
from app.application.usuarios.use_cases.obtener_usuario import ObtenerUsuario
from app.application.usuarios.use_cases.reactivar_usuario import ReactivarUsuario
from app.infrastructure.persistence.repositories.in_memory_user_repository import InMemoryUserRepository


def main() -> None:
    repositorio = InMemoryUserRepository()
    crear = CrearUsuario(repositorio)
    ana = crear.ejecutar(CrearUsuarioDatos(nombre="Ana", apellido="Pérez", email="ANA@ejemplo.com"))
    print("Alta:", ana)
    print("Consulta:", ObtenerUsuario(repositorio).ejecutar(ana.id))
    ModificarUsuario(repositorio).ejecutar(
        ana.id, ModificarUsuarioDatos(nombre="Ana", apellido="Díaz", email=ana.email),
    )
    DarDeBajaUsuario(repositorio).ejecutar(ana.id)
    print("Activos después de la baja:", ListarUsuarios(repositorio).ejecutar())
    try:
        crear.ejecutar(CrearUsuarioDatos(nombre="Otra", apellido="Persona", email=ana.email))
    except UsuarioInactivoReactivable as error:
        print(error.codigo, error.usuario_id)
        # Confirmación explícita de este ejemplo; no es una reactivación automática del alta.
        reactivado = ReactivarUsuario(repositorio).ejecutar(error.usuario_id)
        assert reactivado.id == ana.id and reactivado.fecha_creacion == ana.fecha_creacion
        print("Reactivación explícita, misma identidad y fecha:", reactivado)


if __name__ == "__main__":
    main()
