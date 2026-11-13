import asyncio
import math

from app.application.auth.service import Principal
from app.application.ia.dto import ConsultaDatos, GeneracionEntrada, GeneracionSalida, validate_prompt, validate_output
from app.application.ia.exceptions import IANoDisponible, IATiempoAgotado, IARespuestaInvalida, IAOcupada
from app.application.ia.ports import LLMProvider, NormalAccessAuthorizer, GenerationAdmission


class GenerarRespuesta:
    def __init__(self, provider: LLMProvider, authorizer: NormalAccessAuthorizer,
                 admission: GenerationAdmission, *, timeout_seconds: float = 60):
        if (type(timeout_seconds) not in (int, float) or not math.isfinite(timeout_seconds)
                or not 0 < timeout_seconds <= 60):
            raise ValueError("Deadline IA invalido.")
        self._provider, self._authorizer, self._admission = provider, authorizer, admission
        self._timeout = timeout_seconds

    async def ejecutar(self, principal: Principal, datos: ConsultaDatos) -> GeneracionSalida:
        await self._authorizer.require_normal(principal)
        validate_prompt(datos)
        lease = self._admission.try_acquire(principal)
        timed_out = False
        try:
            try:
                async with asyncio.timeout(self._timeout):
                    result = await self._provider.generate(GeneracionEntrada(prompt=datos.prompt))
            except (TimeoutError, IATiempoAgotado):
                timed_out = True
                raise IATiempoAgotado() from None
            except IANoDisponible:
                # Reconstruir: ni argumentos ni causas arbitrarias de un proveedor.
                raise IANoDisponible() from None
            except IARespuestaInvalida:
                raise IARespuestaInvalida() from None
            except IAOcupada as error:
                raise IAOcupada(retry_after=error.retry_after) from None
            except Exception:
                raise IARespuestaInvalida() from None
            validate_output(result)
            await self._authorizer.require_normal(principal)
            return result
        finally:
            lease.release(timed_out=timed_out)
