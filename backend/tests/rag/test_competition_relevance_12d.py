import asyncio
from dataclasses import replace
from uuid import uuid4
import pytest

from app.application.rag.relevance import AcademicRelevance
from app.application.rag.continuity import complete_article, requirement_section
from app.application.rag.dto import Candidate
from app.application.ia.dto import GeneracionSalida
from app.application.ia.exceptions import IARespuestaInvalida
from tests.rag.test_core import setup


QUESTION='¿Cuáles son los requisitos para acceder a concursos de Coordinaciones de Carreras?'
PAGE=('Articulo 52. Coordinaciones de Carrera.\n'
      'Requisitos del Coordinador de Carrera\n'
      '- Poseer título docente.\n- Acreditar formación específica.\n'
      'Evaluación del proyecto:\nSe evalúa el proyecto.\nArticulo 53. Otras funciones.')


@pytest.mark.parametrize('question',[
    QUESTION, 'Requisitos para acceder al concurso de Coordinación de Carrera',
    'Requisitos para cargos de Coordinadores de Carreras',
])
def test_explicit_requirements_match_role_not_literal_procedural_verbs(question):
    assert tuple(AcademicRelevance().pertinent_units(question,PAGE))


@pytest.mark.parametrize('text',[
    'Las Coordinaciones de Carreras participan en concursos institucionales.',
    'El acceso a concursos de Coordinaciones de Carreras está previsto.',
    'Requisitos del Director de Carrera\n- Poseer título docente.',
])
def test_related_mentions_or_different_role_are_not_requirements(text):
    assert not tuple(AcademicRelevance().pertinent_units(QUESTION,text))


def setup_requirements():
    p,s,chunks,d,provider,gate,vectors,embedding,auth,case=setup()
    full=replace(chunks[0],text=PAGE,start=0,end=len(PAGE),section='')
    # Only the heading and start of the first item are in the retrieved chunk.
    cutoff=PAGE.index('docente')
    seed=replace(full,text=PAGE[:cutoff],end=cutoff)
    vectors.items=(Candidate(chunk=seed,similarity=.6607),)
    case.threshold=.60;case.relevance=AcademicRelevance()
    async def continuity(principal,scope,seeds):
        assert principal==p and scope==s
        article=complete_article(seeds[0],((full,len(PAGE)),))
        return requirement_section(seeds[0],article)
    case.continuity=continuity
    provider.output=GeneracionSalida(respuesta='Poseer título docente [F1].',finalizacion='completa')
    return p,s,d,provider,vectors,embedding,case


def test_split_requirements_expand_before_generation_with_correct_page_and_citation():
    p,s,d,provider,vectors,embedding,case=setup_requirements()
    result=asyncio.run(case.execute(p,s.document_id,QUESTION))
    assert result.status=='FUNDAMENTADA' and result.citations[0].chunk.page==7
    source=result.citations[0].chunk
    assert 'Acreditar formación específica.' in source.text
    assert 'Se evalúa el proyecto' not in source.text
    assert source.text==PAGE[source.start:source.end]
    assert source.scope==s and embedding.calls==1
    assert not provider.inputs  # Exact enumeration no longer invokes a generator.


def test_similar_score_without_requirement_heading_abstains():
    p,s,d,provider,vectors,embedding,case=setup_requirements()
    text='Las Coordinaciones de Carreras participan en concursos institucionales.'
    c=replace(vectors.items[0].chunk,text=text,start=0,end=len(text))
    vectors.items=(Candidate(chunk=c,similarity=.99),)
    result=asyncio.run(case.execute(p,s.document_id,QUESTION))
    assert result.status=='SIN_EVIDENCIA' and not result.citations and not provider.inputs


def test_below_threshold_heading_is_not_approved_only_by_role():
    p,s,d,provider,vectors,embedding,case=setup_requirements()
    vectors.items=(replace(vectors.items[0],similarity=.59),)
    assert asyncio.run(case.execute(p,s.document_id,QUESTION)).status=='SIN_EVIDENCIA'
    assert not provider.inputs


def test_wrong_version_is_not_a_requirement_source():
    p,s,d,provider,vectors,embedding,case=setup_requirements()
    c=replace(vectors.items[0].chunk,scope=replace(s,version_id=uuid4()))
    vectors.items=(Candidate(chunk=c,similarity=.9),)
    with pytest.raises(IARespuestaInvalida):asyncio.run(case.execute(p,s.document_id,QUESTION))
    assert not provider.inputs


def test_unauthorized_user_cannot_retrieve_requirements():
    p,s,d,provider,vectors,embedding,case=setup_requirements()
    with pytest.raises(PermissionError):
        asyncio.run(case.execute(replace(p,usuario_id=uuid4()),s.document_id,QUESTION))
    assert not embedding.calls and not provider.inputs
