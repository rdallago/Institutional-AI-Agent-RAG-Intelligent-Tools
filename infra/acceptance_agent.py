"""Cliente HTTP local de aceptación. No se ejecuta al importar.

Credenciales y tokens solo en memoria. No importa ni invoca el agente.
Ejecutar con backend/.venv/Scripts/python.exe desde la raíz del proyecto.
"""
from __future__ import annotations

import argparse
import ctypes
from dataclasses import dataclass
from datetime import datetime, timezone
import getpass
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener, ProxyHandler, HTTPRedirectHandler
from uuid import UUID, uuid4
import warnings

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend' / 'src'))
API = 'http://127.0.0.1:8000/api/v1'
VERSION = '7cb4e79c-747d-574a-8abb-0ebcb2e07636'
DOCUMENT = '8ac0c745-1307-5bb4-9d56-93dfbee0b3b8'
MIN_GIB = 1.5
MAX_BODY = 1_048_576
SECRET = re.compile(r'(?i)bearer\s+\S+|eyJ[\w-]+\.[\w-]+\.[\w-]+|sk-[\w-]{16,}|'
                    r'(?:password|contrase[nñ]a|access_token|refresh_token|api[_ -]?key)\s*[=:]\s*\S+')


class Stop(Exception):
    """Mensaje público controlado; nunca incluye cuerpos HTTP ni excepciones upstream."""


def safe(value):
    if isinstance(value, str):
        return SECRET.sub('[SECRETO OMITIDO]', value)
    if isinstance(value, list):
        return [safe(v) for v in value]
    if isinstance(value, dict):
        return {k: safe(v) for k, v in value.items()
                if k.lower() not in {'password', 'access_token', 'refresh_token', 'authorization'}}
    return value


def create_private_windows(path: Path):
    """Crear con DACL protegida desde el primer instante, sin mkdir(0700) de Python."""
    from ctypes import wintypes
    ps = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command',
        '[System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value'],
        capture_output=True, text=True, timeout=5, creationflags=subprocess.CREATE_NO_WINDOW)
    sid = ps.stdout.strip()
    if ps.returncode or not re.fullmatch(r'S-1-5-[0-9-]+', sid):
        raise Stop('No se pudo identificar al propietario del directorio privado.')
    class SecurityAttributes(ctypes.Structure):
        _fields_ = [('length', wintypes.DWORD), ('descriptor', ctypes.c_void_p),
                    ('inherit_handle', wintypes.BOOL)]
    security = ctypes.WinDLL('advapi32', use_last_error=True)
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    convert = security.ConvertStringSecurityDescriptorToSecurityDescriptorW
    convert.argtypes = [wintypes.LPCWSTR, wintypes.DWORD,
                        ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(wintypes.DWORD)]
    convert.restype = wintypes.BOOL
    kernel.CreateDirectoryW.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(SecurityAttributes)]
    kernel.CreateDirectoryW.restype = wintypes.BOOL
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    descriptor = ctypes.c_void_p()
    sddl = f'O:{sid}D:P(A;OICI;FA;;;{sid})(A;OICI;FA;;;SY)'
    if not convert(sddl, 1, ctypes.byref(descriptor), None):
        raise Stop('No se pudo construir la ACL privada.')
    try:
        attributes = SecurityAttributes(ctypes.sizeof(SecurityAttributes), descriptor.value, False)
        if not kernel.CreateDirectoryW(str(path.absolute()), ctypes.byref(attributes)):
            code = ctypes.get_last_error()
            raise Stop(f'No se pudo crear el directorio privado {path.absolute()} (Win32 {code}).')
    finally:
        kernel.LocalFree(descriptor)


def permission_rejection(path: Path):
    """Solo ruta y metadatos ACL; sin contenido ni excepciones arbitrarias."""
    if path.is_symlink() or (hasattr(path, 'is_junction') and path.is_junction()):
        return 'enlace o junction no permitido'
    if not path.is_dir():
        return 'no es un directorio existente accesible'
    if os.name != 'nt':
        return 'propietario distinto o permisos de grupo/otros habilitados'
    script = ('$ErrorActionPreference="Stop"; $a=Get-Acl -LiteralPath $env:ACCEPTANCE_ACL_PATH; '
              '$o=$a.GetOwner([System.Security.Principal.SecurityIdentifier]).Value; '
              '$extra=@($a.GetAccessRules($true,$true,[System.Security.Principal.SecurityIdentifier])|'
              'Where-Object {$_.AccessControlType -eq "Allow" -and '
              '$_.IdentityReference.Value -notin @($o,"S-1-5-18")}|'
              'ForEach-Object {$_.IdentityReference.Value}|Select-Object -Unique); '
              '@{protected=$a.AreAccessRulesProtected;owner=$o;extra=$extra}|ConvertTo-Json -Compress')
    try:
        ps = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', script],
            env=dict(os.environ, ACCEPTANCE_ACL_PATH=str(path.absolute())), capture_output=True,
            text=True, timeout=5, creationflags=subprocess.CREATE_NO_WINDOW)
        if ps.returncode:
            return 'no se pudo leer la ACL'
        data = json.loads(ps.stdout)
        reasons = []
        if not data['protected']:
            reasons.append('herencia activa')
        if data['extra']:
            reasons.append('identidades no permitidas: ' + ', '.join(data['extra']))
        return '; '.join(reasons) or 'el comprobador ACL no pudo confirmar los permisos'
    except Exception:
        return 'diagnóstico de ACL no disponible'


def private_directory(path: Path, *, create=False):
    from app.application.agent.diagnostics import restricted_directory
    if create:
        if os.name == 'nt':
            create_private_windows(path)
        else:
            path.mkdir(mode=0o700, exist_ok=False)
    if not restricted_directory(path):
        raise Stop(f'Directorio privado rechazado: {path.absolute()}; {permission_rejection(path)}.')


def available_gib():
    if os.name != 'nt':
        raise Stop('La medición de recursos de este cliente requiere Windows.')
    class Status(ctypes.Structure):
        _fields_ = [('length', ctypes.c_ulong), ('load', ctypes.c_ulong),
                   *[(name, ctypes.c_ulonglong) for name in (
                       'total', 'available', 'page_total', 'page_available',
                       'virtual_total', 'virtual_available', 'extended')]]
    status = Status()
    status.length = ctypes.sizeof(status)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        raise Stop('No se pudo medir la memoria física.')
    return status.available / 1024**3


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


@dataclass
class Reply:
    status: int
    data: object
    seconds: float


class HTTP:
    def __init__(self):
        self.opener = build_opener(ProxyHandler({}), NoRedirect())

    def request(self, method, path, token=None, body=None, *, base=API):
        if base not in {API, 'http://127.0.0.1:11434'} or not path.startswith('/'):
            raise Stop('Destino HTTP no permitido.')
        headers = {'Accept': 'application/json'}
        if token:
            headers['Authorization'] = 'Bearer ' + token
        encoded = None
        if body is not None:
            headers['Content-Type'] = 'application/json'
            encoded = json.dumps(body, ensure_ascii=False).encode('utf-8')
        request = Request(base + path, data=encoded, method=method, headers=headers)
        start = time.monotonic()
        try:
            try:
                response = self.opener.open(request, timeout=70)
            except HTTPError as error:
                response = error
            with response:
                raw = response.read(MAX_BODY + 1)
                if len(raw) > MAX_BODY:
                    raise Stop('Respuesta HTTP demasiado grande; resultado incierto, sin reintento.')
                try:
                    data = json.loads(raw) if raw else None
                except (ValueError, UnicodeError):
                    data = None
                return Reply(response.code, data, time.monotonic() - start)
        except (URLError, TimeoutError, OSError):
            raise Stop('Transporte interrumpido o timeout; no se repetirá la solicitud.') from None


class Account:
    def __init__(self, alias, role):
        self.alias, self.role, self.user_id = alias, role, None
        self.token = None

    def login(self, http, read_secret=getpass.getpass):
        # Fallar en lugar de mostrar la contraseña si no existe consola privada.
        with warnings.catch_warnings():
            warnings.simplefilter('error', getpass.GetPassWarning)
            email = read_secret(f'{self.alias}: email (entrada oculta): ').strip()
            password = read_secret(f'{self.alias}: contraseña (entrada oculta): ')
        try:
            reply = http.request('POST', '/auth/login', body={'email': email, 'password': password})
        finally:
            password = None
        if reply.status != 200 or not isinstance(reply.data, dict):
            raise Stop(f'Login {self.alias} rechazado (HTTP {reply.status}); no se reintenta.')
        token = reply.data.get('access_token')
        restricted = reply.data.get('debe_cambiar_password') is not False
        reply.data.clear()  # No conservar la respuesta de autenticación.
        if not isinstance(token, str):
            raise Stop('Contrato de login inválido.')
        self.token = token
        if restricted:
            raise Stop(f'{self.alias} requiere cambio de contraseña; este cliente no lo realiza.')
        me = http.request('GET', '/auth/me', self.token)
        data = me.data if isinstance(me.data, dict) else {}
        if (me.status != 200 or data.get('rol') != self.role
                or data.get('email', '').casefold() != email.casefold()
                or data.get('activo') is not True or data.get('debe_cambiar_password') is not False):
            raise Stop(f'Identidad o rol de {self.alias} no coincide con /auth/me.')
        identity = str(UUID(data['id']))
        if self.user_id is not None and identity != self.user_id:
            raise Stop('La reanudación debe utilizar la misma identidad original.')
        self.user_id = identity

    def logout(self, http):
        if not self.token:
            return
        try:
            reply = http.request('POST', '/auth/logout', self.token)
            if reply.status != 204:
                raise Stop(f'Logout {self.alias} no confirmado (HTTP {reply.status}).')
        finally:
            self.token = None


RAG = '¿Cuáles son las funciones del Rectorado según el Reglamento Orgánico Marco?'
MEMORY = '¿Sobre qué órgano del Reglamento Orgánico Marco te pregunté anteriormente?'
WEATHER = '¿Cómo está el clima en Esquina, Corrientes, Argentina?'


def matrix():
    # id, identidad, conversación lógica, pregunta, canal, dependencia.
    return [
        ('A1', 'ADMIN', 'academica', RAG, 'RAG', None),
        ('A2', 'ADMIN', 'academica', '¿Y cuáles son los requisitos para concursar las coordinaciones de carrera?', 'RAG', 'A1'),
        ('B1', 'ADMIN', 'memoria', RAG, 'RAG', None),
        ('B2', 'ADMIN', 'memoria', MEMORY, 'MEMORIA', 'B1'),
        ('C1', 'ADMIN', 'clima', WEATHER, 'CLIMA', None),
        ('C2', 'ADMIN', 'clima', '¿Y cómo estará mañana?', 'CLIMA', 'C1'),
        ('D1', 'ADMIN', 'general', '¿Qué es una API REST y para qué sirve?', 'GENERAL', None),
        ('D2', 'ADMIN', 'general', '¿Podés darme un ejemplo de una API REST con Python y FastAPI?', 'GENERAL', 'D1'),
        ('E1', 'ADMIN', 'alternancia', RAG, 'RAG', None),
        ('E2', 'ADMIN', 'alternancia', WEATHER, 'CLIMA', 'E1'),
        ('E3', 'ADMIN', 'alternancia', '¿Qué es una API REST?', 'GENERAL', 'E2'),
        ('E4', 'ADMIN', 'alternancia', 'Volviendo al reglamento, ¿qué establece el artículo 24 sobre el Rectorado?', 'RAG', 'E3'),
        ('U1', 'COMUN', 'propia', RAG, 'RAG', None),
        ('U2', 'COMUN', 'propia', '¿Qué es una API REST?', 'GENERAL', None),
        ('U3', 'COMUN', 'propia', MEMORY, 'MEMORIA', 'U1'),
    ]


def classify(reply, expected):
    if reply.status != 200:
        data = reply.data if isinstance(reply.data, dict) else {}
        error = data.get('error', {})
        code = error.get('codigo') if isinstance(error, dict) else None
        return ('BLOQUEADO' if reply.status in {401, 429, 503, 504} else 'FALLIDO',
                f'HTTP {reply.status}; código={code if isinstance(code, str) else "no disponible"}')
    data = reply.data if isinstance(reply.data, dict) else {}
    result = data.get('resultado', {})
    if (not isinstance(result, dict) or not isinstance(result.get('respuesta'), str)
            or not isinstance(result.get('fuentes'), list)):
        return 'FALLIDO', 'Contrato de turno inválido.'
    strategy, status, text = result.get('estrategia'), result.get('estado'), result['respuesta']
    if expected == 'RAG':
        ok = strategy == 'RAG' and status == 'FUNDAMENTADA' and bool(result['fuentes'])
        ok = ok and all(isinstance(f, dict) and isinstance(f.get('id'), str)
                       and re.fullmatch(r'F[1-3]', f['id'])
                       and f'[{f["id"]}]' in text and isinstance(f.get('pagina'), int)
                       and f['pagina'] > 0
                       for f in result['fuentes'])
    elif expected == 'CLIMA':
        ok = strategy == 'TOOL' and status == 'HERRAMIENTA' and data.get('herramienta') == 'consultar_clima'
    elif expected == 'MEMORIA':
        ok = strategy == 'LLM_DIRECTO' and status == 'GENERADA' and 'rectorado' in text.casefold()
    else:
        ok = strategy == 'LLM_DIRECTO' and status == 'GENERADA' and bool(text.strip())
    return ('APROBADO', 'Contrato, canal y criterio automático satisfechos; revisar calidad/cobertura del texto.') if ok else (
        'FALLIDO', f'Canal/estado/respuesta no satisface el criterio: {strategy}/{status}.')


def history_fingerprint(history):
    if not isinstance(history, list):
        raise Stop('Contrato de historial inválido.')
    return hashlib.sha256(json.dumps(history, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def database_snapshot(conversations=()):
    """Solo metadatos de la versión y conversaciones creadas por esta ejecución."""
    from sqlalchemy import create_engine, text
    from app.infrastructure.configuration.database import load_database_config
    config = load_database_config()
    if (config.host, config.port, config.database) != ('127.0.0.1', 5434, 'usuarios_dev'):
        raise Stop('La configuración no corresponde a usuarios_dev local.')
    engine = create_engine(config.url(), hide_parameters=True, connect_args={
        'connect_timeout': 3, 'options': '-c default_transaction_read_only=on -c statement_timeout=3000'})
    try:
        with engine.connect() as connection:
            assert connection.execute(text('SHOW transaction_read_only')).scalar_one() == 'on'
            row = connection.execute(text('''SELECT v.id::text version,v.estado,
                (SELECT count(*) FROM rag_fragmentos f WHERE f.version_id=v.id) fragments,
                (SELECT count(*) FROM rag_embeddings e JOIN rag_fragmentos f ON f.id=e.fragmento_id
                 WHERE f.version_id=v.id) embeddings FROM rag_documentos d
                JOIN rag_versiones v ON v.id=d.activa_version_id WHERE d.id=:document'''),
                {'document': DOCUMENT}).mappings().one()
            if (row['version'], row['estado'], row['fragments'], row['embeddings']) != (VERSION, 'LISTA', 432, 432):
                raise Stop('Versión o conteos documentales distintos de los esperados.')
            counts = []
            for item in conversations:
                found = connection.execute(text('''SELECT propietario_id::text owner,
                    (SELECT count(*) FROM agent_mensajes m WHERE m.conversacion_id=c.id) messages,
                    (SELECT count(*) FROM agent_solicitudes r WHERE r.conversacion_id=c.id AND r.estado='COMPLETA') complete,
                    (SELECT count(*) FROM agent_solicitudes r WHERE r.conversacion_id=c.id AND r.estado='PENDIENTE') pending,
                    (SELECT count(*) FROM agent_solicitudes r WHERE r.conversacion_id=c.id AND r.estado='FALLIDA') failed
                    FROM agent_conversaciones c WHERE c.id=:id'''), {'id': item['id']}).mappings().one()
                if found['owner'] != item['owner']:
                    raise Stop('Propietario inesperado en una conversación de prueba.')
                if 'message_count' in item and found['messages'] != item['message_count']:
                    raise Stop('El conteo PostgreSQL no coincide con el historial HTTP.')
                counts.append({'conversation': item['id'], **{key: found[key] for key in (
                    'messages', 'complete', 'pending', 'failed')}})
            connection.rollback()
            return {'database': 'usuarios_dev', **dict(row), 'conversations': counts}
    finally:
        engine.dispose()


def associated_diagnostics(directory, request_id):
    if directory is None:
        return []
    private_directory(directory)
    records = []
    for path in sorted(directory.glob('agent-private-*.json'))[:64]:
        if path.is_symlink() or path.stat().st_size > 32768:
            continue
        value = json.loads(path.read_text(encoding='utf-8'))
        if value.get('request_id') == request_id:
            # No duplicar literal_json ni argumentos personales en el informe.
            records.append({'file': str(path), **{key: value[key] for key in (
                'event', 'trace', 'stage', 'json_valid', 'generated', 'accepted',
                'rejected', 'outcome', 'claims', 'sources', 'reason', 'match_count', 'rules') if key in value}})
    return records


class Run:
    def __init__(self, path, state, http, *, memory=available_gib, diagnostics=None):
        self.path, self.state, self.http = path, state, http
        self.memory, self.diagnostics = memory, diagnostics
        self.accounts = {alias: Account(alias, role) for alias, role in [('ADMIN', 'ADMIN'), ('COMUN', 'USUARIO')]}
        for alias, identity in state.get('identities', {}).items():
            self.accounts[alias].user_id = identity['id']

    def save(self):
        counts = {}
        for row in self.state['results'].values():
            status = row.get('status', 'NO EVALUADO')
            counts[status] = counts.get(status, 0) + 1
        self.state['summary'] = {'counts': counts,
            'acceptance': 'REVISIÓN HUMANA PENDIENTE: los aprobados automáticos son técnicos',
            'real_qwen_calls': 'No observable mediante el contrato HTTP; no estimar como conteo real'}
        payload = json.dumps(safe(self.state), ensure_ascii=False, indent=2)
        if len(payload.encode('utf-8')) > 2_000_000:
            raise Stop('Informe excede el límite privado de 2 MB.')
        temporary = self.path.with_name('checkpoint-' + uuid4().hex + '.tmp')
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, 'w', encoding='utf-8') as output:
            output.write(payload)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, self.path)

    def record(self, key, **values):
        self.state['results'][key] = safe(values)
        self.save()

    def authenticate(self):
        for alias, account in self.accounts.items():
            account.login(self.http)
            self.state['identities'][alias] = {'id': account.user_id, 'role': account.role}
            self.save()
        if self.accounts['ADMIN'].user_id == self.accounts['COMUN'].user_id:
            raise Stop('Se requieren dos identidades distintas.')

    def catalog(self):
        for alias, account in self.accounts.items():
            reply = self.http.request('GET', '/ia/documentos', account.token)
            if reply.status != 200 or not isinstance(reply.data, list):
                raise Stop('No se pudo verificar el catálogo documental autorizado.')
            self.state.setdefault('document_access', {})[alias] = any(
                isinstance(v, dict) and v.get('id') == DOCUMENT for v in reply.data)
        self.save()

    def conversation(self, alias, label):
        key = alias + ':' + label
        if key not in self.state['conversations']:
            self.state['conversations'][key] = {'id': str(uuid4()), 'owner': self.accounts[alias].user_id,
                'label': f'ACEPTACION {self.state["run_id"][:8]} {key}', 'created': False}
            self.save()  # UUID persistido ANTES de la creación idempotente.
        entry = self.state['conversations'][key]
        if not entry['created']:
            result = self.http.request('POST', '/ia/conversaciones', self.accounts[alias].token,
                                       {'conversacion_id': entry['id']})
            if result.status != 200 or result.data != {'id': entry['id']}:
                raise Stop(f'Creación de conversación rechazada (HTTP {result.status}).')
            entry['created'] = True
            self.save()
        return entry['id']

    def resource_check(self, expected='RAG'):
        remote = self.state.get('provider', 'ollama') == 'openrouter'
        cloud = self.state.get('embedding_provider') == 'jina'
        minimum = (1.0 if expected == 'RAG' and not cloud else .25) if remote else MIN_GIB
        before = self.memory()
        if before < minimum:
            raise Stop(f'RAM insuficiente: {before:.3f} GiB; mínimo {minimum:.2f} GiB; proveedor={self.state.get("provider", "ollama")}.')
        if not remote or (expected == 'RAG' and not cloud):
            ps = self.http.request('GET', '/api/ps', base='http://127.0.0.1:11434')
            if ps.status != 200 or not isinstance(ps.data, dict) or ps.data.get('models') != []:
                raise Stop('Ollama no está idle o no se pudo verificar; no se cargan modelos en paralelo.')
        # Medición fresca inmediatamente antes del POST que puede inferir.
        before = self.memory()
        if before < minimum:
            raise Stop(f'RAM cayó a {before:.3f} GiB antes del envío.')
        return before

    def turn(self, spec):
        key, alias, label, question, expected, dependency = spec
        previous = self.state['results'].get(key)
        if (previous and previous.get('status') != 'NO EVALUADO'
                and (previous.get('request_id') or previous.get('status') != 'BLOQUEADO')):
            # INFLIGHT nunca se reenvía: ni siquiera se intenta replay por POST.
            return
        if dependency and self.state['results'].get(dependency, {}).get('status') != 'APROBADO':
            self.record(key, status='BLOQUEADO', reason='Antecedente requerido no aprobado.',
                        user=alias, question=question, expected=expected)
            return
        if expected == 'RAG' and self.state.get('document_access', {}).get(alias) is False:
            self.record(key, status='BLOQUEADO', reason='El ROM no figura en el catálogo autorizado; no se cambian ACL.',
                        user=alias, question=question, expected=expected)
            return
        remaining = 13 - (time.time() - self.state.get('last_post_at', 0))
        if remaining > 0:
            time.sleep(min(13, remaining))  # Espaciado preventivo; nunca reintento de una solicitud.
        try:
            before = self.resource_check(expected)
        except Stop as error:
            self.record(key, status='BLOQUEADO', reason=str(error), user=alias,
                        question=question, expected=expected)
            self.state['resources_blocked'] = True
            self.save()
            return
        conversation = self.conversation(alias, label)
        request_id = str(uuid4())
        row = dict(user=alias, role=self.accounts[alias].role, conversation=conversation,
                   question=question, expected=expected, request_id=request_id, ram_before_gib=before)
        self.record(key, **row, status='INFLIGHT', reason='Envío iniciado; no repetir si se interrumpe.')
        self.state['last_post_at'] = time.time()
        self.save()
        try:
            reply = self.http.request('POST', f'/ia/conversaciones/{conversation}/mensajes',
                self.accounts[alias].token, {'prompt': question, 'modo': 'AUTO', 'solicitud_id': request_id})
        except Stop:
            self.record(key, **row, status='BLOQUEADO', uncertain=True,
                        reason='Transporte interrumpido; resultado incierto. No reenviar.')
            raise
        status, reason = classify(reply, expected)
        result = reply.data.get('resultado', {}) if isinstance(reply.data, dict) else {}
        if status == 'APROBADO' and expected == 'RAG':
            expected_pages = {32, 33, 34} if key == 'A2' else {11, 12}
            if not any(f['pagina'] in expected_pages for f in result['fuentes']):
                status, reason = 'FALLIDO', 'Las páginas citadas no corresponden al apartado esperado.'
        if reply.status == 200 and (reply.data.get('conversacion_id') != conversation
                                   or reply.data.get('solicitud_id') != request_id):
            raise Stop('Identificadores de respuesta no coinciden; detener batería.')
        try:
            diagnostics = associated_diagnostics(self.diagnostics, request_id)
        except Exception:
            diagnostics = [{'unavailable': 'No se pudo leer el diagnóstico privado; no inferir causas.'}]
        if not isinstance(result, dict):
            result = {}
        after = self.memory()
        self.record(key, **row, status=status, reason=reason, http=reply.status,
            seconds=reply.seconds, ram_after_gib=after, actual=result.get('estrategia'),
            tool=reply.data.get('herramienta') if isinstance(reply.data, dict) else None,
            response=result.get('respuesta'), state=result.get('estado'), sources=result.get('fuentes'),
            diagnostics=diagnostics, selection_source='NO EVALUADO: no expuesto por HTTP',
            semantic_review='PENDIENTE: revisar texto, cobertura y atribución',
            qwen_calls='NO DETERMINABLE solo mediante el contrato HTTP')
        print(f'{key}: {status}; HTTP {reply.status}; {reply.seconds:.2f} s; RAM {after:.3f} GiB')
        if reply.status in {401, 403} and expected != 'RAG':
            raise Stop('Autenticación/autorización inesperada; batería detenida.')
        if after < (.25 if self.state.get('provider') == 'openrouter' else MIN_GIB):
            self.state['resources_blocked'] = True
            self.save()

    def safety_and_snapshot(self, phase):
        for alias, account in self.accounts.items():
            listing = self.http.request('GET', '/ia/conversaciones', account.token)
            if listing.status != 200 or not isinstance(listing.data, list):
                raise Stop('No se pudo listar conversaciones autenticadas.')
            listed = {v['id'] for v in listing.data}
            own = [v for k, v in self.state['conversations'].items() if k.startswith(alias+':') and v['created']]
            foreign = [v for k, v in self.state['conversations'].items() if not k.startswith(alias+':') and v['created']]
            if any(v['id'] in listed for v in foreign) or any(v['id'] not in listed for v in own):
                raise Stop('Aislamiento/listado inconsistente; fallo crítico.')
            for item in own:
                history = self.http.request('GET', f'/ia/conversaciones/{item["id"]}/mensajes', account.token)
                if history.status != 200:
                    raise Stop('No se pudo recuperar un historial propio de prueba.')
                fingerprint = history_fingerprint(history.data)
                old = item.get('history_hash')
                if old is not None and fingerprint != old:
                    raise Stop('El historial cambió tras logout/reinicio; revisar persistencia.')
                if phase == 'before_logout':
                    item['history_hash'] = fingerprint
                    item['message_count'] = len(history.data)
                self.record(f'{phase}:{alias}:{item["id"]}', user=alias, conversation=item['id'],
                            status='APROBADO', http=200, messages=len(history.data), hash=fingerprint)
            for item in foreign:
                response = self.http.request('GET', f'/ia/conversaciones/{item["id"]}/mensajes', account.token)
                # Contrato actual: PermisoDenegado -> 403.
                self.record(f'{phase}:cross:{alias}:{item["id"]}', user=alias,
                            conversation=item['id'], status='APROBADO' if response.status == 403 else 'FALLIDO',
                            http=response.status, reason='Acceso cruzado: se espera 403.')
                if response.status != 403:
                    raise Stop('Acceso cruzado no rechazado según contrato; detener batería.')
        self.state['database_' + phase] = database_snapshot(
            [v for v in self.state['conversations'].values() if v['created']])
        self.save()


def backend_identity():
    """PID + creación, sin comandos ni entorno del proceso."""
    if os.name != 'nt':
        raise Stop('Reinicio verificable disponible solo en Windows.')
    command = ('$p=Get-NetTCPConnection -State Listen -LocalAddress 127.0.0.1 -LocalPort 8000; '
               '$x=Get-Process -Id $p.OwningProcess; '
               '$c=(Get-CimInstance Win32_Process -Filter ("ProcessId="+$x.Id)).CommandLine; '
               '@{pid=$x.Id;started=$x.StartTime.ToUniversalTime().ToString("o");'
               'local_launcher=($c.Contains("app.presentation.cli.local_server") -and '
               '$c.Contains("--environment local-development") -and $c.Contains("--enable-llm"));'
               'project=$c.Contains($env:ACCEPTANCE_PROJECT_ROOT)}|ConvertTo-Json -Compress')
    reply = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', command],
                           env=dict(os.environ, ACCEPTANCE_PROJECT_ROOT=str(ROOT)),
                           capture_output=True, text=True, timeout=8, creationflags=subprocess.CREATE_NO_WINDOW)
    if reply.returncode:
        raise Stop('No se pudo identificar el backend para comprobar su reinicio.')
    identity = json.loads(reply.stdout)
    if identity.get('local_launcher') is not True or identity.get('project') is not True:
        raise Stop('El puerto 8000 no corresponde al lanzador local esperado de este proyecto.')
    return identity


def exclusive_client():
    """Mutex sin archivos/secretos; Windows lo libera incluso si el cliente se interrumpe."""
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_wchar_p]
    kernel.CreateMutexW.restype = ctypes.c_void_p
    ctypes.set_last_error(0)
    handle = kernel.CreateMutexW(None, False, 'Local\\api-usuarios-clean-acceptance')
    if not handle or ctypes.get_last_error() == 183:
        if handle:
            kernel.CloseHandle.argtypes = [ctypes.c_void_p]
            kernel.CloseHandle(handle)
        raise Stop('Ya hay otro cliente de aceptación abierto, o no se pudo obtener exclusión.')
    return kernel, handle


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--resume', type=Path, help='informe.json de una ejecución anterior')
    parser.add_argument('--output-root', type=Path, default=ROOT / '.acceptance-private')
    parser.add_argument('--diagnostic-dir', type=Path, required=True)
    parser.add_argument('--initialize-only', action='store_true',
                        help='Crear/verificar informe privado y salir sin autenticación ni servicios.')
    args = parser.parse_args(argv)
    run = None
    mutex = None
    try:
        if not args.initialize_only and not sys.stdin.isatty():
            raise Stop('Ejecutar en una terminal interactiva; no redirigir credenciales.')
        if os.name != 'nt':
            raise Stop('Este cliente requiere Windows.')
        mutex = exclusive_client()
        private_directory(args.diagnostic_dir)
        if args.resume:
            if args.resume.is_symlink():
                raise Stop('Checkpoint no válido: enlace simbólico.')
            path = args.resume.resolve()
            if path.stat().st_size > 2_000_000:
                raise Stop('Checkpoint no válido.')
            private_directory(path.parent)
            state = json.loads(path.read_text(encoding='utf-8'))
            if state.get('schema') != 1:
                raise Stop('Versión de checkpoint desconocida.')
        else:
            if not args.output_root.exists():
                private_directory(args.output_root, create=True)
            private_directory(args.output_root)
            directory = args.output_root / ('run-' + uuid4().hex)
            private_directory(directory, create=True)
            path = directory / 'informe.json'
            state = {'schema': 1, 'run_id': str(uuid4()), 'created': datetime.now(timezone.utc).isoformat(),
                     'identities': {}, 'conversations': {}, 'results': {
                         s[0]: {'status': 'NO EVALUADO', 'user': s[1], 'question': s[3], 'expected': s[4]}
                         for s in matrix()}, 'phase': 'turns'}
        run = Run(path, state, HTTP(), diagnostics=args.diagnostic_dir)
        run.save()
        print(f'Informe/checkpoint privado: {path}')
        if args.initialize_only:
            private_directory(path.parent)
            print('INICIALIZACIÓN APROBADA: ACL privada verificada; sin autenticación, HTTP, SQL ni inferencias.')
            return 0
        state['preflight'] = database_snapshot()
        state['preflight_ram_gib'] = available_gib()
        from app.infrastructure.configuration.llm import LLMConfig, load_local_model, apply_provider_settings
        config = apply_provider_settings(LLMConfig(environment='local-development'))
        state['provider'] = config.provider
        state['configured_model'] = config.remote_model if config.provider == 'openrouter' else load_local_model()
        from app.infrastructure.configuration.embeddings import load_embedding_config
        embedding_config = load_embedding_config()
        state['embedding_provider'] = embedding_config.provider
        if embedding_config.provider == 'jina':
            if config.provider != 'openrouter':
                raise Stop('Ruta cloud requiere OpenRouter.')
            # Validar publicación sin embeddings ni HTTP de inferencia.
            from app.infrastructure.configuration.database import load_database_config
            from app.infrastructure.persistence.database import build_engine
            from sqlalchemy import text
            engine = build_engine(load_database_config())
            try:
                with engine.connect() as conn:
                    found = conn.execute(text('''SELECT count(*) FROM rag_cloud_activos a
                        JOIN rag_cloud_ingestas i USING(version_id,espacio_id)
                        JOIN rag_cloud_espacios s ON s.id=a.espacio_id
                        WHERE a.version_id=:v AND s.fingerprint=:fp AND i.estado='VALIDADA' '''),
                        {'v': VERSION, 'fp': embedding_config.space}).scalar_one()
                    if found != 1:
                        raise Stop('Espacio cloud no publicado; no iniciar aceptación.')
            finally:
                engine.dispose()
        else:
            tags = run.http.request('GET', '/api/tags', base='http://127.0.0.1:11434')
            required_model = 'nomic-embed-text:latest' if config.provider == 'openrouter' else 'qwen2.5:1.5b'
            if (tags.status != 200 or not isinstance(tags.data, dict)
                    or not any(v.get('name') == required_model for v in tags.data.get('models', []))):
                raise Stop('No se comprobó el modelo local requerido; no se descarga ningún modelo.')
        if config.provider == 'ollama' and load_local_model() != 'qwen2.5:1.5b':
            raise Stop('La configuración local no selecciona qwen2.5:1.5b.')
        state['runtime_model_evidence'] = 'No expuesto por HTTP; confirmar arranque local antes de iniciar.'
        state['backend_initial'] = backend_identity()
        run.save()
        run.authenticate()
        run.catalog()
        state['resources_blocked'] = False
        if state['phase'] == 'turns':
            if any(r.get('status') == 'INFLIGHT' or r.get('uncertain') for r in state['results'].values()):
                raise Stop('Existe un envío incierto anterior; revisar esa clave antes de continuar la batería.')
            for spec in matrix():
                if state['resources_blocked']:
                    break
                run.turn(spec)
            if state['resources_blocked']:
                raise Stop('Recursos insuficientes. Se conserva el progreso; no se reintenta ninguna inferencia.')
            if any(r.get('status') == 'INFLIGHT' or r.get('uncertain') for r in state['results'].values()):
                raise Stop('Existe una solicitud de resultado incierto; requiere revisión sin reenviarla.')
            state['phase'] = 'logout'
            run.save()
        if state['phase'] == 'logout':
            run.safety_and_snapshot('before_logout')
            for account in run.accounts.values():
                account.logout(run.http)
            run.authenticate()  # Credenciales solicitadas otra vez; nunca retenidas para re-login.
            run.safety_and_snapshot('after_login')
            state['phase'] = 'restart'
            run.save()
        if state['phase'] == 'restart':
            before = state.setdefault('restart_before', backend_identity())
            run.save()
            if backend_identity() == before:
                print('Reinicio MANUAL: solo FastAPI, Ctrl+C en su terminal/lanzador verificado.')
                print('Relanzar con las mismas opciones y variables privadas; no cambiar .env ni detener PostgreSQL.')
                if input('Escribí REINICIADO cuando esté operativo, o Enter para detener: ').strip() != 'REINICIADO':
                    raise Stop('Persistencia tras reinicio pendiente; reanudar con --resume.')
            after = backend_identity()
            if before == after:
                raise Stop('No se demostró un reinicio del backend.')
            state['backend_restart'] = {'before': before, 'after': after}
            run.safety_and_snapshot('after_restart')
            state['phase'] = 'complete'
            run.save()
        print('Batería terminada. Revisar informe: aprobación automática es técnica, no una auditoría semántica.')
        return 0
    except (Stop, KeyboardInterrupt, EOFError, getpass.GetPassWarning) as error:
        message = str(error) if isinstance(error, Stop) else 'Interrumpido; checkpoints conservados.'
        print('BLOQUEADO/DETENIDO: ' + message)
        if run:
            run.state['last_stop'] = message
            run.save()
        return 2
    except Exception:
        print('BLOQUEADO: error local no previsto. No se imprime la excepción para evitar secretos.')
        if run:
            run.state['last_stop'] = 'Error local no previsto; revisar checkpoint sin reenviar solicitudes inciertas.'
            run.save()
        return 2
    finally:
        if run:
            for account in run.accounts.values():
                try:
                    account.logout(run.http)
                except Exception:
                    account.token = None
        if mutex:
            kernel, handle = mutex
            kernel.CloseHandle.argtypes = [ctypes.c_void_p]
            kernel.CloseHandle(handle)


if __name__ == '__main__':
    raise SystemExit(main())
