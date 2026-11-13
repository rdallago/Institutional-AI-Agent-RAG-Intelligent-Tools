import asyncio
from dataclasses import replace

import pytest

from app.application.ia.dto import GeneracionSalida
from app.application.ia.exceptions import IARespuestaInvalida, IANoDisponible
from app.application.rag.dto import Candidate
from app.application.rag.relevance import AcademicRelevance, automatic_strategy
from tests.rag.test_core import setup


@pytest.mark.parametrize('question,expected', [
    ('\u00bfQu\u00e9 es una API REST?', 'LLM_DIRECTO'),
    ('\u00bfCu\u00e1les son los requisitos para mantener la regularidad de una unidad curricular?', 'RAG'),
    ('Inscripci\u00f3n a ex\u00e1menes', 'RAG'),
    ('Explicar una API irregular', 'LLM_DIRECTO'),
])
def test_auto(question, expected):
    assert automatic_strategy(question) == expected


def test_reproduce_false_positive_cosine_then_fix_without_generator():
    p,s,chunks,d,provider,g,v,e,a,case=setup()
    # Coseno alto no implica evidencia; reproduce exactamente el fallo de citas.
    provider.output=GeneracionSalida(respuesta='Una API es una interfaz.',finalizacion='completa')
    with pytest.raises(IARespuestaInvalida):
        asyncio.run(case.execute(p,s.document_id,'\u00bfQu\u00e9 es una API REST?'))
    assert len(provider.inputs)==1
    provider.inputs.clear()
    case.relevance=AcademicRelevance()
    result=asyncio.run(case.execute(p,s.document_id,'\u00bfQu\u00e9 es una API REST?'))
    assert result.status=='SIN_EVIDENCIA' and result.citations==() and result.finalization is None
    assert provider.inputs==[] and a.calls==3 and d.calls==3
    assert e.calls==2  # Consulta documental real; no fallback al generador general.


def academic_case():
    p,s,chunks,d,provider,g,v,e,a,case=setup()
    content='La regularidad de una unidad curricular exige asistencia.'
    chunk=replace(chunks[0],text=content,end=len(content))
    v.items=(Candidate(chunk=chunk,similarity=.95),)
    case.relevance=AcademicRelevance()
    return p,s,provider,case


def test_academic_evidence_and_real_page():
    p,s,provider,case=academic_case()
    result=asyncio.run(case.execute(p,s.document_id,
        '\u00bfCu\u00e1les son los requisitos para mantener la regularidad de una unidad curricular?'))
    assert result.status=='FUNDAMENTADA' and result.citations[0].chunk.page==7
    assert len(provider.inputs)==1


@pytest.mark.parametrize('failure',[IANoDisponible(),IARespuestaInvalida()])
def test_technical_failure_not_abstention(failure,caplog):
    p,s,provider,case=academic_case()
    provider.error=failure
    with pytest.raises(type(failure)):
        asyncio.run(case.execute(p,s.document_id,'Regularidad curricular'))
    assert 'stage=generation' in caplog.text
    assert 'Regularidad curricular' not in caplog.text


def test_invalid_citation_remains_technical(caplog):
    p,s,provider,case=academic_case()
    provider.output=GeneracionSalida(respuesta='Norma [F99]',finalizacion='completa')
    with pytest.raises(IARespuestaInvalida):
        asyncio.run(case.execute(p,s.document_id,'Regularidad curricular'))
    assert 'stage=citations kind=invalid' in caplog.text


def test_relevance_needs_specific_terms_not_only_generic_overlap():
    p,s,chunks,*_=setup()
    policy=AcademicRelevance()
    assert policy.select('\u00bfQu\u00e9 es una API REST?',chunks)==()
    assert policy.select('\u00bfQu\u00e9 dice el reglamento?',chunks)==()
    assert policy.select('Ex\u00e1menes',chunks)==chunks
