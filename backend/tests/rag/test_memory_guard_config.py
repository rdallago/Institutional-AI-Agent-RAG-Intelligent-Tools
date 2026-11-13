"""Solo configuración y flujo previo al transporte: sin modelos, HTTP o bases."""
import asyncio
from types import SimpleNamespace

import pytest

from app.infrastructure.configuration.llm import LLMConfig,LLMConfigInvalida,load_memory_guard,load_llm_config
from app.application.ia.exceptions import IANoDisponible,IARespuestaInvalida
from app.application.agent.errors import MemoriaPlanificadorInsuficiente


@pytest.mark.parametrize('environment',['disabled','production','test'])
def test_exception_cannot_escape_local_environment(environment):
    assert LLMConfig(environment=environment,testing=environment=='test').enforce_memory_guard
    with pytest.raises(LLMConfigInvalida):
        LLMConfig(environment=environment,testing=environment=='test',enforce_memory_guard=False)


def test_loader_default_local_override_environment_precedence_and_testing_isolation(tmp_path,monkeypatch):
    path=tmp_path/'config.env'
    monkeypatch.delenv('AGENT_ENFORCE_MEMORY_GUARD',raising=False)
    monkeypatch.delenv('TEST_AGENT_ENFORCE_MEMORY_GUARD',raising=False)
    assert load_memory_guard(environment='local-development',env_file=path)
    path.write_text('AGENT_ENFORCE_MEMORY_GUARD=false\nLLM_ENABLED=true\nLLM_ENVIRONMENT=local-development\n')
    config=load_llm_config(env_file=path)
    assert config.enabled and not config.enforce_memory_guard
    assert load_memory_guard(environment='test',testing=True,env_file=path)
    with pytest.raises(LLMConfigInvalida):load_memory_guard(environment='production',env_file=path)
    monkeypatch.setenv('AGENT_ENFORCE_MEMORY_GUARD','true')
    assert load_memory_guard(environment='local-development',env_file=path)
    monkeypatch.setenv('AGENT_ENFORCE_MEMORY_GUARD','invalid')
    with pytest.raises(LLMConfigInvalida):load_memory_guard(environment='local-development',env_file=path)


@pytest.mark.parametrize('enforce',[True,False])
def test_all_operational_adapters_respect_same_config_without_network(enforce,monkeypatch):
    import app.infrastructure.rag.planner as planner_module
    import app.infrastructure.rag.resources as resources
    from app.infrastructure.rag.ollama import Embeddings,GroundedProvider
    from app.infrastructure.rag.models import CoordinatedDirectProvider
    from app.infrastructure.llm.work_gate import MemoryModelWorkGate
    from app.application.ia.dto import GeneracionEntrada,GeneracionSalida
    config=LLMConfig(enabled=True,environment='local-development',enforce_memory_guard=enforce)
    checks=[]
    def low_memory(minimum):checks.append(minimum);raise IANoDisponible()
    monkeypatch.setattr(resources,'require_memory',low_memory)
    monkeypatch.setattr(planner_module,'require_memory',low_memory)
    class BeforeNetwork(Exception):pass
    async def idle():raise BeforeNetwork()
    class Direct:
        _config=config
        async def generate(self,input):return GeneracionSalida(respuesta='Prueba sintética',finalizacion='completa')
    async def run():
        gate=MemoryModelWorkGate()
        planner=planner_module.JSONPlanner(config,gate,idle)
        embeddings=Embeddings(config);grounded=GroundedProvider(config)
        direct=CoordinatedDirectProvider(Direct(),gate)
        try:
            with pytest.raises(MemoriaPlanificadorInsuficiente if enforce else BeforeNetwork):await planner.plan('Prueba')
            with pytest.raises(IANoDisponible if enforce else IARespuestaInvalida):await embeddings.embed_query('Prueba',space='invalid')
            with pytest.raises(IANoDisponible if enforce else IARespuestaInvalida):
                await grounded.generate_grounded(SimpleNamespace(question='Prueba',evidence=()))
            if enforce:
                with pytest.raises(IANoDisponible):await direct.generate(GeneracionEntrada(prompt='Prueba'))
            else:assert (await direct.generate(GeneracionEntrada(prompt='Prueba'))).finalizacion=='completa'
        finally:await planner.aclose();await embeddings.close();await grounded.aclose()
        assert checks==([1.5,1.0,1.5,1.5] if enforce else [])
        gate.try_acquire().release()
    asyncio.run(run())
