"""Datos inmutables: texto sensible fuera de representaciones y errores."""
from dataclasses import dataclass, field

from app.application.ia.exceptions import PromptInvalido, IARespuestaInvalida


@dataclass(frozen=True, slots=True, kw_only=True)
class ConsultaDatos:
    prompt: str = field(repr=False)


@dataclass(frozen=True, slots=True, kw_only=True)
class GeneracionEntrada:
    prompt: str = field(repr=False)
    max_output_tokens: int = field(default=256, init=False)
    context_tokens: int = field(default=4096, init=False)


@dataclass(frozen=True, slots=True, kw_only=True)
class GeneracionSalida:
    respuesta: str = field(repr=False)
    finalizacion: str = field(repr=False)


def _valid_text(value, max_chars: int, max_bytes: int) -> bool:
    if not isinstance(value, str) or not value.strip() or '\x00' in value or len(value) > max_chars:
        return False
    try:
        return len(value.encode('utf-8')) <= max_bytes
    except UnicodeError:
        return False


def validate_prompt(datos: ConsultaDatos) -> None:
    if not isinstance(datos, ConsultaDatos) or not _valid_text(datos.prompt, 1000, 3000):
        raise PromptInvalido()


def validate_output(result: GeneracionSalida) -> None:
    if (not isinstance(result, GeneracionSalida)
            or not _valid_text(result.respuesta, 4096, 16384)
            or type(result.finalizacion) is not str
            or result.finalizacion not in ('completa', 'limite')):
        raise IARespuestaInvalida()
