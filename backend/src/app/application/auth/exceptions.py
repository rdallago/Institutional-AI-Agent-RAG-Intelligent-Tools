class CredencialesInvalidas(Exception):
    pass


class AutenticacionRequerida(Exception):
    pass


class PermisoDenegado(Exception):
    pass


class CambioPasswordRequerido(Exception):
    pass


class PasswordInvalida(Exception):
    pass


class PasswordReutilizada(Exception):
    pass


class AprovisionamientoRechazado(Exception):
    pass


class AprovisionamientoNoHabilitado(Exception):
    pass


class CredencialExistente(Exception):
    pass


class UsuarioInactivoNoAprovisionable(Exception):
    pass


class LimiteIntentos(Exception):
    def __init__(self, retry_after: int):
        self.retry_after = max(1, retry_after)
        super().__init__("Límite temporal de intentos.")
