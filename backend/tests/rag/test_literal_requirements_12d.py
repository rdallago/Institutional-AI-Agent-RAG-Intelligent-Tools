import asyncio
from dataclasses import replace
from uuid import uuid4
import pytest

from app.application.rag.continuity import complete_article, requirement_section
from app.application.rag.dto import Chunk, Scope, Evidence, Candidate
from app.application.rag.extractive import enumeration_target, literal_requirements
from tests.rag.test_core import setup

QUESTION='¿Cuáles son los requisitos para acceder a concursos de Coordinaciones de Carreras?'
PAGE=('Articulo 52. Coordinaciones de Carrera.\nRequisitos del Coordinador de Carrera\n'
      '- Poseer título docente;\n- Acreditar formación específica.\n- Presentar proyecto institucional.\n'
      'Evaluación del proyecto:\nSe evalúa el proyecto.\nArticulo 53. Funciones distintas.')


def verified(scope):
    full=Chunk(id='full',scope=scope,page=33,start=0,end=len(PAGE),text=PAGE,section='')
    seed=replace(full,text=PAGE[:PAGE.index('docente')],end=PAGE.index('docente'))
    article=complete_article(seed,((full,len(PAGE)),))
    return seed,requirement_section(seed,article)[0]


def test_three_literal_items_preserve_offsets_page_scope_and_reference():
    _,scope,*_=setup();_,chunk=verified(scope)
    output=literal_requirements(QUESTION,(Evidence(citation='F1',chunk=chunk),),scope)
    assert output and output.count('[F1]')==3 and chunk.page==33
    assert len(chunk.requirements.item_spans)==3
    for start,end in chunk.requirements.item_spans:
        original=PAGE[start:end].rstrip()
        assert original in output and chunk.text[start-chunk.start:end-chunk.start]==PAGE[start:end]
    assert 'Se evalúa el proyecto' not in output and 'Funciones distintas' not in output


@pytest.mark.parametrize('kind',['invented','incomplete','missing_proof','version','document','page'])
def test_unverified_lists_cannot_be_transcribed(kind):
    _,scope,*_=setup();_,chunk=verified(scope)
    if kind=='invented':chunk=replace(chunk,text=chunk.text.replace('docente','inventado'))
    elif kind=='incomplete':chunk=replace(chunk,text=chunk.text[:chunk.text.index('- Presentar')])
    elif kind=='missing_proof':chunk=replace(chunk,requirements=None)
    elif kind=='version':chunk=replace(chunk,scope=replace(scope,version_id=uuid4()))
    elif kind=='document':chunk=replace(chunk,scope=replace(scope,document_id=uuid4()))
    else:chunk=replace(chunk,page=34)
    assert literal_requirements(QUESTION,(Evidence(citation='F1',chunk=chunk),),scope) is None


@pytest.mark.parametrize('question',['Explica los requisitos para concursos de Coordinaciones de Carreras',
    'Explícame los requisitos para concursos de Coordinaciones de Carreras',
    '¿Qué significan los requisitos para concursos de Coordinaciones de Carreras?',
    '¿Qué establece el artículo 24?', '¿Qué establece el artículo 52?', '¿Qué es una API REST?',
    'Compara requisitos para concursos de Coordinaciones de Carreras'])
def test_other_questions_do_not_enter_literal_enumeration(question):
    assert enumeration_target(question) is None


def test_use_case_returns_complete_three_item_list_without_llm_and_rechecks_acl():
    p,s,_,documents,provider,gate,vectors,embedding,auth,case=setup()
    seed,chunk=verified(s)
    vectors.items=(Candidate(chunk=seed,similarity=.6607),)
    case.threshold=.6
    from app.application.rag.relevance import AcademicRelevance
    case.relevance=AcademicRelevance()
    async def continuity(*args):return (chunk,)
    case.continuity=continuity
    result=asyncio.run(case.execute(p,s.document_id,QUESTION))
    assert result.status=='FUNDAMENTADA' and result.answer.count('[F1]')==3
    assert result.citations[0].chunk.page==33 and not provider.inputs and embedding.calls==1
    assert documents.calls>=2


def test_incomplete_list_returns_no_evidence_without_generator():
    p,s,_,documents,provider,gate,vectors,embedding,auth,case=setup()
    seed,chunk=verified(s)
    vectors.items=(Candidate(chunk=seed,similarity=.6607),);case.threshold=.6
    from app.application.rag.relevance import AcademicRelevance
    case.relevance=AcademicRelevance()
    async def continuity(*args):return (replace(chunk,requirements=None),)
    case.continuity=continuity
    result=asyncio.run(case.execute(p,s.document_id,QUESTION))
    assert result.status=='SIN_EVIDENCIA' and not result.citations and not provider.inputs
