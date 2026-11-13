import hashlib
import hmac
from datetime import UTC, datetime, timedelta
from math import ceil
from threading import Lock

from app.application.auth.exceptions import LimiteIntentos


class _Reservation:
    """Handle local de una reserva admitida; liberar una sola vez tras commit."""
    def __init__(self, factory, pair):
        self._factory, self._pair = factory, pair
        self._released = False
        self._lock = Lock()

    def release(self):
        with self._lock:
            if self._released:
                return
            with self._factory() as uow:
                uow.release_attempt(*self._pair[:3])
            self._released = True


class LoginLimiter:
    def __init__(self, factory, key, *, ip_limit=30, pair_limit=5):
        self.factory, self.key = factory, key
        self.ip_limit, self.pair_limit = ip_limit, pair_limit

    def _bucket(self, scope, value, now, seconds):
        digest = hmac.digest(self.key, (scope + "\0" + value).encode("utf-8"), hashlib.sha256)
        timestamp = int(now.timestamp())
        start = datetime.fromtimestamp(timestamp - timestamp % seconds, UTC)
        return scope, digest, start, start + timedelta(seconds=seconds)

    def check(self, email, ip, now):
        with self.factory() as uow:
            uow.cleanup_attempts(now, limit=100)
            for scope, value, seconds, limit in (("ip", ip, 60, self.ip_limit), ("email_ip", email + "\0" + ip, 900, self.pair_limit)):
                bucket = self._bucket(scope, value, now, seconds)
                if uow.consume(*bucket, limit) > limit:
                    # Salir con excepcion revierte AMBOS consumos de esta reserva.
                    raise LimiteIntentos(ceil((bucket[3] - now).total_seconds()))
            pair = bucket
        return _Reservation(self.factory, pair)

    def failure(self, email, ip, now):
        pass  # El cupo se reserva atómicamente antes de ejecutar Argon2.

    def success(self, email, ip, attempted_at, *, reservation):
        reservation.release()

    def cleanup(self, now):
        with self.factory() as uow:
            return uow.cleanup_attempts(now)
