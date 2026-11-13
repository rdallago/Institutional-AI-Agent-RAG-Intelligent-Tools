"""Politica local sin conexiones a desarrollo; dobles de identidad y socket real efimero."""
from contextlib import contextmanager
from dataclasses import replace
import socket

import pytest

from auth_support import bootstrap_login
from app.application.auth.exceptions import AprovisionamientoNoHabilitado, CredencialExistente, CambioPasswordRequerido
from app.application.usuarios.dto import CrearUsuarioDatos
from app.infrastructure.configuration.database import DatabaseConfig
from app.infrastructure.configuration.local_provisioning import LocalProvisioningConfig, verified_local_gate


DEV = DatabaseConfig('127.0.0.1', 5434, 'usuarios_dev', 'fixture_admin', 'fictional-only')


class Result:
    def __init__(self, identity, revisions, sql):
        self.identity, self.revisions, self.sql = identity, revisions, sql

    def one(self): return self.identity
    def scalars(self): return self
    def all(self): return self.revisions


class IdentityEngine:
    def __init__(self, identity=('usuarios_dev', 'fixture_admin'), revisions=None):
        self.identity, self.revisions = identity, ['0003'] if revisions is None else revisions
        self.statements = []

    @contextmanager
    def connect(self): yield self

    def execute(self, sql):
        self.statements.append(str(sql))
        return Result(self.identity, self.revisions, sql)


@pytest.fixture
def listener():
    with socket.socket() as value:
        value.bind(('127.0.0.1', 0))
        value.listen()
        yield value


def test_default_closed(listener):
    with pytest.raises(AprovisionamientoNoHabilitado):
        verified_local_gate(LocalProvisioningConfig('local-development'), DEV, listener, IdentityEngine())


@pytest.mark.parametrize('environment', ['test', 'testing', 'production', 'development', ''])
def test_environment_rejected(environment, listener):
    engine = IdentityEngine()
    with pytest.raises(AprovisionamientoNoHabilitado):
        verified_local_gate(LocalProvisioningConfig(environment, True), DEV, listener, engine)
    assert not engine.statements


@pytest.mark.parametrize('changes', [dict(database='usuarios_test',port=5435), dict(port=5435),
    dict(host='localhost'), dict(host='192.168.1.2'), dict(database='production')])
def test_target_rejected_before_connection(changes, listener):
    engine = IdentityEngine()
    with pytest.raises(AprovisionamientoNoHabilitado):
        verified_local_gate(LocalProvisioningConfig('local-development', True), replace(DEV, **changes), listener, engine)
    assert not engine.statements


@pytest.mark.parametrize('host,listening', [('0.0.0.0', True), ('127.0.0.1', False)])
def test_socket_must_really_listen_on_loopback(host, listening):
    with socket.socket() as value:
        value.bind((host,0))
        if listening: value.listen()
        with pytest.raises(AprovisionamientoNoHabilitado):
            verified_local_gate(LocalProvisioningConfig('local-development', True), DEV, value, IdentityEngine())


@pytest.mark.parametrize('identity,revisions', [(('usuarios_test','fixture_admin'),['0003']),
    (('usuarios_dev','wrong_user'),['0003']), (('usuarios_dev','fixture_admin'),['0002']),
    (('usuarios_dev','fixture_admin'),['0003','0004']),
    (('usuarios_dev','fixture_admin'),[]),
    (('usuarios_dev','fixture_admin'),['0006_unknown'])])
def test_effective_database_and_revision_rejected(identity,revisions,listener):
    with pytest.raises(AprovisionamientoNoHabilitado):
        verified_local_gate(LocalProvisioningConfig('local-development', True), DEV, listener, IdentityEngine(identity,revisions))


@pytest.mark.parametrize('revision', ['0003', '0004_rag', '0005_agent_memory'])
def test_known_additive_revisions_allow_explicit_local_opt_in(revision, listener):
    engine = IdentityEngine(revisions=[revision])
    gate = verified_local_gate(LocalProvisioningConfig('local-development', True), DEV, listener, engine)
    gate()
    assert engine.statements == ['SET TRANSACTION READ ONLY',
                                 'SELECT current_database(), current_user',
                                 'SELECT version_num FROM public.alembic_version']


def test_enabled_gate_fails_closed_after_listener_closes(listener):
    engine=IdentityEngine()
    gate=verified_local_gate(LocalProvisioningConfig('local-development', True), DEV, listener, engine)
    gate()
    assert engine.statements[0]=='SET TRANSACTION READ ONLY'
    listener.close()
    with pytest.raises(AprovisionamientoNoHabilitado): gate()


@pytest.mark.postgres
def test_real_test_database_cannot_enable_local_gate(postgres_resources, listener):
    # Conexion exclusivamente de pruebas, aunque un llamador declare destino dev.
    _, engine, _ = postgres_resources
    with pytest.raises(AprovisionamientoNoHabilitado):
        verified_local_gate(LocalProvisioningConfig('local-development', True), DEV, listener, engine)


def test_opt_in_full_flow_and_normal_instance_stays_closed(backend_security, listener):
    from app.application.auth.provisioning import require_initial_provisioning_enabled
    from app.application.auth.exceptions import PermisoDenegado, AutenticacionRequerida
    service,factory=backend_security
    _,token=bootstrap_login(service)
    principal=service.authenticate(token)
    service._administrative_provisioning_gate=verified_local_gate(
        LocalProvisioningConfig('local-development', True), DEV, listener, IdentityEngine())
    initial='initial-local-fixture-password'
    final='definitive-local-fixture-password'
    user=service.create_with_initial(principal, CrearUsuarioDatos(nombre='Local',apellido='Fixture',email='local@example.com'), initial)
    with pytest.raises(CredencialExistente): service.assign_initial_admin(principal,user.id,initial)
    pending=service.login('local@example.com',initial,'127.0.0.2')
    assert pending.debe_cambiar_password
    restricted=service.authenticate_session(pending.access_token)
    with pytest.raises(CambioPasswordRequerido): service.create_with_initial(restricted,CrearUsuarioDatos(nombre='X',apellido='Y',email='x@example.com'),initial)
    service.change_password(restricted,initial,final,ip='127.0.0.2')
    with pytest.raises(AutenticacionRequerida): service.authenticate_session(pending.access_token)
    normal=service.login('local@example.com',final,'127.0.0.2')
    assert not normal.debe_cambiar_password
    with pytest.raises(PermisoDenegado): service.create_with_initial(service.authenticate(normal.access_token),CrearUsuarioDatos(nombre='X',apellido='Y',email='x@example.com'),initial)
    with factory() as uow:
        credential=uow.credential(user.id)
        assert not credential.debe_cambiar_password
        assert service.hasher.verify(credential.password_inicial_hash,initial)
    with pytest.raises(AprovisionamientoNoHabilitado): require_initial_provisioning_enabled()
    with pytest.raises(AprovisionamientoNoHabilitado): service.bootstrap('X','Y','bootstrap@example.com',initial)


@pytest.mark.parametrize('args', [ ['--environment','production','--enable-initial-provisioning'],
    ['--environment','test','--enable-initial-provisioning'],
    ['--environment','local-development','--host','0.0.0.0','--enable-initial-provisioning'] ])
def test_launcher_rejects_unsafe_settings_before_loading_secrets(args):
    from app.presentation.cli.local_server import main
    with pytest.raises(SystemExit) as error: main(args)
    assert error.value.code==2


@pytest.mark.parametrize('enabled,started', [(False, True), (True, True), (True, False)])
def test_launcher_composes_only_verified_instance(monkeypatch, enabled, started):
    from app.presentation.cli.local_server import main
    engine=IdentityEngine()
    engine.dispose=lambda: None
    composed={}
    def app_factory(**kwargs):
        composed.update(kwargs)
        return object()
    class Server:
        def __init__(self, config): self.started=started
        def run(self, *, sockets):
            assert sockets[0].getsockname()[0]=='127.0.0.1'
            gate=composed['administrative_provisioning_gate']
            if enabled: gate()
            else: assert gate is None
    monkeypatch.setattr('app.infrastructure.configuration.database.load_database_config',lambda: DEV)
    monkeypatch.setattr('app.infrastructure.configuration.auth.load_auth_config',lambda: object())
    monkeypatch.setattr('app.infrastructure.persistence.database.build_engine',lambda config: engine)
    monkeypatch.setattr('app.bootstrap.create_app',app_factory)
    monkeypatch.setattr('uvicorn.Server',Server)
    with socket.socket() as probe:
        probe.bind(('127.0.0.1',0))
        port=probe.getsockname()[1]
    args=['--environment','local-development','--port',str(port)]
    if enabled: args.append('--enable-initial-provisioning')
    assert main(args)==(0 if started else 1)
    assert composed['database_config'] is DEV
    if enabled:
        with pytest.raises(AprovisionamientoNoHabilitado): composed['administrative_provisioning_gate']()
