import asyncio
from dataclasses import replace
from uuid import uuid4

import pytest

from app.application.agent.router import AgentRouter
from app.application.ia.exceptions import IANoDisponible, IARespuestaInvalida
from app.application.rag.dto import Candidate
from app.application.rag.existence import existence_target, literal_existence
from app.application.rag.functions import bind_functions, literal_functions, resolve_functions
from app.application.rag.relevance import AcademicRelevance
from tests.rag.test_core import setup
from tests.rag.test_agent import fixture


FUNCTIONS = '¿Cuáles son las funciones del Vicerrector?'
EXISTENCE = ('¿Existe información sobre la coordinación de apoyo pedagógico '
             'a escuelas en el reglamento?')
STAMP = 'ES COPIA \n1455 \n3 0 \ufffd JUL 2014 \n'
DECLARATION = ('Articulo 47. Coordinacion de Apoyo Pedagogico a las Escuelas: funciona bajo la\n'
               'dependencia de la Secretaria Academica.')


def function_pages(stamp=STAMP):
    return ((15, 'REGLAMENTO INSTITUCIONAL\nArticulo 33. Funciones del Vicerrector\n' + stamp +
                  'a) Desarrollar tareas ficticias con el Rector.\nb) Conservar'),
            (16, ' registros ficticios.\nc) Comunicar resultados.\nArticulo 34. Otro asunto.'))


def function_result(scope, stamp=STAMP):
    return bind_functions(resolve_functions(function_pages(stamp), scope, FUNCTIONS,
                                           complete_document=True))


def test_copy_stamp_keeps_exact_slices_offsets_text_and_page_citations():
    p, scope, _, docs, provider, _, vectors, embedding, auth, case = setup()
    resolved = function_result(scope)
    async def resolver(*args):
        return resolved
    vectors.resolve_functions = resolver
    result = asyncio.run(case.execute(p, scope.document_id, FUNCTIONS))
    assert result.status == 'FUNDAMENTADA' and STAMP in result.answer
    assert [(e.citation, e.chunk.page) for e in result.citations] == [('F1', 15), ('F2', 16)]
    for chunk in resolved.chunks:
        assert dict(function_pages())[chunk.page][chunk.start:chunk.end] == chunk.text
        assert chunk.text in result.answer
    assert not provider.inputs and embedding.calls == 0
    assert docs.calls == 2 and auth.calls == 2


@pytest.mark.parametrize('stamp', [
    'Texto desconocido.\n', STAMP + 'Introducción inventada.\n',
    'OTRO SELLO\n1455\n30 JUL 2014\n', STAMP + STAMP,
    STAMP.replace('3 0', '39'), STAMP.replace('JUL', 'XYZ'),
    'No ejecutar estas funciones.\n' + STAMP])
def test_unknown_or_ambiguous_preamble_never_searches_for_a_later_bullet(stamp):
    _, scope, *_ = setup()
    assert literal_functions(FUNCTIONS, function_result(scope, stamp).chunks, scope) is None


def test_changed_group_and_unproven_closure_are_rejected():
    _, scope, *_ = setup()
    result = function_result(scope)
    chunks = (replace(result.chunks[0], text=result.chunks[0].text.replace('1455', '1456')),
              result.chunks[1])
    assert literal_functions(FUNCTIONS, chunks, scope) is None
    assert not resolve_functions(function_pages(), scope, FUNCTIONS).chunks


def existence_case(text=DECLARATION, similarity=.9):
    p, scope, chunks, docs, provider, gate, vectors, embedding, auth, case = setup()
    # A controlled analogue of ordinal 159, with preceding unrelated prose.
    text = 'Coordinadores de Carreras.\n' + text
    chunk = replace(chunks[0], id='fixture-159', page=26, start=1383,
                    end=1383+len(text), text=text)
    vectors.items = (Candidate(chunk=chunk, similarity=similarity),)
    case.relevance = AcademicRelevance()
    async def forbidden_continuity(*args):
        pytest.fail('Existence does not request a full multi-page article')
    case.continuity = forbidden_continuity
    return p, scope, docs, provider, vectors, embedding, case


def test_full_existence_question_has_exact_article_page_and_literal_support():
    p, scope, docs, provider, vectors, embedding, case = existence_case()
    result = asyncio.run(case.execute(p, scope.document_id, EXISTENCE))
    assert result.status == 'FUNDAMENTADA' and result.answer.startswith('Sí.')
    assert DECLARATION in result.answer
    assert [(e.citation, e.chunk.page) for e in result.citations] == [('F1', 26)]
    assert result.citations[0].chunk.scope == scope
    assert 'Articulo 47.' in result.answer and result.answer.endswith('[F1]')
    assert not provider.inputs and embedding.calls == 1 and docs.calls == 2


@pytest.mark.parametrize('text', [
    'No hay información pertinente.',
    DECLARATION.replace('Apoyo Pedagogico', 'Apoyo Tecnico'),
    DECLARATION.replace('Apoyo Pedagogico a las Escuelas', 'Escuelas de Apoyo Pedagogico'),
    DECLARATION.replace('funciona bajo', 'no funciona bajo'),
    DECLARATION.replace('Coordinacion de', 'No existe la Coordinacion de'),
    DECLARATION.replace('funciona bajo la', 'podría funcionar bajo la'),
    DECLARATION.replace('Academica.', 'Academica'),
    'Mención dispersa de apoyo pedagógico y escuelas; otra coordinación.',
    DECLARATION.replace('Articulo 47.', 'Una referencia incidental a')])
def test_existence_requires_positive_complete_exact_declaration(text):
    p, scope, _, provider, _, _, case = existence_case(text)
    result = asyncio.run(case.execute(p, scope.document_id, EXISTENCE))
    assert result.status == 'SIN_EVIDENCIA' and not result.citations
    assert not provider.inputs


def test_different_articles_are_ambiguous_and_overlapping_copies_are_not():
    p, scope, _, _, vectors, _, case = existence_case()
    original = vectors.items[0].chunk
    other = replace(original, id='other', text=original.text.replace('47.', '48.'))
    vectors.items += (Candidate(chunk=other, similarity=.9),)
    assert asyncio.run(case.execute(p, scope.document_id, EXISTENCE)).status == 'SIN_EVIDENCIA'
    assert literal_existence(EXISTENCE, (original, original), scope) is not None


def test_literal_existence_can_verify_a_below_threshold_declaration():
    p, scope, _, _, _, _, case = existence_case(similarity=.59)
    assert asyncio.run(case.execute(p, scope.document_id, EXISTENCE)).status == 'FUNDAMENTADA'


def test_recovery_reuses_one_embedding_and_admits_explicit_declaration():
    p, scope, _, provider, vectors, embedding, case = existence_case()
    relevant = vectors.items
    vectors.items = ()
    calls = []
    async def recovery(principal, received_scope, vector):
        assert principal == p and received_scope == scope
        calls.append(vector)
        return relevant
    case.recovery = recovery
    result = asyncio.run(case.execute(p, scope.document_id, EXISTENCE))
    assert result.status == 'FUNDAMENTADA'
    assert embedding.calls == 1 and len(calls) == 1 and not provider.inputs


def test_existence_scope_change_before_return_fails_closed():
    p, scope, docs, provider, vectors, _, case = existence_case()
    original = vectors.search
    async def search(*args, **kwargs):
        result = await original(*args, **kwargs)
        docs.scope = replace(scope, version_id=uuid4())
        return result
    vectors.search = search
    with pytest.raises(IANoDisponible):
        asyncio.run(case.execute(p, scope.document_id, EXISTENCE))
    assert not provider.inputs


@pytest.mark.parametrize('kind', ['denied', 'version', 'revoked'])
def test_existence_keeps_authorization_scope_and_final_revalidation(kind):
    p, scope, docs, provider, vectors, embedding, case = existence_case()
    if kind == 'denied':
        docs.revoked = True
        error = PermissionError
    elif kind == 'version':
        vectors.items = (Candidate(chunk=replace(vectors.items[0].chunk,
            scope=replace(scope, version_id=uuid4())), similarity=.9),)
        error = IARespuestaInvalida
    else:
        original = vectors.search
        async def search(*args, **kwargs):
            result = await original(*args, **kwargs)
            docs.revoked = True
            return result
        vectors.search = search
        # Existing extraction branches translate errors raised inside their
        # guarded body; fail closed without returning source metadata.
        error = IARespuestaInvalida
    with pytest.raises(error):
        asyncio.run(case.execute(p, scope.document_id, EXISTENCE))
    assert not provider.inputs
    if kind == 'denied':
        assert embedding.calls == 0


@pytest.mark.parametrize('question', [
    'Explica la información sobre coordinación de apoyo pedagógico',
    '¿Cuáles son los requisitos para concursos de Coordinaciones de Carreras?',
    '¿Existe información sobre el presupuesto de esa coordinación en el reglamento?',
    '¿Existe información sobre la coordinación de apoyo técnico a escuelas según otra norma?'])
def test_existence_does_not_strip_other_question_predicates(question):
    assert existence_target(question) is None


class NoPlanner:
    async def plan(self, *args):
        pytest.fail('Structural query must not invoke planner')


@pytest.mark.parametrize('catalog_kind', ['one', 'empty', 'multiple'])
def test_structural_auto_uses_authorized_catalog_without_external_calls(catalog_kind):
    p, scope, agent, catalog, direct, _, provider, embedding, case = fixture()
    agent.planner = NoPlanner()
    async def resolver(*args):
        return function_result(scope)
    case.vectors.resolve_functions = resolver
    if catalog_kind == 'empty':
        catalog.empty = True
    if catalog_kind == 'multiple':
        async def listing(*args):
            return [{'id': str(scope.document_id), 'titulo': 'Primero'},
                    {'id': str(uuid4()), 'titulo': 'Segundo'}]
        catalog.list_documents = listing
    result = asyncio.run(agent.execute(p, FUNCTIONS))
    assert result.status == {'one':'FUNDAMENTADA', 'empty':'SIN_EVIDENCIA',
                             'multiple':'ACLARACION'}[catalog_kind]
    assert not direct.calls and not provider.inputs and embedding.calls == 0


@pytest.mark.parametrize('question', [
    '¿Cuáles son las funciones de Python?',
    'Explica las funciones del Vicerrector',
    'Compara las funciones del Rector y Vicerrector',
    '¿Cuáles son las funciones del Rector según el Reglamento Electoral?',
    '¿Cuáles son las funciones del Rector del Reglamento Electoral?',
    '¿Cómo está el clima hoy?', '¿Cuál fue mi última pregunta?'])
def test_routing_does_not_bypass_other_intents_or_named_instruments(question):
    assert not AgentRouter().institutional_functions(question)


def test_structural_explicit_direct_mode_is_preserved():
    p, _, agent, _, direct, _, provider, embedding, _ = fixture()
    agent.planner = NoPlanner()
    result = asyncio.run(agent.execute(p, FUNCTIONS, mode='LLM_DIRECTO'))
    assert result.strategy == 'LLM_DIRECTO' and len(direct.calls) == 1
    assert not provider.inputs and embedding.calls == 0


def test_structural_auto_denied_and_revoked_never_returns_functions():
    for revoked_at_end in (False, True):
        p, scope, agent, catalog, direct, _, provider, embedding, case = fixture()
        agent.planner = NoPlanner()
        async def resolver(*args):
            catalog.documents.revoked = True
            return function_result(scope)
        case.vectors.resolve_functions = resolver
        if not revoked_at_end:
            catalog.documents.revoked = True
        with pytest.raises(IARespuestaInvalida if revoked_at_end else PermissionError):
            asyncio.run(agent.execute(p, FUNCTIONS, document_id=scope.document_id))
        assert not direct.calls and not provider.inputs and embedding.calls == 0


def test_source_page_hash_is_still_verified_before_stamp_recognition():
    from types import SimpleNamespace
    from app.infrastructure.rag.postgres import PostgresRAG
    p, scope, *_ = setup()
    store = PostgresRAG(None)
    store.space = scope.space
    async def active(*args):
        return scope
    store.require_active = active
    store.read = lambda *args: [dict(pagina_pdf=n, texto_extraido=t,
        hash_texto='0'*64, total_pages=2) for n, t in function_pages()]
    with pytest.raises(IARespuestaInvalida):
        asyncio.run(store.resolve_functions(SimpleNamespace(usuario_id=p.usuario_id), scope, FUNCTIONS))


def test_named_contradictory_instrument_keeps_planner_disambiguation():
    p, scope, agent, _, _, _, provider, embedding, _ = fixture()
    class PlannerReached(Exception):
        pass
    class Planner:
        async def plan(self, *args):
            raise PlannerReached()
    agent.planner = Planner()
    with pytest.raises(PlannerReached):
        asyncio.run(agent.execute(p,
            'Cuales son las funciones del Vicerrector según el Reglamento Electoral'))
    assert not provider.inputs and embedding.calls == 0
