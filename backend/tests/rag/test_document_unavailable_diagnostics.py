import asyncio
import pytest
from app.application.agent.planning import DocumentProposal
from app.application.ia.exceptions import IANoDisponible
from tests.rag.test_agent import fixture

@pytest.mark.parametrize('kind',['authorized','unauthorized','absent','title_mismatch','not_selected','postgres','jina'])
def test_boundary(kind,caplog):
 async def run():
  p,s,agent,catalog,direct,skills,provider,embedding,case=fixture()
  if kind in ('unauthorized','absent'):catalog.empty=True
  if kind=='postgres':
   async def fail(principal):raise IANoDisponible()
   catalog.list_documents=fail
  class Planner:
   async def plan(self,payload):
    return DocumentProposal.model_validate({'accion':'consultar_documentos_academicos','argumentos':{'documento_id':str(s.document_id) if kind not in ('unauthorized','absent','not_selected') else None,'documento_solicitado':'Otro documento' if kind=='title_mismatch' else None,'consulta':'Regularidad curricular'}})
  agent.planner=Planner()
  if kind=='jina':
   async def fail(*args,**kwargs):raise IANoDisponible()
   embedding.embed_query=fail
  if kind in ('postgres','jina'):
   with pytest.raises(IANoDisponible):await agent.execute(p,'Regularidad curricular')
   assert 'kind=document_unavailable' not in caplog.text
   return
  result=await agent.execute(p,'Regularidad curricular')
  if kind=='authorized':
   assert result.status=='FUNDAMENTADA' and result.citations[0].chunk.page==7
   assert embedding.calls==1
  else:
   assert result.status=='SIN_EVIDENCIA' and not result.citations and embedding.calls==0 and provider.inputs==[]
   reason={'unauthorized':'empty_authorized_catalog','absent':'empty_authorized_catalog','title_mismatch':'requested_title_mismatch','not_selected':'planner_document_not_selected'}[kind]
   assert 'reason='+reason in caplog.text
  assert direct.calls==[]
 asyncio.run(run())
