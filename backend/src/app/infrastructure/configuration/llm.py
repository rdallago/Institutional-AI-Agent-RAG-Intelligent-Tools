"""Configuracion IA separada; pruebas sin fallback al entorno operativo."""
from dataclasses import dataclass, field, replace
import math
import os
from pathlib import Path

from dotenv import dotenv_values


BASE_URL = 'http://127.0.0.1:11434'
MODEL = 'qwen3:1.7b'
PROJECT_ROOT = Path(__file__).resolve().parents[5]


class LLMConfigInvalida(ValueError):
    def __init__(self):
        super().__init__('Configuracion LLM no autorizada o invalida.')


@dataclass(frozen=True, slots=True, kw_only=True)
class LLMConfig:
    enabled: bool = False
    environment: str = 'disabled'
    testing: bool = False
    base_url: str = BASE_URL
    model: str = MODEL
    timeout_seconds: float = 60
    enforce_memory_guard: bool = True
    provider: str = 'ollama'
    remote_model: str = 'nvidia/nemotron-3.5-super-vl:free'
    api_key: str = field(default='', repr=False, compare=False)
    max_concurrent: int = field(default=1, init=False)

    def __post_init__(self):
        import re
        if (self.provider not in ('ollama', 'openrouter')
                or not isinstance(self.api_key, str)
                or (self.provider == 'openrouter' and (
                    not re.fullmatch(r'[a-zA-Z0-9_-]+/[a-zA-Z0-9_.:-]+:free', self.remote_model)
                    or self.remote_model == 'openrouter/free'
                    or (self.enabled and not self.api_key.strip())
                    or '\r' in self.api_key or '\n' in self.api_key))):
            raise LLMConfigInvalida()
        if (type(self.enabled) is not bool or type(self.testing) is not bool
                or type(self.enforce_memory_guard) is not bool
                or (not self.enforce_memory_guard and (self.environment!='local-development' or self.testing))
                or self.base_url != BASE_URL
                or not (self.model == MODEL or (self.model == 'qwen2.5:1.5b'
                    and self.environment == 'local-development' and not self.testing))
                or self.environment not in ('disabled', 'local-development', 'test', 'production')
                or type(self.timeout_seconds) not in (int, float)
                or not math.isfinite(self.timeout_seconds) or not 0 < self.timeout_seconds <= 60
                or (self.testing and self.environment != 'test')
                or (not self.testing and self.environment == 'test')
                or (self.enabled and self.environment != ('test' if self.testing else 'local-development'))):
            raise LLMConfigInvalida()


def load_llm_config(*, testing: bool = False, env_file: Path | None = None) -> LLMConfig:
    if type(testing) is not bool:
        raise LLMConfigInvalida()
    prefix = 'TEST_LLM_' if testing else 'LLM_'
    path = env_file if env_file is not None else PROJECT_ROOT / ('.env.test' if testing else '.env')
    values = dict(dotenv_values(path, interpolate=False)) if path.exists() else {}
    values.update({key: value for key, value in os.environ.items() if key.startswith(prefix)})
    raw = values.get(prefix + 'ENABLED', 'false')
    if raw not in ('true', 'false'):
        raise LLMConfigInvalida()
    try:
        return apply_provider_settings(LLMConfig(enabled=raw == 'true', testing=testing,
            environment=values.get(prefix + 'ENVIRONMENT', 'test' if testing else 'disabled'),
            base_url=values.get(prefix + 'BASE_URL', BASE_URL),
            model=values.get(prefix + 'MODEL', MODEL),
            timeout_seconds=float(values.get(prefix + 'TIMEOUT_SECONDS', '60')),
            enforce_memory_guard=load_memory_guard(environment=values.get(prefix+'ENVIRONMENT','test' if testing else 'disabled'),
                                                   testing=testing,env_file=env_file)),env_file=env_file)
    except (TypeError, ValueError):
        raise LLMConfigInvalida() from None


def load_local_model(*, env_file: Path | None = None) -> str:
    """Solo seleccion del modelo; no heredar opt-in, destino ni aprovisionamiento."""
    path = env_file if env_file is not None else PROJECT_ROOT / '.env'
    values = dotenv_values(path, interpolate=False) if path.exists() else {}
    model = os.environ.get('OLLAMA_MODEL', os.environ.get('LLM_MODEL', values.get('OLLAMA_MODEL',values.get('LLM_MODEL', MODEL))))
    if model not in (MODEL, 'qwen2.5:1.5b'):
        raise LLMConfigInvalida()
    return model


def apply_provider_settings(config, *, env_file=None):
    """Testing no hereda proveedor, claves ni timeouts operativos. Clave solo en entorno."""
    if config.testing:
        return config
    path = env_file if env_file is not None else PROJECT_ROOT / '.env'
    values = dict(dotenv_values(path, interpolate=False)) if path.exists() else {}
    def setting(name, default):
        return os.environ.get(name, values.get(name, default))
    try:
        provider = setting('AGENT_LLM_PROVIDER', 'ollama')
        return replace(config, provider=provider,
            remote_model=setting('OPENROUTER_MODEL', config.remote_model),
            api_key=os.environ.get('OPENROUTER_API_KEY', '') if provider == 'openrouter' else '',
            timeout_seconds=float(setting('AGENT_LLM_TIMEOUT_SECONDS', str(config.timeout_seconds))))
    except (ValueError, TypeError):
        raise LLMConfigInvalida() from None


def load_memory_guard(*, environment: str, testing: bool = False, env_file: Path | None = None) -> bool:
    """Excepción solo local; no hereda opciones LLM que habiliten una instancia."""
    if type(testing) is not bool:raise LLMConfigInvalida()
    key=('TEST_AGENT_' if testing else 'AGENT_')+'ENFORCE_MEMORY_GUARD'
    path=env_file if env_file is not None else PROJECT_ROOT/('.env.test' if testing else '.env')
    values=dotenv_values(path,interpolate=False) if path.exists() else {}
    raw=os.environ.get(key,values.get(key,'true'))
    if raw not in ('true','false'):raise LLMConfigInvalida()
    if raw=='false' and (environment!='local-development' or testing):raise LLMConfigInvalida()
    return raw=='true'
