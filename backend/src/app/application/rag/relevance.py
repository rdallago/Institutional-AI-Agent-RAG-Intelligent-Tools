"""Politica academica conservadora v1, sin modelos ni contenido en logs.

La similitud no demuestra pertinencia. Se exige cobertura lexica de los conceptos
especificos de la pregunta en cada fuente. Puede abstenerse ante sinonimos no
contemplados; no reemplaza una evaluacion semantica del corpus.
"""
import re
import unicodedata

_STOP = set("que cual cuales como cuando donde por para con sin del los las una uno unos unas es son ser se el la en de y o un al a lo su sus me mi mantener requisitos sobre segun dice documento reglamento academico academica cuanto cuanta tiempo dura duracion sucede pasa entonces".split())
_GROUPS = (
    ('vencimiento', 'vence', 'vencer', 'vencida', 'vencido', 'vencimientos'),
    ('regularidad', 'regular', 'regulares'),
    ('curricular', 'curriculares'),
    ('unidad', 'unidades'),
    ('examen', 'examenes'),
    ('inscripcion', 'inscribirse', 'inscribir'),
    ('asistencia', 'asistencias'),
    ('aprobacion', 'aprobar', 'aprobado'),
)
_ALIASES = {word: group[0] for group in _GROUPS for word in group}
_ACADEMIC = set("reglamento academico academica regularidad curricular unidad examen inscripcion asistencia aprobacion correlatividad estudiante alumno evaluacion promocion materia cursada carrera docente matricula equivalencia".split())

def terms(text):
    folded = ''.join(c for c in unicodedata.normalize('NFD', text.lower()) if not unicodedata.combining(c))
    # Error de extraccion observado en terminaciones -cion/-sion. No corrige
    # cifras independientes ni reconstruye palabras ausentes de la evidencia.
    folded = re.sub(r'(?<=[a-z])6(?=n\b)', 'o', folded)
    return {_ALIASES.get(w, w) for w in re.findall(r'[a-z0-9]+', folded) if len(w) > 1 and w not in _STOP}

def automatic_strategy(question):
    # Compatibilidad interna: la seleccion operativa vive en AgentRouter.
    from app.application.agent.router import AgentRouter
    return 'LLM_DIRECTO' if AgentRouter().intent(question) == 'general' else 'RAG'

class AcademicRelevance:
    @staticmethod
    def focus(question):
        # Separar marco documental de la pregunta, sin sinonimos de cargos concretos.
        question = re.sub(r'^\s*[¿?]?en\s+[^,?]+,\s*', '', question, flags=re.I)
        question = re.split(r'\s+seg[uú]n\s+(?:el|la|los|las)\s+',question,maxsplit=1,flags=re.I)[0]
        return question

    @staticmethod
    def role_terms(text):
        # Morfologia de nombres de actividad/titular; no equipara organo y rector.
        folded=unicodedata.normalize('NFD',text.casefold())
        folded=''.join(c for c in folded if not unicodedata.combining(c))
        folded=re.sub(r'(?<=[a-z])6(?=n\b)','o',folded)
        folded=re.sub(r'\bcarreras\b','carrera',folded)
        return {re.sub(r'(?:aciones|acion|adores|ador)$','',w) for w in terms(folded)}

    def pertinent_units(self,question,text):
        from .existence import existence_target, declarations
        if existence_target(question) is not None:
            yield from (match.group() for match in declarations(question, text))
            return
        from .continuity import requested_article, ARTICLE
        number = requested_article(question)
        if number is not None:
            headings = list(ARTICLE.finditer(text))
            if len(headings) == 1 and int(headings[0].group(1)) == number:
                yield from self.units(text)
            return
        focus=self.focus(question)
        anchors=terms(focus)
        # Una solicitud de funciones puede sustentarse en la definicion explicita
        # del MISMO organo; no equipara un organo colegiado con su titular.
        relation=re.search(r'(?:funciones|atribuciones|competencias)\s+(?:del|de la|de los|de las)\s+(.+?)[?¿.]*$',focus,re.I)
        subject=terms(relation.group(1)) if relation else set()
        admission=re.search(r'\brequisitos\b.*?\b(?:concursos?|cargos?)\s+de\s+(.+?)[?¿.]*$',focus,re.I)
        if admission:
            target=self.role_terms(admission.group(1))
            # Encabezado normativo y su contenido, no cualquier concurso docente.
            for match in re.finditer(r'(?im)^\s*Requisitos\s+(?:del|de la|de los|de las)\s+([^\n]+)\n([^\n]+(?:\n[^\n]+)*)',text):
                if self.role_terms(match.group(1))==target:
                    yield match.group(0)
            return
        for unit in self.units(text):
            if subject:
                # Coocurrencia incidental no prueba de quien son las funciones.
                heading=re.search(r'^\s*(?:Articulo\s+\d+\s*[:.]?\s*)?(?:funciones|atribuciones|competencias)\s+(?:del|de la|de los|de las)\s+([^:]+):',unit,re.I)
                definition=re.search(r'^\s*del?\s+([^:]+):\s*es\b',unit,re.I)
                declaration=re.search(r'^\s*(?:las\s+)?(?:funciones|atribuciones|competencias)\s+(?:del|de la|de los|de las)\s+(.+?)\s+(?:son|incluyen|consisten)\b',unit,re.I)
                if definition and terms(definition.group(1))==subject:
                    yield unit
                elif heading and terms(heading.group(1))==subject:
                    yield unit
                elif declaration and terms(re.split(r'\b(?:de|que)\b',declaration.group(1),maxsplit=1,flags=re.I)[0])==subject:
                    yield unit
            elif anchors and anchors <= terms(unit):
                yield unit

    def select(self, question, chunks):
        anchors = terms(self.focus(question))
        if not anchors:
            return ()  # Pregunta sin conceptos verificables: pedir mayor precision.
        # Todos los conceptos deben aparecer en la misma fuente. Evita que palabras
        # genericas o el score coseno justifiquen fuentes sobre otro asunto.
        return tuple(c for c in chunks if tuple(self.pertinent_units(question,c.text)))

    @staticmethod
    def units(text):
        # No unir menciones dispersas en secciones/oraciones como una relación probada.
        # Saltos de linea del extractor son maquetacion, no limites semanticos.
        # Mantener limites de oraciones; unir titulo funcional con su primer inciso.
        text=re.sub(r'\s+',' ',text)
        text=re.sub(r'(\b(?:Funciones|Atribuciones|Competencias)\s+(?:del|de la)\s+[^.]{1,100})\.\s*([a-z])\.\s*',r'\1: ',text,flags=re.I)
        return tuple(part for part in re.split(r'[.!?;]+',text) if part.strip())

    def supports_answer(self,question,answer,citations):
        return self.explain_answer(question,answer,citations)['supported']

    def evidence_units(self, question, evidence):
        from .continuity import requested_article
        link = evidence.chunk.article
        if (link is not None and link.scope == evidence.chunk.scope
                and link.number == requested_article(question)
                and evidence.chunk.page >= link.first_page
                and link.closure in ('next_article','section_change','document_end')):
            # Repository-issued structural identity links exact continuation slices.
            return self.units(evidence.chunk.text)
        return tuple(self.pertinent_units(question,evidence.chunk.text))

    def comparison_claim(self, question, claim, sources):
        """Normalizar solo una introduccion funcional ante una definicion del mismo sujeto.

        No elimina vocabulario del predicado ni cambia el texto publicado.
        Sin definicion explicita y sujeto coincidente se compara el original.
        """
        introduction = re.fullmatch(
            r'\s*La funci[oó]n del ([\w ]{1,80}?) es (la unidad\b.+)\s*', claim, re.I)
        relation = re.search(
            r'funciones\s+del\s+(.+?)[?¿.]*$', self.focus(question), re.I)
        if not introduction or not relation:
            return claim
        def subject_identity(value):
            return ' '.join(unicodedata.normalize('NFC', value).casefold().split())
        subject = subject_identity(introduction.group(1))
        if not subject or subject != subject_identity(relation.group(1)):
            return claim
        for _, _, source in sources:
            definition = re.match(r'\s*Del ([^:]+):\s*Es la unidad\b', source, re.I)
            if definition and subject_identity(definition.group(1)) == subject:
                return introduction.group(1) + ' es ' + introduction.group(2)
        return claim

    def explain_answer(self,question,answer,citations):
        """Diagnostico local explicito. Contiene texto: nunca enviar a logs operativos.

        Usa exactamente el criterio de supports_answer, sin un segundo validador.
        missing_terms describe cobertura lexica, no demuestra falsedad semantica.
        """
        anchors=terms(self.focus(question))
        plain=re.sub(r'\[F[1-3]\]','',answer)
        # A verified article attribution is metadata, not an extra predicate.
        # Never remove arbitrary framing, subjects, numbers or a normative claim.
        from .continuity import requested_article
        from .articles import folded
        article_links={e.chunk.article for e in citations if e.chunk.article is not None}
        if len(article_links)==1:
            link=next(iter(article_links))
            if (link.number==requested_article(question)
                    and all(e.chunk.article==link and e.chunk.scope==link.scope for e in citations)
                    and link.closure in ('next_article','section_change','document_end')):
                pattern=(r'(?im)^\s*(?:(?:el\s+)?art[ií]culo\s+(\d+)(?:\s+del?\s+(.+?))?\s+'
                         r'(?:establece|dispone|indica|señala)\s+que\s+|seg[uú]n\s+el\s+art[ií]culo\s+(\d+)\s*,\s*)')
                def metadata(match):
                    number=int(match.group(1) or match.group(3))
                    section=match.group(2)
                    if number!=link.number:
                        return match.group()
                    if section and folded(section) not in folded(link.section):
                        return match.group()
                    return ''
                plain=re.sub(pattern,metadata,plain)
        # Solo el encabezado inicial literal de una fuente citada y pertinente
        # es metadato documental. No ignorar numeros ni la palabra articulo.
        header_pattern = r'^\s*(Artículo [0-9]+\.)(\s+Del [^:\n]{1,100}:)'
        header = re.match(header_pattern, plain)
        verified_header = None
        headers_valid = True
        if header:
            heading = ' '.join(header.group(0).split())
            headers_valid = False
            for evidence in citations:
                source_header = re.match(header_pattern, evidence.chunk.text)
                if (source_header and ' '.join(source_header.group(0).split()) == heading
                        and tuple(self.pertinent_units(question, evidence.chunk.text))):
                    headers_valid = True
                    verified_header = heading
                    # Conservar "Del <sujeto>:" y todo el predicado para validarlos.
                    plain = plain[:header.start(1)] + plain[header.end(1):]
                    break
        links={e.chunk.article for e in citations if e.chunk.article is not None}
        if len(links)>1:
            headers_valid=False  # Never combine homonymous articles in one claim.
        sources=[(evidence.citation,evidence.chunk.page,unit) for evidence in citations
                 for unit in self.evidence_units(question,evidence)]
        # Las palabras de la pregunta no son una obligacion de repetirlas en la
        # respuesta; si lo son el sujeto y el soporte de cada afirmacion citada.
        claims=[]
        for claim in self.units(plain):
            comparison_claim = self.comparison_claim(question, claim, sources)
            comparisons=[{'citation':citation,'page':page,'source':source,
                          'missing_terms':sorted(terms(comparison_claim)-terms(source)),
                          'polarity_matches':bool(re.search(r'\b(?:no|nunca|sin)\b',claim,re.I)) ==
                              bool(re.search(r'\b(?:no|nunca|sin)\b',source,re.I))}
                         for citation,page,source in sources]
            claims.append({'claim':claim,'comparison_claim':comparison_claim,
                           'supported':any(not c['missing_terms'] and c['polarity_matches'] for c in comparisons),
                           'comparisons':comparisons})
        # Comprobación conservadora de contenido: ninguna afirmación nueva sin soporte
        # léxico en una fuente pertinente citada. No equivale a entailment semántico.
        return {'supported':headers_valid and bool(anchors and sources) and all(c['supported'] for c in claims),
                'claims':claims,'pertinent_units':len(sources),
                'verified_header':verified_header,'headers_valid':headers_valid}
