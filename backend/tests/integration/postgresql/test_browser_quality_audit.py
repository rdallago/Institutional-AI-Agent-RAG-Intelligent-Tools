"""Auditoría de interfaz real con datos ficticios y barrera cerrada."""
import shutil
import socket
import subprocess
import threading
import time
from pathlib import Path

import pytest
import uvicorn

from test_browser_password_flow import browser_resources  # noqa: F401
from auth_support import PASSWORD, auth_config, bootstrap_login, build_auth
from app.bootstrap import create_app
from app.domain.auth.models import Credencial
from app.domain.usuarios.email import Email
from app.domain.usuarios.rol import Rol
from app.domain.usuarios.usuario import Usuario
from app.infrastructure.security.postgres import PostgresSecurityUnitOfWork

ROOT = Path(__file__).resolve().parents[4]
BROWSERS = {
    'chrome': 'C:/Program Files/Google/Chrome/Application/chrome.exe',
    'edge': 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
    'firefox': 'C:/Program Files/Mozilla Firefox/firefox.exe',
}
pytestmark = pytest.mark.postgres


@pytest.mark.parametrize('browser', list(BROWSERS))
def test_browser_quality(browser_resources, browser):
    executable = BROWSERS[browser]
    if not Path(executable).is_file() or not shutil.which('node'):
        pytest.skip('Navegador/Node no disponible; no se instala')
    (_, _, sessions), repository = browser_resources
    for port in (18002, 15174, 19191):
        with socket.socket() as probe:
            probe.bind(('127.0.0.1', port))
    factory = lambda: PostgresSecurityUnitOfWork(sessions)
    service = build_auth(factory, auth_config())
    _, token = bootstrap_login(service)
    service.logout(token)
    target = Usuario.crear(nombre='Historic', apellido='Quality', email=Email('quality-target@example.com'))
    pending = Usuario.crear(nombre='Pending', apellido='Quality', email=Email('quality-pending@example.com'), rol=Rol.ADMIN)
    now = service.clock()
    encoded = service.hasher.hash(PASSWORD)
    with factory() as uow:
        uow.usuarios.agregar(target)
        uow.usuarios.agregar(pending)
        uow.insert_initial_credential(Credencial(pending.id, encoded, now, now,
            debe_cambiar_password=True, password_inicial_hash=encoded))
    # Solo fixtures directas; no se sustituye ni abre la barrera.
    server = uvicorn.Server(uvicorn.Config(create_app(repository=repository, auth_service=service),
        host='127.0.0.1', port=18002, log_level='critical', access_log=False, proxy_headers=False))
    thread = threading.Thread(target=server.run, daemon=True)
    frontend = None
    try:
        thread.start()
        for _ in range(100):
            if server.started:
                break
            time.sleep(.1)
        assert server.started
        frontend = subprocess.Popen([shutil.which('node'), '--input-type=module', '-e',
            "import {createServer} from 'vite'; const s=await createServer({server:{host:'127.0.0.1',port:15174,strictPort:true,proxy:{'/api':{target:'http://127.0.0.1:18002'}}}}); await s.listen();"],
            cwd=ROOT / 'frontend', stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW)
        result = subprocess.run([shutil.which('node'), str(Path(__file__).with_name('browser_quality_audit.mjs')),
            browser, executable, str(target.id)], cwd=ROOT / 'frontend', capture_output=True,
            text=True, timeout=180, creationflags=subprocess.CREATE_NO_WINDOW)
        assert result.returncode == 0, result.stdout + result.stderr
        assert 'QUALITY_OK' in result.stdout
        from app.application.auth.provisioning import require_initial_provisioning_enabled
        from app.application.auth.exceptions import AprovisionamientoNoHabilitado
        with pytest.raises(AprovisionamientoNoHabilitado):
            require_initial_provisioning_enabled()
        with factory() as uow:
            assert uow.credential(target.id) is None
    finally:
        if frontend is not None:
            frontend.terminate()
            frontend.wait(timeout=15)
        server.should_exit = True
        thread.join(timeout=15)
        assert not thread.is_alive()
