from pathlib import Path

from app.application.ia.exceptions import IARespuestaInvalida
from app.application.rag.dto import Page


class ConservativeCounter:
    # Cota por byte UTF-8 + reserva de plantilla en core. Se contrasta con
    # prompt_eval_count real; no se declara equivalencia entre bytes y tokens.
    identity = 'utf8-upper-bound-v1'

    def count(self, text):
        return len(text.encode('utf-8',errors='strict'))


def extract_reference_pdf():
    import hashlib
    from .article24_revision import correct_pages
    path = Path(__file__).resolve().parents[4] / 'data/documents/reglamento_academico.pdf'
    return path,correct_pages(_extract_pages(path),hashlib.sha256(path.read_bytes()).hexdigest())


def _extract_pages(path):
    from pypdf import PdfReader
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 10*1024*1024:
        raise IARespuestaInvalida()
    reader = PdfReader(path, strict=True)
    if reader.is_encrypted or not 1 <= len(reader.pages) <= 1000:
        raise IARespuestaInvalida()
    pages=[]
    for number,page in enumerate(reader.pages,1):
        content=page.get_contents()
        if content is not None and len(content.get_data())>2*1024*1024:
            raise IARespuestaInvalida()
        text=page.extract_text() or ''
        if not text.strip() or '\x00' in text or len(text)>100000:
            raise IARespuestaInvalida()
        pages.append(Page(number=number,text=text))
    return tuple(pages)
