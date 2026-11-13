from uuid import UUID
import asyncio
import logging
from time import monotonic
from contextlib import nullcontext

from app.application.ia.dto import ConsultaDatos, validate_prompt
from app.application.ia.exceptions import IANoDisponible, IATiempoAgotado
from .context import (AgentContext, AgentResult, effective_question, direct_context,
                      conversation_memory_reference, resolve_conversation_memory)
from .router import AgentRouter
from .errors import ClimaNoDisponible
from .diagnostics import execution_trace, record_private
from .tools import ToolRegistry, weather_arguments
from .planning import (planning_context, matches_document,
                       WeatherProposal, DocumentProposal, DirectProposal, ClarificationProposal, EmptyArguments)

logger = logging.getLogger('app.agent')


class Agent:
    def __init__(self, *, authorizer, direct, rag, documents, admission, skills, weather=None, planner=None):
        self.authorizer, self.direct, self.rag = authorizer, direct, rag
        self.documents, self.admission, self.skills = documents, admission, skills
        self.router = AgentRouter()
        self.weather, self.planner, self.tools = weather, planner, ToolRegistry()

    async def execute(self, principal, question, *, mode='AUTO', document_id=None, history=()):
        await self.authorizer.require_normal(principal)
        validate_prompt(ConsultaDatos(prompt=question))
        expanded, weather_context = effective_question(question, history)
        started = monotonic()
        scope = self.admission.scope(principal) if hasattr(self.admission,'scope') else nullcontext()
        try:
            async with asyncio.timeout(60):
                with scope:
                    result = await self._execute(principal, expanded, mode=mode, document_id=document_id,
                        direct_prompt=direct_context(question,history), weather_context=weather_context,
                        original_question=question, history=history)
                    await self.authorizer.require_normal(principal)
                    return result
        except TimeoutError:
            raise IATiempoAgotado() from None
        finally:
            logger.warning('agent_finish duration_ms=%d', int((monotonic()-started)*1000))

    async def _execute(self, principal, question, *, mode, document_id, direct_prompt, weather_context,
                       original_question=None, history=()):
        if mode not in ('AUTO', 'RAG', 'LLM_DIRECTO'):
            raise ValueError('Modo invalido.')
        current = original_question or question
        from .context import next_article_reference, resolve_next_article
        if mode=='AUTO' and next_article_reference(current):
            if resolve_next_article(current,history) is None:
                return AgentResult(strategy='RAG',status='ACLARACION',
                    answer='Indicá el artículo, documento y sección anteriores para identificar el siguiente sin adivinar.')
            # The expanded question carries the verified literal section reference.
            original_question=question
        if mode == 'AUTO' and conversation_memory_reference(current):
            # La memoria de preguntas no es evidencia documental. Resolver antes
            # del atajo por titulo para no buscar en el PDF lo que dijo el usuario.
            answer = resolve_conversation_memory(current, history)
            logger.warning('agent_route source=rules intent=conversation_memory')
            if answer is None:
                return AgentResult(strategy='LLM_DIRECTO', status='ACLARACION',
                    answer='No puedo identificar una única pregunta anterior en el contexto de esta conversación. Indicame a cuál te referís.')
            return AgentResult(strategy='LLM_DIRECTO', status='GENERADA',
                               answer=answer, finalization='completa')
        intent = self.router.intent(question)
        semantic = False
        date_invalid = False
        try:
            weather_args = weather_arguments(question, weather_context) if intent == 'weather' else None
        except ValueError:
            weather_args, date_invalid = None, True
        direct_document = None
        rows = None
        if mode=='AUTO' and intent=='documentary' and self.documents is not None:
            rows = await (getattr(self.documents,'list_sources',self.documents.list_documents))(principal)
            direct_document = self.router.explicit_document(original_question or question,rows)
            if direct_document is not None:
                # Resolver solo un titulo inequívoco del catalogo autorizado.
                # La ACL y version se revalidan tambien en el recorrido RAG habitual.
                if document_id is None or str(document_id)==str(direct_document['id']):
                    document_id=UUID(str(direct_document['id']))
                else:
                    direct_document=None  # Seleccion contradictoria requiere interpretacion.
        direct_weather = intent=='weather' and weather_args is not None and not date_invalid
        procedural_document = intent=='documentary' and self.router.institutional_requirements(question)
        structural_functions = self.router.institutional_functions(question)
        if mode=='AUTO' and self.planner is not None and direct_document is None and not direct_weather and not procedural_document and not structural_functions:
            # AUTO: un plan semántico, una capacidad final. Sin ciclos ni replan.
            if rows is None:
                rows = await (getattr(self.documents,'list_sources',self.documents.list_documents))(principal) if self.documents is not None else []
            if document_id is not None:
                if self.documents is None:raise IANoDisponible()
                await self.documents.require_active(principal, document_id)
            payload = planning_context(original_question or question, history, rows, document_id)
            try:
                logger.warning('agent_stage trace=%s stage=planner', execution_trace.get())
                proposal = await self.planner.plan(payload)
            except (TimeoutError, IATiempoAgotado):
                logger.warning('agent_failure trace=%s stage=planner code=IA_TIEMPO_AGOTADO', execution_trace.get())
                raise
            except IANoDisponible:
                # Solo rutas que el parser existente resuelve completas y sin adivinar.
                logger.warning('agent_route source=safe_fallback reason=planner_unavailable intent=%s', intent)
                if intent=='ambiguous' or (intent=='weather' and weather_args is None):raise
                # Un documento específico no puede sustituirse por el único catálogo disponible.
                if intent=='documentary':raise
            else:
                plan = self.tools.validate_proposal(proposal.model_dump_json())
                semantic = True
                logger.warning('agent_route source=qwen action=%s step=1', plan.accion)
                from .context import contextual_reference
                if (isinstance(plan,WeatherProposal) and self.router.intent(original_question or question)=='general'
                        and not contextual_reference(original_question or question)):
                    logger.warning('agent_coherence rejected=weather_without_current_intent selected=general')
                    plan=DirectProposal(accion='responder_llm_directo',argumentos=EmptyArguments())
                if isinstance(plan, WeatherProposal):
                    record_private('weather_proposal', arguments=plan.argumentos.model_dump())
                    intent, date_invalid = 'weather', False
                    from .geography import normalize_geography,contains_location
                    from .context import contextual_reference
                    import json
                    current=original_question or question
                    previous=json.loads(payload).get('ubicacion_previa')
                    if (self.router.intent(current)=='general' and not contextual_reference(current)
                            and not contains_location(current,plan.argumentos.ciudad)):
                        previous=None  # Ubicación anterior no demuestra intención actual.
                    normalized = normalize_geography(plan.argumentos,original_question or question,
                                                     previous)
                    weather_args = normalized.args
                    record_private('weather_normalization', reason=normalized.reason,
                                   arguments=weather_args.model_dump() if weather_args else None)
                    logger.warning('agent_geography status=%s country_changed=%s',normalized.reason,normalized.country_changed)
                    if weather_args is None:
                        current_intent=self.router.intent(original_question or question)
                        if current_intent=='general' and not contextual_reference(original_question or question):
                            # Propuesta de tool sin argumentos sustentados para consulta autónoma general.
                            # No preguntar por parámetros de una herramienta que no corresponde.
                            intent='general'
                            logger.warning('agent_coherence rejected=ungrounded_weather selected=general')
                        else:
                            return AgentResult(strategy='TOOL',status='ACLARACION',tool='consultar_clima',
                                answer='No pude verificar inequívocamente la ubicación indicada. Confirmá ciudad, provincia o región y país.')
                elif isinstance(plan, DirectProposal):
                    intent = 'general'
                elif isinstance(plan, ClarificationProposal):
                    reason = plan.argumentos.motivo
                    return AgentResult(strategy='TOOL' if reason in ('ubicacion','fecha') else 'RAG',
                        status='ACLARACION', tool='consultar_clima' if reason in ('ubicacion','fecha') else None,
                        answer={'ubicacion':'Indicá ciudad, provincia o región y país para desambiguar la ubicación.',
                                'fecha':'Indicá una única fecha válida para consultar el pronóstico.',
                                'documento':'Precisá el documento académico que querés consultar.',
                                'intencion':'Precisá qué querés consultar para elegir la herramienta adecuada.'}[reason])
                elif isinstance(plan, DocumentProposal):
                    if self.documents is None or self.rag is None:raise IANoDisponible()
                    intent = 'documentary'
                    args = plan.argumentos
                    selected = next((r for r in rows if str(r['id'])==args.documento_id), None)
                    if args.documento_id is not None and selected is None:
                        from app.application.ia.exceptions import IARespuestaInvalida
                        raise IARespuestaInvalida()
                    if selected is None or (args.documento_solicitado and not any(
                            matches_document(args.documento_solicitado,title)
                            for title in (selected['titulo'],*selected.get('aliases',())))):
                        logger.warning('agent_result kind=document_unavailable step=2 reason=%s authorized_catalog_count=%d',
                            'empty_authorized_catalog' if not rows else
                            'planner_document_not_selected' if selected is None else 'requested_title_mismatch',
                            len(rows))
                        return AgentResult(strategy='RAG',status='SIN_EVIDENCIA',
                            answer='No dispongo de ese documento académico entre las fuentes autorizadas disponibles. No puedo fundamentar una respuesta sin él.')
                    document_id = UUID(str(selected['id']))
                    await self.documents.require_active(principal,document_id)
                    # La selección del modelo no autoriza a cambiar el objeto documental.
                    # Usar pregunta original, o referencia expandida por el backend, no una paráfrasis libre.
                    validate_prompt(ConsultaDatos(prompt=question))
        else:
            logger.warning('agent_route source=rules intent=%s', intent)
        if mode=='AUTO' and intent=='weather':
            if date_invalid:
                return AgentResult(strategy='TOOL', status='ACLARACION', tool='consultar_clima',
                    answer='Indicá una única fecha válida (día/mes/año), hoy, mañana o pasado mañana.',
                    tool_context=weather_context or {})
            if weather_args is None:
                return AgentResult(strategy='TOOL', status='ACLARACION', tool='consultar_clima',
                    answer='Indicá ciudad, provincia o región y país para consultar el clima sin confundir ubicaciones.')
            if self.weather is None: raise IANoDisponible()
            skill = self.skills.load('weather')
            logger.warning('agent_tool name=consultar_clima')
            try:
                return await self.weather.execute(weather_args, skill.instructions)
            except IANoDisponible:
                raise ClimaNoDisponible() from None
        if mode == 'LLM_DIRECTO' or (mode == 'AUTO' and intent == 'general'):
            logger.warning('agent_execute action=responder_llm_directo step=2')
            logger.warning('agent_stage trace=%s stage=direct history_included=%s',
                execution_trace.get(), direct_prompt != (original_question or question))
            output = await self.direct.ejecutar(principal, ConsultaDatos(prompt=direct_prompt))
            return AgentResult(strategy='LLM_DIRECTO', status='GENERADA',
                               answer=output.respuesta, finalization=output.finalizacion)
        if self.rag is None or self.documents is None:
            # Runtime no compuesto es fallo tecnico, no ausencia de evidencia.
            raise IANoDisponible()
        if document_id is not None:
            await self.documents.require_active(principal, document_id)
        if mode == 'AUTO' and not semantic:
            catalog = ()
            if document_id is None:
                catalog = tuple(UUID(str(d['id'])) for d in await self.documents.list_documents(principal))
            decision = self.router.decide(question, AgentContext(document_id, catalog))
            document_id = decision.document_id
            clarify = intent=='ambiguous' or (document_id is None and len(catalog)>1)
        else:
            clarify = False
        if clarify or document_id is None:
            lease = self.admission.try_acquire(principal)
            try:
                await self.authorizer.require_normal(principal)
                if document_id is not None:
                    await self.documents.require_active(principal, document_id)
                return AgentResult(strategy='RAG', status='ACLARACION' if clarify else 'SIN_EVIDENCIA', answer=(
                    'Precisá el tema normativo y el documento para resolver la consulta sin adivinar.' if clarify else
                    'No hay evidencia documental autorizada disponible para esta consulta institucional.'))
            finally:
                lease.release(timed_out=False)
        skill = self.skills.load('academic-rag')
        logger.warning('agent_execute action=consultar_documentos_academicos step=2')
        logger.warning('agent_stage trace=%s stage=rag', execution_trace.get())
        output = await skill.execute(self.rag, principal, document_id, question)
        from app.application.rag.relevance import terms
        return AgentResult(strategy='RAG', status=output.status, answer=output.answer,
                           finalization=output.finalization, citations=output.citations,
                           tool_context={'topic':' '.join(sorted(terms(question)))})
