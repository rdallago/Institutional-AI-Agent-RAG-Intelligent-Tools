import asyncio
import os
from dataclasses import replace

import httpx
import pytest

from app.infrastructure.configuration.llm import LLMConfig, LLMConfigInvalida, load_llm_config
from app.infrastructure.llm.ollama import ollama_runtime
from app.application.ia.dto import GeneracionEntrada
from app.application.ia.exceptions import IANoDisponible


def test_default_disabled_builds_no_client(monkeypatch):
    def forbidden(**kwargs): raise AssertionError('No HTTP client for disabled IA')
    monkeypatch.setattr(httpx,'AsyncClient',forbidden)
    async def scenario():
        async with ollama_runtime(LLMConfig()) as runtime:
            with pytest.raises(IANoDisponible): await runtime.provider.generate(GeneracionEntrada(prompt='valid'))
    asyncio.run(scenario())


@pytest.mark.parametrize('url',['http://localhost:11434','http://127.0.0.1:11434/',
    'http://127.0.0.1:11435','https://127.0.0.1:11434','http://[::1]:11434',
    'http://0.0.0.0:11434','http://192.168.1.1:11434','http://127.0.0.1:11434?x=1',
    'http://secret@127.0.0.1:11434','http://127.0.0.1:11434/api/generate'])
def test_only_exact_target_allowed(url):
    with pytest.raises(LLMConfigInvalida) as error: LLMConfig(base_url=url)
    assert url not in str(error.value)


@pytest.mark.parametrize('changes',[dict(model='other'),dict(model='qwen2.5:1.5b-cloud'),
    dict(model='qwen2.5:1.5b'),dict(model='qwen3'),dict(model='qwen3:1.7b-cloud'),
    dict(enabled='true'),dict(testing='false'),dict(enabled=True),
    dict(enabled=True,environment='production'),dict(enabled=True,environment='test'),
    dict(testing=True,environment='local-development'),dict(environment='unknown'),
    dict(timeout_seconds=0),dict(timeout_seconds=61),dict(timeout_seconds=float('nan')),
    dict(timeout_seconds=float('inf')),dict(timeout_seconds=True)])
def test_bad_settings_rejected(changes):
    with pytest.raises(LLMConfigInvalida): LLMConfig(**changes)


def test_explicit_local_and_test_modes():
    assert LLMConfig().model == 'qwen3:1.7b'
    assert LLMConfig(enabled=True,environment='local-development').enabled
    assert LLMConfig(enabled=True,testing=True,environment='test').max_concurrent==1
    with pytest.raises(TypeError): LLMConfig(max_concurrent=2)


@pytest.mark.parametrize('testing', [False, True])
@pytest.mark.parametrize('model', ['qwen2.5:1.5b', 'qwen3:1.7b', 'arbitrary'])
def test_model_environment_allowlist_is_identical_and_isolated(tmp_path, monkeypatch, testing, model):
    prefix = 'TEST_LLM_' if testing else 'LLM_'
    other = 'LLM_' if testing else 'TEST_LLM_'
    for key in list(os.environ):
        if key.startswith(('LLM_', 'TEST_LLM_')): monkeypatch.delenv(key)
    monkeypatch.setenv(prefix + 'MODEL', model)
    monkeypatch.setenv(other + 'MODEL', 'not-allowed-and-must-be-ignored')
    if model == 'qwen3:1.7b':
        config = load_llm_config(testing=testing, env_file=tmp_path/'absent')
        assert config.model == model and not config.enabled
    else:
        with pytest.raises(LLMConfigInvalida):
            load_llm_config(testing=testing, env_file=tmp_path/'absent')


def test_test_config_never_falls_back_to_operational_file_or_environment(tmp_path,monkeypatch):
    import app.infrastructure.configuration.llm as module
    monkeypatch.setattr(module,'PROJECT_ROOT',tmp_path)
    (tmp_path/'.env').write_text('LLM_ENABLED=true\nLLM_ENVIRONMENT=local-development\n',encoding='utf-8')
    monkeypatch.setenv('LLM_ENABLED','true')
    monkeypatch.setenv('LLM_BASE_URL','http://external.invalid')
    for key in list(module.os.environ):
        if key.startswith('TEST_LLM_'): monkeypatch.delenv(key)
    config=load_llm_config(testing=True)
    assert not config.enabled and config.environment=='test' and config.base_url=='http://127.0.0.1:11434'


def test_load_test_file_and_overrides_without_mutation(tmp_path,monkeypatch):
    path=tmp_path/'test-config'
    path.write_text('TEST_LLM_ENABLED=true\nTEST_LLM_ENVIRONMENT=test\nTEST_LLM_TIMEOUT_SECONDS=40\n',encoding='utf-8')
    monkeypatch.setenv('TEST_LLM_TIMEOUT_SECONDS','12')
    config=load_llm_config(testing=True,env_file=path)
    assert config.enabled and config.timeout_seconds==12
    assert '40' in path.read_text(encoding='utf-8')


@pytest.mark.parametrize('value',['yes','1','TRUE','', 'secret-invalid'])
def test_boolean_must_be_explicit_and_sanitized(value,tmp_path,monkeypatch):
    monkeypatch.setenv('TEST_LLM_ENABLED',value)
    with pytest.raises(LLMConfigInvalida) as error: load_llm_config(testing=True,env_file=tmp_path/'absent')
    assert 'secret-invalid' not in str(error.value)


@pytest.mark.parametrize('transport',[None,httpx.AsyncHTTPTransport()])
def test_enabled_test_mode_requires_mock_transport(transport):
    async def scenario():
        with pytest.raises(LLMConfigInvalida):
            async with ollama_runtime(LLMConfig(enabled=True,testing=True,environment='test'),transport=transport): pass
        if transport is not None: await transport.aclose()
    asyncio.run(scenario())


def test_mock_transport_not_allowed_as_operational_override():
    async def scenario():
        with pytest.raises(LLMConfigInvalida):
            async with ollama_runtime(LLMConfig(enabled=True,environment='local-development'),transport=httpx.MockTransport(lambda r:None)): pass
    asyncio.run(scenario())
