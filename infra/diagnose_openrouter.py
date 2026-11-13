"""Diagnóstico sintético aislado; sin red al importar o ejecutar sin --execute.

La prueba anterior se ejecutó por stdin y no dejó un script ni el cuerpo original.
Este cliente conserva un resumen acotado también para errores dentro de HTTP 200.
No modifica ni invoca el adaptador de producción.
"""
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
import re
import sys
from time import monotonic

import httpx

ROOT = Path(__file__).resolve().parents[1]
MODEL = 'xingchen-agi/xing4.0-29b-a4b:free'
AUTHORIZED_PAIRS = {
    MODEL: 'phala',
    'dots-studio/dots-3-note-preview:free': 'atlas-cloud',
}
URL = 'https://openrouter.ai/api/v1/chat/completions'
MAX_BODY = 65536
MAX_TEXT = 512
MISSING = object()


def sanitized(value, *, secret=''):
    """Solo escalares; nunca serializar objetos/headers upstream arbitrarios."""
    if value is None or type(value) in (bool, int):
        return value
    if not isinstance(value, str):
        return '[TIPO NO ESCALAR OMITIDO]'
    if secret:
        value = value.replace(secret, '[SECRETO OMITIDO]')
    for pattern in (
        r'(?i)bearer\s+\S+',
        r'eyJ[\w-]+\.[\w-]+\.[\w-]+',
        r'(?i)sk-[\w-]+',
        r'(?i)(?:password|contrase[nñ]a|api[_ -]?key|access_token|refresh_token|secret)\s*[:=]\s*\S+',
        r'[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}',
        r'(?i)https?://[^\s]+',
        r'(?i)\b(?:nombre|name|tel[eé]fono|phone|direcci[oó]n|address|dni)\s*[:=]\s*[^\n;,]+',
        r'(?<!\w)\+?\d[\d ()-]{7,}\d(?!\w)',
    ):
        value = re.sub(pattern, '[DATO OMITIDO]', value)
    value = ''.join(c if c >= ' ' or c in '\n\t' else '\ufffd' for c in value)
    return value[:MAX_TEXT] + ('[TRUNCADO]' if len(value) > MAX_TEXT else '')


def error_summary(value, location, secret):
    error = value if isinstance(value, dict) else {}
    metadata = error.get('metadata')
    metadata = metadata if isinstance(metadata, dict) else {}
    return {'location': location, 'type': type(value).__name__,
            **{key: sanitized(error.get(key), secret=secret) for key in ('code', 'message')},
            'error_type': sanitized(metadata.get('error_type', error.get('error_type')), secret=secret),
            'limit_source': sanitized(metadata.get('limit_source'), secret=secret)}


def summarize(http_status, body, *, secret='', expected_model=MODEL):
    """Una proyección saneada; no conserva el JSON completo ni razonamiento."""
    result = {'http_status': http_status, 'root_type': type(body).__name__,
              'root_keys': [], 'errors': [], 'generation_valid': False,
              'matches_expected_ok': False}
    if not isinstance(body, dict):
        result.update(reason='root_not_object', choices={'state': 'unavailable'})
        return result
    result['root_keys'] = [sanitized(k, secret=secret) for k in list(body)[:24]]
    result['root_keys_truncated'] = len(body) > 24
    result['response_model'] = sanitized(body.get('model'), secret=secret)
    identifier = body.get('id')
    if (isinstance(identifier, str) and re.fullmatch(r'gen-[A-Za-z0-9_-]{1,100}', identifier)
            and (not secret or secret not in identifier)):
        result['request_id'] = identifier
    for key in ('error',):
        if key in body and body[key] is not None:
            result['errors'].append(error_summary(body[key], 'root', secret))
    # Conservar presencia y tipo: nunca convertir ausencia en una lista vacía.
    choices = body.get('choices', MISSING)
    if choices is MISSING:
        result['choices'] = {'state': 'missing', 'type': 'absent'}
    elif type(choices) is not list:
        result['choices'] = {'state': 'invalid_type', 'type': type(choices).__name__}
    else:
        result['choices'] = {'state': 'empty' if not choices else 'with_elements',
                             'type': 'list', 'count': len(choices)}
    generations = []
    if type(choices) is list:
        for index, choice in enumerate(choices[:3]):
            if not isinstance(choice, dict):
                generations.append({'index': index, 'type': type(choice).__name__})
                continue
            if choice.get('error') is not None:
                result['errors'].append(error_summary(choice['error'], f'choices[{index}]', secret))
            message = choice.get('message')
            message = message if isinstance(message, dict) else {}
            content = message.get('content', MISSING)
            generations.append({'index': index,
                'finish_reason': sanitized(choice.get('finish_reason'), secret=secret),
                'content_present': content is not MISSING,
                'content_type': 'absent' if content is MISSING else type(content).__name__,
                'content': sanitized(content, secret=secret) if content is not MISSING else None,
                'reasoning_present': bool(message.get('reasoning') or message.get('reasoning_details'))})
    result['generations'] = generations
    # Solo señalar campos alternativos: no usarlos como respuesta Chat Completions.
    result['alternative_fields'] = {key: {'type': type(body[key]).__name__}
        for key in ('message', 'output', 'response', 'reasoning') if key in body}
    if result['errors']:
        result['reason'] = 'error_in_body'
    elif http_status != 200:
        result['reason'] = 'http_error'
    elif type(choices) is not list or len(choices) != 1:
        result['reason'] = 'invalid_choices'
    else:
        choice = choices[0]
        message = choice.get('message', {}) if isinstance(choice, dict) else {}
        message = message if isinstance(message, dict) else {}
        valid = (isinstance(choice, dict) and choice.get('finish_reason') == 'stop'
            and message.get('role') == 'assistant' and not message.get('refusal')
            and not message.get('tool_calls') and isinstance(message.get('content'), str)
            and bool(message['content'].strip()) and '\x00' not in message['content']
            and body.get('model') in (expected_model, expected_model.removesuffix(':free')))
        result['generation_valid'] = valid
        result['matches_expected_ok'] = valid and message['content'].strip() == 'OK'
        result['reason'] = 'valid_chat_completion' if valid else 'invalid_completion'
    return result


async def probe(config, *, model=None, provider=None, transport=None):
    """Como máximo un POST; transport solo se inyecta en pruebas aisladas."""
    model = config.remote_model if model is None else model
    authorized_provider = AUTHORIZED_PAIRS.get(model)
    provider = authorized_provider if provider is None else provider
    if (config.provider != 'openrouter' or not config.api_key.strip()
            or not isinstance(model, str) or not model.endswith(':free')
            or authorized_provider is None or provider != authorized_provider):
        return {'generation_valid': False, 'reason': 'configuration_mismatch_or_missing_key', 'posts': 0}
    payload = {'model': model, 'stream': False,
        'messages': [{'role': 'user', 'content': 'Respond only OK'}], 'max_tokens': 256,
        'reasoning': {'enabled': False}, 'provider': {'only': [provider],
            'require_parameters': True, 'allow_fallbacks': False, 'data_collection': 'deny',
            'max_price': {'prompt': 0, 'completion': 0, 'request': 0}}}
    started = monotonic()
    status = None
    result = None
    try:
        async with asyncio.timeout(30):
            async with httpx.AsyncClient(transport=transport or httpx.AsyncHTTPTransport(retries=0),
                    trust_env=False, follow_redirects=False, timeout=httpx.Timeout(30, connect=3)) as client:
                async with client.stream('POST', URL, json=payload, headers={
                        'Authorization': 'Bearer ' + config.api_key, 'Accept-Encoding': 'identity'}) as response:
                    status = response.status_code
                    raw = bytearray()
                    async for chunk in response.aiter_bytes():
                        if len(raw) + len(chunk) > MAX_BODY:
                            return {'generation_valid': False, 'http_status': status,
                                    'reason': 'response_too_large', 'posts': 1}
                        raw.extend(chunk)
                    def unique(pairs):
                        data = {}
                        for k, value in pairs:
                            if k in data:
                                raise ValueError('duplicate_key')
                            data[k] = value
                        return data
                    def constant(_):
                        raise ValueError('invalid_constant')
                    body = json.loads(raw.decode('utf-8'), object_pairs_hook=unique, parse_constant=constant)
                    result = summarize(status, body, secret=config.api_key, expected_model=model)
    except (TimeoutError, httpx.TimeoutException):
        result = {'generation_valid': False, 'http_status': status, 'reason': 'timeout'}
    except httpx.RequestError:
        result = {'generation_valid': False, 'http_status': status, 'reason': 'network_error'}
    except (ValueError, UnicodeError, RecursionError):
        result = {'generation_valid': False, 'http_status': status, 'reason': 'invalid_json'}
    result.update(model_requested=model, provider_requested=provider, posts=1,
                  duration_seconds=round(monotonic() - started, 3))
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true', help='Opt-in explícito: un POST real, sin reintento.')
    parser.add_argument('--model', choices=tuple(AUTHORIZED_PAIRS),
                        help='Modelo gratuito autorizado; por defecto OPENROUTER_MODEL.')
    parser.add_argument('--provider', choices=tuple(AUTHORIZED_PAIRS.values()),
                        help='Proveedor autorizado; por defecto el asociado al modelo.')
    args = parser.parse_args(argv)
    if args.model and args.provider and AUTHORIZED_PAIRS[args.model] != args.provider:
        parser.error('Combinación modelo/proveedor no autorizada.')
    if not args.execute:
        print('SIN SOLICITUDES: la inferencia requiere --execute y autorización previa.')
        return 0
    sys.path.insert(0, str(ROOT / 'backend' / 'src'))
    try:
        from app.infrastructure.configuration.llm import LLMConfig, apply_provider_settings
        from app.infrastructure.rag.resources import require_memory
        config = apply_provider_settings(LLMConfig(environment='local-development'))
        require_memory(.25)
        result = asyncio.run(probe(config, model=args.model, provider=args.provider))
    except KeyboardInterrupt:
        print('INTERRUMPIDO: no reintentar automáticamente; el resultado remoto puede ser incierto.')
        return 2
    except Exception:
        print('BLOQUEADO: configuración o recursos no disponibles. Se omiten detalles para proteger secretos.')
        return 2
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return 0 if result.get('generation_valid') and result.get('matches_expected_ok') else 2


if __name__ == '__main__':
    raise SystemExit(main())
