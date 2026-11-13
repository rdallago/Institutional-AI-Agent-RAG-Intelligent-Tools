"""Errores de invariantes del dominio, independientes del transporte HTTP."""


class ErrorDominioUsuario(ValueError):
    """Base de los errores de validación de usuarios."""


class NombreInvalido(ErrorDominioUsuario):
    """El nombre no cumple las reglas del dominio."""


class ApellidoInvalido(ErrorDominioUsuario):
    """El apellido no cumple las reglas del dominio."""


class EmailInvalido(ErrorDominioUsuario):
    """La dirección no pertenece al formato admitido."""


class RolInvalido(ErrorDominioUsuario):
    """El rol no es un miembro de Rol."""


class EstadoUsuarioInvalido(ErrorDominioUsuario):
    """El estado no es booleano."""


class FechaCreacionInvalida(ErrorDominioUsuario):
    """La fecha no es un datetime con zona horaria."""


class IdentificadorUsuarioInvalido(ErrorDominioUsuario):
    """El identificador no es UUID."""
