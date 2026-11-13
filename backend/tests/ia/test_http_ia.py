import asyncio
from contextlib import asynccontextmanager
from dataclasses import replace
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from auth_support import memory_auth, bootstrap_login
from ia_support import FakeLLMProvider, ControlledClock, SENSITIVE
from app.bootstrap import create_app
from app.domain.usuarios.rol import Rol
from app.domain.usuarios.usuario import Usuario
from app.infrastructure.configuration.llm import LLMConfig
from app.infrastructure.llm.ollama import LLMRuntime, ollama_runtime
from app.infrastructure.llm.admission import MemoryGenerationAdmission


PATH='/api/v1/ia/consultas'
TEST_CONFIG=LLMConfig(testing=True,environment='test',enabled=True)


def setup_app(*, role=Rol.ADMIN, provider=None, config=TEST_CONFIG, timeout=60, factory=None):
    store,auth,_=memory_auth()
    uid,token=bootstrap_login(auth)
    principal=auth.authenticate(token)
    with store.uow() as uow:
        user=uow.usuarios.obtener_por_id(uid)
        uow.usuarios.actualizar(Usuario.reconstruir(id=user.id,nombre=user.nombre,apellido=user.apellido,
            email=user.email,activo=True,rol=role,fecha_creacion=user.fecha_creacion))
    provider=provider or FakeLLMProvider()
    state={'opens':0,'closes':0,'provider':provider}
    @asynccontextmanager
    async def runtime_factory(config):
        state['opens']+=1
        runtime=LLMRuntime(provider,MemoryGenerationAdmission(clock=ControlledClock()),timeout)
        state['runtime']=runtime
        try: yield runtime
        finally: state['closes']+=1
    app=create_app(repository=store.users,auth_service=auth,llm_config=config,
        llm_runtime_factory=factory or runtime_factory)
    return app,store,auth,principal,{'Authorization':'Bearer '+token},state


@pytest.mark.parametrize('role',[Rol.ADMIN,Rol.USUARIO])
def test_normal_roles_success_runtime_reuse_and_cleanup(role):
    app,_,_,_,headers,state=setup_app(role=role)
    with TestClient(app) as client:
        assert state['opens']==1
        for _ in range(2):
            response=client.post(PATH,json={'prompt':' Consulta ficticia. '},headers=headers)
            assert response.status_code==200 and response.headers['Cache-Control']=='no-store'
            assert response.json()=={'respuesta':'Respuesta ficticia.','finalizacion':'completa'}
        assert app.state.llm_runtime is state['runtime'] and len(state['provider'].inputs)==2
        assert client.get('/api/v1/auth/me',headers=headers).status_code==200
        schema=client.get('/openapi.json').json()['paths'][PATH]['post']
        assert schema['security'] and set(schema['responses'])>={'200','401','403','413','422','429','502','503','504'}
    assert state['closes']==1 and not hasattr(app.state,'ia_service') and not hasattr(app.state,'llm_runtime')


def test_disabled_without_client_and_existing_routes_still_work(monkeypatch):
    store,auth,_=memory_auth()
    _,token=bootstrap_login(auth)
    def forbidden(**kwargs): raise AssertionError('Disabled IA must not create client')
    monkeypatch.setattr(httpx,'AsyncClient',forbidden)
    app=create_app(repository=store.users,auth_service=auth)
    with TestClient(app) as client:
        headers={'Authorization':'Bearer '+token}
        response=client.post(PATH,json={'prompt':'valid'},headers=headers)
        assert response.status_code==503 and response.json()['error']['codigo']=='IA_NO_DISPONIBLE'
        assert response.headers['Cache-Control']=='no-store'
        assert client.get('/api/v1/auth/me',headers=headers).status_code==200
        assert client.get('/api/v1/usuarios',headers=headers).status_code==200


@pytest.mark.parametrize('headers',[{}, {'Authorization':'Bearer invalid-fixture'}, {'Authorization':'Basic invalid-fixture'}])
def test_missing_or_invalid_jwt(headers):
    app,_,_,_,_,state=setup_app()
    with TestClient(app) as client:
        response=client.post(PATH,json={'prompt':'valid'},headers=headers)
        assert response.status_code==401 and response.headers['WWW-Authenticate']=='Bearer'
        assert response.headers['Cache-Control']=='no-store' and not state['provider'].inputs


@pytest.mark.parametrize('role',[Rol.ADMIN,Rol.USUARIO])
@pytest.mark.parametrize('condition',['pending','revoked','inactive','expired'])
def test_http_access_denied(role,condition):
    from datetime import timedelta
    app,store,auth,principal,headers,state=setup_app(role=role)
    with store.uow() as uow:
        if condition=='pending':
            credential=uow.credential(principal.usuario_id)
            uow.put_credential(replace(credential,debe_cambiar_password=True,password_inicial_hash=credential.password_hash))
            uow.put_session(replace(uow.session(principal.sesion_id),restringida=True))
        elif condition=='revoked': uow.revoke(principal.usuario_id,auth.clock())
        elif condition=='expired': uow.put_session(replace(uow.session(principal.sesion_id),expira_at=auth.clock()-timedelta(seconds=1)))
        else:
            user=uow.usuarios.obtener_por_id(principal.usuario_id)
            uow.usuarios.actualizar(Usuario.reconstruir(id=user.id,nombre=user.nombre,apellido=user.apellido,
                email=user.email,activo=False,rol=user.rol,fecha_creacion=user.fecha_creacion))
    with TestClient(app) as client:
        response=client.post(PATH,json={'prompt':'valid'},headers=headers)
        assert response.status_code==(403 if condition=='pending' else 401)
        assert response.headers['Cache-Control']=='no-store' and not state['provider'].inputs


@pytest.mark.parametrize('body,code',[({},'SOLICITUD_INVALIDA'),({'prompt':42},'SOLICITUD_INVALIDA'),
    ({'prompt':None},'SOLICITUD_INVALIDA'),({'prompt':''},'PROMPT_INVALIDO'),({'prompt':' \n'},'PROMPT_INVALIDO'),
    ({'prompt':'a'*1001},'PROMPT_INVALIDO'),({'prompt':'\U0001f600'*751},'PROMPT_INVALIDO'),
    ({'prompt':'\ud800'},'PROMPT_INVALIDO'),({'prompt':'a\x00b'},'PROMPT_INVALIDO'),
    ({'prompt':'valid','model':SENSITIVE},'SOLICITUD_INVALIDA')])
def test_prompt_and_structure_validation(body,code,caplog):
    app,_,_,_,headers,state=setup_app()
    with TestClient(app) as client:
        response=client.post(PATH,content=json.dumps(body),headers={**headers,'Content-Type':'application/json'})
        assert response.status_code==422 and response.json()['error']['codigo']==code
        assert SENSITIVE not in response.text+caplog.text
        assert response.headers['Cache-Control']=='no-store' and not state['provider'].inputs


@pytest.mark.parametrize('content_type',[None,'text/plain','application/x-www-form-urlencoded','application/octet-stream'])
def test_incorrect_content_type(content_type):
    app,_,_,_,headers,state=setup_app()
    if content_type: headers['Content-Type']=content_type
    with TestClient(app) as client:
        response=client.post(PATH,content=b'{"prompt":"valid"}',headers=headers)
        assert response.status_code==422 and response.headers['Cache-Control']=='no-store'
        assert not state['provider'].inputs


@pytest.mark.parametrize('body',['{"prompt":"'+SENSITIVE,b'\xff',b'not json'])
def test_invalid_json_sanitized(body):
    app,_,_,_,headers,state=setup_app()
    with TestClient(app) as client:
        response=client.post(PATH,content=body,headers={**headers,'Content-Type':'application/json'})
        assert response.status_code==422 and SENSITIVE not in response.text and not state['provider'].inputs
        assert response.headers['Cache-Control']=='no-store'


@pytest.mark.parametrize('size,status',[(16384,200),(16385,413)])
def test_body_exact_limit_and_over(size,status):
    app,_,_,_,headers,state=setup_app()
    body=b'{"prompt":"valid"}'
    body+=b' '*(size-len(body))
    with TestClient(app) as client:
        response=client.post(PATH,content=body,headers={**headers,'Content-Type':'application/json'})
        assert response.status_code==status and response.headers['Cache-Control']=='no-store'
        assert len(state['provider'].inputs)==(1 if status==200 else 0)


@pytest.mark.parametrize('declared',[None,'1','999999'])
def test_fragmented_request_cap_checked_before_accumulation(declared):
    async def scenario():
        app,_,_,_,headers,state=setup_app()
        headers['Content-Type']='application/json'
        if declared: headers['Content-Length']=declared
        consumed=[]
        async def chunks():
            for chunk in [b'x'*8192,b'x'*8192,b'x',b'never consumed']:
                consumed.append(1)
                yield chunk
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://testserver') as client:
                response=await client.post(PATH,content=chunks(),headers=headers)
                assert response.status_code==413 and response.headers['Cache-Control']=='no-store'
        assert len(consumed)==3 and not state['provider'].inputs
    asyncio.run(scenario())


@pytest.mark.parametrize('mode,status,code',[('invalid',502,'IA_RESPUESTA_INVALIDA'),
    ('unexpected',502,'IA_RESPUESTA_INVALIDA'),('unavailable',503,'IA_NO_DISPONIBLE'),
    ('timeout',504,'IA_TIEMPO_AGOTADO')])
def test_error_translation(mode,status,code,caplog):
    app,_,_,_,headers,_=setup_app(provider=FakeLLMProvider(mode=mode))
    with TestClient(app) as client:
        response=client.post(PATH,json={'prompt':SENSITIVE},headers=headers)
        assert response.status_code==status and response.json()['error']['codigo']==code
        assert response.headers['Cache-Control']=='no-store' and SENSITIVE not in response.text+caplog.text


def test_quota_429_retry_after_and_shared_admission():
    app,_,_,_,headers,_=setup_app()
    with TestClient(app) as client:
        for _ in range(5): assert client.post(PATH,json={'prompt':'valid'},headers=headers).status_code==200
        response=client.post(PATH,json={'prompt':'valid'},headers=headers)
        assert response.status_code==429 and response.json()['error']['codigo']=='IA_LIMITE_INTENTOS'
        assert response.headers['Retry-After']=='60' and response.headers['Cache-Control']=='no-store'


def test_concurrent_http_request_and_cancellation_release_cup():
    async def scenario():
        provider=FakeLLMProvider(blocked=True)
        app,_,_,_,headers,state=setup_app(provider=provider)
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://testserver') as client:
                task=asyncio.create_task(client.post(PATH,json={'prompt':'first'},headers=headers))
                await provider.started.wait()
                response=await client.post(PATH,json={'prompt':'second'},headers=headers)
                assert response.status_code==429 and response.json()['error']['codigo']=='IA_OCUPADA'
                assert response.headers['Retry-After']=='1'
                task.cancel()
                with pytest.raises(asyncio.CancelledError): await task
                assert provider.cancelled
                provider.resume.set()
                assert (await client.post(PATH,json={'prompt':'third'},headers=headers)).status_code==200
        assert state['closes']==1
    asyncio.run(scenario())


def test_http_revalidation_rejects_revocation_during_generation():
    app,store,auth,principal,headers,state=setup_app()
    async def hook():
        with store.uow() as uow: uow.revoke(principal.usuario_id,auth.clock())
    state['provider'].hook=hook
    with TestClient(app) as client:
        response=client.post(PATH,json={'prompt':'valid'},headers=headers)
        assert response.status_code==401 and response.headers['Cache-Control']=='no-store'


def test_internal_failure_no_store_and_sanitized_logs(caplog):
    app,_,auth,_,headers,_=setup_app()
    def fail(principal): raise RuntimeError(SENSITIVE)
    auth.require_normal_access=fail
    with TestClient(app) as client:
        response=client.post(PATH,json={'prompt':SENSITIVE},headers=headers)
        assert response.status_code==500 and response.headers['Cache-Control']=='no-store'
        assert SENSITIVE not in response.text+caplog.text
