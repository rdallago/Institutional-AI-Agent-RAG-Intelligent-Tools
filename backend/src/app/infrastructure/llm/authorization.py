import asyncio

from app.application.auth.service import AuthService, Principal


class AuthServiceNormalAccessAuthorizer:
    def __init__(self, service: AuthService):
        self._service = service

    async def require_normal(self, principal: Principal) -> None:
        # La UoW abre/cierra en el mismo hilo antes de retornar al caso de uso.
        await asyncio.to_thread(self._service.require_normal_access, principal)
