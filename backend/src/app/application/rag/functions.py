"""Closed, literal authority-function sections; no model or fuzzy extraction."""
import re
from dataclasses import dataclass, replace

from .articles import ArticleResolution, folded, resolve_article
from .continuity import ARTICLE
from .dto import Evidence
from .relevance import AcademicRelevance


@dataclass(frozen=True)
class RelatedFunctions:
    heading: str
    authority: str
    section: str
    number: int
    pages: tuple[int, ...]


@dataclass(frozen=True)
class FunctionsResolution(ArticleResolution):
    related: RelatedFunctions | None = None


def _digest(chunks):
    import hashlib
    link=chunks[0].article
    identity=(link.scope,link.number,link.section,link.first_page,link.closure)
    return hashlib.sha256(repr((identity,tuple((c.page,c.start,c.end,c.text) for c in chunks))).encode()).hexdigest()


def functions_target(question):
    normal = folded(question).strip(' ?¿.')
    match = re.fullmatch(r'(?:cuales son las|que|enumera las|lista las) '
                         r'(funciones|atribuciones|competencias) (?:del|de la|de los|de las) (.+)', normal)
    return (match.group(1), AcademicRelevance.role_terms(match.group(2))) if match else None


def resolve_functions(pages, scope, question, *, complete_document=False):
    target = functions_target(question)
    if not target or not complete_document:
        return ArticleResolution(reason='unproven_end')
    # Reuse the normative resolver, including its bounds, gaps and homonym policy.
    choices = []
    all_text = '\n'.join(content for _,content in pages)
    article_positions = list(ARTICLE.finditer(all_text))
    base = 0
    for page, content in pages:
        for title in re.finditer(r'(?m)^[^\n]+',content):
            raw = title.group()
            heading = ARTICLE.match(raw)
            line = (raw[heading.end():] if heading else raw).strip(' .:')
            match = re.fullmatch(r'(funciones|atribuciones|competencias)\s+(?:del|de la|de los|de las)\s+(.+)', folded(line))
            if not match or (match.group(1), AcademicRelevance.role_terms(match.group(2))) != target:
                continue
            enclosing = [h for h in article_positions if h.start()<=base+title.start()]
            if not enclosing:
                continue
            number = int(enclosing[-1].group(1))
            result = resolve_article(pages, scope, number, question, complete_document=True)
            if result.alternatives:
                options = [o for o in result.alternatives if o.page<=page]
                options = options[-1:]
                if len(options) != 1:
                    return ArticleResolution(reason='ambiguous')
                result = resolve_article(pages, scope, number, question+' '+options[0].section,
                                         complete_document=True)
            if not result.chunks:
                return ArticleResolution(reason='ambiguous')
            if heading:
                if result.chunks[0].page != page or result.chunks[0].start != title.start():
                    return ArticleResolution(reason='ambiguous')
            else:
                # A small subsection can be closed by the next explicit heading.
                slices=[];started=False;closed=False
                for c in result.chunks:
                    lo=0
                    if not started:
                        if c.page!=page or not c.start<=title.start()<c.end:
                            continue
                        lo=title.start()-c.start;started=True
                    tail=c.text[lo:]
                    skip=tail.find('\n')+1 if c.page==page else 0
                    following=re.search(
                        r'(?im)^(?:requisitos|funciones|atribuciones|competencias|designaci[oó]n|'
                        r'elecci[oó]n|duraci[oó]n|evaluaci[oó]n)\s+(?:del|de la|de los|de las)\s+[^\n:]{1,100}:\s*$',
                        tail[skip:])
                    hi=lo+skip+following.start() if following else len(c.text)
                    slices.append(replace(c,start=c.start+lo,end=c.start+hi,text=c.text[lo:hi]))
                    if following:
                        closed=True;break
                if not slices:
                    return ArticleResolution(reason='unproven_end')
                link=replace(slices[0].article,first_page=slices[0].page,
                             closure='section_change' if closed else slices[0].article.closure)
                result=replace(result,chunks=tuple(replace(c,article=link) for c in slices))
            choices.append(result)
        base += len(content)+1
    if len(choices) != 1:
        # A bounded suggestion, never a synonym or an extraction for another subject.
        # Only an absent exact heading can offer this known, distinct authority.
        if not choices and target == ('funciones', {'rectorado'}):
            other_question = 'Cuales son las funciones del Rector'
            other = bind_functions(resolve_functions(
                pages, scope, other_question, complete_document=complete_document))
            if literal_functions(other_question, other.chunks, scope) is not None:
                first = other.chunks[0]
                heading = ARTICLE.match(first.text)
                title = first.text[heading.end() if heading else 0:].split('\n', 1)[0].strip(' .:')
                authority = re.split(r'\s+del\s+', title, maxsplit=1, flags=re.I)[-1]
                return FunctionsResolution(reason='related_authority', related=RelatedFunctions(
                    heading=title, authority=authority, section=first.article.section,
                    number=first.article.number, pages=tuple(c.page for c in other.chunks)))
        return ArticleResolution(reason='ambiguous' if choices else 'not_found')
    return choices[0]


def literal_functions(question, chunks, scope):
    """All exact article slices, page-cited. Never a partial context or LLM output."""
    target = functions_target(question)
    if not target or not 1 <= len(chunks) <= 3:
        return None
    first = chunks[0]
    link = first.article
    if (not link or link.scope != scope or link.first_page != first.page
            or link.closure not in ('next_article', 'section_change', 'document_end')):
        return None
    heading = ARTICLE.match(first.text)
    if heading and int(heading.group(1)) != link.number:
        return None
    line, _, body = first.text[heading.end() if heading else 0:].partition('\n')
    match = re.fullmatch(r'(funciones|atribuciones|competencias)\s+(?:del|de la|de los|de las)\s+(.+)',
                         folded(line.strip(' .:')))
    if not match or (match.group(1), AcademicRelevance.role_terms(match.group(2))) != target:
        return None
    if not _list_start(body):
        return None
    for i, chunk in enumerate(chunks):
        if (chunk.scope != scope or chunk.article != link or chunk.end-chunk.start != len(chunk.text)
                or not chunk.text.strip() or '[F' in chunk.text or '\x00' in chunk.text
                or (i and (chunk.page != chunks[i-1].page+1 or chunk.start != 0))):
            return None
    # A repository-created link proves boundaries, not arbitrary caller text.
    # Its group commits to the full exact slices (see repository binding).
    digest = _digest(chunks)
    if link.group != 'literal:'+digest:
        return None
    evidence = tuple(Evidence(citation=f'F{i+1}', chunk=c) for i,c in enumerate(chunks))
    answer = 'Transcripción literal completa del apartado de funciones; se conserva la extracción documental:\n'
    answer += '\n'.join(c.text+f' [F{i+1}]' for i,c in enumerate(chunks))
    if len(answer)>8192 or len(answer.encode())>32768:
        return None
    return answer, evidence


def _list_start(body):
    """Recognize only a leading copy stamp; never skip unknown prose.

    Matching does not remove or rewrite the stamp in the cited source slices.
    The optional replacement glyph is the known separator artifact in the date.
    """
    marker = r'\s*(?:a[.)]|1[.)]|-)\s+'
    if re.match(marker, body):
        return True
    stamp = re.match(
        r'\s*ES COPIA[ \t]*\n[ \t]*[0-9]{1,6}[ \t]*\n'
        r'[ \t]*(?P<day>[0-3][ \t]?[0-9])[ \t]*(?:[\ufffd\u00b7][ \t]*)?'
        r'(?P<month>ENE|FEB|MAR|ABR|MAY|JUN|JUL|AGO|SEP|OCT|NOV|DIC)'
        r'[ \t]+(?P<year>20[0-9]{2})[ \t]*\n', body)
    if not stamp:
        return False
    from datetime import date
    try:
        date(int(stamp['year']),
             ('ENE','FEB','MAR','ABR','MAY','JUN','JUL','AGO','SEP','OCT','NOV','DIC').index(stamp['month'])+1,
             int(re.sub(r'\s', '', stamp['day'])))
    except ValueError:
        return False
    return bool(re.match(marker, body[stamp.end():]))


def bind_functions(result):
    """Bind all verified page slices together, detecting later omission or mutation."""
    if not result.chunks:
        return result
    chunks = result.chunks
    digest = _digest(chunks)
    link = replace(chunks[0].article, group='literal:'+digest)
    return replace(result, chunks=tuple(replace(c,article=link) for c in chunks))
