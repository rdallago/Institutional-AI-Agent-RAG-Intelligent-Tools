"""Contrato interno cerrado; las referencias nunca se completan por conjetura."""
from dataclasses import dataclass, field
import json
import re

from app.application.ia.dto import GeneracionSalida
from app.application.ia.exceptions import IARespuestaInvalida


@dataclass(frozen=True, slots=True)
class Claim:
    text: str = field(repr=False)
    source_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class StructuredGeneration:
    claims: tuple[Claim, ...] = field(repr=False)
    finalizacion: str = 'completa'


def schema(evidence):
    return {'type':'object','additionalProperties':False,'required':['claims'],
        'properties':{'claims':{'type':'array','maxItems':3,'items':{
            'type':'object','additionalProperties':False,'required':['text','source_ids'],
            'properties':{'text':{'type':'string','minLength':1,'maxLength':600},
                'source_ids':{'type':'array','minItems':1,'maxItems':len(evidence),
                    'uniqueItems':True,'items':{'type':'string','enum':[e.citation for e in evidence]}}}}}}}


def parse(output, evidence):
    def invalid():raise IARespuestaInvalida()
    def pairs(items):
        result={}
        for key,value in items:
            if key in result:invalid()
            result[key]=value
        return result
    if output.finalizacion!='completa':invalid()
    try:
        data=json.loads(output.respuesta,object_pairs_hook=pairs,parse_constant=lambda _:invalid())
    except (ValueError,TypeError,RecursionError):invalid()
    if type(data) is not dict or set(data)!={'claims'} or type(data['claims']) is not list or len(data['claims'])>3:invalid()
    allowed={e.citation for e in evidence}
    claims=[]
    seen=set()
    for item in data['claims']:
        if type(item) is not dict or set(item)!={'text','source_ids'}:invalid()
        text,ids=item['text'],item['source_ids']
        if (type(text) is not str or not text.strip() or len(text)>600 or '\x00' in text
                or re.search(r'\[F|\\u',text) or text.strip()=='SIN_EVIDENCIA'
                or type(ids) is not list or not 1<=len(ids)<=len(allowed)
                or any(type(i) is not str or i not in allowed for i in ids)):invalid()
        if len(set(ids))!=len(ids):invalid()
        if text.strip().casefold() in seen:invalid()
        seen.add(text.strip().casefold())
        claims.append(Claim(text,tuple(ids)))
    return StructuredGeneration(tuple(claims))


def supported_text(output, question, evidence, relevance):
    if relevance is None:raise IARespuestaInvalida()
    allowed={e.citation:e for e in evidence}
    accepted=[]
    diagnostics=[]
    from app.application.rag.diagnostics import claim_result
    from app.application.agent.diagnostics import record_rag_private
    for index, claim in enumerate(output.claims):
        if not claim.source_ids or any(i not in allowed for i in claim.source_ids):raise IARespuestaInvalida()
        sources=tuple(allowed[i] for i in claim.source_ids)
        supported = relevance.supports_answer(question,claim.text,sources)
        diagnostics.append(claim_result(index, claim, supported, question, sources, relevance))
        if supported:
            accepted.append(claim.text.rstrip()+' '+ ' '.join(f'[{i}]' for i in claim.source_ids))
    partial=bool(accepted) and len(accepted)<len(output.claims)
    import logging
    logging.getLogger('app.rag').warning('rag_claims generated=%d accepted=%d rejected=%d',
        len(output.claims),len(accepted),len(output.claims)-len(accepted))
    record_rag_private({'stage': 'claims', 'generated': len(output.claims),
        'accepted': len(accepted), 'rejected': len(output.claims)-len(accepted),
        'claims': diagnostics, 'outcome': ('model_abstention' if not output.claims else
            'all_claims_rejected' if not accepted else 'partial_grounded' if partial else 'grounded')})
    return GeneracionSalida(respuesta='\n'.join(accepted) if accepted else 'SIN_EVIDENCIA',
                            finalizacion=output.finalizacion),partial
