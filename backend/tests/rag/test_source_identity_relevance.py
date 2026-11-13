from dataclasses import replace
from app.application.rag.relevance import AcademicRelevance
from app.application.rag.dto import Evidence
from app.infrastructure.rag.postgres import verified_cover_titles
from app.application.agent.router import AgentRouter
from tests.rag.test_agent import fixture

FIRST='¿Cuáles son las funciones del Rectorado según el Reglamento Orgánico Marco?'
SECOND='¿Cuáles son los requisitos para acceder al concurso de coordinación de carrera?'

def test_source_qualifier_is_not_part_of_institutional_subject():
    policy=AcademicRelevance()
    source='Del Rectorado: Es la unidad de conducción de la gestión institucional.'
    assert tuple(policy.pertinent_units(FIRST,source))
    assert not tuple(policy.pertinent_units(FIRST,'Funciones del Rector: dirige la institución.'))
    assert not tuple(policy.pertinent_units(FIRST,'Integra el Rectorado y asiste al Rector en sus funciones.'))

def test_role_morphology_and_requirement_heading_not_other_competitions():
    policy=AcademicRelevance()
    source='Texto anterior\nRequisitos del Coordinador de Carrera\n-Titulo Docente de Nivel Superior\n'
    assert tuple(policy.pertinent_units(SECOND,source))
    assert not tuple(policy.pertinent_units(SECOND,source.replace('de Carrera','de Area')))
    assert not tuple(policy.pertinent_units(SECOND,'Concurso docente: se requiere título y experiencia en la carrera.'))
    p,s,a,c,d,k,provider,e,case=fixture()
    chunk=replace(case.vectors.items[0].chunk,text=source,end=len(source))
    assert policy.supports_answer(SECOND,'Titulo Docente de Nivel Superior [F1].',(Evidence(citation='F1',chunk=chunk),))
    assert not policy.supports_answer(SECOND,'Se requiere doctorado [F1].',(Evidence(citation='F1',chunk=chunk),))

def test_verified_title_is_not_a_global_equivalence_between_regulations():
    cover='ANTEPROYECTO REGLAMENTO\nORGANICO MARCO PARA INSTITUTOS SUPERIORES'
    aliases=verified_cover_titles(cover)
    assert aliases==('REGLAMENTO ORGANICO MARCO',)
    router=AgentRouter()
    ordinary={'id':'a','titulo':'Reglamento académico'}
    assert router.explicit_document(FIRST,[ordinary]) is None
    assert router.explicit_document(FIRST,[{**ordinary,'aliases':aliases}]) is not None
    assert verified_cover_titles('No contiene aquel título.')==()
