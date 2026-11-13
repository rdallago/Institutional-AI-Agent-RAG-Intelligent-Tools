from dataclasses import replace
from uuid import uuid4

import pytest

from auth_support import memory_auth,bootstrap_login,PASSWORD
from app.application.auth.recovery import LocalAdminRecovery
from app.application.auth.exceptions import AutenticacionRequerida,PasswordInvalida,PasswordReutilizada
from app.domain.usuarios.rol import Rol
from app.presentation.cli.recover_admin import main,hidden_password


NEW_PASSWORD='fictional-new-password-for-local-recovery'


def setup():
    store,auth,_=memory_auth();uid,token=bootstrap_login(auth)
    recovery=LocalAdminRecovery(store.uow,auth.hasher)
    return store,auth,uid,token,recovery


def test_reset_revokes_without_deleting_and_login_normal():
    store,auth,uid,token,recovery=setup()
    existing=set(store.sessions)
    recovery.reset(uid,'operator@example.com',NEW_PASSWORD)
    assert set(store.sessions)==existing
    assert all(s.revocada_at is not None for s in store.sessions.values())
    with pytest.raises(AutenticacionRequerida):auth.authenticate(token)
    credential=store.credentials[uid]
    assert not credential.debe_cambiar_password
    assert auth.hasher.verify(credential.password_hash,NEW_PASSWORD)
    assert store.users.obtener_por_id(uid).rol is Rol.ADMIN
    assert auth.login('operator@example.com',NEW_PASSWORD,'127.0.0.1').debe_cambiar_password is False


@pytest.mark.parametrize('email,identifier',[('other@example.com',None),('operator@example.com','wrong')])
def test_identity_mismatch_no_changes(email,identifier):
    store,auth,uid,token,recovery=setup();before=store.credentials[uid]
    with pytest.raises(ValueError):recovery.reset(uuid4() if identifier else uid,email,NEW_PASSWORD)
    assert store.credentials[uid]==before
    assert all(s.revocada_at is None for s in store.sessions.values())


def test_password_policy_and_reuse_no_changes():
    store,auth,uid,token,recovery=setup();before=store.credentials[uid]
    with pytest.raises(PasswordInvalida):recovery.reset(uid,'operator@example.com','short')
    with pytest.raises(PasswordReutilizada):recovery.reset(uid,'operator@example.com',PASSWORD)
    assert store.credentials[uid]==before


def test_rejects_initial_password_reuse():
    store,auth,uid,token,recovery=setup()
    store.credentials[uid]=replace(store.credentials[uid],password_inicial_hash=auth.hasher.hash(NEW_PASSWORD))
    with pytest.raises(PasswordReutilizada):recovery.reset(uid,'operator@example.com',NEW_PASSWORD)


def test_revocation_error_rolls_back_credential():
    store,auth,uid,token,recovery=setup();before=store.credentials[uid]
    def factory():
        uow=store.uow()
        def fail(*args):raise RuntimeError('synthetic error')
        uow.revoke=fail
        return uow
    recovery.uow_factory=factory
    with pytest.raises(RuntimeError):recovery.reset(uid,'operator@example.com',NEW_PASSWORD)
    assert store.credentials[uid]==before
    assert all(s.revocada_at is None for s in store.sessions.values())


def test_apply_requires_selection_and_tty(monkeypatch):
    with pytest.raises(SystemExit):main(['--email','operator@example.com','--apply'])
    monkeypatch.setattr('sys.stdin.isatty',lambda:False)
    with pytest.raises(SystemExit):main(['--email','operator@example.com','--apply','--allow-development','--usuario-id',str(uuid4())])


def test_visible_getpass_fallback_forbidden(monkeypatch):
    import getpass,warnings
    def fallback(*args):warnings.warn('synthetic',getpass.GetPassWarning);return NEW_PASSWORD
    monkeypatch.setattr(getpass,'getpass',fallback)
    with pytest.raises(getpass.GetPassWarning):hidden_password()
