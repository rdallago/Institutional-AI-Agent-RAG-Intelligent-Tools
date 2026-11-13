"""Solo paginas ficticias, vectores sinteticos y dobles sin servicios."""
import asyncio
from dataclasses import replace
from uuid import uuid4

import pytest

from app.application.auth.service import Principal
from app.application.ia.dto import GeneracionSalida
from app.application.ia.exceptions import IARespuestaInvalida, IAOcupada, IATiempoAgotado, PromptInvalido
from app.application.rag.core import (ChunkPolicy, build_context, prepare_pages,
    resolve_citations, select_evidence, validate_vector)
from app.application.rag.dto import Candidate, Page, Scope, Section
from app.application.rag.use_cases import PrepararVersion, ResponderConDocumento
from app.infrastructure.llm.admission import MemoryGenerationAdmission
from app.infrastructure.llm.work_gate import MemoryModelWorkGate


class Counter:
    # Tokenizador ficticio; NO representa tokens reales de Qwen/Nomic.
    identity = 'synthetic-codepoints-v1'
    def count(self, text): return len(text)


def fixture():
    principal = Principal(usuario_id=uuid4(), sesion_id=uuid4())
    scope = Scope(document_id=uuid4(), version_id=uuid4(), space='nomic-embed-text:digest-fixture:768')
    _, chunks = prepare_pages((Page(number=7, text='Regla ficticia de examen.'),), scope, Counter())
    return principal, scope, chunks


class Authorizer:
    def __init__(self): self.calls = 0
    async def require_normal(self, principal): self.calls += 1


class Documents:
    def __init__(self, principal, scope):
        self.owner, self.scope = principal.usuario_id, scope
        self.calls, self.saved = 0, {}
        self.revoked = False
    async def require_active(self, principal, document_id):
        self.calls += 1
        if self.revoked or principal.usuario_id != self.owner or document_id != self.scope.document_id:
            raise PermissionError('Acceso denegado.')
        return self.scope
    async def put_prepared_once(self, principal, scope, key, chunks):
        await self.require_active(principal, scope.document_id)
        self.saved.setdefault((scope, key), chunks)
        return key


class Embeddings:
    def __init__(self): self.calls = 0
    async def embed_query(self, text, *, space):
        self.calls += 1
        return (1.0,) + (0.0,) * 767


class Vectors:
    def __init__(self, principal, scope, chunks):
        self.owner, self.scope = principal.usuario_id, scope
        self.items = tuple(Candidate(chunk=c, similarity=0.9) for c in chunks)
    async def search(self, principal, scope, vector, *, limit):
        assert principal.usuario_id == self.owner and scope == self.scope
        return self.items[:limit]


class Provider:
    def __init__(self):
        self.inputs = []
        self.output = GeneracionSalida(respuesta='Norma ficticia [F1].', finalizacion='completa')
        self.error = None
        self.started, self.resume = asyncio.Event(), asyncio.Event()
        self.blocked = False
        self.hook = None
    async def generate_grounded(self, input):
        self.inputs.append(input)
        self.started.set()
        if self.blocked: await self.resume.wait()
        if self.error: raise self.error
        if self.hook: self.hook()
        return self.output


def setup():
    p, scope, chunks = fixture()
    documents, provider, gate = Documents(p, scope), Provider(), MemoryModelWorkGate()
    vectors, embeddings, authorizer = Vectors(p, scope, chunks), Embeddings(), Authorizer()
    case = ResponderConDocumento(authorizer=authorizer, documents=documents,
        vectors=vectors, embeddings=embeddings, provider=provider, counter=Counter(),
        gate=gate, admission=MemoryGenerationAdmission(), threshold=0.7)
    return p, scope, chunks, documents, provider, gate, vectors, embeddings, authorizer, case


def test_chunk_provenance_sections_overlap_and_idempotency():
    _, scope, _ = fixture()
    text = 'ABC def ghi.\n\nJKL mno pqr.'
    page = Page(number=2, text=text, sections=(Section(start=0, end=14, title='A'),
                                               Section(start=14, end=len(text), title='B')))
    policy = ChunkPolicy(max_tokens=9, overlap_tokens=2)
    first = prepare_pages((page,), scope, Counter(), policy)
    assert first == prepare_pages((page,), scope, Counter(), policy)
    assert first[0] != prepare_pages((replace(page, text=text+'x', sections=()),), scope, Counter(), policy)[0]
    chunks = first[1]
    covered = set()
    for c in chunks:
        assert c.text == text[c.start:c.end] and len(c.text) <= 9 and c.page == 2
        assert c.end <= 14 if c.section == 'A' else c.start >= 14
        covered.update(range(c.start, c.end))
    assert all(i in covered for i, char in enumerate(text) if not char.isspace())
    assert any(a.end > b.start for a,b in zip(chunks,chunks[1:]) if a.section == b.section)


@pytest.mark.parametrize('page', [Page(number=0,text='x'), Page(number=1,text='\ud800'),
    Page(number=1,text='a\x00'), Page(number=1,text='abc',sections=(Section(start=1,end=3,title='x'),))])
def test_invalid_pages(page):
    _, scope, _ = fixture()
    with pytest.raises(IARespuestaInvalida): prepare_pages((page,),scope,Counter())


@pytest.mark.parametrize('max_tokens,overlap', [(0,0),(401,50),(10,10),(10,-1),(True,0)])
def test_invalid_policy(max_tokens, overlap):
    with pytest.raises(ValueError): ChunkPolicy(max_tokens=max_tokens,overlap_tokens=overlap)


@pytest.mark.parametrize('vector', [(),(0.,)*768,(float('nan'),)*768,(True,)*768,(1e308,)*768])
def test_invalid_vectors(vector):
    with pytest.raises(IARespuestaInvalida): validate_vector(vector)


def test_selection_and_context_bounds():
    _,scope,chunks=fixture()
    c=chunks[0]
    candidates=(Candidate(chunk=c,similarity=.9),Candidate(chunk=c,similarity=.8))
    assert select_evidence(candidates,scope,threshold=.7)==(c,)
    assert select_evidence(candidates,scope,threshold=.95)==()
    large=replace(c,text='x'*4000,end=4000)
    input=build_context('Pregunta', (large,c),Counter())
    assert len(input.evidence)==1 and input.evidence[0].chunk==c
    assert Counter().count(input.rendered)+256+512<=4096
    assert build_context('Pregunta',(large,),Counter()) is None
    with pytest.raises(IARespuestaInvalida): build_context('x'*4000,(),Counter())


@pytest.mark.parametrize('answer', ['Sin citas','Texto [F99]','Texto [Fabc]','Texto [F1] [F2]'])
def test_invalid_citations(answer):
    _,_,chunks=fixture()
    input=build_context('q',chunks,Counter())
    with pytest.raises(IARespuestaInvalida): resolve_citations(answer,input.evidence)


def test_success_and_repr_privacy(capsys):
    p,s,chunks,d,provider,g,v,e,a,case=setup()
    result=asyncio.run(case.execute(p,s.document_id,'Pregunta secreta'))
    assert result.status=='FUNDAMENTADA' and result.strategy=='RAG'
    assert result.citations[0].chunk.page==7 and a.calls==2 and d.calls==2
    assert 'Pregunta secreta' not in repr(provider.inputs[0])
    assert chunks[0].text not in repr(chunks[0]) and result.answer not in repr(result)
    assert capsys.readouterr().out==''
    g.try_acquire().release()


def test_abstention_no_generator():
    p,s,_,d,provider,g,v,e,a,case=setup()
    v.items=()
    result=asyncio.run(case.execute(p,s.document_id,'Pregunta'))
    assert result.status=='SIN_EVIDENCIA' and not provider.inputs and not result.citations
    assert a.calls==2 and d.calls==2


def test_user_isolation_before_models():
    p,s,_,d,provider,g,v,e,a,case=setup()
    other=Principal(usuario_id=uuid4(),sesion_id=uuid4())
    with pytest.raises(PermissionError): asyncio.run(case.execute(other,s.document_id,'Pregunta'))
    assert not e.calls and not provider.inputs


def test_untrusted_cross_scope_rejected():
    p,s,chunks,d,provider,g,v,e,a,case=setup()
    v.items=(Candidate(chunk=replace(chunks[0],scope=replace(s,version_id=uuid4())),similarity=.99),)
    with pytest.raises(IARespuestaInvalida): asyncio.run(case.execute(p,s.document_id,'Pregunta'))
    assert not provider.inputs


def test_revocation_during_generation():
    p,s,_,d,provider,g,v,e,a,case=setup()
    provider.hook=lambda: setattr(d,'revoked',True)
    with pytest.raises(PermissionError): asyncio.run(case.execute(p,s.document_id,'Pregunta'))
    g.try_acquire().release()


@pytest.mark.parametrize('error,expected',[(TimeoutError('secret'),IATiempoAgotado),
    (RuntimeError('secret'),IARespuestaInvalida)])
def test_error_sanitized_and_gate_released(error,expected):
    p,s,_,d,provider,g,v,e,a,case=setup()
    provider.error=error
    with pytest.raises(expected) as captured: asyncio.run(case.execute(p,s.document_id,'Pregunta'))
    assert 'secret' not in str(captured.value)
    g.try_acquire().release()


def test_cancellation_and_concurrent_work():
    async def scenario():
        p,s,_,d,provider,g,v,e,a,case=setup()
        provider.blocked=True
        task=asyncio.create_task(case.execute(p,s.document_id,'Pregunta'))
        await provider.started.wait()
        with pytest.raises(IAOcupada): g.try_acquire()
        task.cancel()
        with pytest.raises(asyncio.CancelledError): await task
        old=g.try_acquire();old.release()
        current=g.try_acquire();old.release()
        with pytest.raises(IAOcupada): g.try_acquire()
        current.release()
    asyncio.run(scenario())


def test_preparation_idempotent_and_scoped():
    p,s,_,d,provider,g,v,e,a,case=setup()
    prepare=PrepararVersion(authorizer=a,documents=d,counter=Counter(),policy=ChunkPolicy())
    pages=(Page(number=1,text='Texto sintetico.'),)
    key=asyncio.run(prepare.execute(p,s.document_id,pages))
    assert key==asyncio.run(prepare.execute(p,s.document_id,pages)) and len(d.saved)==1
    assert key!=asyncio.run(prepare.execute(p,s.document_id,(Page(number=1,text='Version nueva.'),)))
    assert len(d.saved)==2


def test_existing_prompt_limits_preserved():
    p,s,_,d,provider,g,v,e,a,case=setup()
    with pytest.raises(PromptInvalido): asyncio.run(case.execute(p,s.document_id,'a'*1001))
    assert not e.calls


@pytest.mark.parametrize('finish',['completa','limite'])
def test_finalizations_preserved(finish):
    p,s,_,d,provider,g,v,e,a,case=setup()
    provider.output=GeneracionSalida(respuesta='Norma [F1].',finalizacion=finish)
    assert asyncio.run(case.execute(p,s.document_id,'Pregunta')).finalization==finish


@pytest.mark.parametrize('answer',['Texto [F1] [F','Texto [F1] [F2','Texto [F1] [F\n2]'])
def test_malformed_reference_alongside_valid_rejected(answer):
    _,_,chunks=fixture()
    with pytest.raises(IARespuestaInvalida):
        resolve_citations(answer,build_context('q',chunks,Counter()).evidence)


def test_deadline_releases_gate():
    p,s,_,d,provider,g,v,e,a,case=setup()
    provider.blocked=True
    case.timeout=.001
    with pytest.raises(IATiempoAgotado): asyncio.run(case.execute(p,s.document_id,'Pregunta'))
    g.try_acquire().release()


def test_admission_failure_releases_gate():
    p,s,_,d,provider,g,v,e,a,case=setup()
    lease=case.admission.try_acquire(p)
    with pytest.raises(IAOcupada): asyncio.run(case.execute(p,s.document_id,'Pregunta'))
    assert not e.calls
    g.try_acquire().release()
    lease.release()


def test_vector_validation_before_search():
    p,s,_,d,provider,g,v,e,a,case=setup()
    async def bad(text,*,space): return (1.0,)
    e.embed_query=bad
    with pytest.raises(IARespuestaInvalida): asyncio.run(case.execute(p,s.document_id,'Pregunta'))
    assert not provider.inputs


def test_document_version_changes_before_delivery():
    p,s,_,d,provider,g,v,e,a,case=setup()
    provider.hook=lambda:setattr(d,'scope',replace(s,version_id=uuid4()))
    from app.application.ia.exceptions import IANoDisponible
    with pytest.raises(IANoDisponible): asyncio.run(case.execute(p,s.document_id,'Pregunta'))
    g.try_acquire().release()


def test_generator_explicit_abstention():
    p,s,_,d,provider,g,v,e,a,case=setup()
    provider.output=GeneracionSalida(respuesta='SIN_EVIDENCIA',finalizacion='completa')
    result=asyncio.run(case.execute(p,s.document_id,'Pregunta'))
    assert result.status=='SIN_EVIDENCIA' and result.finalization is None and result.citations==()
    assert a.calls==2


def test_overlap_never_repeats_a_paragraph_end():
    _,scope,_=fixture()
    page=Page(number=1,text='Primer parrafo.\n\n'+'Palabras de continuidad '*40)
    _,chunks=prepare_pages((page,),scope,Counter(),ChunkPolicy(max_tokens=80,overlap_tokens=30))
    assert all(a.end<b.end for a,b in zip(chunks,chunks[1:]))
    assert chunks[-1].end==len(page.text)
