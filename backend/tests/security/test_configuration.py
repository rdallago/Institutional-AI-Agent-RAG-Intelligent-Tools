import pytest
from auth_support import auth_config
from app.infrastructure.configuration.auth import AuthConfig, load_auth_config


def test_configuration_requires_external_secrets(monkeypatch):
    import os
    import app.infrastructure.configuration.auth as module
    monkeypatch.setattr(module,"dotenv_values",lambda *a,**k:{})
    for key in list(os.environ):
        if key.startswith("TEST_AUTH_"): monkeypatch.delenv(key)
    with pytest.raises(ValueError,match="claves externas"):
        load_auth_config(testing=True)


def test_secret_repr_and_minimum_strength():
    config = auth_config()
    assert str(config.keys[config.active_kid]) not in repr(config)
    with pytest.raises(ValueError): AuthConfig({"short":b"short"},"short",config.limiter_key)
    with pytest.raises(ValueError): AuthConfig(config.keys,config.active_kid,config.keys[config.active_kid])


def test_parse_failure_does_not_echo_invalid_secret(monkeypatch):
    monkeypatch.setenv("TEST_AUTH_JWT_KEYS_JSON","not-valid-secret-json")
    with pytest.raises(ValueError) as captured: load_auth_config(testing=True)
    assert "not-valid-secret-json" not in str(captured.value)
