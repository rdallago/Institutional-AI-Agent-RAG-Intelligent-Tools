"""Literal enumeration from a repository-verified, closed requirements section."""
import hashlib
import re
from .relevance import AcademicRelevance
from .articles import folded


def enumeration_target(question):
    normal=folded(question)
    if re.search(r'\barticulo\b|\b(?:explic\w*|interpret\w*|compar\w*|ejempl\w*|fundament\w*)\b'
                 r'|\bpor que\b|\bque (?:es|son|significa|significan)\b',normal):
        return None
    if not re.search(r'\bcuales\s+(?:son\s+)?(?:los\s+)?requisitos\b|\bque\s+requisitos\b'
                     r'|^\W*requisitos\b|\b(?:enumera\w*|lista\w*|indica\w*|menciona\w*)\b.*\brequisitos\b',normal):
        return None
    match=re.search(r'\brequisitos\b.*?\b(?:concursos?|cargos?)\s+de\s+(.+?)[?¿.]*$',question,re.I)
    return AcademicRelevance.role_terms(match.group(1)) if match else None


def literal_requirements(question, evidence, scope):
    """Returns only original spans plus citation, or None. No fuzzy reconstruction."""
    target=enumeration_target(question)
    if not target or len(evidence)!=1:return None
    source=evidence[0];chunk=source.chunk;proof=chunk.requirements
    if (proof is None or chunk.scope!=scope or proof.scope!=scope
            or (chunk.page,chunk.start,chunk.end)!=(proof.page,proof.start,proof.end)
            or chunk.end-chunk.start!=len(chunk.text)
            or hashlib.sha256(chunk.text.encode()).hexdigest()!=proof.sha256
            or source.citation!='F1' or '[F' in chunk.text):
        return None
    header=re.match(r'^Requisitos\s+(?:del|de la|de los|de las)\s+([^\n]+)\n',chunk.text,re.I)
    if not header or AcademicRelevance.role_terms(header.group(1))!=target:return None
    markers=list(re.finditer(r'(?m)^[ \t]*-[ \t]*',chunk.text))
    if not 1<=len(markers)<=10:return None
    spans=tuple((chunk.start+m.start(),chunk.start+(markers[i+1].start() if i+1<len(markers) else len(chunk.text)))
                for i,m in enumerate(markers))
    if spans!=proof.item_spans or chunk.text[header.end():markers[0].start()].strip():return None
    items=[]
    for i,(m,(start,end)) in enumerate(zip(markers,spans)):
        value=chunk.text[start-chunk.start:end-chunk.start].rstrip()
        # Intermediate items end at the next verified bullet, not necessarily '.'.
        # The final stop plus the repository's closing heading prove list closure.
        if (i==len(spans)-1 and not value.endswith('.')) or not chunk.text[m.end():end-chunk.start].strip():return None
        items.append(value+' [F1]')
    answer='Transcripción literal del apartado de requisitos; cobertura limitada a este apartado:\n'+'\n'.join(items)
    return answer if len(answer)<=1000 and len(answer.encode())<=3000 else None
