from dataclasses import replace
import hashlib
from pathlib import Path
from uuid import UUID, uuid5

import pytest

from app.application.ia.exceptions import IARespuestaInvalida
from app.application.rag.core import prepare_pages
from app.application.rag.continuity import complete_article
from app.application.rag.dto import Scope
from app.infrastructure.rag.article24_revision import (
    BOUNDS, PARTS, PDF_SHA256, REVISION, correct_pages, pipeline_identity, verify_corrected_pages,
)
from app.infrastructure.rag.text import _extract_pages, ConservativeCounter


@pytest.fixture(scope='module')
def source():
    path=Path(__file__).resolve().parents[2]/'data/documents/reglamento_academico.pdf'
    return path, _extract_pages(path)


def test_verified_transcription_and_only_article24_changes(source):
    path,pages=source
    assert hashlib.sha256(path.read_bytes()).hexdigest()==PDF_SHA256
    corrected=correct_pages(pages,PDF_SHA256)
    for before,after in zip(pages,corrected):
        if before.number not in BOUNDS:
            assert after==before
        else:
            start,end=BOUNDS[before.number]
            assert after.text==before.text[:start]+PARTS[before.number]+before.text[end:]
    assert ' '.join((PARTS[11]+PARTS[12]).split())==(
        'Artículo 24. Del Rectorado: Es la unidad de conducción de la gestión académica y '
        'administrativa de la institución y ejerce su representación, promoviendo la construcción '
        'colaborativa del proyecto institucional, la participación de los diferentes estamentos '
        'institucionales, el funcionamiento de los órganos colegiados, la articulación interna y '
        'externa; y el cumplimiento de las políticas definidas para el sistema formador a '
        'través del área específica de conducción jurisdiccional.')
    assert corrected[11].text[corrected[11].text.index('Articulo 25.'):]==pages[11].text[351:]
    assert correct_pages(pages,PDF_SHA256)==corrected
    assert hashlib.sha256(path.read_bytes()).hexdigest()==PDF_SHA256


def test_unknown_pdf_extraction_mismatch_and_double_application_fail(source):
    _,pages=source
    with pytest.raises(IARespuestaInvalida):correct_pages(pages,'0'*64)
    broken=list(pages);broken[10]=replace(broken[10],text=broken[10].text+'x')
    with pytest.raises(IARespuestaInvalida):correct_pages(broken,PDF_SHA256)
    with pytest.raises(IARespuestaInvalida):correct_pages(correct_pages(pages,PDF_SHA256),PDF_SHA256)


def test_version_identity_distinct_reproducible_and_staging_input_verified(source):
    _,pages=source
    legacy,_=pipeline_identity();revised,extractor=pipeline_identity(REVISION)
    assert legacy==hashlib.sha256(b'pypdf-6.21.4:exact-pages:400-50:utf8-upper-bound-v1').hexdigest()
    assert legacy!=revised and REVISION in extractor
    document=UUID(int=1)
    assert uuid5(document,PDF_SHA256+legacy)!=uuid5(document,PDF_SHA256+revised)
    with pytest.raises(IARespuestaInvalida):pipeline_identity('unknown')
    corrected=correct_pages(pages,PDF_SHA256)
    verify_corrected_pages(corrected,PDF_SHA256)
    broken=list(corrected);broken[0]=replace(broken[0],text=broken[0].text+'x')
    with pytest.raises(IARespuestaInvalida):verify_corrected_pages(broken,PDF_SHA256)


def test_existing_fragmentation_keeps_exact_slices_and_page25_separation(source):
    _,pages=source
    corrected=correct_pages(pages,PDF_SHA256)
    scope=Scope(document_id=UUID(int=1),version_id=UUID(int=2),space='offline')
    _,chunks=prepare_pages(corrected,scope,ConservativeCounter())
    indexed={p.number:p for p in corrected}
    assert chunks
    for chunk in chunks:
        assert chunk.text==indexed[chunk.page].text[chunk.start:chunk.end]
        assert chunk.end-chunk.start==len(chunk.text)
    assert 'Articulo 25.' in corrected[11].text
    seed=next(c for c in chunks if c.page==11 and 'Artículo 24.' in c.text)
    article=complete_article(seed,tuple((c,len(indexed[c.page].text)) for c in chunks if 10<=c.page<=12))
    assert [c.page for c in article]==[11,12]
    assert all('Articulo 25.' not in c.text and 'Funciones del Rector.' not in c.text for c in article)
