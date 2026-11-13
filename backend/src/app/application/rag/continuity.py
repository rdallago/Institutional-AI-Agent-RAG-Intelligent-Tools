"""Completar articulos con slices exactos, sin reparar texto ni inferir contenido."""
import hashlib
import re
from dataclasses import replace

from app.application.ia.exceptions import IARespuestaInvalida

# Incluye la perdida del primer caracter observada en la extraccion de encabezados.
ARTICLE = re.compile(r'(?im)^[ \t]*(?:art[ií]culo|rt[ií]culo|art\.)\s*(\d+)\s*[.:]')


def requested_article(question):
    numbers = {int(m) for m in re.findall(r'\b(?:art[ií]culo|art\.)\s*(\d+)\b', question, re.I)}
    return next(iter(numbers)) if len(numbers) == 1 else None


def complete_article(seed, rows):
    """rows: (Chunk, longitud de pagina), ordenados; ventana autorizada acotada.

    Una laguna o ausencia del siguiente encabezado no demuestra fin del articulo.
    Se devuelve vacio en ese caso; nunca una expansion parcial como completa.
    """
    pages = {}
    for chunk, length in rows:
        if (chunk.scope != seed.scope or chunk.start < 0 or chunk.end > length
                or chunk.end - chunk.start != len(chunk.text)):
            raise IARespuestaInvalida()
        pages.setdefault(chunk.page, []).append((chunk, length))
    texts = []
    for page, items in sorted(pages.items()):
        items.sort(key=lambda item: (item[0].start, item[0].id))
        length = items[0][1]
        content = ''
        for chunk, expected in items:
            if expected != length or chunk.start > len(content):
                return ()
            overlap = min(len(content) - chunk.start, len(chunk.text))
            if content[chunk.start:chunk.start + overlap] != chunk.text[:overlap]:
                raise IARespuestaInvalida()
            content += chunk.text[overlap:]
        if len(content) != length:
            return ()
        texts.append((page, content))
    if not texts or any(b[0] != a[0] + 1 for a, b in zip(texts, texts[1:])):
        return ()
    locations = []
    joined = ''
    seed_position = None
    for page, content in texts:
        locations.append((page, len(joined), len(content)))
        if page == seed.page:
            if content[seed.start:seed.end] != seed.text:
                raise IARespuestaInvalida()
            # El encabezado pertinente debe estar dentro del seed, no en otro apartado.
            heading = ARTICLE.search(seed.text)
            if heading:
                seed_position = len(joined) + seed.start + heading.start()
            else:
                # Algunos chunks comienzan directamente con el titulo del articulo.
                seed_position = len(joined) + seed.start
        joined += content + '\n'
    if seed_position is None:
        return ()
    boundaries = list(ARTICLE.finditer(joined))
    before = [m for m in boundaries if m.start() <= seed_position]
    after = [m for m in boundaries if m.start() > seed_position]
    if not before or not after:
        return ()
    start, end = before[-1].start(), after[0].start()
    result = []
    for page, base, length in locations:
        lo, hi = max(start, base), min(end, base + length)
        if lo < hi:
            value = joined[lo:hi]
            result.append(replace(seed, page=page, start=lo-base, end=hi-base, text=value,
                id=hashlib.sha256(f'{seed.scope.version_id}:{page}:{lo-base}:{hi-base}'.encode()).hexdigest()))
    return tuple(result)


def requirement_section(seed, article):
    """Seccion de lista delimitada por encabezados dentro de un articulo probado.

    Solo selecciona una lista completa en una pagina; si no se demuestra su fin,
    conserva la abstencion/expansion original. Nunca recompone texto u offsets.
    """
    heading = re.search(r'(?im)^\s*(Requisitos\s+(?:del|de la)\s+[^\n]+)\n', seed.text)
    if not heading:
        return ()
    title = heading.group(1).strip()
    for chunk in article:
        if chunk.page != seed.page:
            continue
        match = re.search(r'(?m)^' + re.escape(title) + r'\s*\n', chunk.text)
        if not match:
            continue
        following = re.search(r'(?m)^[^\n\-][^\n]{1,140}:\s*$', chunk.text[match.end():])
        if following is None:
            return ()
        end = match.end() + following.start()
        body = chunk.text[match.end():end].strip()
        if not body.startswith('-') or not body.endswith('.'):
            return ()
        start = chunk.start + match.start()
        end = chunk.start + end
        value = chunk.text[match.start():end-chunk.start]
        from .dto import RequirementList
        markers=list(re.finditer(r'(?m)^[ \t]*-[ \t]*',value))
        if not markers:
            return ()
        spans=tuple((start+m.start(),start+(markers[i+1].start() if i+1<len(markers) else len(value)))
                    for i,m in enumerate(markers))
        proof=RequirementList(scope=chunk.scope,page=chunk.page,start=start,end=end,
                              sha256=hashlib.sha256(value.encode()).hexdigest(),item_spans=spans)
        return (replace(chunk, start=start, end=end, text=value,
            section='Sección normativa parcial: '+title,
            requirements=proof,
            id=hashlib.sha256(f'{chunk.scope.version_id}:{chunk.page}:{start}:{end}'.encode()).hexdigest()),)
    return ()
