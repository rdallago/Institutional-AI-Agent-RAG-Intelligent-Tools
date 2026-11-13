"""Recuperacion documental acotada y soporte; sin modelos ni base externa."""
import asyncio
from dataclasses import replace
import pytest
from app.application.rag.dto import Candidate, Evidence
from app.application.rag.relevance import AcademicRelevance
from app.application.ia.dto import GeneracionSalida
from app.application.ia.exceptions import IARespuestaInvalida
from tests.rag.test_agent import fixture

QUESTION='¿En el reglamento académico de Institutos Superiores, cuáles son las funciones del Rectorado?'
SOURCE='Del Rectorado: Es la unidad de conducción de la gestión académica y\nadministrativa de la institución y ejerce su representación.'

def test_documentary_frame_and_layout_are_not_false_content_requirements():
    p,s,a,c,d,k,provider,e,case=fixture()
    chunk=replace(case.vectors.items[0].chunk,text=SOURCE,end=len(SOURCE))
    policy=AcademicRelevance()
    assert policy.select(QUESTION,(chunk,))==(chunk,)
    assert policy.supports_answer(QUESTION,SOURCE+' [F1]',(Evidence(citation='F1',chunk=chunk),))
    assert not policy.select(QUESTION,(replace(chunk,text='Funciones del Rector: dirige la gestión institucional.'),))
    assert not policy.supports_answer(QUESTION,'La Secretaría Administrativa dirige el instituto [F1].',(Evidence(citation='F1',chunk=chunk),))

def test_incidental_mentions_do_not_prevent_recovery_of_actual_subject():
    policy=AcademicRelevance()
    text='Integra el Rectorado y asiste al Rector en el ejercicio de sus funciones especificas.'
    assert not tuple(policy.pertinent_units(QUESTION,text))
    # JSON/schema y cita valida no vuelven verdadero un concepto inventado.
    p,s,a,c,d,k,provider,e,case=fixture()
    chunk=replace(case.vectors.items[0].chunk,text=SOURCE,end=len(SOURCE))
    assert not policy.supports_answer(QUESTION,'El Rectorado construye la órbita institucional [F1].',
        (Evidence(citation='F1',chunk=chunk),))

@pytest.mark.parametrize('initial',[True,False])
def test_relevant_evidence_inside_or_outside_initial_top_k(initial):
    async def run():
        p,s,a,c,d,k,provider,e,case=fixture()
        case.threshold=.60  # Configuracion operativa, distinta del fixture generico .70.
        chunk=replace(case.vectors.items[0].chunk,text=SOURCE,end=len(SOURCE))
        good=Candidate(chunk=chunk,similarity=.688318)
        case.vectors.items=(good,) if initial else ()
        calls=[]
        async def recover(principal,scope,vector):
            assert principal==p and scope==s
            calls.append(1);return (good,)
        case.recovery=recover
        provider.output=GeneracionSalida(respuesta=SOURCE+' [F1]',finalizacion='completa')
        result=await case.execute(p,s.document_id,QUESTION)
        assert result.status=='FUNDAMENTADA' and result.citations[0].chunk==chunk
        assert len(calls)==(0 if initial else 1) and e.calls==1
    asyncio.run(run())

def test_recovery_keeps_threshold_and_abstention_without_generator():
    async def run():
        p,s,a,c,d,k,provider,e,case=fixture()
        case.threshold=.60
        chunk=replace(case.vectors.items[0].chunk,text=SOURCE,end=len(SOURCE))
        case.vectors.items=()
        async def recover(*args):return (Candidate(chunk=chunk,similarity=.59),)
        case.recovery=recover
        result=await case.execute(p,s.document_id,QUESTION)
        assert result.status=='SIN_EVIDENCIA' and not result.citations and not provider.inputs
    asyncio.run(run())

def test_recovery_rejects_foreign_scope():
    async def run():
        p,s,a,c,d,k,provider,e,case=fixture()
        case.vectors.items=()
        from tests.rag.test_core import setup
        foreign=setup()[2][0]
        async def recover(*args):return (Candidate(chunk=foreign,similarity=.99),)
        case.recovery=recover
        with pytest.raises(IARespuestaInvalida):await case.execute(p,s.document_id,QUESTION)
    asyncio.run(run())
