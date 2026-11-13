"""Bounded existence questions backed by an explicit article declaration."""
import re

from .articles import folded
from .dto import Evidence


def _identity(text):
    # Order and every substantive word matter; only grammatical particles are
    # optional. No global aliases, stemming or authority equivalences.
    return tuple(word for word in re.findall(r'[a-z0-9]+', folded(text))
                 if word not in {'la', 'las', 'el', 'los', 'de', 'a'})


def existence_target(question):
    match = re.fullmatch(
        r'existe informacion sobre (?:la|el) (.+?) en el reglamento',
        folded(question).strip(' ¿?.'))
    if not match:
        return None
    subject = match.group(1)
    if not re.fullmatch(r'coordinacion de [a-z ]{3,100}', subject):
        return None
    return _identity(subject)


def declarations(question, text):
    target = existence_target(question)
    if target is None:
        return ()
    # A complete, positive sentence, anchored to its article heading. No fuzzy
    # identity, incidental mentions, negative statements or unfinished chunks.
    pattern = (r'(?m)^[ \t]*Art[ií]culo[ \t]+(?P<number>[0-9]+)\.[ \t]+'
               r'(?P<heading>Coordinaci[oó]n\s+de\s+[^:\n]{3,160}):\s*'
               r'funciona\s+bajo\s+la\s+dependencia\s+de\s+'
               r'(?:la|el)\s+[A-Za-zÁÉÍÓÚÜÑáéíóúüñ \t\n]{3,120}\.')
    return tuple(m for m in re.finditer(pattern, text)
                 if _identity(m['heading']) == target
                 and not re.search(r'\b(?:no|nunca|excepto|sin)\b', folded(m.group())))


def literal_existence(question, chunks, scope):
    choices = {}
    for chunk in chunks:
        if chunk.scope != scope or chunk.end - chunk.start != len(chunk.text):
            return None
        for match in declarations(question, chunk.text):
            # Overlap copies of the same declaration are one source; distinct
            # articles, locations or declarations remain ambiguous.
            key = (chunk.page, chunk.start + match.start(), match.group())
            choices[key] = (chunk, match)
    if len(choices) != 1:
        return None
    chunk, match = next(iter(choices.values()))
    answer = 'Sí. Información documental localizada (extracto literal):\n' + match.group().strip() + ' [F1]'
    if len(answer) > 3000 or len(answer.encode()) > 9000:
        return None
    return answer, (Evidence(citation='F1', chunk=chunk),)
