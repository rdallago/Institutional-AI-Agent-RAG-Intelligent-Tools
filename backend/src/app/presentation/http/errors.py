"""Errores públicos sin valores originales, SQL ni trazas sensibles."""

import logging
from pathlib import Path
from traceback import extract_tb
from uuid import UUID

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse

from app.application.usuarios.exceptions import (
    UsuarioNoEncontrado, UsuarioActivoExistente, UsuarioInactivoReactivable, EmailEnUso,
    FiltroEstadoInvalido, PaginacionInvalida,
)
from app.domain.usuarios.exceptions import NombreInvalido, ApellidoInvalido, EmailInvalido, RolInvalido
from app.application.auth.exceptions import CredencialesInvalidas, AutenticacionRequerida, PermisoDenegado, PasswordInvalida, LimiteIntentos
from app.application.auth.exceptions import CambioPasswordRequerido
from app.application.auth.exceptions import PasswordReutilizada
from app.application.auth.exceptions import AprovisionamientoNoHabilitado, CredencialExistente, UsuarioInactivoNoAprovisionable, AprovisionamientoRechazado
from app.application.agent.errors import ClimaNoDisponible, PlanificadorNoDisponible, MemoriaPlanificadorInsuficiente
from app.application.ia.exceptions import (PromptInvalido, IANoDisponible, IATiempoAgotado,
    IARespuestaInvalida, IAOcupada, IALimiteIntentos)


logger = logging.getLogger("app.http.errors")


class ErrorDetalle(BaseModel):
    campo: str
    codigo: str
    mensaje: str


class ErrorContenido(BaseModel):
    codigo: str
    mensaje: str
    usuario_id: UUID | None = None
    detalles: list[ErrorDetalle] | None = None


class ErrorRespuesta(BaseModel):
    error: ErrorContenido


PUBLIC_ERRORS = {
    PromptInvalido: (422, 'PROMPT_INVALIDO', 'La consulta no cumple los limites admitidos.', 'body.prompt'),
    IANoDisponible: (503, 'IA_NO_DISPONIBLE', 'El servicio IA no esta disponible.', None),
    ClimaNoDisponible: (503, 'CLIMA_NO_DISPONIBLE', 'El proveedor meteorologico no esta disponible.', None),
    PlanificadorNoDisponible: (503, 'IA_PLANIFICADOR_NO_DISPONIBLE', 'El planificador local no esta disponible.', None),
    MemoriaPlanificadorInsuficiente: (503, 'IA_MEMORIA_INSUFICIENTE', 'No hay memoria suficiente para interpretar la consulta con el modelo local.', None),
    IATiempoAgotado: (504, 'IA_TIEMPO_AGOTADO', 'Se agoto el tiempo de generacion.', None),
    IARespuestaInvalida: (502, 'IA_RESPUESTA_INVALIDA', 'El servicio IA no devolvio una respuesta valida.', None),
    AprovisionamientoNoHabilitado: (403, "APROVISIONAMIENTO_NO_HABILITADO", "El aprovisionamiento de credenciales iniciales aún no está habilitado.", None),
    CredencialExistente: (409, "CREDENCIAL_EXISTENTE", "El perfil ya tiene una credencial; no se puede reemplazar.", None),
    UsuarioInactivoNoAprovisionable: (409, "USUARIO_INACTIVO_NO_APROVISIONABLE", "El perfil debe estar activo para asignar una credencial inicial.", None),
    AprovisionamientoRechazado: (409, "CREDENCIAL_EXISTENTE", "No se pudo asignar una credencial inicial sin reemplazar datos existentes.", None),
    PasswordReutilizada: (422, "PASSWORD_REUTILIZADA", "Debe elegir una contraseña diferente de la actual y de la inicial.", "body.password_nueva"),
    CambioPasswordRequerido: (403, "CAMBIO_PASSWORD_REQUERIDO", "Debe cambiar su contraseña antes de continuar.", None),
    CredencialesInvalidas: (401, "CREDENCIALES_INVALIDAS", "No se pudo iniciar sesión con las credenciales proporcionadas.", None),
    AutenticacionRequerida: (401, "AUTENTICACION_REQUERIDA", "Se requiere una sesión válida.", None),
    PermisoDenegado: (403, "PERMISO_DENEGADO", "No tiene permiso para realizar esta operación.", None),
    PasswordInvalida: (422, "PASSWORD_INVALIDA", "La contraseña no cumple la política de seguridad.", "body.password_nueva"),
    NombreInvalido: (422, "NOMBRE_INVALIDO", "El nombre debe contener entre 1 y 100 caracteres.", "body.nombre"),
    ApellidoInvalido: (422, "APELLIDO_INVALIDO", "El apellido debe contener entre 1 y 100 caracteres.", "body.apellido"),
    EmailInvalido: (422, "EMAIL_INVALIDO", "El email no cumple el formato admitido.", "body.email"),
    RolInvalido: (422, "ROL_INVALIDO", "El rol debe ser ADMIN o USUARIO.", "body.rol"),
    FiltroEstadoInvalido: (422, "FILTRO_ESTADO_INVALIDO", "El estado del filtro no es válido.", "query.estado"),
    PaginacionInvalida: (422, "PAGINACION_INVALIDA", "El límite debe estar entre 1 y 100 y el desplazamiento no puede ser negativo.", "query"),
    UsuarioNoEncontrado: (404, "USUARIO_NO_ENCONTRADO", "El usuario no existe.", None),
    UsuarioActivoExistente: (409, "USUARIO_ACTIVO_EXISTENTE", "Ya existe un usuario activo con ese email.", None),
    UsuarioInactivoReactivable: (409, "USUARIO_INACTIVO_REACTIVABLE", "El usuario está dado de baja y puede reactivarse explícitamente.", None),
    EmailEnUso: (409, "EMAIL_EN_USO", "El email pertenece a otro usuario.", None),
}


def error_response(status: int, code: str, message: str, *, user_id=None, details=None) -> JSONResponse:
    body = ErrorRespuesta(error=ErrorContenido(codigo=code, mensaje=message, usuario_id=user_id, detalles=details))
    return JSONResponse(status_code=status, content=body.model_dump(mode="json", exclude_none=True))


async def public_error_handler(request: Request, exc: Exception) -> JSONResponse:
    status, code, message, field = PUBLIC_ERRORS[type(exc)]
    if request.url.path.startswith('/api/v1/ia/'):
        logger.warning('ia_http status=%d code=%s', status, code)
    if isinstance(exc, PasswordInvalida) and request.url.path.startswith("/api/v1/usuarios"):
        field = "body.password_inicial"
    details = [ErrorDetalle(campo=field, codigo=code, mensaje=message)] if field else None
    user_id = exc.usuario_id if isinstance(exc, (UsuarioNoEncontrado, UsuarioInactivoReactivable)) else None
    response = error_response(status, code, message, user_id=user_id, details=details)
    if status == 401:
        response.headers["WWW-Authenticate"] = "Bearer"
    return response


async def rate_limit_handler(request: Request, exc: LimiteIntentos):
    response = error_response(429, "LIMITE_INTENTOS", "Demasiados intentos; espere antes de reintentar.")
    response.headers["Retry-After"] = str(exc.retry_after)
    return response


async def ia_admission_handler(request: Request, exc):
    import logging
    code = 'IA_OCUPADA' if isinstance(exc, IAOcupada) else 'IA_LIMITE_INTENTOS'
    logging.getLogger('app.agent').warning('agent_admission code=%s retry_after=%d', code, exc.retry_after)
    response = error_response(429, code, 'No se puede admitir otra consulta IA; espere antes de reintentar.')
    response.headers['Retry-After'] = str(exc.retry_after)
    return response


async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    # Ni mensajes de validadores arbitrarios, ni input/ctx, ni nombres de campos desconocidos.
    allowed = {"body", "query", "path", "id", "nombre", "apellido", "email", "rol", "estado", "limite", "desplazamiento", "prompt"}
    details = []
    for item in exc.errors():
        location = ".".join(str(part) if part in allowed else "campo" for part in item.get("loc", ()))
        details.append(ErrorDetalle(campo=location, codigo="DATO_INVALIDO", mensaje="Campo ausente, adicional o con formato inválido."))
    return error_response(422, "SOLICITUD_INVALIDA", "La solicitud contiene datos inválidos.", details=details)


def log_internal(request: Request, exc: Exception, code: str) -> None:
    route = getattr(request.scope.get("route"), "path", "ruta_no_resuelta")
    # Solo ubicaciones de código: nunca mensaje, repr, SQL, cuerpo o variables locales.
    frames = ",".join(f"{Path(frame.filename).name}:{frame.lineno}:{frame.name}" for frame in extract_tb(exc.__traceback__))
    logger.error("codigo=%s tipo=%s metodo=%s ruta=%s ubicaciones=%s", code, type(exc).__name__, request.method, route, frames)


async def persistence_error_handler(request: Request, exc: Exception) -> JSONResponse:
    log_internal(request, exc, "ERROR_PERSISTENCIA")
    return error_response(500, "ERROR_PERSISTENCIA", "No se pudo completar la operación de persistencia.")


async def unexpected_error_handler(request: Request, exc: Exception) -> JSONResponse:
    log_internal(request, exc, "ERROR_INTERNO")
    return error_response(500, "ERROR_INTERNO", "No se pudo completar la operación.")


async def http_error_handler(request: Request, exc: HTTPException) -> JSONResponse:
    if exc.status_code >= 500:
        return await unexpected_error_handler(request, exc)
    code = "RUTA_NO_ENCONTRADA" if exc.status_code == 404 else "ERROR_HTTP"
    response = error_response(exc.status_code, code, "La ruta no existe." if exc.status_code == 404 else "La solicitud no pudo procesarse.")
    if exc.status_code == 405:
        response.headers["Allow"] = (exc.headers or {}).get("Allow", "")
    return response


def register_error_handlers(app: FastAPI) -> None:
    @app.middleware("http")
    async def internal_failure_boundary(request: Request, call_next):
        # Evitar que ServerErrorMiddleware vuelva a lanzar la excepción original
        # y que el servidor registre su mensaje/SQL después de responder 500.
        try:
            response = await call_next(request)
        except Exception as exc:
            response = await unexpected_error_handler(request, exc)
        if request.url.path.startswith("/api/v1/auth/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    for exception in PUBLIC_ERRORS:
        app.add_exception_handler(exception, public_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(HTTPException, http_error_handler)
    app.add_exception_handler(Exception, unexpected_error_handler)
    app.add_exception_handler(LimiteIntentos, rate_limit_handler)
    app.add_exception_handler(IAOcupada, ia_admission_handler)
    app.add_exception_handler(IALimiteIntentos, ia_admission_handler)


def documented_errors(*statuses: int) -> dict:
    responses = {status: {
        "model": ErrorRespuesta,
        "description": {401: "Autenticación requerida", 403: "Permiso denegado", 404: "Usuario inexistente", 409: "Conflicto de negocio", 413: 'Cuerpo excesivo', 422: "Solicitud inválida", 429: "Límite de intentos; Retry-After en segundos", 500: "Error interno saneado", 502: 'Respuesta IA invalida', 503: 'Servicio IA no disponible', 504: 'Timeout IA'}[status],
        "content": {"application/json": {"example": {"error": {
            "codigo": {401: "AUTENTICACION_REQUERIDA", 403: "PERMISO_DENEGADO", 404: "USUARIO_NO_ENCONTRADO", 409: "EMAIL_EN_USO", 413: 'SOLICITUD_DEMASIADO_GRANDE', 422: "SOLICITUD_INVALIDA", 429: "LIMITE_INTENTOS", 500: "ERROR_INTERNO", 502: 'IA_RESPUESTA_INVALIDA', 503: 'IA_NO_DISPONIBLE', 504: 'IA_TIEMPO_AGOTADO'}[status],
            "mensaje": "Descripción pública del error.",
        }}}},
    } for status in statuses}
    for status, header in ((401, "WWW-Authenticate"), (429, "Retry-After")):
        if status in responses:
            responses[status]["headers"] = {header: {"schema": {"type": "string"},
                "description": "Bearer" if status == 401 else "Segundos antes de reintentar"}}
    return responses
