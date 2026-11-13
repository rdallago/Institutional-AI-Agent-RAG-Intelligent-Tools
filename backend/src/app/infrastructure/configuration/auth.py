import base64
import json
import os
from dataclasses import dataclass, field

from dotenv import dotenv_values

from app.infrastructure.configuration.database import PROJECT_ROOT


@dataclass(frozen=True, slots=True)
class AuthConfig:
    keys: dict[str, bytes] = field(repr=False)
    active_kid: str
    limiter_key: bytes = field(repr=False)
    issuer: str = "api-usuarios-clean"
    audience: str = "api-usuarios-clean-api"

    def __post_init__(self):
        if not self.keys or self.active_kid not in self.keys or any(not isinstance(k, str) or not k or not isinstance(v, bytes) or len(v) < 32 for k, v in self.keys.items()):
            raise ValueError("Configuración de claves JWT inválida.")
        if (not isinstance(self.limiter_key, bytes) or len(self.limiter_key) < 32
            or self.limiter_key in self.keys.values() or not isinstance(self.issuer, str)
            or not isinstance(self.audience, str) or not self.issuer or not self.audience):
            raise ValueError("Configuración de autenticación inválida.")


def load_auth_config(*, testing=False) -> AuthConfig:
    prefix = "TEST_AUTH_" if testing else "AUTH_"
    path = PROJECT_ROOT / (".env.test" if testing else ".env")
    values = dict(dotenv_values(path, interpolate=False)) if path.exists() else {}
    values.update({k: v for k, v in os.environ.items() if k.startswith(prefix)})
    try:
        encoded = json.loads(values[prefix + "JWT_KEYS_JSON"])
        keys = {k: base64.b64decode(v, validate=True) for k, v in encoded.items()}
        return AuthConfig(keys, values[prefix + "JWT_CURRENT_KID"],
            base64.b64decode(values[prefix + "LIMITER_KEY"], validate=True),
            values.get(prefix + "JWT_ISSUER") or "api-usuarios-clean",
            values.get(prefix + "JWT_AUDIENCE") or "api-usuarios-clean-api")
    except Exception:
        raise ValueError("Configurar claves externas de autenticación; no hay claves predeterminadas.") from None
