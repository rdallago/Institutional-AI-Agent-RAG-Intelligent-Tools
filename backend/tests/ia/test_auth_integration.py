"""Integracion con AuthService y UoW reales de memoria, sin PostgreSQL ni HTTP."""
import asyncio
from contextlib import contextmanager
from dataclasses import replace
from datetime import timedelta
from threading import Event, get_ident

import pytest

from auth_support import memory_auth, bootstrap_login
from ia_support import FakeLLMProvider, ControlledClock
from app.application.auth.exceptions import AutenticacionRequerida, CambioPasswordRequerido
from app.application.ia.dto import ConsultaDatos
from app.application.ia.use_cases.generar_respuesta import GenerarRespuesta
from app.domain.usuarios.rol import Rol
from app.domain.usuarios.usuario import Usuario
from app.infrastructure.llm.authorization import AuthServiceNormalAccessAuthorizer
from app.infrastructure.llm.admission import MemoryGenerationAdmission


def prepare(role):
    store,service,_=memory_auth()
    uid,token=bootstrap_login(service)
    principal=service.authenticate(token)
    with store.uow() as uow:
        user=uow.usuarios.obtener_por_id(uid)
        uow.usuarios.actualizar(Usuario.reconstruir(id=user.id,nombre=user.nombre,apellido=user.apellido,
            email=user.email,activo=True,rol=role,fecha_creacion=user.fecha_creacion))
    return store,service,principal


def invalidate(store,service,principal,condition):
    with store.uow() as uow:
        credential=uow.credential(principal.usuario_id)
        session=uow.session(principal.sesion_id)
        if condition in ('pending','restricted'):
            uow.put_credential(replace(credential,debe_cambiar_password=True,password_inicial_hash=credential.password_hash))
            if condition=='restricted': uow.put_session(replace(session,restringida=True))
        elif condition=='revoked': uow.revoke(principal.usuario_id,service.clock())
        elif condition=='expired': uow.put_session(replace(session,expira_at=service.clock()-timedelta(seconds=1)))
        elif condition=='inactive':
            user=uow.usuarios.obtener_por_id(principal.usuario_id)
            uow.usuarios.actualizar(Usuario.reconstruir(id=user.id,nombre=user.nombre,apellido=user.apellido,
                email=user.email,activo=False,rol=user.rol,fecha_creacion=user.fecha_creacion))
        elif condition=='credential_missing': store.credentials.pop(principal.usuario_id)
        elif condition=='restricted_definitive': uow.put_session(replace(session,restringida=True))


@pytest.mark.parametrize('role',[Rol.ADMIN,Rol.USUARIO])
def test_normal_roles_and_no_uow_open_during_generation(role):
    store,service,principal=prepare(role)
    original=service.uow_factory
    transactions=[]
    @contextmanager
    def tracked():
        with original() as uow:
            transactions.append(get_ident())
            try: yield uow
            finally: transactions.pop()
    service.uow_factory=tracked
    async def scenario():
        async def hook(): assert transactions==[]
        provider=FakeLLMProvider(hook=hook)
        before=dict(store.attempts)
        case=GenerarRespuesta(provider,AuthServiceNormalAccessAuthorizer(service),MemoryGenerationAdmission())
        assert (await case.ejecutar(principal,ConsultaDatos(prompt='Consulta ficticia.'))).finalizacion=='completa'
        assert transactions==[] and store.attempts==before
    asyncio.run(scenario())


CONDITIONS=[('pending',CambioPasswordRequerido),('restricted',CambioPasswordRequerido),
    ('revoked',AutenticacionRequerida),('inactive',AutenticacionRequerida),('expired',AutenticacionRequerida),
    ('credential_missing',AutenticacionRequerida),('restricted_definitive',AutenticacionRequerida)]


@pytest.mark.parametrize('role',[Rol.ADMIN,Rol.USUARIO])
@pytest.mark.parametrize('condition,error',CONDITIONS)
def test_invalid_access_before_provider(role,condition,error):
    store,service,principal=prepare(role)
    invalidate(store,service,principal,condition)
    async def scenario():
        provider=FakeLLMProvider()
        admission=MemoryGenerationAdmission()
        with pytest.raises(error):
            await GenerarRespuesta(provider,AuthServiceNormalAccessAuthorizer(service),admission).ejecutar(principal,ConsultaDatos(prompt='valid'))
        assert not provider.inputs and admission._global_count==0
    asyncio.run(scenario())


@pytest.mark.parametrize('condition,error',CONDITIONS)
def test_access_change_during_generation_discards_result_and_releases(condition,error):
    store,service,principal=prepare(Rol.ADMIN)
    async def scenario():
        async def hook(): invalidate(store,service,principal,condition)
        admission=MemoryGenerationAdmission()
        provider=FakeLLMProvider(hook=hook)
        with pytest.raises(error):
            await GenerarRespuesta(provider,AuthServiceNormalAccessAuthorizer(service),admission).ejecutar(principal,ConsultaDatos(prompt='valid'))
        assert len(provider.inputs)==1
        admission.try_acquire(principal).release()
    asyncio.run(scenario())


def test_revocation_while_provider_blocked():
    store,service,principal=prepare(Rol.ADMIN)
    async def scenario():
        admission=MemoryGenerationAdmission()
        provider=FakeLLMProvider(blocked=True)
        case=GenerarRespuesta(provider,AuthServiceNormalAccessAuthorizer(service),admission)
        task=asyncio.create_task(case.ejecutar(principal,ConsultaDatos(prompt='valid')))
        await provider.started.wait()
        invalidate(store,service,principal,'revoked')
        provider.resume.set()
        with pytest.raises(AutenticacionRequerida): await task
        admission.try_acquire(principal).release()
    asyncio.run(scenario())


def test_sync_authorization_runs_in_worker_without_blocking_event_loop():
    _,service,principal=prepare(Rol.ADMIN)
    entered,release=Event(),Event()
    actual=service.require_normal_access
    threads=[]
    def blocking(actor):
        threads.append(get_ident())
        entered.set()
        assert release.wait(timeout=2)
        actual(actor)
    service.require_normal_access=blocking
    async def scenario():
        task=asyncio.create_task(AuthServiceNormalAccessAuthorizer(service).require_normal(principal))
        try:
            assert await asyncio.to_thread(entered.wait,1)
            assert not task.done() and threads[0]!=get_ident()
        finally: release.set()
        await task
    asyncio.run(scenario())


def test_ia_quotas_do_not_change_authentication_attempts():
    store,service,principal=prepare(Rol.ADMIN)
    before=dict(store.attempts)
    async def scenario():
        admission=MemoryGenerationAdmission(clock=ControlledClock())
        case=GenerarRespuesta(FakeLLMProvider(),AuthServiceNormalAccessAuthorizer(service),admission)
        for _ in range(5): await case.ejecutar(principal,ConsultaDatos(prompt='valid'))
        from app.application.ia.exceptions import IALimiteIntentos
        with pytest.raises(IALimiteIntentos): await case.ejecutar(principal,ConsultaDatos(prompt='valid'))
        assert store.attempts==before
    asyncio.run(scenario())
