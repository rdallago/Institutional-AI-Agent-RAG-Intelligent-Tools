"""Auditoría aislada: no servicios reales, sin modificar fixtures heredados."""
import asyncio
from dataclasses import replace
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory

from app.application.ia.exceptions import IARespuestaInvalida
from app.application.rag.core import build_context
from app.infrastructure.configuration.embeddings import EmbeddingConfig
from app.infrastructure.rag.jina import DOCUMENT_EXPORT_APPROVED
from tests.rag.test_agent import fixture
from tests.rag.test_relevance import academic_case

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location('jina_passage_diagnostic', ROOT / 'infra' / 'diagnose_jina_passage.py')
diagnostic = importlib.util.module_from_spec(spec)
spec.loader.exec_module(diagnostic)


def test_synthetic_cli_default_has_no_network(monkeypatch, capsys):
    monkeypatch.setattr(diagnostic, 'probe', lambda *_a, **_k: pytest.fail('No HTTP'))
    assert diagnostic.main([]) == 0
    assert 'SIN SOLICITUDES' in capsys.readouterr().out


@pytest.mark.parametrize('valid', [True, False])
def test_only_fixed_passage_with_shared_validator(valid, capsys, caplog):
    calls = []
    def handler(request):
        calls.append(request)
        payload = json.loads(request.content)
        assert payload['input'] == [diagnostic.SYNTHETIC]
        assert payload['task'] == 'retrieval.passage'
        assert payload['model'] == 'jina-embeddings-v3' and payload['dimensions'] == 768
        assert str(request.url) == 'https://api.jina.ai/v1/embeddings'
        return httpx.Response(200, json={'model': payload['model'], 'data': [
            {'index': 0, 'embedding': [1.] + [0.] * (767 if valid else 10)}]})
    config = EmbeddingConfig(provider='jina', testing=True, api_key='synthetic-secret')
    result = asyncio.run(diagnostic.probe(config, transport=httpx.MockTransport(handler)))
    assert result['valid'] is valid and result['http'] == 200 and len(calls) == 1
    assert 'synthetic-secret' not in json.dumps(result) + capsys.readouterr().out + caplog.text
    assert DOCUMENT_EXPORT_APPROVED is False


def test_catalog_counter_failure_is_redundant_read_not_jina(monkeypatch):
    monkeypatch.setattr('app.infrastructure.configuration.embeddings.load_embedding_config',
                        lambda *_a, **_k: pytest.fail('No cloud configuration'))
    p, scope, agent, catalog, direct, skills, provider, _, _ = fixture()
    result = asyncio.run(agent.execute(p, '¿Cuánto tiempo dura la regularidad de una unidad curricular?'))
    assert catalog.listed == 2
    assert result.status == 'FUNDAMENTADA' and not direct.calls
    assert skills.selected == ['academic-rag']


def test_missing_title_is_fixture_contract_error():
    p, scope, agent, catalog, *_ = fixture()
    async def invalid(_): return [{'id': scope.document_id}, {'id': uuid4()}]
    catalog.list_documents = invalid
    with pytest.raises(KeyError, match='titulo'):
        asyncio.run(agent.execute(p, 'Regularidad curricular'))
    async def valid(_):
        return [{'id': scope.document_id, 'titulo': 'Documento uno'}, {'id': uuid4(), 'titulo': 'Documento dos'}]
    catalog.list_documents = valid
    result = asyncio.run(agent.execute(p, 'Regularidad curricular'))
    assert result.status == 'ACLARACION'


def test_default_answer_fixture_rejection_is_correct():
    _, _, provider, case = academic_case()
    question = '¿Cuáles son los requisitos para mantener la regularidad de una unidad curricular?'
    context = build_context(question, tuple(c.chunk for c in case.vectors.items), case.counter)
    explanation = case.relevance.explain_answer(question, provider.output.respuesta, context.evidence)
    assert provider.output.respuesta == 'Norma ficticia [F1].'
    assert not explanation['supported']
    assert explanation['claims'][0]['comparisons'][0]['missing_terms'] == ['ficticia', 'norma']
    assert case.relevance.supports_answer(question,
        'La regularidad de una unidad curricular exige asistencia [F1].', context.evidence)


def test_alembic_graph_without_environment_or_database():
    config = Config()
    config.set_main_option('script_location', str(ROOT / 'backend' / 'migrations'))
    script = ScriptDirectory.from_config(config)
    assert script.get_heads() == ['0006_cloud_embeddings']
    assert script.get_revision('0006_cloud_embeddings').down_revision == '0005_agent_memory'
    assert script.get_revision('0005_agent_memory').down_revision == '0004_rag'
