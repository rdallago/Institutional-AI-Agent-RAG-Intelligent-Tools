"""Regresiones del diagnóstico; ninguna llamada a servicios reales."""
import asyncio
import json
from unittest.mock import Mock

import httpx
import pytest

from tests.rag.test_jina_10b_audit import diagnostic
from app.infrastructure.configuration.embeddings import EmbeddingConfig
from app.application.ia.exceptions import IANoDisponible

SECRET = 'never-print-this-key'
CONFIG = EmbeddingConfig(provider='jina', testing=True, api_key=SECRET)


@pytest.mark.parametrize('key,code', [('', 'missing_api_key'), ('  ', 'missing_api_key'),
                                    (SECRET+'\r\n', 'invalid_configuration')])
def test_configuration_errors_before_any_client(monkeypatch, capsys, key, code):
    monkeypatch.setenv('JINA_API_KEY', key)
    monkeypatch.setattr(diagnostic, 'JinaEmbeddings', lambda *_a, **_k: pytest.fail('No client'))
    assert diagnostic.main(['--execute']) == 2
    output = capsys.readouterr().out
    result = json.loads(output)
    assert result['error_code'] == code and result['stage'] == 'configuration'
    assert SECRET not in output


def test_client_constructor_is_now_caught(monkeypatch):
    def rejected(*_a, **_k):
        raise OSError('Authorization: Bearer '+SECRET)
    monkeypatch.setattr(diagnostic, 'JinaEmbeddings', rejected)
    result = asyncio.run(diagnostic.probe(CONFIG))
    assert result['stage'] == 'client_initialization'
    assert result['error_type'] == 'OSError' and result['http'] is None
    assert SECRET not in json.dumps(result)


def test_resource_failure_categorized_without_transport(monkeypatch):
    from dataclasses import replace
    def blocked(_): raise IANoDisponible()
    monkeypatch.setattr('app.infrastructure.rag.resources.require_memory', blocked)
    monkeypatch.setattr(diagnostic, 'JinaEmbeddings', lambda *_a, **_k: pytest.fail('No client'))
    result = asyncio.run(diagnostic.probe(replace(CONFIG, testing=False)))
    assert result['stage'] == 'resources' and result['error_code'] == 'resource_check_failed'


@pytest.mark.parametrize('status,code', [(401, 'authentication_rejected'),
    (402, 'payment_or_balance_rejected'), (403, 'access_or_balance_rejected'),
    (429, 'rate_limited'), (503, 'provider_unavailable'), (504, 'timeout')])
def test_http_failure_status_is_preserved(status, code):
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(status, text='Sensitive body '+SECRET)
    result = asyncio.run(diagnostic.probe(CONFIG, transport=httpx.MockTransport(handler)))
    assert result['http'] == status and result['error_code'] == code
    assert len(calls) == 1 and SECRET not in json.dumps(result)


@pytest.mark.parametrize('error,code', [(httpx.ConnectError, 'availability_or_transport_failed'),
                                     (httpx.ReadTimeout, 'timeout')])
def test_network_does_not_report_missing_key(error, code):
    calls = []
    def handler(request):
        calls.append(request)
        raise error(SECRET, request=request)
    result = asyncio.run(diagnostic.probe(CONFIG, transport=httpx.MockTransport(handler)))
    assert result['http'] is None and result['error_code'] == code
    assert result['stage'] == 'request_and_validation'
    assert len(calls) == 1 and SECRET not in json.dumps(result)


@pytest.mark.parametrize('primary_failure', [True, False])
def test_close_failure_never_hides_request_result(monkeypatch, primary_failure):
    class Provider:
        client = Mock(event_hooks={'response': []})
        async def _embed(self, *_args):
            if primary_failure: raise IANoDisponible()
            return (1.,) + (0.,)*767
        async def close(self): raise RuntimeError(SECRET)
    monkeypatch.setattr(diagnostic, 'JinaEmbeddings', lambda *_a, **_k: Provider())
    result = asyncio.run(diagnostic.probe(CONFIG))
    assert not result['valid']
    if primary_failure:
        assert result['error_code'] == 'availability_or_transport_failed'
        assert result['cleanup_error']['error_code'] == 'client_close_failed'
    else:
        assert result['error_code'] == 'client_close_failed' and result['dimensions'] == 768
    assert SECRET not in json.dumps(result)


def test_main_execution_failure_safe_and_interrupt_no_retry(monkeypatch, capsys):
    monkeypatch.setenv('JINA_API_KEY', SECRET)
    async def interrupted(*_args): raise KeyboardInterrupt(SECRET)
    monkeypatch.setattr(diagnostic, 'probe', interrupted)
    assert diagnostic.main(['--execute']) == 2
    output = capsys.readouterr().out
    assert json.loads(output)['error_code'] == 'interrupted'
    assert SECRET not in output


def test_non_finite_response_reports_contract_error():
    raw = '{"model":"jina-embeddings-v3","data":[{"index":0,"embedding":[NaN]}]}'
    result = asyncio.run(diagnostic.probe(CONFIG, transport=httpx.MockTransport(
        lambda _: httpx.Response(200, text=raw))))
    assert result['error_code'] == 'invalid_response' and result['http'] == 200
