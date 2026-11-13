"""Esquemas operativos con transporte simulado: nunca red real."""
import asyncio
from dataclasses import replace
import json

import httpx
import pytest

from app.application.agent.planning import Proposal
from app.application.ia.dto import GeneracionEntrada
from app.application.ia.exceptions import IARespuestaInvalida
from app.application.rag.core import build_context
from app.application.rag.structured_output import schema
from app.infrastructure.llm.openrouter import DOTS_MODEL, OpenRouterProvider, OpenRouterPlanner, OpenRouterGroundedProvider
from app.infrastructure.llm.work_gate import MemoryModelWorkGate
from app.infrastructure.rag.text import ConservativeCounter
from tests.ia.test_openrouter import CONFIG, catalog, completion
from tests.rag.test_structured_output import evidence, QUESTION

CONFIG_DOTS = replace(CONFIG, remote_model=DOTS_MODEL)


@pytest.mark.parametrize('kind,literal,accepted', [
    ('planner', '{"accion":"responder_llm_directo","argumentos":{}}', True),
    ('planner', '{"accion":"shell","argumentos":{}}', False),
    ('planner', '{"accion":"responder_llm_directo","argumentos":{"extra":1}}', False),
    ('planner', '{"accion":"responder_llm_directo","accion":"shell","argumentos":{}}', False),
    ('rag', '{"claims":[]}', True),
    ('rag', '{"claims":[{"text":"Unidad institucional","source_ids":["F1"]}]}', True),
    ('rag', '{"claims":[{"text":"Algo","source_ids":["F99"]}]}', False),
    ('rag', '{"claims":[],"extra":1}', False),
    ('rag', '{"claims":[],"claims":[]}', False),
    ('rag', '{"claims":[', False),
    ('rag', '{"claims":[{"text":"Algo","source_ids":[]}]}', False),
])
def test_operational_schemas(kind, literal, accepted):
    calls = []
    context = build_context(QUESTION, (evidence()[0].chunk,), ConservativeCounter())
    def handler(request):
        calls.append(request.method)
        if request.method == 'GET':
            data = catalog(DOTS_MODEL)
            data['data']['endpoints'][0]['tag'] = 'atlas-cloud/fp8'
            return httpx.Response(200, json=data)
        payload = json.loads(request.content)
        assert payload['model'] == DOTS_MODEL
        assert payload['provider'] == {'only': ['atlas-cloud'], 'require_parameters': True,
            'allow_fallbacks': False, 'data_collection': 'deny',
            'max_price': {'prompt': 0, 'completion': 0}}
        assert payload['response_format'] == {'type': 'json_schema', 'json_schema': {
            'name': 'agent_output', 'strict': True,
            'schema': Proposal.json_schema() if kind == 'planner' else schema(context.evidence)}}
        assert payload['max_tokens'] == 256
        return httpx.Response(200, json=completion(literal, model=DOTS_MODEL))
    async def idle():
        pass
    async def run():
        transport = httpx.MockTransport(handler)
        provider = (OpenRouterPlanner(CONFIG_DOTS, MemoryModelWorkGate(), idle, transport=transport)
                    if kind == 'planner' else OpenRouterGroundedProvider(CONFIG_DOTS, transport=transport))
        try:
            operation = provider.plan('Consulta sintetica') if kind == 'planner' else provider.generate_grounded(context)
            if accepted:
                await operation
            else:
                with pytest.raises(IARespuestaInvalida):
                    await operation
        finally:
            await provider.aclose()
    asyncio.run(run())
    assert calls == ['GET', 'POST']


@pytest.mark.parametrize('tag,price', [('other/fp8', '0'), ('atlas-cloud/fp8', '0.01')])
def test_wrong_provider_or_paid_endpoint_blocks_before_post(tag, price):
    calls = []
    def handler(request):
        calls.append(request.method)
        data = catalog(DOTS_MODEL)
        endpoint = data['data']['endpoints'][0]
        endpoint['tag'] = tag
        endpoint['pricing']['completion'] = price
        return httpx.Response(200, json=data)
    async def run():
        provider = OpenRouterProvider(CONFIG_DOTS, transport=httpx.MockTransport(handler))
        try:
            with pytest.raises(IARespuestaInvalida):
                await provider.generate(GeneracionEntrada(prompt='Prueba sintetica'))
        finally:
            await provider.aclose()
    asyncio.run(run())
    assert calls == ['GET']
