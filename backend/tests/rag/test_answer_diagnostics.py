from dataclasses import replace

from app.application.rag.dto import Evidence
from app.application.rag.relevance import AcademicRelevance, terms
from tests.rag.test_agent import fixture


def evidence(text):
    *_, case = fixture()
    chunk = replace(case.vectors.items[0].chunk, text=text, end=len(text))
    return (Evidence(citation='F1', chunk=chunk),)


QUESTION = 'Funciones del consejo'


def test_explanation_and_acceptance_share_the_same_criterion():
    policy = AcademicRelevance()
    citations = evidence('Del consejo: Es la unidad de conducci6n de la gesti6n institucional.')
    answer = 'La unidad de gestión institucional es el consejo [F1].'
    assert policy.supports_answer(QUESTION, answer, citations)
    assert policy.explain_answer(QUESTION, answer, citations)['supported']


def test_invention_reports_missing_terms_without_accepting_it():
    policy = AcademicRelevance()
    citations = evidence('Del consejo: Es la unidad de gestión institucional.')
    result = policy.explain_answer(QUESTION, 'El consejo gestiona presupuestos [F1].', citations)
    assert not result['supported']
    assert 'presupuestos' in result['claims'][0]['comparisons'][0]['missing_terms']


def test_wrong_organ_and_reversed_polarity_are_rejected():
    policy = AcademicRelevance()
    assert not policy.supports_answer(QUESTION, 'Gestiona la institución [F1].',
        evidence('Funciones del director: gestiona la institución.'))
    assert not policy.supports_answer(QUESTION, 'El consejo no gestiona la institución [F1].',
        evidence('Funciones del consejo: gestiona la institución.'))


def test_ocr_normalization_never_changes_independent_numbers_or_roles():
    assert terms('gesti6n 6 7 Rectorado') == terms('gestión 6 7 Rectorado')
    assert terms('Rectorado') != terms('Rector')
    assert terms('16') != terms('17')
