"""Lanzador con socket efimero real; servidor, configuracion y persistencia doblados."""
import socket
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.infrastructure.configuration.database import DatabaseConfig
from app.infrastructure.configuration.llm import LLMConfig, LLMConfigInvalida
from app.infrastructure.configuration.llm_local import require_local_runtime
from app.presentation.cli import local_server


@pytest.fixture
def launch(monkeypatch):
    monkeypatch.delenv('WEB_CONCURRENCY', raising=False)
    held = {}
    database = DatabaseConfig('127.0.0.1', 5434, 'usuarios_dev', 'fixture', 'fictional')
    monkeypatch.setattr('app.infrastructure.configuration.database.load_database_config', lambda: database)
    monkeypatch.setattr('app.infrastructure.configuration.auth.load_auth_config', lambda: object())
    monkeypatch.setattr('app.infrastructure.persistence.database.build_engine', Mock(side_effect=AssertionError('No database')))
    monkeypatch.setattr('app.infrastructure.configuration.llm.load_llm_config', Mock(side_effect=AssertionError('No env files')))
    def compose(**kwargs):
        held.update(kwargs)
        require_local_runtime(kwargs['llm_config'], kwargs['llm_local_context'])
        return object()
    monkeypatch.setattr('app.bootstrap.create_app', compose)
    class Server:
        started = True
        def __init__(self, config):
            held['server_config'] = config
        def run(self, *, sockets):
            held['served'] = sockets[0]
            assert held['llm_local_context'].listener is sockets[0]
            assert sockets[0].family == socket.AF_INET
            assert sockets[0].getsockname()[0] == '127.0.0.1'
            assert sockets[0].getsockopt(socket.SOL_SOCKET, socket.SO_ACCEPTCONN) == 1
    monkeypatch.setattr('uvicorn.Server', Server)
    # Reserve an ephemeral port only to choose a test destination; never use operational ports.
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        port = probe.getsockname()[1]
    args = ['--environment', 'local-development', '--port', str(port)]
    return SimpleNamespace(held=held, args=args, server=Server)


@pytest.mark.parametrize('enabled', [False, True])
def test_explicit_config_and_exact_validated_socket_served_and_closed(launch, enabled):
    assert local_server.main(launch.args + (['--enable-llm'] if enabled else [])) == 0
    held = launch.held
    assert held['llm_config'].enabled is enabled
    assert held['llm_config'].testing is False
    assert held['llm_config'].environment == ('local-development' if enabled else 'disabled')
    assert held['llm_local_context'].workers == 1
    assert held['llm_local_context'].listener is held['served']
    assert held['served'].fileno() == -1
    assert held['server_config'].workers == 1
    assert held['server_config'].reload is False
    assert held['server_config'].proxy_headers is False
    assert held['server_config'].access_log is False
    assert held['administrative_provisioning_gate'] is None


@pytest.mark.parametrize('enabled', [False, True])
def test_environment_cannot_implicitly_enable_or_override_cli_config(launch, monkeypatch, enabled):
    # Aislar la selección permitida del modelo del .env operativo del desarrollador.
    monkeypatch.setenv('OLLAMA_MODEL', 'qwen3:1.7b')
    for name, value in {'LLM_ENABLED': 'true', 'LLM_ENVIRONMENT': 'production',
                        'LLM_BASE_URL': 'http://external.invalid', 'TEST_LLM_ENABLED': 'true'}.items():
        monkeypatch.setenv(name, value)
    assert local_server.main(launch.args + (['--enable-llm'] if enabled else [])) == 0
    assert launch.held['llm_config'].enabled is enabled
    assert launch.held['llm_config'].base_url == 'http://127.0.0.1:11434'
    assert launch.held['llm_config'].model == 'qwen3:1.7b'


@pytest.mark.parametrize('args', [
    ['--environment', 'production', '--enable-llm'],
    ['--environment', 'test', '--enable-llm'],
    ['--environment', 'local-development', '--host', '0.0.0.0', '--enable-llm'],
    ['--environment', 'local-development', '--host', '::1', '--enable-llm'],
    ['--environment', 'local-development', '--workers', '2', '--enable-llm'],
    ['--environment', 'local-development', '--reload', '--enable-llm'],
])
def test_unsafe_cli_rejected_before_configuration(monkeypatch, args):
    load = Mock(side_effect=AssertionError('No operational configuration'))
    monkeypatch.setattr('app.infrastructure.configuration.database.load_database_config', load)
    with pytest.raises(SystemExit) as error:
        local_server.main(args)
    assert error.value.code == 2
    load.assert_not_called()


def test_environment_multiple_workers_rejected_before_composition(launch, monkeypatch):
    monkeypatch.setenv('WEB_CONCURRENCY', '2')
    assert local_server.main(launch.args + ['--enable-llm']) == 1
    assert not launch.held


@pytest.mark.parametrize('failure', ['closed', 'not_listening', 'workers'])
def test_real_guard_rejects_invalid_context_and_launcher_closes_resources(launch, monkeypatch, failure):
    from app.infrastructure.configuration import llm_local
    real_context = llm_local.LocalLLMContext
    captured = []
    def context(**kwargs):
        listener = kwargs['listener']
        captured.append(listener)
        if failure == 'closed': listener.close()
        if failure == 'not_listening':
            listener.close()
            listener = socket.socket()
            listener.bind(('127.0.0.1', 0))
            captured.append(listener)
        return real_context(listener=listener, workers=2 if failure == 'workers' else 1)
    monkeypatch.setattr(llm_local, 'LocalLLMContext', real_context)
    # Preserve isinstance in the real guard; alter only the context built by the CLI.
    original_guard = llm_local.require_local_runtime
    def guard(config, ctx):
        invalid = context(listener=ctx.listener)
        try: original_guard(config, invalid)
        finally:
            for listener in captured: listener.close()
    monkeypatch.setattr(llm_local, 'require_local_runtime', guard)
    assert local_server.main(launch.args + ['--enable-llm']) == 1
    assert not launch.held
    assert all(listener.fileno() == -1 for listener in captured)


def test_unsafe_llm_configuration_rejected_and_socket_closed(launch, monkeypatch, capsys):
    captured = []
    def invalid(**kwargs):
        raise LLMConfigInvalida()
    monkeypatch.setattr('app.infrastructure.configuration.llm.LLMConfig', invalid)
    original = local_server.socket.socket
    def track(*args, **kwargs):
        value = original(*args, **kwargs); captured.append(value); return value
    monkeypatch.setattr(local_server.socket, 'socket', track)
    assert local_server.main(launch.args + ['--enable-llm']) == 1
    assert captured and all(value.fileno() == -1 for value in captured)
    assert 'Inicio local rechazado' in capsys.readouterr().err


@pytest.mark.parametrize('where', ['composition', 'server', 'not_started'])
def test_cleanup_on_composition_or_server_error(launch, monkeypatch, where, capsys):
    held = launch.held
    def broken(**kwargs):
        held.update(kwargs)
        raise RuntimeError('SENSITIVE_SENTINEL')
    if where == 'composition': monkeypatch.setattr('app.bootstrap.create_app', broken)
    elif where == 'not_started': launch.server.started = False
    else:
        def fail(self, **kwargs): raise RuntimeError('SENSITIVE_SENTINEL')
        monkeypatch.setattr(launch.server, 'run', fail)
    assert local_server.main(launch.args + ['--enable-llm']) == 1
    assert held['llm_local_context'].listener.fileno() == -1
    assert 'SENSITIVE_SENTINEL' not in str(capsys.readouterr())


def test_opt_in_does_not_change_provisioning_gate(launch, monkeypatch):
    gate = object()
    engine = Mock()
    monkeypatch.setattr('app.infrastructure.persistence.database.build_engine', lambda config: engine)
    verified = Mock(return_value=gate)
    monkeypatch.setattr(local_server, 'verified_local_gate', verified)
    assert local_server.main(launch.args + ['--enable-llm', '--enable-initial-provisioning']) == 0
    assert launch.held['administrative_provisioning_gate'] is gate
    assert verified.call_args.args[2] is launch.held['served']
    engine.dispose.assert_called_once()


def test_failed_provisioning_verification_disposes_engine_and_socket(launch, monkeypatch):
    engine = Mock()
    captured = []
    def rejected(config, database, listener, engine):
        captured.append(listener)
        raise RuntimeError('SENSITIVE_SENTINEL')
    monkeypatch.setattr('app.infrastructure.persistence.database.build_engine', lambda config: engine)
    monkeypatch.setattr(local_server, 'verified_local_gate', rejected)
    assert local_server.main(launch.args + ['--enable-llm', '--enable-initial-provisioning']) == 1
    engine.dispose.assert_called_once()
    assert captured[0].fileno() == -1
    assert not launch.held


@pytest.mark.parametrize('observe', [False, True])
def test_observation_cli_explicit_independent_and_not_inherited(launch, monkeypatch, observe):
    monkeypatch.setenv('LLM_OBSERVE', 'true')
    monkeypatch.setenv('TEST_LLM_OBSERVE', 'true')
    args = launch.args + ['--enable-llm'] + (['--observe-llm'] if observe else [])
    assert local_server.main(args) == 0
    assert launch.held['llm_observe'] is observe
    assert launch.held['administrative_provisioning_gate'] is None


@pytest.mark.parametrize('environment,enable', [('local-development',False),('production',True),('test',True)])
def test_observer_unsafe_cli_rejected_before_secrets(monkeypatch, environment, enable):
    load = Mock(side_effect=AssertionError('No secrets'))
    monkeypatch.setattr('app.infrastructure.configuration.database.load_database_config', load)
    args = ['--environment',environment,'--observe-llm'] + (['--enable-llm'] if enable else [])
    with pytest.raises(SystemExit): local_server.main(args)
    load.assert_not_called()
