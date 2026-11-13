"""Encabezados literales: no inferencias ni lectura de evidencia privada."""
from dataclasses import replace

import pytest

from app.application.rag.relevance import AcademicRelevance, terms
from app.application.rag.structured_output import Claim, StructuredGeneration, supported_text
from tests.rag.test_answer_diagnostics import evidence

QUESTION = '¿Cuáles son las funciones del Rectorado según el Reglamento Orgánico Marco?'
# Texto exacto de F1 de la aceptacion, revision rom-art24-visual-20261106-r1.
F1 = ('Artículo 24. Del Rectorado: Es la unidad de conducción de la gestión académica y '
      'administrativa de la institución y ejerce su representación, promoviendo la construcción '
      'colaborativa del proyecto institucional, la participación de los diferentes estamentos\n'
      'Sigue Hoja N° 121// ... ')
ANSWER = F1.split('\n')[0]


def test_literal_heading_is_metadata_only_when_verified_in_cited_source():
    policy = AcademicRelevance()
    sources = evidence(F1)
    result = policy.explain_answer(QUESTION, ANSWER, sources)
    assert result['supported'] and result['headers_valid']
    assert result['verified_header'] == 'Artículo 24. Del Rectorado:'
    assert len(result['claims']) == 1
    assert result['claims'][0]['claim'].strip().startswith('Del Rectorado:')
    assert {'articulo','24'} <= terms('Artículo 24')
    rendered, partial = supported_text(
        StructuredGeneration((Claim(ANSWER, ('F1',)),)), QUESTION, sources, policy)
    assert rendered.respuesta == ANSWER + ' [F1]' and not partial
    assert policy.supports_answer(QUESTION, rendered.respuesta, sources)


@pytest.mark.parametrize('answer', [
    ANSWER.replace('Artículo 24.', 'Artículo 25.'),
    ANSWER.replace('Artículo 24.', 'Artículo 28.'),
    ANSWER.replace('Del Rectorado:', 'Del Rector:'),
    ANSWER.replace('Del Rectorado:', 'Del Consejo:'),
    ANSWER.replace('ejerce su representación', 'no ejerce su representación'),
    ANSWER + ' y designa al Rector',
    ANSWER.replace('gestión académica', 'instrucción académica'),
    ANSWER.replace('proyecto institucional', 'pro-rectivo institucional'),
    ANSWER + '. El Rectorado concede becas',
])
def test_invented_headers_or_predicates_are_rejected(answer):
    assert not AcademicRelevance().supports_answer(QUESTION, answer, evidence(F1))


@pytest.mark.parametrize('source', [
    F1.replace('Artículo 24. ', ''),
    F1.replace('Artículo 24.', 'Artículo 25.'),
    F1.replace('Del Rectorado:', 'Del Rector:'),
    F1.replace('ejerce su representación', 'no ejerce su representación'),
])
def test_heading_requires_literal_cited_relevant_evidence(source):
    assert not AcademicRelevance().supports_answer(QUESTION, ANSWER, evidence(source))


def test_heading_from_uncited_source_does_not_authorize_it():
    sources = evidence(F1)
    other = replace(sources[0], citation='F2', chunk=replace(sources[0].chunk,
        text=F1.replace('Artículo 24.', 'Artículo 25.')))
    policy = AcademicRelevance()
    assert not policy.supports_answer(QUESTION, ANSWER, (other,))


def test_header_only_is_not_a_supported_answer():
    assert not AcademicRelevance().supports_answer(QUESTION, 'Artículo 24.', evidence(F1))
