import asyncio
from dataclasses import replace

import pytest

from app.application.auth.exceptions import PermisoDenegado
from app.application.ia.exceptions import IARespuestaInvalida
from app.application.rag.continuity import complete_article
from app.application.rag.dto import Chunk
from app.infrastructure.rag.postgres import ACL, PostgresRAG
from tests.rag.test_agent import fixture


def make(scope, page, value, start=0, end=None):
    end = len(value) if end is None else end
    return Chunk(id=f'{page}:{start}:{end}', scope=scope, page=page,
                 start=start, end=end, text=value[start:end], section='')


def test_whole_article_one_page_stops_at_next_article():
    _, scope, *rest = fixture()
    value='Articulo 24. Del Rectorado: Es la unidad institucional.\nArticulo 25. Composicion.'
    seed=make(scope,11,value,0,40)
    result=complete_article(seed,((make(scope,11,value),len(value)),))
    assert len(result)==1
    assert result[0].text==value[:value.index('Articulo 25')]
    assert result[0].end==len(result[0].text)


def test_page_transition_mid_sentence_and_no_rector_functions():
    _, scope, *_=fixture()
    first='Articulo 24. Del Rectorado: Es responsable de los organos'
    second='colegiados y la articulacion.\nArticulo 25. Composicion.\nArticulo 28. Funciones del Rector.'
    seed=make(scope,11,first,0,38)
    rows=((make(scope,11,first,0,45),len(first)),
          (make(scope,11,first,35),len(first)),
          (make(scope,12,second),len(second)))
    result=complete_article(seed,rows)
    assert [c.page for c in result]==[11,12]
    assert result[0].text==first
    assert result[1].text=='colegiados y la articulacion.\n'
    assert all('Articulo 25' not in c.text and 'Funciones del Rector' not in c.text for c in result)
    assert complete_article(seed,rows+rows)==result


def test_missing_contiguous_chunk_or_article_boundary_does_not_claim_completion():
    _, scope, *_=fixture()
    value='Articulo 24. Del consejo: Es la unidad institucional.'
    seed=make(scope,11,value,0,35)
    assert complete_article(seed,())==()
    assert complete_article(seed,((make(scope,11,value),len(value)),))==()
    assert complete_article(seed,((make(scope,11,value,0,35),len(value)),))==()


def test_scope_and_overlap_integrity():
    _, scope, *_=fixture()
    value='Articulo 24. Del consejo: Es la unidad.\nArticulo 25. Otro.'
    seed=make(scope,11,value,0,35)
    bad=replace(make(scope,11,value),scope=replace(scope,document_id=fixture()[1].document_id))
    with pytest.raises(IARespuestaInvalida):
        complete_article(seed,((bad,len(value)),))
    bad=replace(make(scope,11,value,20),text='x'+value[21:])
    with pytest.raises(IARespuestaInvalida):
        complete_article(seed,((make(scope,11,value,0,30),len(value)),(bad,len(value))))


def test_repository_reuses_acl_and_exact_slice_checks():
    async def run():
        principal,scope,*_=fixture()
        from app.infrastructure.rag.ollama import SPACE
        scope=replace(scope,space=SPACE)
        store=PostgresRAG(None)
        calls=[]
        async def active(p,d):
            assert p==principal and d==scope.document_id
            return scope
        store.require_active=active
        def read(query,params):
            calls.append(query)
            assert ACL in query and 'substring(p.texto_extraido' in query
            assert "v.estado='LISTA'" in query and 'd.activa_version_id=v.id' in query
            assert 'LIMIT 65' in query and params['actor']==principal.usuario_id
            return []
        store.read=read
        assert await store.article_context(principal,scope,(make(scope,11,'Articulo 24. Texto'),))==()
        assert len(calls)==1
        def corrupt(query,params):return [{'intact':False}]
        store.read=corrupt
        with pytest.raises(IARespuestaInvalida):
            await store.article_context(principal,scope,(make(scope,11,'texto'),))
        async def denied(*args):raise PermisoDenegado()
        store.require_active=denied
        with pytest.raises(PermisoDenegado):
            await store.article_context(principal,scope,(make(scope,11,'texto'),))
        assert len(calls)==1
    asyncio.run(run())


def test_insufficient_context_budget_abstains_without_generation():
    async def run():
        principal,scope,*_,case=fixture()
        called=[]
        async def continuity(p,s,seeds):
            called.append(1)
            value='Articulo 24. '+('texto institucional '*300)
            return (make(scope,11,value),)
        case.continuity=continuity
        result=await case.execute(principal,scope.document_id,'regularidad curricular')
        assert called and result.status=='SIN_EVIDENCIA' and not result.citations
        assert not case.provider.inputs
    asyncio.run(run())
