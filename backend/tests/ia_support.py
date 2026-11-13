"""Proveedor determinista exclusivamente de pruebas; sin red ni configuracion."""
import asyncio

from app.application.ia.dto import GeneracionSalida
from app.application.ia.exceptions import IANoDisponible, IARespuestaInvalida


SENSITIVE = 'fictional-sensitive-content-sentinel'


class FakeLLMProvider:
    def __init__(self, *, mode='success', output=None, hook=None, blocked=False):
        self.mode, self.hook, self.blocked = mode, hook, blocked
        self.output = output if output is not None else GeneracionSalida(respuesta='Respuesta ficticia.', finalizacion='completa')
        self.inputs = []
        self.started, self.resume = asyncio.Event(), asyncio.Event()
        self.cancelled = False

    async def generate(self, input):
        self.inputs.append(input)
        self.started.set()
        try:
            if self.blocked:
                await self.resume.wait()
            if self.hook:
                await self.hook()
            if self.mode == 'timeout': raise TimeoutError(SENSITIVE)
            if self.mode == 'unavailable':
                error = IANoDisponible()
                error.args = (SENSITIVE,)
                raise error
            if self.mode == 'invalid':
                error = IARespuestaInvalida()
                error.args = (SENSITIVE,)
                raise error
            if self.mode == 'unexpected': raise RuntimeError(SENSITIVE)
            if self.mode == 'cancel': raise asyncio.CancelledError()
            return self.output
        except asyncio.CancelledError:
            self.cancelled = True
            raise


class FakeAuthorizer:
    def __init__(self, *, error=None):
        self.error, self.calls = error, 0

    async def require_normal(self, principal):
        self.calls += 1
        if self.error: raise self.error()


class ControlledClock:
    def __init__(self, now=0.0): self.now = now
    def __call__(self): return self.now
