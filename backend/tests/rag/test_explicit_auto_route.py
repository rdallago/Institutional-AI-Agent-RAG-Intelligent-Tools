import asyncio
from dataclasses import replace
import pytest
from app.application.agent.planning import validate_proposal
from app.application.agent.context import AgentResult
from app.application.ia.exceptions import IANoDisponible, IARespuestaInvalida, IATiempoAgotado
from tests.rag.test_agent import fixture
from tests.rag.test_semantic_planning import WeatherCapture

QUESTION='¿En el reglamento académico de Institutos Superiores, cuáles son las funciones del Rectorado?'

def test_explicit_document_goes_to_rag_without_planning():
    async def run():
        p,s,agent,catalog,*_=fixture()
        async def listed(principal):
            return [{'id':str(s.document_id),'titulo':'Reglamento académico'}] if principal.usuario_id==catalog.documents.owner else []
        catalog.list_documents=listed
        class NoPlanner:
            async def plan(self,*args):raise AssertionError('Must not plan')
        class RAG:
            async def execute(self,principal,document,question,**kwargs):
                assert principal==p and document==s.document_id and question==QUESTION
                await catalog.require_active(principal,document)
                return AgentResult(strategy='RAG',status='SIN_EVIDENCIA',answer='Sin evidencia en este doble.')
        agent.planner=NoPlanner();agent.rag=RAG()
        result=await agent.execute(p,QUESTION)
        assert result.strategy=='RAG'
        with pytest.raises(PermissionError):  # Excepcion del repositorio doble existente.
            await agent.execute(replace(p,usuario_id=__import__('uuid').uuid4()),QUESTION,mode='RAG',document_id=s.document_id)
    asyncio.run(run())

def test_complete_weather_keeps_tool_without_planning():
    async def run():
        p,s,agent,*_=fixture()
        class NoPlanner:
            async def plan(self,*args):raise AssertionError('Must not plan')
        agent.planner=NoPlanner();agent.weather=WeatherCapture()
        result=await agent.execute(p,'Clima en Goya, Corrientes, Argentina hoy')
        assert result.tool=='consultar_clima' and len(agent.weather.calls)==1
    asyncio.run(run())

def test_ambiguous_still_plans():
    async def run():
        p,s,agent,*_=fixture()
        calls=[]
        class Planner:
            async def plan(self,payload):
                calls.append(payload)
                return validate_proposal('{"accion":"solicitar_aclaracion","argumentos":{"motivo":"intencion"}}')
        agent.planner=Planner()
        result=await agent.execute(p,'¿Cuánto tiempo dura?')
        assert calls and result.status=='ACLARACION'
    asyncio.run(run())

def test_catalog_identity_does_not_replace_unknown_document():
    from app.application.agent.router import AgentRouter
    router=AgentRouter()
    rows=[{'id':'a','titulo':'Reglamento académico'}]
    assert router.explicit_document('Consultar el reglamento orgánico marco',rows) is None
    assert router.explicit_document(QUESTION,[]) is None
    assert router.explicit_document(QUESTION,rows+rows) is None


@pytest.mark.parametrize('failure',[IANoDisponible,IARespuestaInvalida,IATiempoAgotado])
def test_direct_document_rag_failure_is_not_fabricated_evidence(failure):
    async def run():
        p,s,agent,catalog,direct,*_=fixture()
        async def listed(principal):
            return [{'id':str(s.document_id),'titulo':'Reglamento académico'}]
        catalog.list_documents=listed
        class NoPlanner:
            async def plan(self,*args):raise AssertionError('Must not plan')
        class BrokenRAG:
            async def execute(self,*args,**kwargs):raise failure()
        agent.planner=NoPlanner();agent.rag=BrokenRAG()
        with pytest.raises(failure):await agent.execute(p,QUESTION)
        assert direct.calls==[]  # No fallback general ni SIN_EVIDENCIA ante fallo tecnico.
    asyncio.run(run())
