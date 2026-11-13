"""Errores de aplicación, sin dependencias HTTP."""

from uuid import UUID


class ErrorAplicacionUsuario(Exception):
    """Base de errores de los casos de uso."""


class UsuarioNoEncontrado(ErrorAplicacionUsuario):
    codigo = "USUARIO_NO_ENCONTRADO"

    def __init__(self, usuario_id: UUID):
        self.usuario_id = usuario_id
        super().__init__(f"No existe el usuario {usuario_id}.")


class UsuarioActivoExistente(ErrorAplicacionUsuario):
    codigo = "USUARIO_ACTIVO_EXISTENTE"

    def __init__(self):
        super().__init__("Ya existe un usuario activo con ese email.")


class UsuarioInactivoReactivable(ErrorAplicacionUsuario):
    codigo = "USUARIO_INACTIVO_REACTIVABLE"

    def __init__(self, usuario_id: UUID):
        self.usuario_id = usuario_id
        super().__init__("El usuario está dado de baja y puede reactivarse explícitamente.")


class EmailEnUso(ErrorAplicacionUsuario):
    codigo = "EMAIL_EN_USO"

    def __init__(self):
        super().__init__("El email pertenece a otro usuario.")


class PaginacionInvalida(ErrorAplicacionUsuario, ValueError):
    pass


class FiltroEstadoInvalido(ErrorAplicacionUsuario, ValueError):
    pass
