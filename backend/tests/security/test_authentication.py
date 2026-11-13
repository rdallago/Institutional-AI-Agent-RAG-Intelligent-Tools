from datetime import UTC, datetime, timedelta
from dataclasses import replace
from uuid import uuid4

import jwt
import pytest

from auth_support import PASSWORD, memory_auth, bootstrap_login, auth_config
from app.application.auth.exceptions import AutenticacionRequerida, CredencialesInvalidas, PasswordInvalida
from app.application.auth.service import validate_password
from app.domain.auth.models import Sesion
from app.domain.usuarios.email import Email
from app.domain.usuarios.usuario import Usuario
from app.infrastructure.security.crypto import JWTService, Argon2Hasher


def test_argon2_random_salts_and_default_parameters():
    hasher = Argon2Hasher()
    first, second = hasher.hash(PASSWORD), hasher.hash(PASSWORD)
    assert first != second and first.startswith("$argon2id$")
    assert "m=65536,t=3,p=1" in first
    assert hasher.verify(first, PASSWORD) and not hasher.verify(first, PASSWORD + "wrong")
    assert not hasher.needs_rehash(first)


@pytest.mark.parametrize("password", ["short", "x" * 129, "123456789012345", "\ud800" * 15])
def test_password_policy(password):
    with pytest.raises(PasswordInvalida):
        validate_password(password)


def test_login_claims_and_normalization(security):
    _, service, _, admin_id, _ = security
    result = service.login(" OPERATOR@example.com ", PASSWORD, "127.0.0.2")
    claims = jwt.decode(result.access_token, options={"verify_signature": False})
    assert set(claims) == {"sub", "jti", "iat", "exp", "iss", "aud", "token_use"}
    assert claims["sub"] == str(admin_id) and claims["exp"] - claims["iat"] == 900
    assert PASSWORD not in repr(result)
    assert service.me(service.authenticate(result.access_token)).id == admin_id


@pytest.mark.parametrize("scenario", ["missing", "wrong", "inactive", "no_credential"])
def test_login_rejections_share_exception_and_verify_hash(security, monkeypatch, scenario):
    store, service, _, admin_id, _ = security
    email, password = "operator@example.com", PASSWORD
    if scenario == "missing": email = "absent@example.com"
    if scenario == "wrong": password += "wrong"
    if scenario == "inactive":
        user = store.users.obtener_por_id(admin_id); user.dar_de_baja(); store.users.actualizar(user)
    if scenario == "no_credential": store.credentials.clear()
    calls = []
    original = service.hasher.verify
    monkeypatch.setattr(service.hasher, "verify", lambda encoded, raw: (calls.append(True), original(encoded, raw))[1])
    with pytest.raises(CredencialesInvalidas): service.login(email, password, "127.0.0.3")
    assert calls == [True]


def test_logout_and_password_change_revoke_sessions(security):
    _, service, _, _, token = security
    another = service.login("operator@example.com", PASSWORD, "127.0.0.3").access_token
    service.logout(token); service.logout(token)
    with pytest.raises(AutenticacionRequerida): service.authenticate(token)
    principal = service.authenticate(another)
    service.change_password(principal, PASSWORD, PASSWORD + "-new")
    with pytest.raises(AutenticacionRequerida): service.authenticate(another)
    with pytest.raises(CredencialesInvalidas): service.login("operator@example.com", PASSWORD, "127.0.0.4")
    assert service.authenticate(service.login("operator@example.com", PASSWORD + "-new", "127.0.0.4").access_token)


def test_controlled_rehash(security):
    store, service, _, admin_id, _ = security
    credential = store.credentials[admin_id]
    weaker = Argon2Hasher(memory_cost=512, time_cost=1)
    store.credentials[admin_id] = replace(credential, password_hash=weaker.hash(PASSWORD))
    service.login("operator@example.com", PASSWORD, "127.0.0.5")
    assert not service.hasher.needs_rehash(store.credentials[admin_id].password_hash)


@pytest.mark.parametrize("mutation", ["expired", "future", "issuer", "audience", "missing", "wrong_type", "long", "purpose", "none", "wrong_alg", "unknown_kid", "tampered", "jku"])
def test_strict_jwt_validation(mutation):
    config = auth_config()
    now = datetime.now(UTC)
    codec = JWTService(config)
    claims = {"sub": str(uuid4()), "jti": str(uuid4()), "iat": int(now.timestamp()),
        "exp": int(now.timestamp()) + 900, "iss": config.issuer, "aud": config.audience, "token_use": "access"}
    headers = {"kid": config.active_kid, "typ": "at+jwt"}
    algorithm, key = "HS256", config.keys[config.active_kid]
    if mutation == "expired": claims.update(iat=int(now.timestamp())-1000, exp=int(now.timestamp())-100)
    if mutation == "future": claims.update(iat=int(now.timestamp())+100, exp=int(now.timestamp())+900)
    if mutation == "issuer": claims["iss"] = "wrong"
    if mutation == "audience": claims["aud"] = "wrong"
    if mutation == "missing": del claims["jti"]
    if mutation == "wrong_type": claims["iat"] = True
    if mutation == "long": claims["exp"] += 1
    if mutation == "purpose": claims["token_use"] = "refresh"
    if mutation == "none": algorithm, key = "none", None
    if mutation == "wrong_alg":
        import secrets
        algorithm, key = "HS512", secrets.token_bytes(64)
    if mutation == "unknown_kid": headers["kid"] = "unknown"
    if mutation == "jku": headers["jku"] = "https://untrusted.invalid/keys"
    token = jwt.encode(claims, key, algorithm=algorithm, headers=headers)
    if mutation == "tampered":
        first, payload, signature = token.split(".")
        token = first + "." + payload + "." + ("A" if signature[0] != "A" else "B") + signature[1:]
    with pytest.raises(AutenticacionRequerida): codec.verify(token)


def test_expiry_and_session_binding(security):
    store, service, _, admin_id, token = security
    principal = service.authenticate(token)
    store.sessions[principal.sesion_id] = replace(store.sessions[principal.sesion_id], expira_at=service.clock()-timedelta(seconds=1))
    with pytest.raises(AutenticacionRequerida): service.authenticate(token)
    store.sessions[principal.sesion_id] = Sesion(principal.sesion_id, uuid4(), service.clock(), service.clock()+timedelta(seconds=900), restringida=False)
    with pytest.raises(AutenticacionRequerida): service.authenticate(token)


def test_key_rotation_accepts_only_configured_keys(security):
    import secrets
    from app.infrastructure.configuration.auth import AuthConfig
    _, service, old, _, token = security
    rotated = AuthConfig({**old.keys, "new": secrets.token_bytes(32)}, "new", old.limiter_key)
    codec = JWTService(rotated)
    assert codec.verify(token)
    removed = AuthConfig({"new": rotated.keys["new"]}, "new", old.limiter_key)
    with pytest.raises(AutenticacionRequerida): JWTService(removed).verify(token)
