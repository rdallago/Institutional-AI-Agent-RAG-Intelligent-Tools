"""Normalización geográfica general; el candidato requiere geocoding inequívoco."""
from dataclasses import dataclass, field
import re

from .countries_data import COUNTRIES
from .router import normalize


def words(value):
    return tuple(re.findall(r'[^\W_]+',normalize(value),re.UNICODE))


ALIASES={}
for code,names in COUNTRIES.items():
    for name in names:
        ALIASES.setdefault(words(name),set()).add(code)


def country_code(value):
    candidates=ALIASES.get(words(value or ''),set())
    return next(iter(candidates)) if len(candidates)==1 else None


def explicit_countries(question):
    tokens=words(question)
    original=re.findall(r'[^\W_]+',question,re.UNICODE)
    found=[]
    for name,codes in ALIASES.items():
        n=len(name)
        for i in range(len(tokens)-n+1):
            if tokens[i:i+n]!=name:continue
            # ISO2/ISO3 deben escribirse como códigos, no palabras como «en»/«de».
            if n==1 and len(name[0])<=3 and not original[i].isupper():continue
            found.append((i,i+n,codes))
    maximal=[f for f in found if not any(g[0]<=f[0] and g[1]>=f[1] and g[:2]!=f[:2] for g in found)]
    return set().union(*(f[2] for f in maximal)) if maximal else set()


def contains_location(question,value):
    source,target=words(question),words(value or '')
    return bool(target) and any(source[i:i+len(target)]==target for i in range(len(source)-len(target)+1))


@dataclass(frozen=True)
class GeographicCandidate:
    args: object | None = field(repr=False)
    reason: str
    country_changed: bool=False


def normalize_geography(proposal,question,previous=None):
    explicit=explicit_countries(question)
    if len(explicit)>1:return GeographicCandidate(None,'ambiguous_country')
    previous=previous or {}
    if not proposal.ciudad:return GeographicCandidate(None,'missing_city')
    if not contains_location(question,proposal.ciudad) and words(proposal.ciudad)!=words(previous.get('ciudad','')):
        return GeographicCandidate(None,'ungrounded_city')
    if proposal.provincia and not contains_location(question,proposal.provincia) and words(proposal.provincia)!=words(previous.get('region','')):
        return GeographicCandidate(None,'ungrounded_region')
    stated=next(iter(explicit)) if explicit else None
    # No aceptar el país inferido por el modelo si no está en pregunta/contexto.
    resolved=stated or country_code(previous.get('pais'))
    if not resolved:return GeographicCandidate(None,'missing_country')
    candidate=proposal.model_copy(update={'pais':resolved})
    args=candidate.resolved()
    if args is None:return GeographicCandidate(None,'missing_date')
    return GeographicCandidate(args,'requires_geocoding',country_code(proposal.pais)!=resolved)
