import asyncio
from datetime import datetime, timezone
from dataclasses import replace
from uuid import UUID, uuid4
import pytest

from app.application.agent.context import conversation_memory_reference, resolve_conversation_memory
from app.application.agent.conversations import Conversations
from app.application.auth.exceptions import PermisoDenegado
from app.application.rag.structured_output import Claim, StructuredGeneration, supported_text
from app.application.rag.relevance import AcademicRelevance
from tests.rag.test_agent import fixture
from tests.rag.test_evidence_memory_12d import evidence
from tests.rag.test_tools_memory import MemoryConversations


QUERIES=(
    '¿De qué te estuve preguntando?',
    '¿Sobre qué te estuve preguntando?',
    '¿Sobre qué te pregunté hoy?',
    'En el día de la fecha, ¿sobre qué te estuve preguntando?',
    '¿Qué temas estuvimos tratando?',
    '¿Qué estuvimos hablando?',
    '¿Cuál fue mi última pregunta?',
    '¿Qué me respondiste anteriormente?',
)


@pytest.mark.parametrize('query',QUERIES)
@pytest.mark.parametrize('status',['SIN_EVIDENCIA','FUNDAMENTADA','ACLARACION'])
def test_functional_queries_bypass_all_providers(query,status):
    p,_,agent,_,direct,_,provider,embedding,_=fixture()
    class NoPlanner:
        async def plan(self,*args):raise AssertionError('No planner for deterministic memory')
    agent.planner=NoPlanner()
    history=({'role':'user','content':'Pregunta sobre el articulo 24','creado_at':datetime.now(timezone.utc)},
             {'role':'assistant','content':'Respuesta guardada','status':status,'strategy':'RAG','creado_at':datetime.now(timezone.utc)})
    assert conversation_memory_reference(query)
    result=asyncio.run(agent.execute(p,query,history=history))
    assert result.status=='GENERADA' and not result.citations
    assert ('Respuesta guardada' if 'respondiste' in query else 'articulo 24') in result.answer
    assert not direct.calls and not provider.inputs and not embedding.calls


def test_today_uses_buenos_aires_calendar_not_utc_or_position():
    # At 02:00 UTC on Nov 12, Buenos Aires is still Nov 11.
    now=datetime(2026,11,12,2,tzinfo=timezone.utc)
    h=({'role':'user','content':'Yesterday local','creado_at':'2026-11-11T02:00:00Z'},
       {'role':'user','content':'Today local','creado_at':'2026-11-12T01:00:00Z'})
    answer=resolve_conversation_memory('Sobre que te pregunte hoy',h,now=now)
    assert 'Today local' in answer and 'Yesterday local' not in answer


@pytest.mark.parametrize('stamp',[None,'2026-11-11T10:00:00','invalid'])
def test_missing_timestamps_never_claim_today(stamp):
    answer=resolve_conversation_memory('Sobre que te pregunte hoy',({'role':'user','content':'Unknown day','creado_at':stamp},))
    assert 'No puedo verificar' in answer and 'Unknown day' not in answer


def test_topics_uses_user_turns_only_and_limits_available_history():
    h=tuple(m for i in range(70) for m in (
        {'role':'user','content':f'Pregunta real {i}'},
        {'role':'assistant','content':'PRIVATE_ASSISTANT_EVIDENCE'}))
    answer=resolve_conversation_memory('Que temas estuvimos tratando',h)
    assert 'Pregunta real 69' in answer and 'Pregunta real 59' not in answer
    assert 'PRIVATE_ASSISTANT' not in answer
    assert resolve_conversation_memory('Que temas estuvimos tratando',()) is None
    long=({'role':'user','content':'x'*1000},)*4
    assert len(resolve_conversation_memory('Que temas estuvimos tratando',long))<=3000


def test_topics_service_keeps_conversations_and_users_isolated():
    async def run():
        p,_,agent,*_=fixture()
        repo=MemoryConversations();service=Conversations(authorizer=agent.authorizer,repository=repo,agent=agent)
        a=UUID((await service.create(p))['id']);b=UUID((await service.create(p))['id'])
        repo.rows[a]=[{'role':'user','content':'Pregunta propia articulo 24','strategy':'RAG'}]
        result=await service.turn(p,a,uuid4(),'De que te estuve preguntando','AUTO',None)
        assert 'articulo 24' in result['resultado']['respuesta']
        empty=await service.turn(p,b,uuid4(),'De que te estuve preguntando','AUTO',None)
        assert empty['resultado']['estado']=='ACLARACION'
        with pytest.raises(PermisoDenegado):
            await service.turn(replace(p,usuario_id=uuid4()),a,uuid4(),'De que te estuve preguntando','AUTO',None)
    asyncio.run(run())


def test_legitimate_partial_rejects_inventions_without_dropping_valid_claim(caplog):
    claims=(Claim('El artículo 24 establece que la asistencia es obligatoria.',('F1',)),
            Claim('El Rector concede becas.',('F1',)),Claim('La asistencia es del 80 por ciento.',('F1',)))
    output,partial=supported_text(StructuredGeneration(claims),'Articulo 24',evidence(),AcademicRelevance())
    assert partial and 'asistencia es obligatoria' in output.respuesta and '[F1]' in output.respuesta
    assert 'becas' not in output.respuesta and '80' not in output.respuesta
    assert 'generated=3 accepted=1 rejected=2' in caplog.text
    assert 'becas' not in caplog.text


def test_synthetic_false_rejection_fixed_without_weakening_predicate():
    claims=(Claim('El artículo 24 establece que la asistencia es obligatoria.',('F1',)),
            Claim('Según el artículo 24, la asistencia es obligatoria.',('F1',)))
    output,partial=supported_text(StructuredGeneration(claims),'Articulo 24',evidence(),AcademicRelevance())
    assert not partial and output.respuesta.count('[F1]')==2
