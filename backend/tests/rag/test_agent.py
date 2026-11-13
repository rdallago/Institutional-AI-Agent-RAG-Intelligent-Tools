"""Agente/skill reales con evidencia y modelos ficticios; sin bases externas."""
import asyncio
from dataclasses import replace
from uuid import uuid4

import httpx
import pytest

from app.application.agent.agent import Agent
from app.application.agent.context import AgentContext
from app.application.agent.router import AgentRouter
from app.application.agent.skills.registry import Skill, SkillRegistry
from app.application.ia.dto import GeneracionSalida
from app.application.ia.exceptions import IANoDisponible, IARespuestaInvalida
from app.application.rag.dto import Candidate
from app.application.rag.relevance import AcademicRelevance
from app.infrastructure.rag.skills import PackagedSkillLoader
from app.infrastructure.rag.ollama import GroundedProvider
from tests.rag.test_core import setup
from tests.rag.test_adapters import CONFIG


class Direct:
    def __init__(self): self.calls = []
    async def ejecutar(self, principal, question):
        self.calls.append(question)
        return GeneracionSalida(respuesta='Respuesta general ficticia.', finalizacion='completa')


class Catalog:
    def __init__(self, documents):
        self.documents = documents
        self.listed = 0
        self.empty = False
    async def list_documents(self, principal):
        self.listed += 1
        if self.empty or principal.usuario_id != self.documents.owner:
            return []
        return [{'id': self.documents.scope.document_id, 'titulo': 'Ficticio'}]
    async def require_active(self, principal, document):
        return await self.documents.require_active(principal, document)


class TrackedRegistry(SkillRegistry):
    def __init__(self):
        super().__init__(PackagedSkillLoader())
        self.selected = []
    def load(self, name):
        self.selected.append(name)
        return super().load(name)


def fixture():
    p,s,chunks,documents,provider,gate,vectors,embeddings,auth,case = setup()
    content = 'La regularidad de una unidad curricular dura dos ciclos. Se exige asistencia.'
    chunk = replace(chunks[0], text=content, end=len(content))
    vectors.items = (Candidate(chunk=chunk, similarity=.90),)
    case.relevance = AcademicRelevance()
    provider.output=GeneracionSalida(respuesta='La regularidad de una unidad curricular dura dos ciclos [F1].',finalizacion='completa')
    catalog, direct, skills = Catalog(documents), Direct(), TrackedRegistry()
    agent = Agent(authorizer=auth, direct=direct, rag=case, documents=catalog,
                  admission=case.admission, skills=skills)
    return p,s,agent,catalog,direct,skills,provider,embeddings,case


def test_auto_general_does_not_read_or_load_skill_even_with_document():
    p,s,agent,catalog,direct,skills,provider,embedding,case = fixture()
    result = asyncio.run(agent.execute(p, '¿Qué es una API REST?'))
    assert result.strategy == 'LLM_DIRECTO' and result.status == 'GENERADA'
    assert len(direct.calls) == 1 and catalog.listed == 0
    assert skills.selected == [] and provider.inputs == [] and embedding.calls == 0


def test_auto_academic_selects_authorized_document_and_applies_real_skill():
    p,s,agent,catalog,direct,skills,provider,embedding,case = fixture()
    result = asyncio.run(agent.execute(p, '¿Cuánto tiempo dura la regularidad de una unidad curricular?'))
    assert result.status == 'FUNDAMENTADA' and result.strategy == 'RAG'
    assert result.citations[0].chunk.page == 7
    assert catalog.listed == 1 and skills.selected == ['academic-rag'] and direct.calls == []
    input = provider.inputs[0]
    loaded = SkillRegistry(PackagedSkillLoader()).load('academic-rag')
    assert input.instructions == loaded.instructions
    assert loaded.instructions in input.rendered
    assert 'Skill academic-rag:' in input.rendered
    assert 'description:' not in input.rendered  # No cargar el Markdown completo.
    assert len(input.rendered) + 256 + 512 <= 4096


def test_manual_rag_off_topic_never_calls_general_or_grounded_generator():
    p,s,agent,catalog,direct,skills,provider,embedding,case = fixture()
    result = asyncio.run(agent.execute(p, '¿Qué es una API REST?', mode='RAG', document_id=s.document_id))
    assert result.status == 'SIN_EVIDENCIA' and result.citations == ()
    assert direct.calls == [] and provider.inputs == [] and embedding.calls == 1
    assert skills.selected == ['academic-rag']


def test_institutional_without_authorized_evidence_abstains_without_model():
    p,s,agent,catalog,direct,skills,provider,embedding,case = fixture()
    catalog.empty = True
    result = asyncio.run(agent.execute(p, '¿Qué establece el reglamento institucional?'))
    assert result.status == 'SIN_EVIDENCIA' and result.strategy == 'RAG'
    assert result.citations == () and provider.inputs == [] and direct.calls == [] and embedding.calls == 0


def test_another_user_cannot_read_selected_private_document_or_load_skill():
    p,s,agent,catalog,direct,skills,provider,embedding,case = fixture()
    other = replace(p, usuario_id=uuid4())
    with pytest.raises(PermissionError):
        asyncio.run(agent.execute(other, 'Regularidad curricular', document_id=s.document_id))
    assert provider.inputs == [] and embedding.calls == 0 and skills.selected == []


def test_ambiguous_question_requests_precision_without_guessing_or_extra_llm():
    p,s,agent,catalog,direct,skills,provider,embedding,case = fixture()
    result = asyncio.run(agent.execute(p, '¿Cuánto tiempo dura?', document_id=s.document_id))
    assert result.status == 'ACLARACION' and 'Precisá' in result.answer
    assert provider.inputs == [] and direct.calls == [] and embedding.calls == 0


def test_multiple_documents_require_selection_not_random_choice():
    p,s,agent,catalog,direct,skills,provider,embedding,case = fixture()
    async def many(principal):
        return [{'id': s.document_id}, {'id': uuid4()}]
    catalog.list_documents = many
    result = asyncio.run(agent.execute(p, 'Regularidad curricular'))
    assert result.status == 'ACLARACION' and embedding.calls == 0


@pytest.mark.parametrize('question,expected', [
    ('¿Cómo funciona una unidad de almacenamiento?', 'general'),
    ('¿Qué es la regularidad de una función matemática?', 'general'),
    ('¿Cómo inscribirse para rendir un examen?', 'documentary'),
    ('¿Qué es una API REST?', 'general'),
    ('¿Cuánto tiempo dura?', 'ambiguous'),
    ('¿Quién es el rector de esta institución?', 'documentary'),
])
def test_router_relations_and_ambiguity(question, expected):
    assert AgentRouter().intent(question) == expected


def test_router_uses_authorized_context_for_unique_document():
    document = uuid4()
    assert AgentRouter().decide('Regularidad curricular', AgentContext(authorized_documents=(document,))).document_id == document
    assert AgentRouter().decide('Regularidad curricular', AgentContext()).document_id is None


def test_revoked_access_during_generation_is_not_delivered():
    p,s,agent,catalog,direct,skills,provider,embedding,case = fixture()
    provider.hook = lambda: setattr(catalog.documents, 'revoked', True)
    with pytest.raises(PermissionError):
        asyncio.run(agent.execute(p, 'Regularidad curricular', document_id=s.document_id))


@pytest.mark.parametrize('name', ['../academic-rag', 'unknown', '/tmp/evil'])
def test_skill_allowlist_rejects_unknown_paths(name):
    with pytest.raises(IANoDisponible): SkillRegistry(PackagedSkillLoader()).load(name)


@pytest.mark.parametrize('instructions', ['', 'x'*513, 'invalid\x00instruction'])
def test_skill_loader_contract_rejects_unbounded_instructions(instructions):
    class BadLoader:
        def load(self, name): return Skill(name, instructions)
    with pytest.raises(IANoDisponible): SkillRegistry(BadLoader()).load('academic-rag')


def test_missing_skill_is_technical_unavailable_not_abstention():
    p,s,agent,catalog,direct,skills,provider,embedding,case = fixture()
    class Broken:
        def load(self, name): raise IANoDisponible()
    agent.skills = Broken()
    with pytest.raises(IANoDisponible): asyncio.run(agent.execute(p, 'Regularidad curricular', document_id=s.document_id))
    assert provider.inputs == [] and direct.calls == []


def test_skill_reaches_actual_ollama_adapter_payload_with_budget():
    import json
    async def scenario():
        p,s,agent,catalog,direct,skills,provider,embedding,case = fixture()
        sent = []
        def handler(request):
            body = json.loads(request.content)
            sent.append(body)
            assert 'Skill academic-rag:' in body['prompt']
            assert 'SIN_EVIDENCIA' in body['prompt']
            assert len(body['prompt'].encode('utf-8')) + 256 + 512 <= 4096
            assert body['think'] is False and body['keep_alive'] == 0
            return httpx.Response(200, json={'model':'qwen3:1.7b', 'done':True,
                'done_reason':'stop', 'response':'La regularidad de una unidad curricular dura dos ciclos [F1].', 'prompt_eval_count':100})
        case.provider = GroundedProvider(CONFIG, transport=httpx.MockTransport(handler))
        try:
            result = await agent.execute(p, 'Regularidad curricular', document_id=s.document_id)
            assert result.status == 'FUNDAMENTADA' and len(sent) == 1
        finally:
            await case.provider.aclose()
    asyncio.run(scenario())


def test_skill_cannot_make_invalid_citation_successful():
    p,s,agent,catalog,direct,skills,provider,embedding,case = fixture()
    provider.output = GeneracionSalida(respuesta='Norma [F999].', finalizacion='completa')
    with pytest.raises(IARespuestaInvalida):
        asyncio.run(agent.execute(p, 'Regularidad curricular', document_id=s.document_id))


@pytest.mark.parametrize('scenario', ['general', 'academic', 'manual', 'no_evidence', 'forbidden'])
def test_agent_http_with_normal_auth_and_actual_rag_pipeline(scenario):
    from contextlib import asynccontextmanager
    from fastapi.testclient import TestClient
    from auth_support import memory_auth, bootstrap_login
    from ia_support import FakeLLMProvider
    from app.bootstrap import create_app
    from app.application.auth.exceptions import PermisoDenegado
    from app.infrastructure.llm.ollama import LLMRuntime
    from app.infrastructure.llm.admission import MemoryGenerationAdmission

    store, auth, _ = memory_auth()
    _, token = bootstrap_login(auth)
    actor = auth.authenticate(token)
    @asynccontextmanager
    async def runtime(config):
        yield LLMRuntime(FakeLLMProvider(), MemoryGenerationAdmission(), 60)
    app = create_app(repository=store.users, auth_service=auth, llm_config=CONFIG,
                     llm_runtime_factory=runtime)
    p,s,agent,catalog,direct,skills,provider,embedding,case = fixture()
    catalog.documents.owner = actor.usuario_id
    case.vectors.owner = actor.usuario_id
    class ProtectedCatalog(Catalog):
        async def require_active(self, principal, document):
            try:
                return await super().require_active(principal, document)
            except PermissionError:
                raise PermisoDenegado() from None
    protected = ProtectedCatalog(catalog.documents)
    with TestClient(app) as client:
        operational = app.state.ia_agent
        operational.rag, operational.documents = case, protected
        case.authorizer, case.admission = operational.authorizer, operational.admission
        question = '¿Cuánto tiempo dura la regularidad de una unidad curricular?'
        body = {'modo': 'AUTO', 'prompt': question}
        if scenario == 'general': body = {'prompt': '¿Qué es una API REST?'}  # AUTO por defecto HTTP.
        if scenario == 'manual': body = {'modo':'RAG','documento_id':str(s.document_id),'prompt':'¿Qué es una API REST?'}
        if scenario == 'no_evidence': protected.empty = True
        if scenario == 'forbidden':
            catalog.documents.owner = uuid4()
            body['documento_id'] = str(s.document_id)
        result = client.post('/api/v1/ia/respuestas', headers={'Authorization':'Bearer '+token}, json=body)
        assert result.headers['Cache-Control'] == 'no-store'
        if scenario == 'forbidden':
            assert result.status_code == 403 and embedding.calls == 0 and provider.inputs == []
        else:
            assert result.status_code == 200
            output = result.json()
            assert output['estrategia'] == ('LLM_DIRECTO' if scenario == 'general' else 'RAG')
            assert output['estado'] == ('GENERADA' if scenario == 'general' else
                                        'FUNDAMENTADA' if scenario == 'academic' else 'SIN_EVIDENCIA')
            assert output['fuentes'] == ([{'id':'F1','pagina':7}] if scenario == 'academic' else [])
            if scenario == 'academic': assert 'Skill academic-rag:' in provider.inputs[0].rendered
