"""Una admision por solicitud, compartida por planificacion y capacidad final."""
from contextlib import contextmanager
from contextvars import ContextVar
import asyncio


class ScopedAdmission:
    def __init__(self, delegate):
        self.delegate = delegate
        self.current = ContextVar('agent_admission', default=None)

    @contextmanager
    def scope(self, principal):
        lease = self.delegate.try_acquire(principal)
        state = {'principal': principal, 'lease': lease, 'timeout': False}
        token = self.current.set(state)
        try:
            yield
        except (TimeoutError, asyncio.CancelledError):
            state['timeout'] = True
            raise
        finally:
            self.current.reset(token)
            lease.release(timed_out=state['timeout'])

    def try_acquire(self, principal):
        state = self.current.get()
        if state is None or state['principal'] != principal:
            return self.delegate.try_acquire(principal)
        class Borrowed:
            def release(self, *, timed_out=False):
                state['timeout'] |= timed_out
        return Borrowed()
