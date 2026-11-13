"""Bounded structural resolution over verified pages, without model inference."""
from dataclasses import dataclass
import hashlib
import re
import unicodedata

from .continuity import ARTICLE
from .dto import Chunk, ArticleLink


def folded(value):
    value = ''.join(c for c in unicodedata.normalize('NFD', value.casefold())
                    if not unicodedata.combining(c))
    return ' '.join(re.sub(r'(?<=\w)\.(?=\w)', '', value).split())


def section_heading(line):
    """Only explicit normative headings, not mentions in prose."""
    value = line.strip()
    normal = folded(value)
    match = re.match(r'^(anexo|titulo|capitulo|seccion)\s+([ivxlcdm]+|\d+)\b', normal)
    if match:
        return match.group(1), value
    if (value.isupper() and len(value) <= 180
            and re.match(r'^(reglamento|regimen)\b', normal)):
        return 'norma', value
    return None


@dataclass(frozen=True)
class ArticleOption:
    section: str
    page: int
    offset: int


@dataclass(frozen=True)
class ArticleResolution:
    chunks: tuple = ()
    alternatives: tuple[ArticleOption, ...] = ()
    reason: str = 'not_found'


def resolve_article(pages, scope, number, question='', *, complete_document=False):
    """pages are (number, exact text); closure and section labels come from text.

    Caller verifies hashes/ACL. At most 100 pages / 1M characters are accepted.
    Multiple occurrences are never collapsed merely because their bodies match.
    """
    if not pages or len(pages)>100 or sum(len(t) for _,t in pages)>1_000_000:
        return ArticleResolution(reason='document_bound')
    if any(b[0]!=a[0]+1 for a,b in zip(pages,pages[1:])):
        return ArticleResolution(reason='page_gap')
    text='';locations=[]
    for page,content in pages:
        locations.append((page,len(text),len(content)))
        text+=content+'\n'
    sections=[]
    for m in re.finditer(r'(?m)^[^\n]+',text):
        parsed=section_heading(m.group())
        if parsed:sections.append((m.start(),*parsed))
    headings=list(ARTICLE.finditer(text))
    matches=[m for m in headings if int(m.group(1))==number]
    def hierarchy(position):
        levels={};order=('anexo','norma','titulo','capitulo','seccion')
        for at,kind,label in sections:
            if at>=position:break
            level=order.index(kind)
            if kind=='norma':
                levels={}  # A new normative title supersedes earlier index headings.
            levels={k:v for k,v in levels.items() if order.index(k)<=level}
            levels[kind]=label
        return tuple(levels[k] for k in order if k in levels)
    def option(m):
        page,base,_=next(loc for loc in reversed(locations) if loc[1]<=m.start())
        labels=hierarchy(m.start())
        return ArticleOption(' / '.join(labels) or 'Sección sin encabezado identificado',page,m.start()-base)
    if not matches:return ArticleResolution()
    if len(matches)>1:
        q=folded(question)
        # Require a literal section name, not overlap of topic words or numbers.
        def phrases(label):
            normal=folded(label)
            return (normal,re.sub(r'^(?:anexo|titulo|capitulo|seccion)\s+(?:[ivxlcdm]+|\d+)\s*[.:]?\s*','',normal))
        selected=[m for m in matches if any(len(phrase)>=8 and phrase in q
                    for label in hierarchy(m.start()) for phrase in phrases(label))]
        if len(selected)!=1:
            return ArticleResolution(alternatives=tuple(option(m) for m in matches),reason='ambiguous')
        match=selected[0]
    else:match=matches[0]
    start=match.start()
    boundaries=[(m.start(),'next_article') for m in headings if m.start()>start]
    boundaries += [(at,'section_change') for at,_,_ in sections if at>start]
    if boundaries:end,closure=min(boundaries)
    elif complete_document:end,closure=len(text)-1,'document_end'
    else:return ArticleResolution(reason='unproven_end')
    if end<=match.end():return ArticleResolution(reason='empty_article')
    chosen=option(match)
    group=hashlib.sha256(f'{scope}:{start}:{end}'.encode()).hexdigest()
    link=ArticleLink(number=number,group=group,section=chosen.section,
                     first_page=chosen.page,closure=closure,scope=scope)
    chunks=[]
    for page,base,length in locations:
        lo,hi=max(start,base),min(end,base+length)
        if lo<hi:
            value=text[lo:hi]
            chunks.append(Chunk(id=hashlib.sha256(f'{scope.version_id}:{page}:{lo-base}:{hi-base}'.encode()).hexdigest(),
                scope=scope,page=page,start=lo-base,end=hi-base,text=value,
                section=chosen.section,article=link))
    return ArticleResolution(chunks=tuple(chunks),reason=closure)
