"""Correlacion efimera de ejecucion, sin identidad ni contenido."""
from contextvars import ContextVar
from collections import deque
import json
import os
from pathlib import Path
import re
from uuid import uuid4

execution_trace = ContextVar('agent_execution_trace', default='isolated')
request_identifier = ContextVar('agent_request_identifier', default='isolated')
_private_events = deque(maxlen=64)


def restricted_directory(directory):
    """Fail closed: owner-only POSIX directory or protected owner/SYSTEM Windows ACL."""
    if (not directory.is_dir() or directory.is_symlink()
            or (hasattr(directory, 'is_junction') and directory.is_junction())):
        return False
    if os.name != 'nt':
        return directory.stat().st_uid == os.getuid() and not directory.stat().st_mode & 0o077
    import subprocess
    environment = dict(os.environ, RAG_DIAGNOSTIC_ACL_PATH=str(directory))
    script = ('$a=Get-Acl -LiteralPath $env:RAG_DIAGNOSTIC_ACL_PATH; '
              '$o=$a.GetOwner([System.Security.Principal.SecurityIdentifier]).Value; '
              'if(!$a.AreAccessRulesProtected){exit 1}; '
              'foreach($r in $a.GetAccessRules($true,$true,[System.Security.Principal.SecurityIdentifier])){'
              'if($r.AccessControlType -eq "Allow" -and $r.IdentityReference.Value -notin @($o,"S-1-5-18")){exit 1}}; exit 0')
    return subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', script],
                          env=environment, capture_output=True, timeout=3,
                          creationflags=subprocess.CREATE_NO_WINDOW).returncode == 0


def record_rag_private(metadata, *, literal=None):
    """Bounded metadata buffer; literal output is disk-only, separately opted in."""
    try:
        entry = {'event': 'rag_validation', 'request_id': request_identifier.get(),
                 'trace': execution_trace.get(), **metadata}
        encoded = json.dumps(entry, ensure_ascii=False)
        if len(encoded.encode('utf-8')) > 12000:
            return
        _private_events.append(json.loads(encoded))
        destination = os.environ.get('AGENT_PRIVATE_DIAGNOSTIC_DIR')
        if not destination:
            return
        directory = Path(destination)
        if not restricted_directory(directory):
            return
        if sum(1 for _ in directory.glob('agent-private-*.json')) >= 64:
            return
        if literal is not None and os.environ.get('AGENT_PRIVATE_CAPTURE_RAG_JSON') == 'true':
            if len(literal.encode('utf-8')) <= 16384:
                entry['literal_json'] = literal
        encoded = json.dumps(entry, ensure_ascii=False)
        if len(encoded.encode('utf-8')) > 32768:
            return
        path = directory / ('agent-private-' + uuid4().hex + '.json')
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, 'w', encoding='utf-8') as output:
            output.write(encoded)
    except Exception:
        pass  # Diagnostic failures must never change generation/validation.


def private_diagnostics():
    """Copia para diagnostico administrativo explicito; no expuesta por HTTP."""
    return json.loads(json.dumps(list(_private_events)))


def record_private(event, **metadata):
    """Buffer acotado; exportacion opcional exclusiva a directorio privado explicito.

    Sin logger operativo, JSON original, prompts o excepciones arbitrarias.
    """
    if event not in {'weather_proposal', 'weather_normalization', 'weather_geocoding', 'planner_validation'}:
        return
    allowed = {'arguments','reason','match_count','proposal_type','rules'}
    def clean(value):
        if value is None or type(value) in (bool, int):
            return value
        if isinstance(value, str):
            if (len(value)>100 or re.search(r'(?i)bearer|eyJ|password|contrase[nñ]a|secret|token|jwt|api.?key|sk-|[@:=/\\]', value)):
                return '[redacted]'
            return value
        if isinstance(value, dict):
            return {k:clean(v) for k,v in value.items() if k in {'ciudad','provincia','region','pais','fecha','dia','field','rule'}}
        if isinstance(value, (list, tuple)):
            return [clean(v) for v in value[:8]]
        return '[redacted]'
    entry = {'event':event, 'request_id':request_identifier.get(), 'trace':execution_trace.get(),
             **{k:clean(v) for k,v in metadata.items() if k in allowed}}
    encoded = json.dumps(entry, ensure_ascii=False)
    if len(encoded.encode('utf-8'))>4096:
        return
    _private_events.append(entry)
    destination = os.environ.get('AGENT_PRIVATE_DIAGNOSTIC_DIR')
    if destination:
        directory = Path(destination)
        if not directory.is_dir() or directory.is_symlink():
            return
        try:
            if sum(1 for _ in directory.glob('agent-private-*.json'))>=64:
                return
            with (directory / ('agent-private-'+uuid4().hex+'.json')).open('x', encoding='utf-8') as output:
                output.write(encoded)
        except OSError:
            pass  # El diagnostico no altera el resultado funcional.
