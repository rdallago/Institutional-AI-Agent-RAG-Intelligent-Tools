import asyncio
from dataclasses import replace
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.application.ia.exceptions import IARespuestaInvalida, IANoDisponible
from app.application.rag.core import build_context, resolve_citations
from app.application.rag.functions import (bind_functions, functions_target,
    literal_functions, resolve_functions)
from app.infrastructure.rag.conversations import message_record, restore_record, EXTENDED_RECORD
from tests.rag.test_core import setup, Counter

QUESTION = '¿Cuáles son las funciones del Director?'


def pages(long=False):
    extra = ' Texto documental ficticio.' * (80 if long else 1)
    return ((1,'REGLAMENTO INSTITUCIONAL\nArticulo 8. Funciones del Director.\n'
             'a. Supervisar tareas ficticias.'+extra+'\nb. Iniciar actividades'),
            (2,' ficticias con el equipo.\nc. Mantener el registro.'+extra),
            (3,' Continuación del registro.\nd. Comunicar resultados.\nArticulo 9. Otro asunto.'))


def resolved(scope,long=False):
    return bind_functions(resolve_functions(pages(long),scope,QUESTION,complete_document=True))


def test_complete_functions_preserve_every_page_and_continuation():
    _,s,*_=setup();r=resolved(s)
    answer,evidence=literal_functions(QUESTION,r.chunks,s)
    assert len(evidence)==3
    assert [(x.citation,x.chunk.page) for x in resolve_citations(answer,evidence)]==[('F1',1),('F2',2),('F3',3)]
    for c in r.chunks:
        assert c.text in answer
        assert dict(pages())[c.page][c.start:c.end]==c.text
    assert 'Otro asunto' not in answer


def test_budget_failure_reproduced_and_literal_route_returns_complete_long_answer():
    p,s,_,docs,provider,_,vectors,embedding,auth,case=setup();r=resolved(s,True)
    context=build_context(QUESTION,r.chunks,Counter())
    assert context is None or tuple(e.chunk for e in context.evidence)!=r.chunks
    async def resolver(principal,scope,question):
        assert principal==p and scope==s
        return r
    vectors.resolve_functions=resolver
    result=asyncio.run(case.execute(p,s.document_id,QUESTION))
    assert result.status=='FUNDAMENTADA' and len(result.answer)>4096
    assert len(result.citations)==3 and not provider.inputs and embedding.calls==0
    assert docs.calls==2 and auth.calls==2


@pytest.mark.parametrize('change',['omission','invented','page','version','document','link','last_page'])
def test_missing_or_altered_function_is_rejected(change):
    _,s,*_=setup();r=resolved(s);chunks=list(r.chunks)
    if change=='omission':chunks[0]=replace(chunks[0],text=chunks[0].text.replace('Supervisar',''))
    elif change=='invented':chunks[1]=replace(chunks[1],text=chunks[1].text+' Crear becas.')
    elif change=='page':chunks[1]=replace(chunks[1],page=7)
    elif change=='version':chunks[0]=replace(chunks[0],scope=replace(s,version_id=uuid4()))
    elif change=='document':chunks[0]=replace(chunks[0],scope=replace(s,document_id=uuid4()))
    elif change=='link':chunks[0]=replace(chunks[0],article=None)
    else:chunks.pop()
    assert literal_functions(QUESTION,tuple(chunks),s) is None


def test_homonymous_functions_are_not_selected_automatically():
    _,s,*_=setup()
    p=((1,'REGLAMENTO PRIMERO\nArticulo 8. Funciones del Director.\na. Una tarea.\nArticulo 9. Fin.\n'
         'REGLAMENTO SEGUNDO\nArticulo 8. Funciones del Director.\na. Otra tarea.\nArticulo 9. Fin.'),)
    result=resolve_functions(p,s,QUESTION,complete_document=True)
    assert not result.chunks and result.reason=='ambiguous'


def test_small_closed_subsection_of_extensive_article():
    _,s,*_=setup()
    text=('REGLAMENTO INSTITUCIONAL\nArticulo 8. Autoridades.\n'+('Antecedentes ficticios. '*400)+
          '\nFunciones del Director:\na. Supervisar tareas.\nb. Comunicar resultados.\n'
          'Requisitos del Director:\n- Título ficticio.\nArticulo 9. Otro asunto.')
    r=bind_functions(resolve_functions(((1,text),),s,QUESTION,complete_document=True))
    output=literal_functions(QUESTION,r.chunks,s)
    assert output and 'Supervisar tareas.' in output[0]
    assert 'Antecedentes' not in output[0] and 'Título' not in output[0]


def test_colon_inside_a_function_does_not_close_the_list():
    _,s,*_=setup()
    text=('Articulo 8. Autoridades.\nFunciones del Director:\na. Comunicar resultados.\n'
          'Detalle:\nComunicación institucional ficticia.\nb. Supervisar tareas.\n'
          'Requisitos del Director:\n- Formación ficticia.\nArticulo 9. Otro asunto.')
    r=bind_functions(resolve_functions(((1,text),),s,QUESTION,complete_document=True))
    answer,_=literal_functions(QUESTION,r.chunks,s)
    assert 'b. Supervisar tareas.' in answer and 'Detalle:' in answer
    assert 'Formación ficticia' not in answer


@pytest.mark.parametrize('question',['Explica las funciones del Director',
    '¿Qué establece el artículo 24?', '¿Qué es un director?',
    '¿Cuáles son los requisitos para concursos de Coordinaciones de Carreras?',
    '¿Cuáles son las funciones del Subdirector?', '¿Cómo está el clima hoy?'])
def test_other_sections_or_intents_do_not_receive_director_functions(question):
    _,s,*_=setup();r=resolved(s)
    assert literal_functions(question,r.chunks,s) is None


def test_gaps_and_unproven_end_fail_closed():
    _,s,*_=setup()
    assert not resolve_functions(pages()[:-1],s,QUESTION).chunks
    assert not resolve_functions((pages()[0],pages()[2]),s,QUESTION,complete_document=True).chunks


def test_acl_denied_before_read_and_scope_changed_after_read():
    p,s,_,docs,provider,_,vectors,embedding,auth,case=setup()
    docs.revoked=True
    with pytest.raises(PermissionError):asyncio.run(case.execute(p,s.document_id,QUESTION))
    docs.revoked=False
    async def resolver(*args):
        docs.scope=replace(s,version_id=uuid4())
        return resolved(s)
    vectors.resolve_functions=resolver
    with pytest.raises(IANoDisponible):asyncio.run(case.execute(p,s.document_id,QUESTION))
    assert not provider.inputs and embedding.calls==0


def test_extended_record_uses_atomic_result_and_restores_without_truncation():
    _,s,*_=setup();answer,evidence=literal_functions(QUESTION,resolved(s,True).chunks,s)
    result=SimpleNamespace(answer=answer,strategy='RAG',status='FUNDAMENTADA',
                           finalization='completa',citations=evidence)
    public={'respuesta':answer,'estrategia':'RAG','estado':'FUNDAMENTADA','finalizacion':'completa'}
    assert message_record(result,{'resultado':public})==EXTENDED_RECORD
    row={'role':'assistant','content':EXTENDED_RECORD,'strategy':'RAG','status':'FUNDAMENTADA',
         'references':[{'id':'F1'}],'turn_result':{'resultado':public}}
    assert restore_record(row)['content']==answer and 'turn_result' not in restore_record(row)
    with pytest.raises(IARespuestaInvalida):restore_record(dict(row,turn_result=None))
    with pytest.raises(IARespuestaInvalida):message_record(result,{'resultado':{}})
    with pytest.raises(IARespuestaInvalida):message_record(replace_namespace(result,strategy='LLM_DIRECTO'),{'resultado':public})


def replace_namespace(value,**kwargs):
    return SimpleNamespace(**(vars(value)|kwargs))


def test_repository_reads_verified_pages_with_acl_and_rechecks_scope():
    import hashlib
    from app.infrastructure.rag.postgres import PostgresRAG
    _,s,*_=setup();store=PostgresRAG(None);store.space=s.space
    calls=[]
    async def active(*args):calls.append('acl');return s
    def read(query,params):
        assert 'p.hash_texto' in query and 'd.activa_version_id=v.id' in query
        assert 'd.propietario_id=:actor' in query and params['version']==s.version_id
        return [dict(pagina_pdf=n,texto_extraido=t,hash_texto=hashlib.sha256(t.encode()).hexdigest(),
                     total_pages=3) for n,t in pages()]
    store.require_active=active;store.read=read
    result=asyncio.run(store.resolve_functions(SimpleNamespace(usuario_id=uuid4()),s,QUESTION))
    assert literal_functions(QUESTION,result.chunks,s) and calls==['acl','acl']
    def corrupt(query,params):
        rows=read(query,params);rows[0]['hash_texto']='0'*64;return rows
    store.read=corrupt
    with pytest.raises(IARespuestaInvalida):
        asyncio.run(store.resolve_functions(SimpleNamespace(usuario_id=uuid4()),s,QUESTION))


def test_fake_sql_persistence_keeps_constraints_and_full_result_atomically():
    import json
    from app.infrastructure.rag.conversations import PostgresConversations
    _,s,*_=setup();answer,evidence=literal_functions(QUESTION,resolved(s,True).chunks,s)
    result=SimpleNamespace(answer=answer,strategy='RAG',status='FUNDAMENTADA',
        finalization='completa',citations=evidence,tool=None,tool_context={})
    payload={'resultado':{'respuesta':answer}}
    operations=[]
    class Connection:
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def execute(self,query,params):
            operations.append((str(query),params));return SimpleNamespace(rowcount=1)
    store=PostgresConversations(SimpleNamespace(begin=lambda:Connection()))
    store.owned=lambda *args,**kwargs:None
    asyncio.run(store.complete(None,uuid4(),uuid4(),QUESTION,result,[],payload))
    inserts=[p for q,p in operations if 'INSERT INTO public.agent_mensajes' in q]
    assert len(inserts)==2 and inserts[1]['t']==EXTENDED_RECORD
    assert all(len(p['t'])<=4096 and len(p['t'].encode())<=16384 for p in inserts)
    assert json.loads(operations[0][1]['p'])['resultado']['respuesta']==answer


def test_four_pages_and_unbounded_output_are_explicitly_refused():
    _,s,*_=setup()
    p=list(pages());p[2]=(3,' Continuación.');p.append((4,'e. Final.\nArticulo 9. Otro asunto.'))
    r=bind_functions(resolve_functions(tuple(p),s,QUESTION,complete_document=True))
    assert literal_functions(QUESTION,r.chunks,s) is None
    p=((1,'Articulo 8. Funciones del Director.\na. '+('Texto ficticio. '*900)+'\nArticulo 9. Fin.'),)
    r=bind_functions(resolve_functions(p,s,QUESTION,complete_document=True))
    assert literal_functions(QUESTION,r.chunks,s) is None


def test_wrong_normative_section_cannot_reuse_proof():
    _,s,*_=setup();r=resolved(s)
    link=replace(r.chunks[0].article,section='Otra norma')
    assert literal_functions(QUESTION,tuple(replace(c,article=link) for c in r.chunks),s) is None


def test_http_returns_full_page_cited_literal_without_provider():
    from fastapi.testclient import TestClient
    from tests.ia.test_http_ia import setup_app
    from app.application.agent.context import AgentResult
    app,_,_,_,headers,state=setup_app()
    _,s,*_=setup();answer,evidence=literal_functions(QUESTION,resolved(s,True).chunks,s)
    async def execute(*args,**kwargs):
        return AgentResult(strategy='RAG',status='FUNDAMENTADA',answer=answer,
                           citations=evidence,finalization='completa')
    with TestClient(app) as client:
        app.state.ia_agent=SimpleNamespace(execute=execute)
        response=client.post('/api/v1/ia/respuestas',headers=headers,
            json={'prompt':QUESTION,'modo':'RAG','documento_id':str(s.document_id)})
        assert response.status_code==200 and response.json()['respuesta']==answer
        assert response.json()['fuentes']==[{'id':f'F{i+1}','pagina':i+1} for i in range(3)]
        assert not state['provider'].inputs
