"""Exclusion compartible entre ingesta, embeddings y generacion; sin cola."""
from threading import Lock

from app.application.ia.exceptions import IAOcupada


class _Lease:
    def __init__(self, gate, token):
        self._gate, self._token = gate, token

    def release(self):
        with self._gate._lock:
            if self._gate._active is self._token:
                self._gate._active = None


class MemoryModelWorkGate:
    def __init__(self):
        self._lock = Lock()
        self._active = None

    def try_acquire(self):
        with self._lock:
            if self._active is not None:
                raise IAOcupada(retry_after=1)
            token = object()
            self._active = token
            return _Lease(self, token)
