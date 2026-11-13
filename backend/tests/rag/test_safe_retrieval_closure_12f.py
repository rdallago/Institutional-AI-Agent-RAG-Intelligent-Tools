import asyncio
import json
import logging
import socket
from dataclasses import replace

import pytest

from app.application.agent.diagnostics import execution_trace
from app.application.rag.dto import Candidate
from app.application.rag.functions import literal_functions
from app.application.rag.retrieval_diagnostics import observe_candidates
from tests.rag.test_final_corrections_12f import (
    FUNCTIONS, EXISTENCE, function_result, function_pages, existence_case,
)
from tests.rag.test_core import setup


STAMP = 'ES COPIA\n1455\n3 0 \u00b7 JUL 2014\n'


@pytest.fixture(autouse=True)
def forbid_external_connections(monkeypatch):
    # Windows asyncio crea su self-pipe mediante socketpair TCP de loopback.
    for method in ('connect', 'connect_ex'):
        original = getattr(socket.socket, method)
        def guarded(sock, address, _original=original):
            if not isinstance(address, tuple) or address[0] not in ('127.0.0.1', '::1'):
                pytest.fail('No external network connections allowed')
            return _original(sock, address)
        monkeypatch.setattr(socket.socket, method, guarded)


def events(caplog):
    return [json.loads(r.message.split(' ', 1)[1]) for r in caplog.records
            if r.message.startswith('rag_retrieval_diagnostic ')]


def test_realistic_middle_dot_preserves_complete_two_page_article():
    p, scope, _, docs, provider, _, vectors, embedding, auth, case = setup()
    resolved = function_result(scope, STAMP)
    async def resolver(*args):
        return resolved
    vectors.resolve_functions = resolver
    result = asyncio.run(case.execute(p, scope.document_id, FUNCTIONS))
    assert result.status == 'FUNDAMENTADA' and STAMP in result.answer
    assert [(c.citation, c.chunk.page) for c in result.citations] == [('F1', 15), ('F2', 16)]
    for chunk in resolved.chunks:
        assert dict(function_pages(STAMP))[chunk.page][chunk.start:chunk.end] == chunk.text
        assert chunk.text in result.answer
    assert not provider.inputs and embedding.calls == 0


@pytest.mark.parametrize('stamp', [
    STAMP.replace('\u00b7', '/'), STAMP.replace('\u00b7', ':'),
    STAMP + STAMP, STAMP + 'Prosa inesperada.\n',
    STAMP.replace('3 0', '31').replace('JUL', 'FEB'),
    STAMP.replace('2014', '1914'), STAMP.replace('JUL', 'XYZ'),
])
def test_middle_dot_does_not_expand_other_stamp_grammar(stamp):
    _, scope, *_ = setup()
    assert literal_functions(FUNCTIONS, function_result(scope, stamp).chunks, scope) is None


@pytest.mark.parametrize('environment,flag', [
    ('local-development', None), ('local-development', 'false'),
    ('production', 'true'), (None, 'true'),
])
def test_observability_is_off_unless_explicit_local_opt_in(monkeypatch, caplog, environment, flag):
    if flag is None:
        monkeypatch.delenv('AGENT_RAG_RETRIEVAL_DIAGNOSTICS', raising=False)
    else:
        monkeypatch.setenv('AGENT_RAG_RETRIEVAL_DIAGNOSTICS', flag)
    _, scope, chunks, *_ = setup()
    with caplog.at_level(logging.INFO, logger='app.rag'):
        observe_candidates(environment, 'initial', (Candidate(chunk=chunks[0], similarity=.9),), scope, .6)
    assert not events(caplog)


def test_metadata_pipeline_preserves_output_candidates_and_provider_calls(monkeypatch, caplog):
    p, scope, docs, provider, vectors, embedding, case = existence_case()
    original = vectors.items
    vectors.items = tuple(Candidate(chunk=replace(c.chunk, ordinal=159), similarity=c.similarity)
                          for c in original)
    original = vectors.items
    baseline = asyncio.run(case.execute(p, scope.document_id, EXISTENCE))
    case.diagnostic_environment = 'local-development'
    monkeypatch.setenv('AGENT_RAG_RETRIEVAL_DIAGNOSTICS', 'true')
    token = execution_trace.set('a' * 32)
    try:
        with caplog.at_level(logging.INFO, logger='app.rag'):
            observed = asyncio.run(case.execute(p, scope.document_id, EXISTENCE))
    finally:
        execution_trace.reset(token)
    assert observed == baseline and vectors.items is original
    assert not provider.inputs and embedding.calls == 2
    records = events(caplog)
    assert [r['stage'] for r in records] == ['initial', 'initial_selection', 'literal_existence']
    assert all(r['ordinal'] == 159 and r['page'] == 26 and r['trace_id'] == 'a'*32 for r in records)
    assert records[0]['score'] == .9 and records[0]['threshold_passed'] is True
    assert records[1]['pertinent'] is True and records[-1]['reached_literal_existence'] is True
    for r in records:
        assert set(r) == {'trace_id', 'stage', 'ordinal', 'page', 'score', 'threshold_passed',
                          'scope_authorization', 'integrity', 'pertinent', 'reached_literal_existence'}
    assert 'Coordinacion' not in '\n'.join(json.dumps(r) for r in records)


def test_recovery_logs_rejection_and_acceptance_without_reordering(monkeypatch, caplog):
    p, scope, _, provider, vectors, embedding, case = existence_case()
    seed = replace(vectors.items[0].chunk, ordinal=159)
    unrelated = replace(seed, id='unrelated', text='Texto privado inesperado.',
                        end=seed.start+len('Texto privado inesperado.'), ordinal=158)
    vectors.items = (Candidate(chunk=unrelated, similarity=.99),)
    expanded = (Candidate(chunk=seed, similarity=.8), Candidate(chunk=unrelated, similarity=.99))
    async def recovery(*args):
        return expanded
    case.recovery = recovery
    case.diagnostic_environment = 'local-development'
    monkeypatch.setenv('AGENT_RAG_RETRIEVAL_DIAGNOSTICS', 'true')
    with caplog.at_level(logging.INFO, logger='app.rag'):
        result = asyncio.run(case.execute(p, scope.document_id, EXISTENCE))
    assert result.status == 'FUNDAMENTADA' and embedding.calls == 1 and not provider.inputs
    recovered = [e for e in events(caplog) if e['stage'] == 'recovery_selection']
    assert [(e['ordinal'], e['pertinent']) for e in recovered] == [(159, True), (158, False)]
    assert 'Texto privado' not in caplog.text
    assert expanded[0].chunk is seed and expanded[1].chunk is unrelated


def test_scope_integrity_threshold_and_trace_are_safe(monkeypatch, caplog):
    monkeypatch.setenv('AGENT_RAG_RETRIEVAL_DIAGNOSTICS', 'true')
    _, scope, chunks, *_ = setup()
    foreign = replace(scope, space='different')
    items = (Candidate(chunk=replace(chunks[0], scope=foreign), similarity=.9),
             Candidate(chunk=replace(chunks[0], end=0), similarity=.9),
             Candidate(chunk=chunks[0], similarity=.4))
    token = execution_trace.set('SECRET PROMPT JWT')
    try:
        with caplog.at_level(logging.INFO, logger='app.rag'):
            observe_candidates('local-development', 'initial_selection', items, scope, .6, pertinent=())
    finally:
        execution_trace.reset(token)
    rows = events(caplog)
    assert rows[0]['scope_authorization'] is False
    assert rows[1]['integrity'] is False
    assert rows[2]['threshold_passed'] is False
    assert all(r['trace_id'] == 'isolated' for r in rows)
    assert 'SECRET' not in caplog.text


def test_logger_failure_never_changes_result(monkeypatch):
    p, scope, _, _, _, _, case = existence_case()
    baseline = asyncio.run(case.execute(p, scope.document_id, EXISTENCE))
    case.diagnostic_environment = 'local-development'
    monkeypatch.setenv('AGENT_RAG_RETRIEVAL_DIAGNOSTICS', 'true')
    logger = logging.getLogger('app.rag')
    original = logger.warning
    def broken(message, *args, **kwargs):
        if message.startswith('rag_retrieval_diagnostic'):
            raise RuntimeError('logger unavailable')
        return original(message, *args, **kwargs)
    monkeypatch.setattr(logger, 'warning', broken)
    assert asyncio.run(case.execute(p, scope.document_id, EXISTENCE)) == baseline


def test_repository_preserves_returned_ordinal_without_query_or_order_changes():
    from app.infrastructure.rag.postgres import PostgresRAG
    p, scope, chunks, *_ = setup()
    store = PostgresRAG(None)
    store.space = scope.space
    chunk = chunks[0]
    rows = [dict(identificador_estable=str(n), pagina_inicio=chunk.page,
                 offset_inicio=chunk.start, offset_fin=chunk.end, texto=chunk.text,
                 titulo_seccion='', ordinal=n, similarity=score)
            for n, score in [(159, .9), (160, .8)]]
    def read(query, params):
        assert 'SELECT f.*' in query and params['limit'] == 12
        return rows
    store.read = read
    candidates = asyncio.run(store._search(p, scope, (1.,)+(0.,)*767, limit=12))
    assert [(c.chunk.ordinal, c.similarity) for c in candidates] == [(159, .9), (160, .8)]
