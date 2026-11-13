"""Una prueba sintetica de JSON Schema; sin red salvo --execute."""
import argparse
import asyncio
import json
from pathlib import Path
import sys
from time import monotonic

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend' / 'src'))
import httpx
from app.application.ia.dto import GeneracionEntrada
from app.infrastructure.configuration.llm import LLMConfig, apply_provider_settings
from app.infrastructure.llm.openrouter import OpenRouterProvider
from app.infrastructure.llm.ollama import _object, _constant
from diagnose_openrouter import sanitized

MODEL = 'dots-studio/dots-3-note-preview:free'
SCHEMA = {'type': 'object', 'additionalProperties': False, 'required': ['result'],
          'properties': {'result': {'type': 'string', 'enum': ['OK']}}}


def validate_literal(literal):
    value = json.loads(literal, object_pairs_hook=_object, parse_constant=_constant)
    if type(value) is not dict or set(value) != {'result'} or value['result'] != 'OK':
        raise ValueError('schema_rejected')


class DiagnosticProvider(OpenRouterProvider):
    """Mismo adaptador; restriccion adicional al proveedor, solo en esta prueba."""
    async def _request(self, method, path, *, payload=None):
        if method == 'POST':
            if path != '/chat/completions' or self.posts:
                raise ValueError('only_one_post')
            self.posts += 1
            payload['provider']['only'] = ['atlas-cloud']
        body = await super()._request(method, path, payload=payload)
        if method == 'POST':
            self.observed = body
        return body


async def run(config, transport=None):
    provider = DiagnosticProvider(config, transport=transport)
    provider.posts, provider.observed = 0, None
    status = None
    async def observe(response):
        nonlocal status
        if response.request.method == 'POST':
            status = response.status_code
    provider._client.event_hooks['response'].append(observe)
    start = monotonic()
    result = {'model_requested': MODEL, 'provider_requested': 'atlas-cloud', 'schema_valid': False}
    try:
        output = await provider._generate_validated(
            GeneracionEntrada(prompt='Return a JSON object with result equal to OK.'),
            system='Synthetic protocol test. Return only JSON matching the supplied schema.',
            output_format=SCHEMA)
        result['content'] = sanitized(output.respuesta, secret=config.api_key)
        validate_literal(output.respuesta)
        if output.finalizacion != 'completa':
            raise ValueError('incomplete_generation')
        result['schema_valid'] = True
    except Exception as error:
        # No representar cuerpos, mensajes arbitrarios o cabeceras upstream.
        result['error_type'] = type(error).__name__
    finally:
        body = provider.observed or {}
        result.update(http=status, posts=provider.posts,
            duration_seconds=round(monotonic()-start, 3),
            model_returned=sanitized(body.get('model'), secret=config.api_key),
            provider_returned=sanitized(body.get('provider'), secret=config.api_key))
        await provider.aclose()
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--self-test', action='store_true')
    args = parser.parse_args()
    if args.execute and args.self_test:
        parser.error('Modos excluyentes.')
    if args.self_test:
        for invalid in ('{}', '{', '{"result":"NO"}', '{"result":"OK","extra":1}',
                        '{"result":"OK","result":"OK"}', '{"result":null}'):
            try:
                validate_literal(invalid)
            except ValueError:
                continue
            raise AssertionError('invalid JSON accepted')
        calls = []
        def handler(request):
            calls.append(request.method)
            if request.method == 'GET':
                return httpx.Response(200, json={'data': {'id': MODEL, 'endpoints': [{
                    'tag': 'atlas-cloud/fp8',
                    'pricing': {'prompt': '0', 'completion': '0'},
                    'supported_parameters': ['structured_outputs', 'response_format', 'reasoning', 'max_tokens']}]}})
            payload = json.loads(request.content)
            assert payload['model'] == MODEL
            assert payload['response_format']['json_schema']['strict'] is True
            assert payload['response_format']['type'] == 'json_schema'
            assert payload['response_format']['json_schema']['schema'] == SCHEMA
            assert payload['provider'] == {'only': ['atlas-cloud'], 'require_parameters': True,
                'allow_fallbacks': False, 'data_collection': 'deny',
                'max_price': {'prompt': 0, 'completion': 0}}
            return httpx.Response(200, json={'model': MODEL, 'provider': 'AtlasCloud',
                'choices': [{'finish_reason': 'stop', 'message': {
                    'role': 'assistant', 'content': '{"result":"OK"}'}}]})
        config = LLMConfig(enabled=True, testing=True, environment='test', provider='openrouter',
                           remote_model=MODEL, api_key='synthetic-not-a-key')
        result = asyncio.run(run(config, httpx.MockTransport(handler)))
        assert result['schema_valid'] and calls == ['GET', 'POST']
        print('SELF-TEST OK: transporte simulado, esquema y seis rechazos; cero red real.')
        return 0
    if not args.execute:
        print('SIN SOLICITUDES. Usar --self-test o --execute.')
        return 0
    config = apply_provider_settings(LLMConfig(enabled=True, environment='local-development'))
    if config.provider != 'openrouter' or config.remote_model != MODEL or not config.api_key.strip():
        print('BLOQUEADO: proveedor, modelo gratuito o clave no coinciden; cero solicitudes.')
        return 2
    result = asyncio.run(run(config))
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return 0 if result['schema_valid'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
