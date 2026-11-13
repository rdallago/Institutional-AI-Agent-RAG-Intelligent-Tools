"""Content-free validation metadata; optional literal capture stays private."""
from hashlib import sha256

from app.application.agent.diagnostics import record_rag_private


def safe_event(stage, reason, **metadata):
    """Opt-in operational metadata only; never claims, prompts or missing words."""
    import os
    if os.environ.get('AGENT_RAG_SAFE_DIAGNOSTICS') != 'true':
        return
    import json
    import logging
    from app.application.agent.diagnostics import request_identifier
    try:
        logging.getLogger('app.rag').warning('rag_safe_diagnostic %s', json.dumps(
            {'stage':stage,'reason':reason,'request_id':request_identifier.get(),**metadata},
            ensure_ascii=True,separators=(',',':')))
    except Exception:
        pass  # Diagnostics must never change validation or availability.


def generation(output, evidence, valid, count=None):
    safe_event('parser','valid' if valid else 'structured_contract_rejected',
               json_valid=valid,source_count=len(evidence),generated=count)
    record_rag_private({'stage': 'generation', 'json_valid': valid,
        'generated': count, 'sources': [
            {'citation': e.citation, 'chunk_id': e.chunk.id, 'page': e.chunk.page,
             'start': e.chunk.start, 'end': e.chunk.end,
             'version_id': str(e.chunk.scope.version_id),
             'sha256': sha256(e.chunk.text.encode('utf-8')).hexdigest()}
            for e in evidence]}, literal=output.respuesta)


def claim_result(index, claim, accepted, question, sources, relevance):
    result = {'index': index, 'source_ids': list(claim.source_ids), 'accepted': accepted}
    if not accepted:
        result['reason'] = 'support_rejected'
        try:
            explanation = relevance.explain_answer(question, claim.text, sources)
            result['headers_valid'] = explanation['headers_valid']
            result['pertinent_units'] = explanation['pertinent_units']
            result['units'] = [
                {'supported': unit['supported'], 'comparisons': [
                    {'citation': c['citation'], 'missing_terms': c['missing_terms'],
                     'polarity_matches': c['polarity_matches']}
                    for c in unit['comparisons'][:8]]}
                for unit in explanation['claims'][:8]]
            comparisons=[c for unit in explanation['claims'][:8] for c in unit['comparisons'][:8]]
            reason=('header_identity_mismatch' if not explanation['headers_valid'] else
                    'no_pertinent_units' if not explanation['pertinent_units'] else
                    'polarity_mismatch' if any(set(c['missing_terms']) <= {'no','nunca','sin'}
                                              and not c['polarity_matches'] for c in comparisons) else
                    'lexical_gap' if any(c['missing_terms'] for c in comparisons) else 'support_rejected')
            safe_event('claim_support',reason,index=index,accepted=False,
                sources=[e.citation for e in sources],pages=[e.chunk.page for e in sources],
                headers_valid=explanation['headers_valid'],
                comparisons=[{'source':c['citation'],'page':c['page'],
                    'missing_count':len(c['missing_terms']),'polarity_matches':c['polarity_matches']}
                    for c in comparisons])
        except Exception:
            result['detail'] = 'diagnostic_unavailable'
    else:
        safe_event('claim_support','accepted',index=index,accepted=True,
                   sources=[e.citation for e in sources],pages=[e.chunk.page for e in sources])
    return result


def outcome(value):
    record_rag_private({'stage': 'publication', 'outcome': value})
