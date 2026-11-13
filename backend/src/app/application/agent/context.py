from dataclasses import dataclass, field
from uuid import UUID
import json
import re


@dataclass(frozen=True, slots=True)
class AgentContext:
    selected_document: UUID | None = None
    authorized_documents: tuple[UUID, ...] = ()


@dataclass(frozen=True, slots=True)
class Decision:
    strategy: str
    document_id: UUID | None = None
    clarification: bool = False


@dataclass(frozen=True, slots=True, kw_only=True)
class AgentResult:
    strategy: str
    status: str
    answer: str = field(repr=False)
    finalization: str | None = None
    citations: tuple = field(default=(), repr=False)
    tool: str | None = None
    tool_context: dict = field(default_factory=dict, repr=False)


@dataclass(frozen=True, slots=True, kw_only=True)
class ConversationContext:
    user_id: UUID
    conversation_id: UUID
    question: str = field(repr=False)
    history: tuple = field(default=(), repr=False)


def contextual_reference(question):
    """Señal estructural de continuación, no clasificación por tema concreto."""
    from .router import normalize
    text=normalize(question).strip(' ¿?')
    if re.match(r'^(?:(?:y\s+)?(?:cambiando de tema|otro tema)|(?:ahora\s+)?hablemos de)\b', text):
        return False
    return bool(re.match(
        r'^(?:(?:y|entonces)\s+(?:que|cual(?:es)?|como|cuando|cuanto(?:s|a|as)?|donde|quien(?:es)?|el|la|eso|esa|ese|hoy|manana|pasado|\d)\b'
        r'|manana\b|(?:volviendo|retomando|regresando)\s+(?:a|al|el|la|los|las)\b)', text))


def effective_question(question, history):
    """El historial resuelve referencia, nunca se convierte en evidencia RAG."""
    from .router import normalize
    if next_article_reference(question):
        expanded = resolve_next_article(question, history)
        return (expanded or question), None
    followup = contextual_reference(question)
    previous = next((m for m in reversed(history) if m['role']=='assistant'), None)
    if not followup or previous is None:
        return question, None
    # Una referencia estructural no autoriza a imponer el canal anterior ante
    # un tema explícito de otra capacidad. El planificador conserva la pregunta.
    from .router import AgentRouter
    intent = AgentRouter().intent(question)
    if re.match(r'^(?:volviendo|retomando|regresando)\s+', normalize(question).strip(' ¿?')):
        return question, None
    if previous.get('strategy') == 'RAG' and intent == 'weather':
        return question, None
    if previous.get('strategy') == 'RAG' and intent == 'general':
        # Las preguntas autónomas generales no heredan un tema académico.
        if re.search(r'\b(?:api\s+rest|python|fastapi|programacion|algoritmo\w*|matematic\w*|estadistic\w*)\b', normalize(question)):
            return question, None
    if intent == 'documentary' and previous.get('strategy') == 'TOOL':
        return question, None
    if previous.get('tool') == 'consultar_clima' or (previous.get('strategy') == 'TOOL' and previous.get('tool_context', {}).get('ciudad')):
        from .tools import DATE_PATTERN
        if re.search(r'\b(manana|hoy|temperatura|pronostico)\b|'+DATE_PATTERN, normalize(question)):
            return 'Pronóstico del clima: '+question, previous.get('tool_context')
    if previous.get('strategy') == 'RAG':
        user = next((m for m in reversed(history) if m['role']=='user'), None)
        if user:
            from app.application.rag.relevance import terms
            topic = previous.get('tool_context',{}).get('topic') or ' '.join(sorted(terms(user['content'])))
            expanded = 'Sobre '+topic+': '+question
            if len(expanded)<=1000 and len(expanded.encode('utf-8'))<=3000:
                return expanded, None
    return question, None


def conversation_memory_reference(question):
    """Consulta explicita sobre preguntas previas, no sobre contenido normativo."""
    from .router import normalize
    text = normalize(question)
    if previous_answer_reference(question) or conversation_topics_reference(question):
        return True
    return bool(re.search(
        r'\b(?:te\s+)?(?:pregunte|habia preguntado|he preguntado)\s+(?:antes|anteriormente|previamente)\b'
        r'|\b(?:que|cual(?:es)?)\s+(?:fue|era|fueron|eran)\s+mi(?:s)?\s+(?:pregunta|consulta)(?:s)?\s+(?:anterior(?:es)?|previa(?:s)?)\b',
        text) or re.search(
        r'\b(?:mi|mis|la|las)\s+(?:(?:ultima|ultimas|penultima|primera|primeras)\s+(?:\d+\s+)?)?(?:pregunta|consulta)s?\b'
        r'.*\b(?:anterior|anteriores|previa|previas|hice|pregunte)\b'
        r'|\b(?:mi|mis)\s+(?:ultima|ultimas|penultima|primera|primeras)\s+(?:\d+\s+)?(?:pregunta|consulta)s?\b'
        r'|\bque\s+te\s+pregunte\b'
        r'|\b(?:que|cual)\s+(?:fue|era)\s+la\s+(?:ultima|penultima|primera)\s+(?:pregunta|consulta)\b'
        r'|\b(?:preguntas|consultas)\s+(?:anteriores|previas)\b', text))


def conversation_memory_context(question, history):
    """Solo preguntas del usuario de la ventana autorizada; nunca respuestas RAG.

    La pregunta actual se conserva completa y se mantienen los limites del directo.
    Si la pregunta previa inmediata no cabe, no sustituirla por una mas antigua.
    """
    selected = []
    for message in reversed(history[-8:]):
        if message.get('role') != 'user':
            continue
        item = {'role':'user', 'content':message['content']}
        candidate = json.dumps({'historial_no_confiable':[item, *selected],
                                'pregunta_actual':question}, ensure_ascii=False)
        if len(candidate)>1000 or len(candidate.encode('utf-8'))>3000:
            break
        selected.insert(0, item)
    if not selected:
        return None
    return json.dumps({'historial_no_confiable':selected,
                       'pregunta_actual':question}, ensure_ascii=False)


def resolve_conversation_memory(question, history, *, now=None):
    """Extraccion literal de preguntas propias; no inferir ni usar respuestas."""
    from .router import normalize
    history = memory_date_history(question, history, now=now)
    if history is None:
        return 'No puedo verificar qué mensajes corresponden a hoy porque faltan marcas temporales con zona horaria en el historial disponible.'
    ordered = [m['content'] for m in history[-100:] if m.get('role') == 'user']
    current = normalize(question)
    if conversation_topics_reference(question):
        # Quote user topics through their actual questions, without summarizing
        # normative claims or treating previous assistant answers as evidence.
        questions=list(dict.fromkeys(q for q in ordered if not conversation_memory_reference(q)))
        selected=questions[-10:]
        if not selected:return None
        value='En esta conversación, estos temas aparecen en tus preguntas:\n'+'\n'.join(f'{i+1}. {q}' for i,q in enumerate(selected))
        return value if len(value)<=3000 and len(value.encode('utf-8'))<=9000 else None
    if previous_answer_reference(question):
        previous=next((m for m in reversed(history[-100:]) if m.get('role')=='assistant'),None)
        if previous is None:return None
        value='Registro de la respuesta anterior, no evidencia nueva:\n'+previous['content']
        return value if len(value)<=3000 and len(value.encode('utf-8'))<=9000 else None
    if 'organo' not in current and (re.search(r'\b(?:antes|anteriormente|previamente)\b',current)
            or re.search(r'\bde que\s+(?:veniamos|estabamos)\s+hablando\b',current)):
        if not ordered:return None
        value='Me preguntaste: '+ordered[-1]
        return value if len(value)<=3000 and len(value.encode('utf-8'))<=9000 else None
    # Temporal references select turns, preserving repeated questions and order.
    if re.search(r'\b(?:ultima|ultimas|penultima|primera|primeras|anterior|anteriores|previa|previas)\b',current) and 'organo' not in current:
        count_match=re.search(r'\b(?:ultimas|primeras)\s+(\d+)\b',current)
        count=int(count_match.group(1)) if count_match else (3 if re.search(r'\b(?:preguntas|consultas)\b',current) else 1)
        if not 1<=count<=10:return None
        if 'penultima' in current:
            selected=ordered[-2:-1] if len(ordered)>=2 else []
        elif re.search(r'\b(?:primera|primeras)\b',current):
            selected=ordered[:count]
        else:selected=ordered[-count:]
        if not selected:return None
        if count_match and len(selected)!=count:return None
        value='Preguntas del historial disponible:\n'+'\n'.join(f'{i+1}. {q}' for i,q in enumerate(selected))
        return value if len(value)<=3000 and len(value.encode('utf-8'))<=9000 else None
    candidates = list({normalize(' '.join(q.split())):q for q in ordered
                       if not conversation_memory_reference(q)}.values())
    if 'reglamento' in current:
        candidates = [q for q in candidates if 'reglamento' in normalize(q)]
    if 'organo' in current:
        # Contar sujetos verificables, no preguntas de otros temas/cargos.
        # Distintas formulaciones sobre el mismo organo no son ambiguedad.
        subjects = {}
        for previous in candidates:
            if len(previous)>1000 or len(previous.encode('utf-8'))>3000:
                return None
            found = re.findall(r'\b(?:funciones|atribuciones|competencias)\s+(?:del|de la)\s+(.+?)(?=\s+seg[uú]n\b|[?¿.!]|$)', previous, re.I)
            for value in found:
                subject = value.strip()
                if re.search(r'\b(?:y|o)\b', subject, re.I):
                    return None
                subjects[normalize(subject)] = subject
        if len(subjects) != 1:
            return None
        return f'Me preguntaste por {next(iter(subjects.values()))}.'
    if len(candidates) != 1:
        return None
    previous = candidates[0]
    if len(previous)>1000 or len(previous.encode('utf-8'))>3000:
        return None
    articles = re.findall(r'\bart[ií]culo\s+\d+\b', previous, re.I)
    if 'articulo' in current:
        if len(set(articles)) != 1:
            return None
        return f'Tu pregunta mencionaba literalmente «{articles[0]}».'
    return f'Tu pregunta anterior fue: «{previous}»'


def previous_answer_reference(question):
    from .router import normalize
    text=normalize(question)
    return bool(re.search(r'\bque\s+me\s+(?:respondiste|habias respondido)\s+(?:antes|anteriormente|previamente)\b'
                          r'|\b(?:repetir|repeti|repite|recordar)\s+(?:tu|la)\s+respuesta\s+anterior\b',text))


def conversation_topics_reference(question):
    from .router import normalize
    text=normalize(question)
    return bool(re.search(
        r'\b(?:de|sobre)\s+que\s+te\s+estuve\s+preguntando\b'
        r'|\bsobre\s+que\s+te\s+pregunte\s+hoy\b'
        r'|\bque\s+temas\s+(?:estuvimos|venimos|veniamos)\s+(?:tratando|hablando)\b'
        r'|\b(?:de\s+)?que\s+(?:estuvimos|veniamos|estabamos)\s+hablando\b',text))


def memory_date_history(question, history, *, now=None):
    """Calendar scope requires aware timestamps; never infer dates from order."""
    from .router import normalize
    if not re.search(r'\bhoy\b|\ben el dia de la fecha\b',normalize(question)):
        return history
    from datetime import datetime
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
    try:
        zone=ZoneInfo('America/Buenos_Aires')
    except ZoneInfoNotFoundError:
        return None
    now=now or datetime.now(zone)
    if now.tzinfo is None:return None
    today=now.astimezone(zone).date()
    selected=[]
    for message in history[-100:]:
        if message.get('role') not in ('user','assistant'):continue
        stamp=message.get('creado_at')
        if isinstance(stamp,str):
            try:stamp=datetime.fromisoformat(stamp.replace('Z','+00:00'))
            except ValueError:return None
        if not isinstance(stamp,datetime) or stamp.tzinfo is None:return None
        if stamp.astimezone(zone).date()==today:selected.append(message)
    return tuple(selected)


def next_article_reference(question):
    from .router import normalize
    return bool(re.fullmatch(r'[¿?\s]*(?:y\s+)?(?:que\s+(?:establece|dice|dispone)\s+)?el\s+(?:articulo\s+)?siguiente[?\s.]*',normalize(question)))


def resolve_next_article(question, history):
    """Only the immediately preceding user turn can supply an article identity."""
    from app.application.rag.continuity import requested_article
    previous=next((m for m in reversed(history[-8:]) if m.get('role')=='user'),None)
    if previous is None or conversation_memory_reference(previous['content']):return None
    number=requested_article(previous['content'])
    if number is None:return None
    expanded=re.sub(r'\b(?:art[ií]culo|art\.)\s*\d+\b',f'artículo {number+1}',previous['content'],flags=re.I)
    return expanded if len(expanded)<=1000 and len(expanded.encode('utf-8'))<=3000 else None


def direct_context(question, history):
    """Ultimos mensajes acotados; mantiene intacta la pregunta actual."""
    if not contextual_reference(question):
        return question
    selected = []
    for message in reversed(history[-8:]):
        if message.get('strategy') in ('RAG', 'TOOL'):
            continue  # Una salida de otra capacidad no es contexto conversacional directo.
        item = {'role':message['role'], 'content':message['content']}
        candidate = json.dumps({'historial_no_confiable': [item,*selected],
                                'pregunta_actual':question}, ensure_ascii=False)
        if len(candidate)>1000 or len(candidate.encode('utf-8'))>3000:
            continue
        selected.insert(0,item)
    if not selected:
        return question
    return json.dumps({'historial_no_confiable':selected,'pregunta_actual':question}, ensure_ascii=False)
