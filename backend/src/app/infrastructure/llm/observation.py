"""Evento tecnico acotado: sin cuerpos, identidades, headers ni excepciones."""
from dataclasses import asdict, dataclass
import json


@dataclass(frozen=True, slots=True)
class GenerationMetadata:
    http_status: int | None
    model_matches: bool
    done_valid: bool
    done_reason: str
    think_requested: bool
    thinking_present: bool
    duration_seconds: float
    response_bytes: int

    def emit(self) -> None:
        # No logger con exc_info, objetos request/response o metadatos heredados.
        try:
            print(json.dumps(asdict(self), allow_nan=False), flush=True)
        except Exception:
            # Un fallo del destino de observacion no cambia la generacion ni filtra causas.
            pass
