from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import pytest

from ia_support import ControlledClock
from app.application.auth.service import Principal
from app.application.ia.exceptions import IAOcupada, IALimiteIntentos
from app.infrastructure.llm.admission import MemoryGenerationAdmission


def actor(user=None): return Principal(user or uuid4(),uuid4())


def test_five_per_user_across_sessions_and_exact_window_recovery():
    clock,principal=ControlledClock(0.25),actor()
    admission=MemoryGenerationAdmission(clock=clock)
    for _ in range(5): admission.try_acquire(actor(principal.usuario_id)).release()
    with pytest.raises(IALimiteIntentos) as error: admission.try_acquire(principal)
    assert error.value.retry_after==60
    clock.now=59.9
    with pytest.raises(IALimiteIntentos) as error: admission.try_acquire(principal)
    assert error.value.retry_after==1
    clock.now=60
    admission.try_acquire(principal).release()


def test_fifteen_global_without_partial_per_user_consumption():
    clock,admission=ControlledClock(),None
    admission=MemoryGenerationAdmission(clock=clock)
    for _ in range(15): admission.try_acquire(actor()).release()
    new=actor()
    with pytest.raises(IALimiteIntentos): admission.try_acquire(new)
    assert new.usuario_id not in admission._users
    assert sum(admission._users.values())==15
    clock.now=60
    admission.try_acquire(new).release()
    assert len(admission._users)==1


def test_busy_request_consumes_neither_quota_and_old_release_cannot_unlock_new_lease():
    principal,admission=actor(),MemoryGenerationAdmission()
    first=admission.try_acquire(principal)
    for _ in range(10):
        with pytest.raises(IAOcupada): admission.try_acquire(principal)
    first.release()
    second=admission.try_acquire(principal)
    first.release(timed_out=True)
    with pytest.raises(IAOcupada): admission.try_acquire(principal)
    second.release()
    for _ in range(3): admission.try_acquire(principal).release()
    with pytest.raises(IALimiteIntentos): admission.try_acquire(principal)


def test_timeout_cooldown_idempotence_and_window_rollover_while_busy():
    clock,admission=ControlledClock(59),None
    admission=MemoryGenerationAdmission(clock=clock)
    lease=admission.try_acquire(actor())
    clock.now=60
    with pytest.raises(IAOcupada): admission.try_acquire(actor())
    lease.release(timed_out=True)
    clock.now=89.5
    lease.release(timed_out=True)
    with pytest.raises(IAOcupada) as error: admission.try_acquire(actor())
    assert error.value.retry_after==1
    clock.now=90
    admission.try_acquire(actor()).release()


def test_registry_bounded_and_expired_entries_reclaimed_without_evicting_quota():
    clock=ControlledClock()
    admission=MemoryGenerationAdmission(clock=clock,max_users=1)
    first=actor()
    admission.try_acquire(first).release()
    with pytest.raises(IAOcupada): admission.try_acquire(actor())
    admission.try_acquire(first).release()
    assert len(admission._users)==1 and admission._global_count==2
    clock.now=60
    admission.try_acquire(actor()).release()
    assert len(admission._users)==1


def test_threaded_race_has_one_winner_and_no_partial_consumption():
    admission=MemoryGenerationAdmission()
    barrier=Barrier(8)
    def attempt(_):
        barrier.wait(timeout=3)
        try: return admission.try_acquire(actor())
        except IAOcupada: return None
    with ThreadPoolExecutor(max_workers=8) as pool: results=list(pool.map(attempt,range(8)))
    winners=[lease for lease in results if lease is not None]
    assert len(winners)==1 and admission._global_count==1 and sum(admission._users.values())==1
    with ThreadPoolExecutor(max_workers=8) as pool: list(pool.map(lambda _:winners[0].release(),range(8)))
    admission.try_acquire(actor()).release()


@pytest.mark.parametrize('capacity',[0,1025,True,1.5])
def test_registry_configuration_bounded(capacity):
    with pytest.raises(ValueError): MemoryGenerationAdmission(max_users=capacity)
