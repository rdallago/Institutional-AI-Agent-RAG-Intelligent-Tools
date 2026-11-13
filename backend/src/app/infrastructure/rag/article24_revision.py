"""Revision puntual de extraccion; PDF original inmutable, sin OCR generico.

Procedencia: cotejo visual de paginas fisicas 11 y 12 del PDF identificado abajo,
realizado el 2026-11-06 y transcripcion aprobada por el responsable en esta sesion.
Detalle de procedencia y procedimiento: docs/article24-extraction-revision.md.
"""
from dataclasses import replace
import hashlib

from app.application.ia.exceptions import IARespuestaInvalida

PDF_SHA256 = '1decdfbfd41cc8eea5a9bb097949d0c8ade3aa3e504be23950b4b842875a2c71'
REVISION = 'rom-art24-visual-20261106-r1'
ORIGINAL_PAGE_HASHES = {
    11: '1f4118282d65f34fde80c8bd0cb2ba296c5f4f5acd3acd2e97433982c181b108',
    12: 'ed78950e931d88d913cf7a06a9dee831fa803e4b654f428de41a1a30561137a1',
}
# Slices verificados de la extraccion original: no tocar encabezados, pies u otros articulos.
BOUNDS = {11: (2062, 2315), 12: (124, 351)}
PARTS = {
    11: ('Artículo 24. Del Rectorado: Es la unidad de conducción de la gestión académica y '
         'administrativa de la institución y ejerce su representación, promoviendo la construcción '
         'colaborativa del proyecto institucional, la participación de los diferentes estamentos\n'),
    12: ('institucionales, el funcionamiento de los órganos colegiados, la articulación interna y '
         'externa; y el cumplimiento de las políticas definidas para el sistema formador a '
         'través del área específica de conducción jurisdiccional.\n'),
}
TRANSCRIPTION = ' '.join((PARTS[11] + PARTS[12]).split())
LEGACY_PIPELINE = 'pypdf-6.21.4:exact-pages:400-50:utf8-upper-bound-v1'


def pipeline_identity(revision=None):
    if revision is None:
        return hashlib.sha256(LEGACY_PIPELINE.encode()).hexdigest(), 'pypdf-6.21.4'
    if revision != REVISION:
        raise IARespuestaInvalida()
    manifest = repr((REVISION, PDF_SHA256, ORIGINAL_PAGE_HASHES, BOUNDS, PARTS))
    fingerprint = hashlib.sha256((LEGACY_PIPELINE + ':' + manifest).encode()).hexdigest()
    return fingerprint, 'pypdf-6.21.4+' + REVISION


def correct_pages(pages, pdf_hash):
    if pdf_hash != PDF_SHA256 or len({p.number for p in pages}) != len(pages):
        raise IARespuestaInvalida()
    indexed = {p.number: p for p in pages}
    for number, expected in ORIGINAL_PAGE_HASHES.items():
        page = indexed.get(number)
        if page is None or page.sections or hashlib.sha256(page.text.encode()).hexdigest() != expected:
            raise IARespuestaInvalida()
    corrected = []
    for page in pages:
        if page.number in BOUNDS:
            start, end = BOUNDS[page.number]
            page = replace(page, text=page.text[:start] + PARTS[page.number] + page.text[end:])
        corrected.append(page)
    return tuple(corrected)


def verify_corrected_pages(pages, pdf_hash):
    """Antes de staging, contrastar todas las paginas con la revision reproducida."""
    if pdf_hash != PDF_SHA256:
        raise IARespuestaInvalida()
    from .text import _extract_pages
    from pathlib import Path
    path = Path(__file__).resolve().parents[4] / 'data/documents/reglamento_academico.pdf'
    if hashlib.sha256(path.read_bytes()).hexdigest() != pdf_hash:
        raise IARespuestaInvalida()
    if tuple(pages) != correct_pages(_extract_pages(path), pdf_hash):
        raise IARespuestaInvalida()
