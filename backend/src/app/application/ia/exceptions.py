"""Errores publicos sin mensajes recibidos del proveedor ni contenido del usuario."""


class ErrorIA(Exception):
    mensaje = "No se pudo completar la consulta IA."

    def __init__(self):
        super().__init__(self.mensaje)


class PromptInvalido(ErrorIA):
    mensaje = "La consulta no cumple los limites admitidos."


class IANoDisponible(ErrorIA):
    mensaje = "El proveedor IA no esta disponible."


class IATiempoAgotado(ErrorIA):
    mensaje = "Se agoto el tiempo de generacion."


class IARespuestaInvalida(ErrorIA):
    mensaje = "El proveedor IA no devolvio una respuesta valida."


class RechazoAdmision(ErrorIA):
    def __init__(self, retry_after: int):
        if type(retry_after) is not int or retry_after < 1:
            raise ValueError("Espera de admision invalida.")
        self.retry_after = retry_after
        super().__init__()


class IAOcupada(RechazoAdmision):
    mensaje = "El servicio IA esta ocupado temporalmente."


class IALimiteIntentos(RechazoAdmision):
    mensaje = "Se alcanzo el limite temporal de consultas IA."
