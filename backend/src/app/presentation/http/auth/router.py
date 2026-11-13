from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, ConfigDict, SecretStr, StrictStr, Field

from app.application.auth.service import AuthService, Principal, CambioPasswordResultado
from app.presentation.http.auth.dependencies import get_auth_service, get_valid_session, get_token
from app.presentation.http.errors import documented_errors
from app.presentation.http.usuarios.schemas import UsuarioRespuesta
from app.presentation.http.usuarios.mappers import usuario_respuesta


class LoginSolicitud(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: StrictStr
    password: SecretStr = Field(min_length=1, max_length=128)


class PasswordSolicitud(BaseModel):
    model_config = ConfigDict(extra="forbid")
    password_actual: SecretStr = Field(min_length=1, max_length=128)
    password_nueva: SecretStr = Field(min_length=15, max_length=128)


class TokenRespuesta(BaseModel):
    access_token: str = Field(description="JWT de acceso; no guardarlo en logs ni compartirlo.")
    token_type: str = "bearer"
    expires_in: int = 900
    debe_cambiar_password: bool


class PerfilAuthRespuesta(UsuarioRespuesta):
    debe_cambiar_password: Literal[False]


class CambioPasswordRespuesta(BaseModel):
    id: UUID
    debe_cambiar_password: Literal[True]


AuthRespuesta = Annotated[PerfilAuthRespuesta | CambioPasswordRespuesta,
                          Field(discriminator="debe_cambiar_password")]


router = APIRouter(prefix="/api/v1/auth", tags=["Autenticación"])
Service = Annotated[AuthService, Depends(get_auth_service)]
ValidSession = Annotated[Principal, Depends(get_valid_session)]


@router.post("/login", response_model=TokenRespuesta, operation_id="login",
    description="Login JSON. Misma respuesta para email ausente, contraseña incorrecta, perfil sin credencial o inactivo. Token válido 900 segundos.",
    responses=documented_errors(401, 422, 429, 500))
def login(body: LoginSolicitud, request: Request, response: Response, service: Service):
    result = service.login(body.email, body.password.get_secret_value(), request.client.host if request.client else "unknown")
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    return TokenRespuesta(access_token=result.access_token, token_type=result.token_type,
                          expires_in=result.expires_in, debe_cambiar_password=result.debe_cambiar_password)


@router.get("/me", response_model=AuthRespuesta, operation_id="auth_me", responses=documented_errors(401, 500),
    description="Perfil propio normal o contexto mínimo id/debe_cambiar_password si hay cambio pendiente. Estado validado en backend.")
def me(principal: ValidSession, service: Service):
    result = service.me(principal)
    if isinstance(result, CambioPasswordResultado):
        return CambioPasswordRespuesta(id=result.id, debe_cambiar_password=True)
    return PerfilAuthRespuesta(**usuario_respuesta(result).model_dump(), debe_cambiar_password=False)


@router.post("/logout", status_code=204, response_class=Response, response_model=None, operation_id="logout",
    responses=documented_errors(401, 500), description="Revoca la sesión del token. Repetir con el mismo token firmado y vigente devuelve 204.")
def logout(token: Annotated[str, Depends(get_token)], service: Service):
    service.logout(token)
    return Response(status_code=204)


@router.put("/password", status_code=204, response_class=Response, response_model=None, operation_id="cambiar_password",
    responses=documented_errors(401, 422, 429, 500), description="Exige contraseña actual, rechaza reutilización actual/inicial y aplica límites compartidos con login. Revoca todas las sesiones y requiere un nuevo login.")
def change_password(body: PasswordSolicitud, request: Request, principal: ValidSession, service: Service):
    service.change_password(principal, body.password_actual.get_secret_value(), body.password_nueva.get_secret_value(),
                            ip=request.client.host if request.client else "unknown")
    return Response(status_code=204)
