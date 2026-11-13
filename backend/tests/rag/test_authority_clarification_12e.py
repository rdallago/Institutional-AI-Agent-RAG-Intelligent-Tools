import asyncio
from dataclasses import replace

import pytest

from app.application.ia.exceptions import IANoDisponible
from app.application.rag.functions import bind_functions, literal_functions, resolve_functions
from tests.rag.test_core import setup


def pages():
    return ((12, 'REGLAMENTO ORGANICO MARCO\nArticulo 28. Funciones del Rector.\n'
                  'a. Supervisar actividades ficticias.\nb. Comunicar'),
            (13, ' resultados ficticios.\nc. Conservar registros.'),
            (14, '\nd. Coordinar tareas ficticias.\nArticulo 29. Otro asunto.\n'
                  'Articulo 33. Funciones del Vicerrector.\na. Asistir al titular.\n'
                  'Articulo 34. Otro asunto.\n'
                  'Articulo 9. Funciones del Consejo de Rectores.\na. Deliberar en conjunto.\n'
                  'Articulo 10. Otro asunto.'))


def resolve(scope, subject, document=None):
    return bind_functions(resolve_functions(document or pages(), scope,
        f'Cuales son las funciones del {subject}', complete_document=True))


@pytest.mark.parametrize('subject,expected', [
    ('Rector', 'Supervisar actividades'), ('Vicerrector', 'Asistir al titular'),
    ('Consejo de Rectores', 'Deliberar en conjunto')])
def test_exact_authorities_keep_their_own_literal_functions(subject, expected):
    _, scope, *_ = setup()
    result = resolve(scope, subject)
    answer, _ = literal_functions(f'Cuales son las funciones del {subject}', result.chunks, scope)
    assert expected in answer
    assert getattr(result, 'related', None) is None
    if subject != 'Rector':
        assert 'Supervisar actividades' not in answer


def test_related_authority_clarifies_without_transcribing_or_calling_providers():
    principal, scope, _, docs, provider, _, vectors, embeddings, auth, case = setup()
    async def resolver(*args):
        return resolve(scope, 'Rectorado')
    vectors.resolve_functions = resolver
    result = asyncio.run(case.execute(principal, scope.document_id,
                                     '¿Cuáles son las funciones del Rectorado?'))
    assert result.status == 'ACLARACION'
    assert 'artículo 28' in result.answer and 'Funciones del Rector' in result.answer
    assert 'REGLAMENTO ORGANICO MARCO' in result.answer
    assert 'páginas 12 a 14' in result.answer and '¿Querés consultar' in result.answer
    assert 'Supervisar actividades' not in result.answer and not result.citations
    assert not provider.inputs and embeddings.calls == 0
    assert docs.calls == 2 and auth.calls == 2


def test_exact_rectorado_heading_takes_priority():
    _, scope, *_ = setup()
    document = ((1, 'Articulo 1. Funciones del Rectorado.\na. Una tarea del órgano.\n'
                    'Articulo 2. Funciones del Rector.\na. Otra tarea del titular.\n'
                    'Articulo 3. Fin.'),)
    result = resolve(scope, 'Rectorado', document)
    assert getattr(result, 'related', None) is None
    answer, _ = literal_functions('Cuales son las funciones del Rectorado', result.chunks, scope)
    assert 'Una tarea del órgano' in answer and 'Otra tarea del titular' not in answer


@pytest.mark.parametrize('subject', ['Autoridad Inexistente', 'Rectorado'])
def test_no_evidence_keeps_normal_abstention(subject):
    principal, scope, _, _, provider, _, vectors, embeddings, _, case = setup()
    document = ((1, 'Articulo 1. Sin funciones.\nTexto ficticio.\nArticulo 2. Fin.'),)
    async def resolver(*args):
        return resolve(scope, subject, document)
    vectors.resolve_functions = resolver
    result = asyncio.run(case.execute(principal, scope.document_id,
                                     f'Cuales son las funciones del {subject}'))
    assert result.status == 'SIN_EVIDENCIA'
    assert not provider.inputs and embeddings.calls == 0


def test_denied_document_never_reads_or_reveals_alternatives():
    principal, scope, _, docs, provider, _, vectors, embeddings, _, case = setup()
    docs.revoked = True
    async def resolver(*args):
        pytest.fail('Unauthorized document must not be read')
    vectors.resolve_functions = resolver
    with pytest.raises(PermissionError):
        asyncio.run(case.execute(principal, scope.document_id,
                                'Cuales son las funciones del Rectorado'))
    assert not provider.inputs and embeddings.calls == 0


def test_related_metadata_is_not_returned_after_version_changes():
    principal, scope, _, docs, _, _, vectors, _, _, case = setup()
    async def resolver(*args):
        docs.scope = replace(scope, space='changed')
        return resolve(scope, 'Rectorado')
    vectors.resolve_functions = resolver
    with pytest.raises(IANoDisponible):
        asyncio.run(case.execute(principal, scope.document_id,
                                'Cuales son las funciones del Rectorado'))


def test_ambiguous_related_heading_does_not_offer_a_choice():
    _, scope, *_ = setup()
    document = ((1, 'REGLAMENTO PRIMERO\nArticulo 1. Funciones del Rector.\na. Primera tarea.\n'
                    'Articulo 2. Fin.\nREGLAMENTO SEGUNDO\n'
                    'Articulo 1. Funciones del Rector.\na. Segunda tarea.\nArticulo 2. Fin.'),)
    result = resolve(scope, 'Rectorado', document)
    assert not result.chunks and getattr(result, 'related', None) is None


def test_unproven_document_does_not_suggest_related_authority():
    _, scope, *_ = setup()
    result = resolve_functions(pages(), scope, 'Cuales son las funciones del Rectorado')
    assert not result.chunks and getattr(result, 'related', None) is None


def test_http_accepts_existing_rag_clarification_contract():
    from types import SimpleNamespace
    from fastapi.testclient import TestClient
    from tests.ia.test_http_ia import setup_app
    from app.application.agent.context import AgentResult
    principal, scope, _, _, _, _, vectors, _, _, case = setup()
    async def resolver(*args):
        return resolve(scope, 'Rectorado')
    vectors.resolve_functions = resolver
    async def execute(*args, **kwargs):
        result = await case.execute(principal, scope.document_id,
                                    'Cuales son las funciones del Rectorado')
        return AgentResult(strategy='RAG', status=result.status, answer=result.answer)
    app, _, _, _, headers, state = setup_app()
    with TestClient(app) as client:
        app.state.ia_agent = SimpleNamespace(execute=execute)
        response = client.post('/api/v1/ia/respuestas', headers=headers,
            json={'prompt': 'Cuales son las funciones del Rectorado', 'modo': 'RAG',
                  'documento_id': str(scope.document_id)})
    assert response.status_code == 200
    assert response.json()['estado'] == 'ACLARACION'
    assert response.json()['fuentes'] == []
    assert response.json()['finalizacion'] is None
    assert not state['provider'].inputs
