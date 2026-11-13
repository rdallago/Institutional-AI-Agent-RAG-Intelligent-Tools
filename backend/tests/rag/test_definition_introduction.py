"""Acotacion de una introduccion funcional; sin modelos ni servicios."""
import pytest

from app.application.rag.relevance import AcademicRelevance, terms
from app.application.rag.structured_output import Claim, StructuredGeneration, supported_text
from tests.rag.test_answer_diagnostics import evidence

QUESTION = '¿Cuáles son las funciones del Rectorado según el Reglamento Orgánico Marco?'
SOURCE = ('Del Rectorado: Es la unidad de conducción de la gestión académica y '
          'administrativa de la institución y ejerce su representación.')
ANSWER = ('La función del Rectorado es la unidad de conducción de la gestión académica y '
          'administrativa de la institución y ejerce su representación')


def test_verified_intro_is_normalized_explicitly_before_coverage_check():
    policy = AcademicRelevance()
    sources = evidence(SOURCE)
    assert 'funcion' in terms(ANSWER)  # No palabra ignorada globalmente.
    result = policy.explain_answer(QUESTION, ANSWER + ' [F1].', sources)
    claim = result['claims'][0]
    assert result['supported'] and policy.supports_answer(QUESTION, ANSWER + ' [F1].', sources)
    assert claim['claim'].strip() == ANSWER
    assert claim['comparison_claim'].startswith('Rectorado es la unidad')
    assert claim['comparisons'][0]['missing_terms'] == []
    assert claim['comparisons'][0]['polarity_matches']
    rendered, partial = supported_text(
        StructuredGeneration((Claim(ANSWER, ('F1',)),)), QUESTION, sources, policy)
    assert rendered.respuesta == ANSWER + ' [F1]' and not partial
    assert policy.supports_answer(QUESTION, rendered.respuesta, sources)


@pytest.mark.parametrize('answer', [
    'El Rectorado no ejerce su representación',
    'El Rectorado ejerce funciones de instrucción académica',
    'El Rectorado tiene facultades para designar al Rector',
    'El Rectorado promueve la expresión del pro-rectivo institucional',
    'La función del Rectorado es la unidad de instrucción académica',
    'La función del Rectorado es la unidad que tiene facultades para designar al Rector',
    'La función del Rectorado es la unidad que promueve la expresión del pro-rectivo institucional',
    'La función del Rectorado es la unidad que no ejerce su representación',
    ANSWER + ' y designa al Rector',
    ANSWER.replace('del Rectorado', 'del Rector'),
    ANSWER.replace('del Rectorado', 'del Rectorado académico'),
    ANSWER.replace('es la unidad', 'no es la unidad'),
])
def test_intro_never_authorizes_invented_predicates_wrong_subject_or_negation(answer):
    assert not AcademicRelevance().supports_answer(QUESTION, answer + ' [F1].', evidence(SOURCE))


@pytest.mark.parametrize('question,source', [
    (QUESTION, SOURCE.replace('Del Rectorado:', 'Del Rector:')),
    ('Funciones del Rector', SOURCE),
    (QUESTION, SOURCE.replace('Del Rectorado:', 'Funciones del Rectorado:')),
    (QUESTION, SOURCE.replace('Es la unidad', 'Es la institución')),
])
def test_normalization_requires_same_subject_and_explicit_unit_definition(question, source):
    policy = AcademicRelevance()
    assert not policy.supports_answer(question, ANSWER + ' [F1].', evidence(source))


def test_other_uses_of_funcion_are_still_checked():
    policy = AcademicRelevance()
    answer = 'El Rectorado es la unidad de función institucional'
    result = policy.explain_answer(QUESTION, answer, evidence(SOURCE))
    assert not result['supported']
    assert 'funcion' in result['claims'][0]['comparisons'][0]['missing_terms']


def test_negative_evidence_is_not_made_positive_by_intro_normalization():
    source = SOURCE.replace('ejerce su representación', 'no ejerce su representación')
    assert not AcademicRelevance().supports_answer(QUESTION, ANSWER, evidence(source))


def test_second_invented_sentence_is_not_hidden_by_valid_intro():
    answer = ANSWER + ' [F1]. El Rectorado designa al Rector [F1].'
    result = AcademicRelevance().explain_answer(QUESTION, answer, evidence(SOURCE))
    assert not result['supported']
    assert [c['supported'] for c in result['claims']] == [True, False]
