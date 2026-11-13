"""Admision atomica local de un solo proceso; nunca almacena contenido IA."""
from math import ceil
import logging
from threading import Lock
from time import monotonic

from app.application.auth.service import Principal
from app.application.ia.exceptions import IAOcupada, IALimiteIntentos


class _Lease:
    __slots__ = ('_owner', '_token')

    def __init__(self, owner, token):
        self._owner, self._token = owner, token

    def release(self, *, timed_out: bool = False) -> None:
        self._owner._release(self._token, timed_out)


class MemoryGenerationAdmission:
    def __init__(self, *, clock=monotonic, max_users: int = 1024):
        if type(max_users) is not int or not 1 <= max_users <= 1024:
            raise ValueError("Capacidad de contadores IA invalida.")
        self._clock, self._max_users = clock, max_users
        self._lock = Lock()
        self._active = None
        self._cooldown_until = 0.0
        self._window = None
        self._global_count = 0
        self._users = {}

    def try_acquire(self, principal: Principal) -> _Lease:
        with self._lock:
            now = self._clock()
            if now < self._cooldown_until:
                logging.getLogger('app.agent').warning('agent_admission_reason kind=cooldown')
                raise IAOcupada(max(1, ceil(self._cooldown_until - now)))
            if self._active is not None:
                logging.getLogger('app.agent').warning('agent_admission_reason kind=active')
                raise IAOcupada(1)
            window = int(now // 60)
            if window != self._window:
                self._window, self._global_count = window, 0
                self._users.clear()
            retry = max(1, ceil((window + 1) * 60 - now))
            count = self._users.get(principal.usuario_id, 0)
            if count >= 5 or self._global_count >= 15:
                logging.getLogger('app.agent').warning('agent_admission_reason kind=quota')
                raise IALimiteIntentos(retry)
            if principal.usuario_id not in self._users and len(self._users) >= self._max_users:
                raise IAOcupada(retry)
            token = object()
            lease = _Lease(self, token)
            self._users[principal.usuario_id] = count + 1
            self._global_count += 1
            self._active = token
            return lease

    def _release(self, token, timed_out):
        with self._lock:
            if self._active is not token:
                return
            if timed_out:
                self._cooldown_until = self._clock() + 30
            self._active = None
