"""Chrome real -> Vite -> FastAPI -> PostgreSQL; sin MSW ni secretos reales."""
import shutil
import socket
import subprocess
import threading
import time
from pathlib import Path

import pytest
import uvicorn
from sqlalchemy import text

from auth_support import auth_config, bootstrap_login, build_auth
from app.bootstrap import create_app
from app.domain.usuarios.email import Email
from app.domain.usuarios.usuario import Usuario
from app.infrastructure.configuration.database import load_database_config
from app.infrastructure.persistence.database import build_engine
from app.infrastructure.security.postgres import PostgresSecurityUnitOfWork
from postgres_support import require_test_connection

pytestmark = pytest.mark.postgres
ROOT = Path(__file__).resolve().parents[4]
CHROME = Path('C:/Program Files/Google/Chrome/Application/chrome.exe')


@pytest.fixture
def browser_resources(request):
    # Comprobar revisión ANTES de las fixtures que migran o limpian pruebas.
    config = load_database_config(testing=True)
    config.require_test_database()
    assert config.host == '127.0.0.1'
    engine = build_engine(config)
    try:
        with engine.connect() as connection:
            require_test_connection(connection, config)
            assert connection.execute(text('SELECT version_num FROM public.alembic_version')).scalar_one() == '0003'
    finally:
        engine.dispose()
    resources = request.getfixturevalue('postgres_resources')
    repository = request.getfixturevalue('postgres_repository')
    return resources, repository


@pytest.mark.parametrize('enabled', [False, True], ids=['closed-gate', 'isolated-positive'])
def test_real_browser_password_flow(request, browser_resources, enabled):
    if not CHROME.is_file() or not shutil.which('node'):
        pytest.skip('Requiere Chrome y Node ya instalados; no instala herramientas')
    (config, engine, sessions), postgres_repository = browser_resources
    config.require_test_database()
    with engine.connect() as connection:
        require_test_connection(connection, config)
        assert connection.execute(text('SELECT version_num FROM public.alembic_version')).scalar_one() == '0003'
    # No reemplazar ni detener servicios ajenos.
    for port in (18001, 15173):
        with socket.socket() as probe:
            probe.bind(('127.0.0.1', port))
    if enabled:
        request.getfixturevalue('initial_provisioning_test_gate')
    factory = lambda: PostgresSecurityUnitOfWork(sessions)
    service = build_auth(factory, auth_config())
    _, seed_token = bootstrap_login(service)
    service.logout(seed_token)  # El navegador inicia su propia sesión, no reutiliza la del helper.
    target = Usuario.crear(nombre='Historic', apellido='Browser', email=Email('historic-browser@example.com'))
    with factory() as uow:
        uow.usuarios.agregar(target)
    app = create_app(repository=postgres_repository, auth_service=service)
    server = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=18001,
        access_log=False, log_level='critical', proxy_headers=False))
    thread = threading.Thread(target=server.run, daemon=True)
    frontend = None
    try:
        thread.start()
        for _ in range(100):
            if server.started:
                break
            time.sleep(.1)
        assert server.started, 'FastAPI aislado no disponible'
        frontend = subprocess.Popen([shutil.which('node'), '--input-type=module', '-e',
            "import {createServer} from 'vite'; const s=await createServer({server:{host:'127.0.0.1',port:15173,strictPort:true,proxy:{'/api':{target:'http://127.0.0.1:18001'}}}}); await s.listen();"],
            cwd=ROOT / 'frontend', stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW)
        result = subprocess.run([shutil.which('node'), str(Path(__file__).with_name('browser_password_flow.mjs')),
            'positive' if enabled else 'closed', str(target.id)], cwd=ROOT / 'frontend',
            capture_output=True, text=True, timeout=150, creationflags=subprocess.CREATE_NO_WINDOW)
        # El helper nunca imprime cuerpos HTTP, valores de inputs, tokens o hashes.
        assert result.returncode == 0, result.stdout + result.stderr
        assert 'REAL_BROWSER_OK' in result.stdout
        with factory() as uow:
            credential = uow.credential(target.id)
            if enabled:
                assert credential is not None and not credential.debe_cambiar_password
                assert service.hasher.verify(credential.password_hash, 'browser-definitive-password-2026')
                assert credential.password_inicial_hash is not None
                created = uow.usuarios.obtener_por_email(Email('created-browser@example.com'))
                assert created is not None and created.activo
                created_credential = uow.credential(created.id)
                assert created_credential is not None and not created_credential.debe_cambiar_password
                assert service.hasher.verify(created_credential.password_hash, 'browser-definitive-password-2026')
                assert service.hasher.verify(created_credential.password_inicial_hash, 'browser-initial-password-2026')
                assert service.hasher.verify(credential.password_inicial_hash, 'browser-initial-password-2026')
            else:
                assert credential is None
                assert uow.usuarios.obtener_por_email(Email('created-browser@example.com')) is None
        if enabled:
            with engine.connect() as connection:
                require_test_connection(connection, config)
                assert connection.execute(text('SELECT count(*) FROM public.auth_sesiones WHERE revocada_at IS NULL')).scalar_one() == 0
    finally:
        if frontend is not None:
            frontend.terminate()
            frontend.wait(timeout=15)
        server.should_exit = True
        thread.join(timeout=15)
        assert not thread.is_alive()
