import asyncio
import math
import logging
from time import monotonic

from app.application.ia.dto import ConsultaDatos, validate_output, validate_prompt
from app.application.ia.exceptions import IANoDisponible, IARespuestaInvalida, IATiempoAgotado
from app.application.rag.core import (build_context, prepare_pages, resolve_citations,
                                     select_evidence, validate_vector)
from app.application.rag.dto import RAGResult
from app.application.rag.extractive import enumeration_target, literal_requirements
from app.application.rag.existence import existence_target, literal_existence

_logger = logging.getLogger("app.rag")


class PrepararVersion:
    """Preparacion de paginas ya extraidas; staging idempotente, sin embeddings."""
    def __init__(self, *, authorizer, documents, counter, policy):
        self.authorizer, self.documents = authorizer, documents
        self.counter, self.policy = counter, policy

    async def execute(self, principal, document_id, pages):
        await self.authorizer.require_normal(principal)
        scope = await self.documents.require_active(principal, document_id)
        key, chunks = prepare_pages(pages, scope, self.counter, self.policy)
        await self.authorizer.require_normal(principal)
        # El repositorio revalida permiso de ingesta atomicamente; acceso de lectura no basta.
        return await self.documents.put_prepared_once(principal, scope, key, chunks)


class ResponderConDocumento:
    def __init__(self, *, authorizer, documents, vectors, embeddings, provider,
                 counter, gate, admission, threshold, timeout_seconds=60, relevance=None, recovery=None,
                 continuity=None, diagnostic_environment=None):
        if (type(threshold) not in (int, float) or not math.isfinite(threshold)
                or not -1 <= threshold <= 1 or type(timeout_seconds) not in (int, float)
                or not math.isfinite(timeout_seconds) or not 0 < timeout_seconds <= 60):
            raise ValueError('Configuracion RAG invalida.')
        self.authorizer, self.documents, self.vectors = authorizer, documents, vectors
        self.embeddings, self.provider, self.counter = embeddings, provider, counter
        self.gate, self.admission = gate, admission
        self.threshold, self.timeout = threshold, timeout_seconds
        self.relevance = relevance
        self.recovery = recovery
        self.continuity = continuity
        self.diagnostic_environment = diagnostic_environment

    async def execute(self, principal, document_id, question, *, instructions=''):
        await self.authorizer.require_normal(principal)
        validate_prompt(ConsultaDatos(prompt=question))
        scope = await self.documents.require_active(principal, document_id)
        work = self.gate.try_acquire()
        lease, timed_out = None, False
        try:
            lease = self.admission.try_acquire(principal)
            try:
                stage = "embedding"
                started = monotonic()
                deadline = asyncio.timeout(self.timeout)
                async with deadline:
                    from app.application.rag.continuity import requested_article
                    number = requested_article(question)
                    from app.application.rag.functions import functions_target, literal_functions
                    functions = functions_target(question) is not None
                    if functions and hasattr(self.vectors, 'resolve_functions'):
                        stage = 'functions_extraction'
                        resolution = await self.vectors.resolve_functions(principal, scope, question)
                        literal = literal_functions(question, resolution.chunks, scope)
                        related = getattr(resolution, 'related', None)
                        if related is not None:
                            page_label = (f'la página {related.pages[0]}' if len(related.pages) == 1
                                          else f'las páginas {related.pages[0]} a {related.pages[-1]}')
                            section = related.section or 'El documento autorizado'
                            result = RAGResult(status='ACLARACION', answer=
                                f"{section} contiene el artículo {related.number}, '{related.heading}', "
                                f'en {page_label}. No pude identificar un apartado específico denominado '
                                "'Funciones del Rectorado'. ¿Querés consultar las funciones del "
                                f'{related.authority} establecidas en ese artículo?')
                        elif literal is None:
                            result = RAGResult(status='SIN_EVIDENCIA', answer=
                                'No pude verificar un apartado completo e inequívoco de funciones para esa autoridad.')
                            _logger.warning('rag_abstention reason=functions_integrity')
                        else:
                            answer, evidence = literal
                            citations = resolve_citations(answer, evidence)
                            result = RAGResult(status='FUNDAMENTADA', answer=answer,
                                               citations=citations, finalization='completa')
                            _logger.warning('rag_functions mode=extractive sources=%d',len(citations))
                        await self.authorizer.require_normal(principal)
                        if await self.documents.require_active(principal,document_id) != scope:
                            raise IANoDisponible()
                        return result
                    structured = number is not None and hasattr(self.vectors, 'explicit_article')
                    context_reason = 'no_context'
                    existence = existence_target(question) is not None
                    literal_candidates = ()
                    if structured:
                        stage = "article_retrieval"
                        if hasattr(self.vectors, 'resolve_article'):
                            resolution = await self.vectors.resolve_article(principal, scope, number, question)
                            _logger.warning('rag_article_resolution reason=%s',resolution.reason)
                            if resolution.alternatives:
                                await self.authorizer.require_normal(principal)
                                if await self.documents.require_active(principal,document_id)!=scope:
                                    raise IANoDisponible()
                                return RAGResult(status='ACLARACION',answer=
                                    'Hay varias apariciones de ese artículo. Indicá la sección: '+
                                    '; '.join(f'{o.section} (página {o.page})' for o in resolution.alternatives)+'.')
                            chunks = resolution.chunks
                            if not chunks:
                                context_reason = resolution.reason
                        else:
                            chunks = await self.vectors.explicit_article(principal, scope, number)
                        from app.application.rag.dto import Candidate
                        select_evidence(tuple(Candidate(chunk=c, similarity=1.0) for c in chunks),
                                        scope, threshold=self.threshold)
                        _logger.warning('rag_article sources=%d', len(chunks))
                    else:
                        vector = await self.embeddings.embed_query(question, space=scope.space)
                        validate_vector(vector)
                        stage = "retrieval"
                        candidates = await self.vectors.search(principal, scope, vector, limit=12)
                        if len(candidates) > 12:
                            raise IARespuestaInvalida()
                        from app.application.rag.retrieval_diagnostics import observe_candidates
                        observe_candidates(self.diagnostic_environment, 'initial', candidates, scope, self.threshold)
                        chunks = select_evidence(candidates, scope, threshold=self.threshold)
                        # select_evidence validates EVERY candidate before thresholding.
                        # Keep the retrieved pool only for the isolated literal path.
                        if existence:
                            literal_candidates = tuple(c.chunk for c in candidates)
                        if self.relevance is not None:
                            chunks = self.relevance.select(question, chunks)
                        observe_candidates(self.diagnostic_environment, 'initial_selection', candidates,
                                           scope, self.threshold, pertinent=chunks)
                        _logger.warning('rag_selection initial_sources=%d',len(chunks))
                        if not chunks and self.recovery is not None and self.relevance is not None:
                            # Una sola ampliacion acotada; mismo vector, ACL y umbral.
                            stage = "recovery"
                            expanded = await self.recovery(principal,scope,vector)
                            if len(expanded)>48:raise IARespuestaInvalida()
                            observe_candidates(self.diagnostic_environment, 'recovery', expanded, scope, self.threshold)
                            chunks=self.relevance.select(question,select_evidence(expanded,scope,threshold=self.threshold))
                            if existence:
                                literal_candidates += tuple(c.chunk for c in expanded)
                            observe_candidates(self.diagnostic_environment, 'recovery_selection', expanded,
                                               scope, self.threshold, pertinent=chunks)
                            _logger.warning('rag_recovery candidates=%d relevant=%d pages=%s scores=%s',
                                len(expanded),len(chunks),tuple(c.chunk.page for c in expanded),
                                tuple(round(c.similarity,4) for c in expanded))
                        _logger.warning('rag_retrieval candidates=%d relevant=%d pages=%s scores=%s',
                            len(candidates),len(chunks),tuple(c.chunk.page for c in candidates),
                            tuple(round(c.similarity,4) for c in candidates))
                    if existence:
                        stage = 'existence_extraction'
                        if not structured:
                            # No score is evidence here. Examine only already retrieved,
                            # scope/formally validated chunks; include both bounded batches
                            # to avoid hiding a distinct declaration across recovery.
                            chunks = literal_candidates
                        from app.application.rag.retrieval_diagnostics import observe_candidates
                        observe_candidates(self.diagnostic_environment, 'literal_existence',
                            chunks, scope,
                            self.threshold, literal=True)
                        # Existence needs one complete declaration, not an entire
                        # multi-page article. Literal identity, positivity and uniqueness
                        # are mandatory independently of similarity/relevance admission.
                        literal = literal_existence(question, chunks, scope)
                        if literal is None:
                            _logger.warning('rag_abstention reason=existence_integrity')
                            result = RAGResult(status='SIN_EVIDENCIA', answer=
                                'No pude verificar una declaración documental inequívoca sobre ese órgano.')
                        else:
                            from app.application.ia.dto import GeneracionSalida
                            answer, evidence = literal
                            validate_output(GeneracionSalida(respuesta=answer, finalizacion='completa'))
                            result = RAGResult(status='FUNDAMENTADA', answer=answer,
                                citations=resolve_citations(answer, evidence), finalization='completa')
                            _logger.warning('rag_existence mode=extractive sources=1')
                        await self.authorizer.require_normal(principal)
                        if await self.documents.require_active(principal, document_id) != scope:
                            raise IANoDisponible()
                        return result
                    stage = "context"
                    if chunks and self.continuity is not None and not structured:
                        chunks = await self.continuity(principal, scope, chunks)
                        # Validar tambien los slices transitorios antes de renderizarlos.
                        from app.application.rag.dto import Candidate
                        select_evidence(tuple(Candidate(chunk=c, similarity=1.0) for c in chunks),
                                        scope, threshold=self.threshold)
                    input = build_context(question, chunks, self.counter, instructions)
                    if (input is not None and (self.continuity is not None or structured)
                            and tuple(e.chunk for e in input.evidence) != tuple(chunks)):
                        context_reason = 'article_context_budget'
                        input = None  # Articulo completo o abstencion; nunca truncamiento silencioso.
                    if input is None:
                        _logger.warning('rag_abstention reason=%s',context_reason)
                        result = RAGResult(status='SIN_EVIDENCIA', answer=(
                            'El artículo fue localizado, pero no cabe completo en el contexto disponible. No se enviará una versión truncada.'
                            if context_reason == 'article_context_budget' else
                            'No hay evidencia pertinente suficiente en el documento para responder esta pregunta. Pod\u00e9s reformular la pregunta o consultar sobre otro tema.'))
                    elif enumeration_target(question) is not None:
                        stage = 'requirements_extraction'
                        answer = literal_requirements(question, input.evidence, scope)
                        if answer is None:
                            _logger.warning('rag_abstention reason=requirements_integrity')
                            result = RAGResult(status='SIN_EVIDENCIA',answer=
                                'No pude verificar una lista completa de requisitos para ese cargo en las fuentes autorizadas.')
                        else:
                            from app.application.ia.dto import GeneracionSalida
                            validate_output(GeneracionSalida(respuesta=answer,finalizacion='completa'))
                            citations = resolve_citations(answer,input.evidence)
                            _logger.warning('rag_requirements mode=extractive sources=%d',len(citations))
                            result = RAGResult(status='FUNDAMENTADA',answer=answer,
                                               citations=citations,finalization='completa')
                    else:
                        _logger.warning('rag_context sources=%d pages=%s',len(input.evidence),tuple(e.chunk.page for e in input.evidence))
                        stage = "generation"
                        output = await self.provider.generate_grounded(input)
                        stage = "output"
                        from app.application.rag.structured_output import StructuredGeneration, supported_text
                        partial = False
                        from app.application.rag.diagnostics import outcome
                        abstention_reason = 'model_abstention'
                        if isinstance(output, StructuredGeneration):
                            if output.claims:
                                abstention_reason = 'all_claims_rejected'
                            output, partial = supported_text(output, question, input.evidence, self.relevance)
                        validate_output(output)
                        if output.respuesta == 'SIN_EVIDENCIA':
                            _logger.warning('rag_abstention reason=%s', abstention_reason)
                            outcome(abstention_reason)
                            result = RAGResult(status='SIN_EVIDENCIA',answer='No hay evidencia pertinente suficiente en el documento para responder esta pregunta. Pod\u00e9s reformular la pregunta o consultar sobre otro tema.')
                        else:
                            stage = "citations"
                            citations = resolve_citations(output.respuesta, input.evidence)
                            if self.relevance is not None and not self.relevance.supports_answer(question,output.respuesta,citations):
                                _logger.warning('rag_abstention reason=answer_not_supported')
                                outcome('final_support_rejected')
                                result=RAGResult(status='SIN_EVIDENCIA',answer='La evidencia recuperada no permite responder de forma suficientemente sustentada a esta pregunta.')
                            else:
                                section_partial = any(e.chunk.section.startswith('Sección normativa parcial:') for e in input.evidence)
                                outcome('partial_grounded' if partial or section_partial else 'grounded')
                                result = RAGResult(status='FUNDAMENTADA', answer=(
                                    'Respuesta parcial: se responde solo con la sección normativa recuperada.\n'
                                    if section_partial else
                                    'Respuesta parcial: se omitieron afirmaciones sin respaldo suficiente.\n'
                                    if partial else '') + output.respuesta,
                                                   citations=citations, finalization=output.finalizacion)
            except (TimeoutError, IATiempoAgotado):
                _logger.warning('rag_timeout category=%s stage=%s duration_s=%.6f',
                    'deadline' if deadline.expired() else 'upstream', stage, monotonic() - started)
                _logger.warning("rag_failure stage=%s kind=timeout", stage)
                timed_out = True
                raise IATiempoAgotado() from None
            except IANoDisponible:
                _logger.warning("rag_failure stage=%s kind=unavailable", stage)
                raise IANoDisponible() from None
            except Exception:
                _logger.warning("rag_failure stage=%s kind=invalid", stage)
                raise IARespuestaInvalida() from None
            await self.authorizer.require_normal(principal)
            if await self.documents.require_active(principal, document_id) != scope:
                raise IANoDisponible()
            return result
        finally:
            if lease is not None:
                lease.release(timed_out=timed_out)
            work.release()
