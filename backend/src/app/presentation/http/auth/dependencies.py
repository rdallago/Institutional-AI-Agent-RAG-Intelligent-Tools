from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.application.auth.exceptions import AutenticacionRequerida
from app.application.auth.service import AuthService, Principal


bearer = HTTPBearer(auto_error=False, scheme_name="BearerAuth", description="JWT de acceso obtenido mediante POST /api/v1/auth/login")


def get_auth_service(request: Request) -> AuthService:
    return request.app.state.auth_service


def get_token(credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]) -> str:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise AutenticacionRequerida()
    return credentials.credentials


def get_current_user(token: Annotated[str, Depends(get_token)],
    service: Annotated[AuthService, Depends(get_auth_service)]) -> Principal:
    return service.authenticate(token)


def get_valid_session(token: Annotated[str, Depends(get_token)],
    service: Annotated[AuthService, Depends(get_auth_service)]) -> Principal:
    return service.authenticate_session(token)
