"""Retrieved low-score evidence is usable only by exact literal existence checks."""
import asyncio
import logging
from dataclasses import replace
from uuid import uuid4

import pytest

from app.application.ia.exceptions import IARespuestaInvalida
from app.application.rag.dto import Candidate
from tests.rag.test_final_corrections_12f import existence_case as base_case, EXISTENCE, DECLARATION
from tests.rag.test_safe_retrieval_closure_12f import forbid_external_connections
from tests.rag.test_safe_retrieval_closure_12f import events


SCORE = 0.5442609896426569


def existence_case(*args, **kwargs):
    values = base_case(*args, **kwargs)
    values[-1].threshold = .6  # Production threshold; base synthetic fixture uses .7.
    return values


def test_reported_159_below_threshold_is_literal_only_and_keeps_recovery():
    p, scope, docs, provider, vectors, embedding, case = existence_case(similarity=SCORE)
    vectors.items = (Candidate(chunk=replace(vectors.items[0].chunk, ordinal=159), similarity=SCORE),)
    original = vectors.items
    calls = []
    search = vectors.search
    async def tracked_search(*args, **kwargs):
        calls.append(('search', kwargs['limit']))
        return await search(*args, **kwargs)
    async def recovery(principal, received_scope, vector):
        assert principal == p and received_scope == scope and len(vector) == 768
        calls.append(('recovery', len(original)))
        return original
    vectors.search = tracked_search
    case.recovery = recovery
    result = asyncio.run(case.execute(p, scope.document_id, EXISTENCE))
    assert result.status == 'FUNDAMENTADA' and DECLARATION in result.answer
    assert [(e.citation, e.chunk.page, e.chunk.ordinal) for e in result.citations] == [('F1', 26, 159)]
    assert calls == [('search', 12), ('recovery', 1)]
    assert vectors.items is original and case.threshold == .6
    assert embedding.calls == 1 and not provider.inputs and docs.calls == 2


@pytest.mark.parametrize('text', [
    'Mencion incidental sin declaracion.',
    DECLARATION.replace('Apoyo Pedagogico', 'Apoyo Tecnico'),
    DECLARATION.replace('funciona bajo', 'no funciona bajo'),
    DECLARATION[:-1],
    DECLARATION.replace('Articulo 47.', ''),
])
def test_low_score_never_substitutes_for_literal_support(text):
    p, scope, _, provider, _, _, case = existence_case(text, similarity=SCORE)
    result = asyncio.run(case.execute(p, scope.document_id, EXISTENCE))
    assert result.status == 'SIN_EVIDENCIA' and not result.citations and not provider.inputs


def test_distinct_below_threshold_declaration_is_ambiguous_even_across_batches():
    p, scope, _, provider, vectors, _, case = existence_case(similarity=SCORE)
    first = vectors.items[0]
    other = Candidate(chunk=replace(first.chunk, id='different', page=27,
                      text=first.chunk.text.replace('47.', '48.')), similarity=.4)
    async def recovery(*args):
        return (other,)
    case.recovery = recovery
    result = asyncio.run(case.execute(p, scope.document_id, EXISTENCE))
    assert result.status == 'SIN_EVIDENCIA' and not result.citations and not provider.inputs


@pytest.mark.parametrize('bad', ['document', 'version', 'offset', 'page', 'nul', 'nan'])
def test_low_score_never_bypasses_scope_or_formal_integrity(bad):
    p, scope, _, provider, vectors, _, case = existence_case(similarity=SCORE)
    candidate = vectors.items[0]
    chunk = candidate.chunk
    if bad == 'document':
        chunk = replace(chunk, scope=replace(scope, document_id=uuid4()))
    elif bad == 'version':
        chunk = replace(chunk, scope=replace(scope, version_id=uuid4()))
    elif bad == 'offset':
        chunk = replace(chunk, end=chunk.end+1)
    elif bad == 'page':
        chunk = replace(chunk, page=0)
    elif bad == 'nul':
        chunk = replace(chunk, text=chunk.text[:-1]+'\x00')
    vectors.items = (Candidate(chunk=chunk, similarity=float('nan') if bad == 'nan' else SCORE),)
    with pytest.raises(IARespuestaInvalida):
        asyncio.run(case.execute(p, scope.document_id, EXISTENCE))
    assert not provider.inputs


@pytest.mark.parametrize('revoked', [False, True])
def test_low_score_acl_denial_or_final_revocation_fails_closed(revoked):
    p, scope, docs, provider, vectors, embedding, case = existence_case(similarity=SCORE)
    if revoked:
        original = vectors.search
        async def search(*args, **kwargs):
            result = await original(*args, **kwargs)
            docs.revoked = True
            return result
        vectors.search = search
    else:
        docs.revoked = True
    with pytest.raises(IARespuestaInvalida if revoked else PermissionError):
        asyncio.run(case.execute(p, scope.document_id, EXISTENCE))
    assert not provider.inputs
    if not revoked:
        assert embedding.calls == 0


def test_non_existence_question_keeps_global_threshold_and_never_generates():
    p, scope, _, provider, _, _, case = existence_case(similarity=SCORE)
    result = asyncio.run(case.execute(p, scope.document_id,
        'Describi la coordinacion de apoyo pedagogico a escuelas.'))
    assert result.status == 'SIN_EVIDENCIA' and not result.citations
    assert case.threshold == .6 and not provider.inputs


@pytest.mark.parametrize('score,expected', [(.599999, 0), (.6, 1)])
def test_non_existence_threshold_boundary_is_unchanged(score, expected):
    p, scope, _, provider, _, _, case = existence_case(similarity=score)
    received = []
    class Relevance:
        def select(self, question, chunks):
            received.append(len(chunks))
            return ()
    case.relevance = Relevance()
    result = asyncio.run(case.execute(p, scope.document_id, 'Otra pregunta documental.'))
    assert result.status == 'SIN_EVIDENCIA' and received == [expected] and not provider.inputs


def test_diagnostic_keeps_failed_threshold_and_records_literal_arrival(monkeypatch, caplog):
    p, scope, _, _, vectors, _, case = existence_case(similarity=SCORE)
    vectors.items = (replace(vectors.items[0], chunk=replace(vectors.items[0].chunk, ordinal=159)),)
    case.diagnostic_environment = 'local-development'
    monkeypatch.setenv('AGENT_RAG_RETRIEVAL_DIAGNOSTICS', 'true')
    with caplog.at_level(logging.WARNING, logger='app.rag'):
        result = asyncio.run(case.execute(p, scope.document_id, EXISTENCE))
    rows = events(caplog)
    initial = next(r for r in rows if r['stage'] == 'initial_selection')
    literal = next(r for r in rows if r['stage'] == 'literal_existence')
    assert result.status == 'FUNDAMENTADA'
    assert initial['ordinal'] == literal['ordinal'] == 159
    assert initial['threshold_passed'] is False and initial['pertinent'] is None
    assert literal['reached_literal_existence'] is True and literal['pertinent'] is None


@pytest.mark.parametrize('batch', ['initial', 'recovery'])
def test_candidate_limits_remain_enforced(batch):
    p, scope, _, provider, vectors, _, case = existence_case(similarity=SCORE)
    if batch == 'initial':
        async def search(*args, **kwargs):
            return vectors.items * 13
        vectors.search = search
    else:
        async def recovery(*args):
            return vectors.items * 49
        case.recovery = recovery
    with pytest.raises(IARespuestaInvalida):
        asyncio.run(case.execute(p, scope.document_id, EXISTENCE))
    assert not provider.inputs
