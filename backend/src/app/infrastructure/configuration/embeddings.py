"""Configuración independiente; claves exclusivamente en memoria del proceso."""
from dataclasses import dataclass, field
import hashlib
import json
import math
import os
from dotenv import dotenv_values
from .database import PROJECT_ROOT


@dataclass(frozen=True, kw_only=True)
class EmbeddingConfig:
    provider: str = 'ollama'
    model: str = 'jina-embeddings-v3'
    dimensions: int = 768
    timeout: float = 30
    max_input_bytes: int = 2048
    max_response_bytes: int = 65536
    api_key: str = field(default='', repr=False, compare=False)
    testing: bool = False

    def __post_init__(self):
        if (self.provider not in ('ollama', 'jina') or self.model != 'jina-embeddings-v3'
                or type(self.dimensions) is not int or self.dimensions != 768
                or type(self.timeout) not in (int, float) or not math.isfinite(self.timeout)
                or not 0 < self.timeout <= 55
                or type(self.max_input_bytes) is not int or not 1 <= self.max_input_bytes <= 8192
                or type(self.max_response_bytes) is not int or not 16384 <= self.max_response_bytes <= 65536
                or type(self.testing) is not bool or not isinstance(self.api_key, str)
                or '\r' in self.api_key or '\n' in self.api_key):
            raise ValueError('Configuración de embeddings inválida.')

    @property
    def identity(self):
        # No afirmar un digest de pesos que la API no publica.
        return json.dumps({'provider': 'jina', 'model': self.model, 'dimensions': self.dimensions,
            'query_task': 'retrieval.query', 'document_task': 'retrieval.passage',
            'normalization': 'provider-l2-unit-tolerance-0.01', 'input': 'exact-utf8-v1',
            'revision': 'api-model-id-unpinned-v1'}, sort_keys=True, separators=(',', ':'))

    @property
    def space(self):
        return hashlib.sha256(self.identity.encode()).hexdigest()


def load_embedding_config(*, testing=False, env_file=None):
    if testing:
        return EmbeddingConfig(testing=True)
    path = env_file or PROJECT_ROOT / '.env'
    values = dotenv_values(path, interpolate=False) if path.exists() else {}
    def get(name, default):
        return os.environ.get(name, values.get(name, default))
    try:
        return EmbeddingConfig(provider=get('EMBEDDING_PROVIDER', 'ollama'),
            model=get('EMBEDDING_MODEL', 'jina-embeddings-v3'),
            dimensions=int(get('EMBEDDING_DIMENSIONS', '768')),
            timeout=float(get('EMBEDDING_TIMEOUT_SECONDS', '30')),
            max_input_bytes=int(get('EMBEDDING_MAX_INPUT_BYTES', '2048')),
            max_response_bytes=int(get('EMBEDDING_MAX_RESPONSE_BYTES', '65536')),
            api_key=os.environ.get('JINA_API_KEY', ''))
    except (TypeError, ValueError):
        raise ValueError('Configuración de embeddings inválida.') from None
