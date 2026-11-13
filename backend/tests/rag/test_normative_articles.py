import asyncio
from dataclasses import replace
from uuid import uuid4
import pytest

from app.application.rag.articles import resolve_article
from app.application.rag.dto import Scope, Evidence
from app.application.rag.relevance import AcademicRelevance
from app.application.ia.dto import GeneracionSalida
from app.presentation.http.ia.respuestas import Respuesta


def scope():
    return Scope(document_id=uuid4(),version_id=uuid4(),space='synthetic')


PAGES=((1,'REGLAMENTO ORGANICO MARCO\nTITULO III. GOBIERNO\nArticulo 24. La asistencia es obligatoria.\nArticulo 25. Otra regla.'),
       (2,'ANEXO I REGIMEN ACADEMICO MARCO\nCapitulo 3 TRAYECTORIA\nArticulo 24. La inscripcion es anual.\nArticulo 25. Otra regla.'))


def test_ambiguity_and_explicit_section():
    s=scope()
    r=resolve_article(PAGES,s,24)
    assert r.reason=='ambiguous' and not r.chunks
    assert [a.page for a in r.alternatives]==[1,2]
    for name,page in [('Reglamento Organico Marco',1),('Regimen Academico Marco',2)]:
        selected=resolve_article(PAGES,s,24,'Articulo 24 del '+name)
        assert len(selected.chunks)==1 and selected.chunks[0].page==page
        assert 'Otra regla' not in selected.chunks[0].text


def test_identical_extraction_does_not_silently_select_first():
    pages=((1,'Articulo 24. Texto.\nArticulo 25. Fin.'),(2,'Articulo 24. Texto.\nArticulo 25. Fin.'))
    assert resolve_article(pages,scope(),24).reason=='ambiguous'


@pytest.mark.parametrize('ending,closure',[
    ('Articulo 53. Otra norma.','next_article'),
    ('CAPITULO II. OTRA SECCION','section_change'),
    ('','document_end')])
def test_multipage_boundaries_and_linked_citations(ending,closure):
    s=scope()
    pages=((1,'Articulo 52. Inicio.'),(2,'La asistencia es obligatoria.'),(3,ending))
    r=resolve_article(pages,s,52,complete_document=True)
    assert r.reason==closure and [c.page for c in r.chunks][:2]==[1,2]
    assert all(c.article==r.chunks[0].article for c in r.chunks)
    e=Evidence(citation='F2',chunk=r.chunks[1])
    assert AcademicRelevance().supports_answer('Articulo 52','La asistencia es obligatoria [F2].',(e,))
    foreign=replace(e,chunk=replace(e.chunk,scope=scope()))
    assert not AcademicRelevance().supports_answer('Articulo 52','La asistencia es obligatoria [F2].',(foreign,))
    assert 'Otra norma' not in ''.join(c.text for c in r.chunks)


def test_unproven_end_gap_and_scope():
    s=scope()
    assert resolve_article(((1,'Articulo 52. Inicio.'),),s,52).reason=='unproven_end'
    assert resolve_article(((1,'Articulo 52. Inicio.'),(3,'Articulo 53. Fin.')),s,52).reason=='page_gap'


def test_ambiguity_contract_and_no_generation():
    from tests.rag.test_core import setup
    p,s,_,d,provider,gate,vectors,embedding,auth,case=setup()
    async def exact(*args):return resolve_article(PAGES,s,24)
    vectors.resolve_article=exact
    vectors.explicit_article=lambda *a:None
    result=asyncio.run(case.execute(p,s.document_id,'Articulo 24'))
    assert result.status=='ACLARACION' and 'página 1' in result.answer and 'página 2' in result.answer
    assert not provider.inputs and embedding.calls==0
    Respuesta(respuesta=result.answer,finalizacion=result.finalization,estado=result.status,estrategia='RAG',fuentes=[])


def test_full_context_or_abstain_no_truncation():
    from tests.rag.test_core import setup
    p,s,_,d,provider,gate,vectors,embedding,auth,case=setup()
    pages=tuple((i,('Articulo 52. ' if i==1 else '')+'Contenido. '*100) for i in range(1,5))+((5,'Articulo 53. Fin.'),)
    r=resolve_article(pages,s,52)
    async def exact(*args):return r
    vectors.resolve_article=exact;vectors.explicit_article=lambda *a:None
    result=asyncio.run(case.execute(p,s.document_id,'Articulo 52'))
    assert result.status=='SIN_EVIDENCIA' and not provider.inputs and not result.citations


def test_grounded_continuation_through_use_case():
    from tests.rag.test_core import setup
    p,s,_,d,provider,gate,vectors,embedding,auth,case=setup()
    case.relevance=AcademicRelevance()
    r=resolve_article(((1,'Articulo 52. Inicio.'),(2,'La asistencia es obligatoria.\nArticulo 53. Fin.')),s,52)
    async def exact(*args):return r
    vectors.resolve_article=exact;vectors.explicit_article=lambda *a:None
    provider.output=GeneracionSalida(respuesta='La asistencia es obligatoria [F2].',finalizacion='completa')
    result=asyncio.run(case.execute(p,s.document_id,'Articulo 52'))
    assert result.status=='FUNDAMENTADA' and result.citations[0].chunk.page==2
    assert embedding.calls==0
