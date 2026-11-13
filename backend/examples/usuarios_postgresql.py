"""Demostración explícita en usuarios_test; desarrollo permanece intacto."""

from app.application.usuarios.dto import CrearUsuarioDatos, ModificarUsuarioDatos
from app.application.usuarios.use_cases.crear_usuario import CrearUsuario
from app.application.usuarios.use_cases.obtener_usuario import ObtenerUsuario
from app.application.usuarios.use_cases.modificar_usuario import ModificarUsuario
from app.application.usuarios.use_cases.dar_de_baja_usuario import DarDeBajaUsuario
from app.application.usuarios.use_cases.reactivar_usuario import ReactivarUsuario
from app.bootstrap import crear_persistencia_postgresql
from app.infrastructure.configuration.database import load_database_config
from uuid import uuid4


def main() -> None:
    config = load_database_config(testing=True)
    engine, repository = crear_persistencia_postgresql(config)
    try:
        user = CrearUsuario(repository).ejecutar(CrearUsuarioDatos(
            nombre="Ana", apellido="Pérez", email=f"demo-{uuid4().hex}@example.com",
        ))
        ModificarUsuario(repository).ejecutar(user.id, ModificarUsuarioDatos(
            nombre="Ana", apellido="Díaz", email=user.email,
        ))
        DarDeBajaUsuario(repository).ejecutar(user.id)
        ReactivarUsuario(repository).ejecutar(user.id)
        restored = ObtenerUsuario(repository).ejecutar(user.id)
        assert restored.id == user.id and restored.fecha_creacion == user.fecha_creacion
        print("ABMC PostgreSQL correcto en usuarios_test; UUID y fecha conservados.")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
