import json
import os
import asyncio

import pytest

from app.application.agent import diagnostics as private
from app.application.rag.diagnostics import generation
from app.application.rag.relevance import AcademicRelevance
from app.application.rag.structured_output import parse, supported_text
from tests.rag.test_structured_output import evidence, output, QUESTION
from app.application.ia.dto import GeneracionSalida
from app.application.ia.exceptions import IARespuestaInvalida
from app.application.rag.core import build_context
from app.infrastructure.configuration.llm import LLMConfig
from app.infrastructure.rag.ollama import GroundedProvider
from app.infrastructure.rag.text import ConservativeCounter


@pytest.mark.parametrize('valid,invalid,outcome', [
    (0, 0, 'model_abstention'), (1, 0, 'grounded'),
    (0, 1, 'all_claims_rejected'), (1, 1, 'partial_grounded')])
def test_claim_counts_and_reasons(monkeypatch, valid, invalid, outcome):
    monkeypatch.delenv('AGENT_PRIVATE_DIAGNOSTIC_DIR', raising=False)
    claims = ([{'text': 'El Rectorado es la unidad de gestion institucional.', 'source_ids': ['F1']}] * valid
              + [{'text': 'El Rectorado concede becas.', 'source_ids': ['F1']}] * invalid)
    e = evidence()
    parsed = parse(output(claims), e)
    supported_text(parsed, QUESTION, e, AcademicRelevance())
    event = private.private_diagnostics()[-1]
    assert (event['generated'], event['accepted'], event['rejected']) == (valid+invalid, valid, invalid)
    assert event['outcome'] == outcome
    if invalid:
        rejected = event['claims'][-1]
        assert rejected['reason'] == 'support_rejected'
        assert any('becas' in c['missing_terms'] for u in rejected['units'] for c in u['comparisons'])


def test_literal_requires_opt_in_and_never_enters_buffer(tmp_path, monkeypatch, caplog):
    monkeypatch.setenv('AGENT_PRIVATE_DIAGNOSTIC_DIR', str(tmp_path))
    monkeypatch.setattr(private, 'restricted_directory', lambda _: True)
    monkeypatch.delenv('AGENT_PRIVATE_CAPTURE_RAG_JSON', raising=False)
    e = evidence()
    raw = output([])
    generation(raw, e, True, 0)
    first = next(tmp_path.glob('*.json'))
    assert 'literal_json' not in json.loads(first.read_text(encoding='utf-8'))
    monkeypatch.setenv('AGENT_PRIVATE_CAPTURE_RAG_JSON', 'true')
    generation(raw, e, True, 0)
    second = next(p for p in tmp_path.glob('*.json') if p != first)
    entry = json.loads(second.read_text(encoding='utf-8'))
    assert entry['literal_json'] == raw.respuesta
    assert len(entry['sources'][0]['sha256']) == 64
    assert 'literal_json' not in private.private_diagnostics()[-1]
    assert raw.respuesta not in caplog.text
    if os.name != 'nt':
        assert second.stat().st_mode & 0o077 == 0


def test_permissions_and_limits_fail_closed(tmp_path, monkeypatch):
    monkeypatch.setenv('AGENT_PRIVATE_DIAGNOSTIC_DIR', str(tmp_path))
    monkeypatch.setenv('AGENT_PRIVATE_CAPTURE_RAG_JSON', 'true')
    monkeypatch.setattr(private, 'restricted_directory', lambda _: False)
    generation(output([]), evidence(), True, 0)
    assert not list(tmp_path.iterdir())
    monkeypatch.setattr(private, 'restricted_directory', lambda _: True)
    for n in range(64):
        (tmp_path / f'agent-private-{n}.json').write_text('{}')
    generation(output([]), evidence(), True, 0)
    assert len(list(tmp_path.iterdir())) == 64


def test_export_failure_does_not_change_validation(tmp_path, monkeypatch):
    monkeypatch.setenv('AGENT_PRIVATE_DIAGNOSTIC_DIR', str(tmp_path))
    monkeypatch.setattr(private, 'restricted_directory', lambda _: (_ for _ in ()).throw(OSError()))
    generation(output([]), evidence(), True, 0)
    result, _ = supported_text(parse(output([]), evidence()), QUESTION, evidence(), AcademicRelevance())
    assert result.respuesta == 'SIN_EVIDENCIA'


def test_malformed_json_records_failure_without_repair(monkeypatch):
    monkeypatch.delenv('AGENT_PRIVATE_DIAGNOSTIC_DIR', raising=False)
    async def run():
        e = evidence()
        context = build_context(QUESTION, (e[0].chunk,), ConservativeCounter())
        provider = GroundedProvider(LLMConfig(enabled=True, environment='local-development',
            model='qwen2.5:1.5b', enforce_memory_guard=False))
        async def generate(*args, **kwargs):
            return GeneracionSalida(respuesta='{"claims":[', finalizacion='completa')
        provider._generate_validated = generate
        try:
            with pytest.raises(IARespuestaInvalida):
                await provider.generate_grounded(context)
        finally:
            await provider.aclose()
    asyncio.run(run())
    event = private.private_diagnostics()[-1]
    assert event['json_valid'] is False and event['generated'] is None
    assert 'literal_json' not in event


def test_directory_permission_check(tmp_path, monkeypatch):
    assert not private.restricted_directory(tmp_path / 'absent')
    if os.name == 'nt':
        import subprocess
        from types import SimpleNamespace
        calls = []
        def check(*args, **kwargs):
            calls.append((args, kwargs))
            return SimpleNamespace(returncode=1)
        monkeypatch.setattr(subprocess, 'run', check)
        assert not private.restricted_directory(tmp_path)
        assert 'AreAccessRulesProtected' in calls[0][0][0][-1]
        assert 'S-1-5-18' in calls[0][0][0][-1]
    else:
        tmp_path.chmod(0o700)
        assert private.restricted_directory(tmp_path)
        tmp_path.chmod(0o755)
        assert not private.restricted_directory(tmp_path)


def test_request_correlation_and_publication(monkeypatch):
    from tests.rag.test_structured_output import test_use_case_marks_partial_response_and_publishes_only_valid_sources
    monkeypatch.delenv('AGENT_PRIVATE_DIAGNOSTIC_DIR', raising=False)
    token = private.request_identifier.set('controlled-request')
    try:
        test_use_case_marks_partial_response_and_publishes_only_valid_sources()
        event = private.private_diagnostics()[-1]
        assert event['request_id'] == 'controlled-request'
        assert event['stage'] == 'publication'
        assert event['outcome'] == 'partial_grounded'
    finally:
        private.request_identifier.reset(token)
