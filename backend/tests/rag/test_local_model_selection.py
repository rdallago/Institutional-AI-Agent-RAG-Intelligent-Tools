import pytest

from app.infrastructure.configuration.llm import (
    LLMConfig, LLMConfigInvalida, MODEL, load_local_model, load_llm_config,
)


def test_qwen25_allowed_only_in_operational_local_environment():
    assert LLMConfig(enabled=True, environment='local-development', model='qwen2.5:1.5b').model == 'qwen2.5:1.5b'
    for environment, testing in [('production', False), ('disabled', False), ('test', True), ('local-development', True)]:
        with pytest.raises(LLMConfigInvalida):
            LLMConfig(environment=environment, testing=testing, model='qwen2.5:1.5b')
    assert LLMConfig().model == MODEL
    assert LLMConfig(environment='test', testing=True).model == MODEL


def test_local_loader_default_file_and_process_precedence(tmp_path, monkeypatch):
    monkeypatch.delenv('LLM_MODEL', raising=False)
    path=tmp_path/'local.env'
    assert load_local_model(env_file=path)==MODEL
    path.write_text('LLM_MODEL=qwen2.5:1.5b\nLLM_ENABLED=true\n', encoding='utf-8')
    assert load_local_model(env_file=path)=='qwen2.5:1.5b'
    monkeypatch.setenv('LLM_MODEL',MODEL)
    assert load_local_model(env_file=path)==MODEL
    monkeypatch.setenv('LLM_MODEL','unknown')
    with pytest.raises(LLMConfigInvalida):load_local_model(env_file=path)


def test_test_configuration_does_not_inherit_operational_model(tmp_path, monkeypatch):
    monkeypatch.setenv('LLM_MODEL','qwen2.5:1.5b')
    path=tmp_path/'test.env'
    path.write_text('TEST_LLM_ENVIRONMENT=test\n',encoding='utf-8')
    assert load_llm_config(testing=True,env_file=path).model==MODEL
    path.write_text('TEST_LLM_MODEL=qwen2.5:1.5b\n',encoding='utf-8')
    with pytest.raises(LLMConfigInvalida):load_llm_config(testing=True,env_file=path)
