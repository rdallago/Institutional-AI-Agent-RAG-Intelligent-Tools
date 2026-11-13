"""Solo MockTransport; nunca se invocan servicios reales."""
import asyncio
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import sys

import httpx
import pytest

spec = importlib.util.spec_from_file_location('openrouter_diagnostic',
    Path(__file__).resolve().parents[3] / 'infra' / 'diagnose_openrouter.py')
diagnostic = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = diagnostic
spec.loader.exec_module(diagnostic)


def valid():
    return {'id': 'gen-synthetic', 'model': diagnostic.MODEL,
        'choices': [{'finish_reason': 'stop', 'message': {'role': 'assistant', 'content': 'OK'}}]}


def config():
    return SimpleNamespace(provider='openrouter', remote_model=diagnostic.MODEL, api_key='private-test-secret')


@pytest.mark.parametrize('body,state,success,reason', [
    (valid(), 'with_elements', True, 'valid_chat_completion'),
    ({'id': 'gen-error', 'error': {'code': 429, 'message': 'Synthetic overload',
        'metadata': {'error_type': 'rate_limit_exceeded', 'limit_source': 'upstream_provider_shared_pool'}}},
     'missing', False, 'error_in_body'),
    ({'id': 'gen-missing'}, 'missing', False, 'invalid_choices'),
    ({'choices': []}, 'empty', False, 'invalid_choices'),
    ({'choices': None}, 'invalid_type', False, 'invalid_choices'),
    ({'choices': {}}, 'invalid_type', False, 'invalid_choices'),
])
def test_http200_diagnostic_cases(body, state, success, reason):
    requests = []
    def handler(request):
        requests.append(request)
        payload = json.loads(request.content)
        assert payload['model'] == diagnostic.MODEL
        assert payload['messages'] == [{'role': 'user', 'content': 'Respond only OK'}]
        assert payload['provider']['data_collection'] == 'deny'
        assert payload['provider']['allow_fallbacks'] is False
        assert 'response_format' not in payload
        return httpx.Response(200, json=body)
    result = asyncio.run(diagnostic.probe(config(), transport=httpx.MockTransport(handler)))
    assert len(requests) == 1
    assert result['generation_valid'] is success
    assert result['choices']['state'] == state and result['reason'] == reason
    if success:
        assert result['generations'][0]['content'] == 'OK'
        assert result['matches_expected_ok'] is True
    if reason == 'error_in_body':
        assert result['errors'][0]['code'] == 429
        assert result['errors'][0]['error_type'] == 'rate_limit_exceeded'
        assert result['errors'][0]['limit_source'] == 'upstream_provider_shared_pool'


def test_error_overrides_content_and_http200():
    body = valid()
    body['error'] = {'code': 503, 'message': 'Synthetic failure'}
    result = diagnostic.summarize(200, body)
    assert result['reason'] == 'error_in_body' and not result['generation_valid']
    body = valid()
    body['choices'][0]['error'] = {'code': 502, 'message': 'Synthetic partial failure'}
    assert not diagnostic.summarize(200, body)['generation_valid']


@pytest.mark.parametrize('body', ['{', '{"choices":[],"choices":[]}', '{"error":NaN}'])
def test_invalid_json_is_not_success(body):
    result = asyncio.run(diagnostic.probe(config(), transport=httpx.MockTransport(
        lambda _: httpx.Response(200, text=body))))
    assert result['reason'] == 'invalid_json' and not result['generation_valid']


def test_sensitive_fields_and_reasoning_not_exposed():
    body = valid()
    body['authorization'] = 'Bearer private-test-secret'
    body['output'] = {'private': 'do not copy'}
    body['choices'][0]['message']['reasoning'] = 'PRIVATE_REASONING'
    body['choices'][0]['message']['content'] = 'private-test-secret email@example.com phone: +54 1112345678'
    body['error'] = {'code': 502, 'message': 'Bearer private-test-secret',
        'metadata': {'raw': 'PRIVATE_RAW', 'error_type': 'provider_unavailable'}}
    result = diagnostic.summarize(200, body, secret='private-test-secret')
    encoded = json.dumps(result)
    for value in ('private-test-secret', 'email@example.com', '+54 1112345678',
                  'PRIVATE_REASONING', 'PRIVATE_RAW', 'do not copy'):
        assert value not in encoded
    assert result['generations'][0]['reasoning_present'] is True


def test_bounds():
    body = valid()
    body['choices'][0]['message']['content'] = 'x' * 20000
    body.update({f'field-{i}': 'never copy' for i in range(100)})
    result = diagnostic.summarize(200, body)
    assert len(result['root_keys']) == 24 and result['root_keys_truncated']
    assert len(result['generations'][0]['content']) < 550
    assert len(json.dumps(result)) < 6000


def test_reasoning_is_not_answer_and_alternative_output_is_not_chat():
    body = valid()
    body['choices'][0]['message'] = {'role': 'assistant', 'content': None, 'reasoning': 'OK'}
    assert not diagnostic.summarize(200, body)['generation_valid']
    assert not diagnostic.summarize(200, {'output': 'OK'})['generation_valid']


@pytest.mark.parametrize('finish', ['error', 'length', None])
def test_finish_reason_required(finish):
    body = valid(); body['choices'][0]['finish_reason'] = finish
    assert not diagnostic.summarize(200, body)['generation_valid']


def test_non200_valid_shape_is_not_success():
    assert not diagnostic.summarize(503, valid())['generation_valid']


def test_main_default_never_uses_network(monkeypatch, capsys):
    monkeypatch.setattr(diagnostic, 'probe', lambda *_args, **_kwargs: pytest.fail('No network'))
    assert diagnostic.main([]) == 0
    assert 'SIN SOLICITUDES' in capsys.readouterr().out


def test_timeout_no_retry():
    calls=[]
    def handler(request):
        calls.append(request)
        raise httpx.ReadTimeout('private-test-secret', request=request)
    result=asyncio.run(diagnostic.probe(config(), transport=httpx.MockTransport(handler)))
    assert result['reason']=='timeout' and len(calls)==1
    assert 'private-test-secret' not in json.dumps(result)


@pytest.mark.parametrize('model,provider', list(diagnostic.AUTHORIZED_PAIRS.items()))
def test_authorized_pairs_mock_transport(model, provider):
    calls = []
    def handler(request):
        calls.append(request)
        payload = json.loads(request.content)
        assert payload['model'] == model
        assert payload['provider'] == {
            'only': [provider], 'require_parameters': True,
            'allow_fallbacks': False, 'data_collection': 'deny',
            'max_price': {'prompt': 0, 'completion': 0, 'request': 0}}
        assert payload['messages'] == [{'role': 'user', 'content': 'Respond only OK'}]
        assert payload['max_tokens'] == 256
        assert 'response_format' not in payload
        body = valid()
        body['model'] = model
        return httpx.Response(200, json=body)
    result = asyncio.run(diagnostic.probe(config(), model=model, provider=provider,
        transport=httpx.MockTransport(handler)))
    assert len(calls) == 1 and result['generation_valid']
    assert result['model_requested'] == model
    assert result['provider_requested'] == provider


@pytest.mark.parametrize('model,provider', [
    (diagnostic.MODEL.removesuffix(':free'), 'phala'),
    ('dots-studio/dots-3-note-preview', 'atlas-cloud'),
    ('unknown/model:free', 'phala'),
    (diagnostic.MODEL, 'atlas-cloud'),
    ('dots-studio/dots-3-note-preview:free', 'phala'),
    (diagnostic.MODEL, 'unknown'),
    (diagnostic.MODEL, ''),
])
def test_unauthorized_selection_never_posts(model, provider):
    result = asyncio.run(diagnostic.probe(config(), model=model, provider=provider,
        transport=httpx.MockTransport(lambda _: pytest.fail('No network'))))
    assert result['posts'] == 0 and not result['generation_valid']


def test_configured_dots_selects_authorized_provider():
    settings = config()
    settings.remote_model = 'dots-studio/dots-3-note-preview:free'
    def handler(request):
        assert json.loads(request.content)['provider']['only'] == ['atlas-cloud']
        body = valid()
        body['model'] = settings.remote_model
        return httpx.Response(200, json=body)
    result = asyncio.run(diagnostic.probe(settings, transport=httpx.MockTransport(handler)))
    assert result['generation_valid']


def test_dots_cli_requires_execute(monkeypatch, capsys):
    monkeypatch.setattr(diagnostic, 'probe', lambda *_args, **_kwargs: pytest.fail('No network'))
    assert diagnostic.main(['--model', 'dots-studio/dots-3-note-preview:free',
                            '--provider', 'atlas-cloud']) == 0
    assert 'SIN SOLICITUDES' in capsys.readouterr().out


@pytest.mark.parametrize('args', [
    ['--model', diagnostic.MODEL, '--provider', 'atlas-cloud'],
    ['--model', 'dots-studio/dots-3-note-preview'],
    ['--provider', 'unknown'],
])
def test_cli_rejects_unauthorized_arguments(args):
    with pytest.raises(SystemExit) as error:
        diagnostic.main(args)
    assert error.value.code == 2


def test_dots_does_not_accept_other_response_model():
    result = diagnostic.summarize(200, valid(),
        expected_model='dots-studio/dots-3-note-preview:free')
    assert not result['generation_valid']
