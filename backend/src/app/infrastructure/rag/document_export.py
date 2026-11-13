"""Capacidad efímera para la exportación CLI del único reglamento aprobado.

No es una frontera frente a código Python malicioso dentro del mismo proceso.
No se serializa, hereda por entorno ni se acepta desde FastAPI.
"""
import asyncio
import hashlib
import os
import sys
import time
from types import MappingProxyType
from uuid import UUID

DOCUMENT = UUID('8ac0c745-1307-5bb4-9d56-93dfbee0b3b8')
VERSION = UUID('7cb4e79c-747d-574a-8abb-0ebcb2e07636')
OWNER = UUID('32eabde4-7d17-4029-a47a-60e2e38faf05')
SPACE = '1f0482094b5531fc5d3406985eb3ba0ec870af28871c4b2b7c4c6f12b6c37ed1'
_SEAL = object()


def require_cli_entry():
    spec = getattr(sys.modules.get('__main__'), '__spec__', None)
    if getattr(spec, 'name', None) != 'app.presentation.cli.reindex_jina':
        raise RuntimeError('Autorización reservada al proceso CLI de indexación.')


class DocumentExportPermit:
    def __init__(self, seal, *, adapter, manifest, limit):
        if seal is not _SEAL:
            raise RuntimeError('Emisor de autorización inválido.')
        self._adapter = adapter
        self._manifest = MappingProxyType(dict(manifest))
        self._pid = os.getpid()
        self._task = asyncio.current_task()
        self._expires = time.monotonic() + 600
        self._remaining = limit
        self._used = set()
        self._closed = False

    def consume(self, adapter, fragment, value, space):
        require_cli_entry()
        if (self._closed or os.getpid() != self._pid or asyncio.current_task() is not self._task
                or adapter is not self._adapter or space != SPACE or time.monotonic() >= self._expires
                or self._remaining < 1 or fragment in self._used
                or not isinstance(value, str)
                or self._manifest.get(fragment) != hashlib.sha256(value.encode('utf-8')).hexdigest()):
            raise RuntimeError('Exportación fuera del alcance autorizado.')
        # Consumir antes del HTTP: un resultado incierto nunca permite reenviar con este permiso.
        self._remaining -= 1
        self._used.add(fragment)

    def close(self):
        self._closed = True


def issue_permit(*, adapter, owner, version, document, space, manifest, limit):
    require_cli_entry()
    if ((owner, version, document, space) != (OWNER, VERSION, DOCUMENT, SPACE)
            or type(limit) is not int or not 1 <= limit <= 10
            or len(manifest) != 432 or any(not isinstance(k, UUID) or not isinstance(v, str)
                or len(v) != 64 or any(c not in '0123456789abcdef' for c in v)
                for k, v in manifest.items())):
        raise RuntimeError('Identidad o manifiesto documental no autorizado.')
    return DocumentExportPermit(_SEAL, adapter=adapter, manifest=manifest, limit=limit)
