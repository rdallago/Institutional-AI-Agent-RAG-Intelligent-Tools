from typing import Annotated

from fastapi import Depends, Request

from app.application.usuarios.ports.user_repository import UserRepository
from app.presentation.http.auth.dependencies import get_auth_service, get_current_user
from app.application.auth.service import AuthService, Principal


def get_repository(request: Request) -> UserRepository:
    return request.app.state.user_repository


Repository = Annotated[UserRepository, Depends(get_repository)]
Service = Annotated[AuthService, Depends(get_auth_service)]
Current = Annotated[Principal, Depends(get_current_user)]


class AuthorizedCase:
    def __init__(self, service, principal, action):
        self.service, self.principal, self.action = service, principal, action

    def ejecutar(self, *args):
        return self.service.manage(self.principal, self.action, *args)


def get_crear_usuario(service: Service, principal: Current):
    return AuthorizedCase(service, principal, "crear")


def get_listar_usuarios(service: Service, principal: Current):
    return AuthorizedCase(service, principal, "listar")


def get_obtener_usuario(service: Service, principal: Current):
    return AuthorizedCase(service, principal, "obtener")


def get_modificar_usuario(service: Service, principal: Current):
    return AuthorizedCase(service, principal, "modificar")


def get_dar_de_baja_usuario(service: Service, principal: Current):
    return AuthorizedCase(service, principal, "baja")


def get_reactivar_usuario(service: Service, principal: Current):
    return AuthorizedCase(service, principal, "reactivar")
