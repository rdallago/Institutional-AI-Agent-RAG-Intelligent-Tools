"""Opt-in local de metadata; nunca serializa objetos ni contenido documental."""
import json
import logging
import math
import os
import re

from app.application.agent.diagnostics import execution_trace
from app.application.rag.core import select_evidence
from app.application.rag.dto import Candidate


def observe_candidates(environment, stage, candidates, scope, threshold,
                       *, pertinent=None, literal=False):
    """Fail-soft. Pertinencia registra admisión efectiva, no reejecuta filtros.

    Scope/autorización se refiere al scope ya autorizado por require_active y
    el repositorio: no observa las filas excluidas por la ACL SQL.
    Integridad es la validación formal de select_evidence, no un nuevo hash.
    """
    try:
        if (environment != 'local-development'
                or os.environ.get('AGENT_RAG_RETRIEVAL_DIAGNOSTICS') != 'true'):
            return
        if stage not in {'initial', 'initial_selection', 'recovery',
                         'recovery_selection', 'literal_existence'}:
            return
        trace = execution_trace.get()
        trace = trace if isinstance(trace, str) and re.fullmatch(
            r'(?:[0-9a-fA-F]{32}|[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12})', trace
        ) else 'isolated'
        for candidate in candidates:
            chunk = candidate if literal else candidate.chunk
            score = None if literal else candidate.similarity
            numeric = type(score) in (int, float) and math.isfinite(score)
            score = score if numeric else None
            matches = chunk.scope == scope
            try:
                # Validación pura sobre el scope propio: separa integridad de scope.
                select_evidence((Candidate(chunk=chunk, similarity=(score if numeric else 1.)),),
                                chunk.scope, threshold=-1.)
                integrity = literal or numeric
            except Exception:
                integrity = False
            passed = score >= threshold if numeric else None
            admitted = (chunk in pertinent if pertinent is not None and matches
                        and integrity and (passed or literal) else None)
            event = dict(trace_id=trace, stage=stage,
                         ordinal=chunk.ordinal if type(chunk.ordinal) is int else None,
                         page=chunk.page if type(chunk.page) is int else None,
                         score=score, threshold_passed=passed,
                         scope_authorization=matches, integrity=integrity,
                         pertinent=admitted, reached_literal_existence=literal)
            logging.getLogger('app.rag').warning('rag_retrieval_diagnostic %s',
                                            json.dumps(event, allow_nan=False))
    except Exception:
        # Observabilidad nunca cambia el resultado ni propaga fallos de logging.
        return
