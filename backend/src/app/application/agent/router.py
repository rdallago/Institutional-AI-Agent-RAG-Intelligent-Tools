"""Seleccion conservadora: titulo autorizado explicito, respaldo y modos manuales.

AUTO puede resolver identidades documentales sin inferencia; la ambiguedad conserva
el planificador semantico. No se conceden permisos mediante coincidencias de titulo.
"""
import re
import unicodedata

from .context import AgentContext, Decision


def normalize(text):
    return ''.join(c for c in unicodedata.normalize('NFD', text.casefold())
                   if not unicodedata.combining(c))


class AgentRouter:
    def institutional_functions(self, question):
        from app.application.rag.functions import functions_target
        target = functions_target(question)
        if target is None:
            return False
        # Only unqualified institutional authorities. A named instrument or an
        # explanatory/comparative suffix must keep document disambiguation.
        text = normalize(question).strip(' ¿?.')
        return bool(re.fullmatch(
            r'(?:cuales son las|que|enumera las|lista las) '
            r'(?:funciones|atribuciones|competencias) '
            r'(?:del|de la|de los|de las) '
            r'(?:rector|rectorado|vicerrector|director|vicedirector|consejo de rectores)', text))

    def institutional_requirements(self, question):
        """A narrow procedural intent; grants no document identity or ACL."""
        text=normalize(question)
        if re.search(r'\b(?:clima|pronostico|temperatura|lluvia|python|fastapi|programacion|algoritmo)\b',text):
            return False
        # A specifically named instrument must still be matched to its catalog.
        if re.search(r'\b(?:reglamento|resolucion|rom|anexo)\b|\bsegun\b',text):
            return False
        if re.search(r'^\s*[¿?]?\s*(?:que es|que significa|define|explica el concepto)\b',text):
            return False
        return bool(re.search(r'\brequisitos?\b',text)
            and re.search(r'\b(?:concursos?|acceder|cargo)\b',text)
            and re.search(r'\bcoordinaci(?:on|ones)\s+de\s+carreras?\b|\b(?:cargos?|concursos?)\s+docentes?\b',text))

    def explicit_document(self, question, catalog):
        """Identidad textual de titulo disponible, no inferencia por tema o cargo."""
        text=normalize(question)
        matches=[row for row in catalog if any(title.strip() and
            re.search(r'(?<!\w)'+re.escape(normalize(title).strip())+r'(?!\w)',text)
            for title in (row['titulo'],*row.get('aliases',())))]
        return matches[0] if len(matches)==1 else None

    def intent(self, question):
        text = normalize(question)
        if self.institutional_functions(question):
            return 'documentary'
        if self.institutional_requirements(question):
            return 'documentary'
        # Referencia normativa explícita o relación normativa con un objeto
        # académico. No basta la presencia de 'unidad' o 'regular' aisladas.
        normative = re.search(
            r'\b(reglamento|normativa|institucional(?:es)?|correlatividad|rector|rectorado|secretaria|resolucion)\b'
            r'|\b(?:esta|este|mi|nuestra|nuestro|la|el)\s+(?:institucion|instituto|universidad|facultad)\b'
            r'|\bunidad(?:es)?\s+curricular(?:es)?\b', text)
        academic_action = (re.search(r'\b(regularidad|inscri\w*|rendir|aprobar|asistencia|promocion|requisito\w*|plazo\w*)\b', text)
                           and re.search(r'\b(curricular\w*|academico\w*|examen\w*|materia\w*|cursad\w*|carrera\w*|alumn\w*|estudiant\w*)\b', text))
        if normative or academic_action:
            return 'documentary'
        if re.search(r'\bque (?:es|significa) (?:el |la )?(?:clima|temperatura|pronostico)\b', text) and not re.search(r'\b(en|hoy|manana)\b', text):
            return 'general'
        if re.search(r'\b(clima|meteorologico|pronostico|temperatura|llover\w*|lluvia|tiempo\s+(?:(?:hoy|manana|pasado manana)\s+)?(?:hace\s+)?en)\b', text):
            return 'weather'
        # Intención general explícita; no emplea documentos aunque estén elegidos.
        if re.search(r'\b(api\s+rest|python|fastapi|algoritmo\w*|programacion|matematic\w*|estadistic\w*)\b', text):
            return 'general'
        if re.search(r'\b(cuanto\s+(?:tiempo|dura)|que\s+requisitos|como\s+(?:solicito|se\s+solicita)|y\s+si)\b', text):
            return 'ambiguous'
        if re.search(r'\b(abrigo|paraguas|conviene|recomendas)\b', text):
            return 'ambiguous'
        if re.search(r'\b(regularidad|examen\w*|inscripcion|matricula|equivalencia|evaluacion)\b', text):
            return 'ambiguous'
        return 'general'

    def decide(self, question, context: AgentContext):
        intent = self.intent(question)
        if intent == 'general':
            return Decision('LLM_DIRECTO')
        document = context.selected_document
        if document is None and len(context.authorized_documents) == 1:
            document = context.authorized_documents[0]
        # Una pregunta ambigua no se manda a un modelo para adivinar su alcance.
        return Decision('RAG', document, clarification=(intent == 'ambiguous' or
                        (document is None and len(context.authorized_documents) > 1)))
