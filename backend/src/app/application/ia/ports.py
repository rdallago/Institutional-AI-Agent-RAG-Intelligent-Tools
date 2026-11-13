from typing import Protocol

from app.application.auth.service import Principal
from app.application.ia.dto import GeneracionEntrada, GeneracionSalida


class LLMProvider(Protocol):
    async def generate(self, input: GeneracionEntrada) -> GeneracionSalida: ...


class NormalAccessAuthorizer(Protocol):
    async def require_normal(self, principal: Principal) -> None: ...


class GenerationLease(Protocol):
    def release(self, *, timed_out: bool = False) -> None:
        """Liberacion sin await, idempotente y no fallable para una concesion valida."""
        ...


class GenerationAdmission(Protocol):
    def try_acquire(self, principal: Principal) -> GenerationLease:
        """Adquirir y consumir cuotas atomicamente, sin espera ni I/O."""
        ...
