from contextlib import asynccontextmanager
from dataclasses import replace
import socket

import httpx
import pytest
from fastapi.testclient import TestClient

from auth_support import memory_auth, bootstrap_login
from app.bootstrap import create_app
from app.infrastructure.configuration.llm import LLMConfig, LLMConfigInvalida
from app.infrastructure.configuration.llm_local import LocalLLMContext, require_local_runtime
from app.infrastructure.llm.ollama import ollama_runtime


TEST_CONFIG=LLMConfig(enabled=True,testing=True,environment='test')


class Transport(httpx.MockTransport):
    def __init__(self):
        super().__init__(self.handle)
        self.calls=0
        self.closed=False
    def handle(self,request):
        self.calls+=1
        return httpx.Response(200,json={'model':'qwen3:1.7b','done':True,'done_reason':'stop','response':'Respuesta ficticia.'})
    async def aclose(self): self.closed=True


@pytest.mark.parametrize('fail_after_enter',[False,True])
def test_real_mock_runtime_shared_and_closed_on_scope_or_composition_failure(fail_after_enter):
    store,auth,_=memory_auth()
    _,token=bootstrap_login(auth)
    transport=Transport()
    held=[]
    @asynccontextmanager
    async def factory(config):
        async with ollama_runtime(config,transport=transport) as runtime:
            held.append(runtime)
            yield replace(runtime,timeout_seconds=61) if fail_after_enter else runtime
    app=create_app(repository=store.users,auth_service=auth,llm_config=TEST_CONFIG,llm_runtime_factory=factory)
    if fail_after_enter:
        with pytest.raises(ValueError):
            with TestClient(app): pass
    else:
        with TestClient(app) as client:
            for _ in range(2):
                response=client.post('/api/v1/ia/consultas',json={'prompt':'valid'},headers={'Authorization':'Bearer '+token})
                assert response.status_code==200
            assert len(held)==1 and transport.calls==2
            assert not held[0].provider._client.is_closed
    assert transport.closed and held[0].provider._client.is_closed
    for name in ('ia_service','llm_runtime','auth_service','user_repository'):
        assert not hasattr(app.state,name)


def test_injected_memory_app_does_not_read_operational_llm_config(monkeypatch):
    store,auth,_=memory_auth()
    def forbidden(**kwargs): raise AssertionError('No operational config in memory test')
    monkeypatch.setattr('app.infrastructure.configuration.llm.load_llm_config',forbidden)
    with TestClient(create_app(repository=store.users,auth_service=auth)) as client:
        assert client.get('/openapi.json').status_code==200


def test_operational_enabled_without_socket_proof_fails_before_database_composition(monkeypatch):
    def forbidden(*args,**kwargs): raise AssertionError('No database should be constructed')
    monkeypatch.setattr('app.bootstrap.crear_persistencia_postgresql',forbidden)
    config=LLMConfig(enabled=True,environment='local-development')
    with pytest.raises(LLMConfigInvalida):
        with TestClient(create_app(llm_config=config)): pass


def test_test_runtime_override_rejected_for_operational_config():
    store,auth,_=memory_auth()
    def forbidden(config): raise AssertionError('Override must not be used')
    config=LLMConfig()
    with pytest.raises(LLMConfigInvalida):
        with TestClient(create_app(repository=store.users,auth_service=auth,llm_config=config,llm_runtime_factory=forbidden)): pass


@pytest.mark.parametrize('host,listening,workers,environment_workers,allowed',[
    ('127.0.0.1',True,1,'1',True),('0.0.0.0',True,1,'1',False),
    ('127.0.0.1',False,1,'1',False),('127.0.0.1',True,2,'1',False),
    ('127.0.0.1',True,1,'2',False),('127.0.0.1',True,True,'1',False)])
def test_operational_local_socket_and_single_worker_guard(host,listening,workers,environment_workers,allowed,monkeypatch):
    monkeypatch.setenv('WEB_CONCURRENCY',environment_workers)
    with socket.socket() as listener:
        listener.bind((host,0))
        if listening: listener.listen()
        context=LocalLLMContext(listener=listener,workers=workers)
        config=LLMConfig(enabled=True,environment='local-development')
        if allowed: require_local_runtime(config,context)
        else:
            with pytest.raises(LLMConfigInvalida): require_local_runtime(config,context)


def test_closed_socket_rejected():
    listener=socket.socket()
    listener.close()
    with pytest.raises(LLMConfigInvalida):
        require_local_runtime(LLMConfig(enabled=True,environment='local-development'),LocalLLMContext(listener=listener,workers=1))
