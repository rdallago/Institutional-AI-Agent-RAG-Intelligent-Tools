import asyncio
import logging

import httpx
import pytest

from app.application.ia.dto import GeneracionEntrada
from app.application.ia.exceptions import IATiempoAgotado
from app.infrastructure.llm.ollama import OllamaProvider
from tests.rag.test_adapters import CONFIG
from tests.rag.test_agent import fixture


@pytest.mark.parametrize('kind,category', [
    (httpx.ConnectTimeout, 'connect'), (httpx.ReadTimeout, 'read'),
    (httpx.WriteTimeout, 'write'), (httpx.PoolTimeout, 'pool'),
])
def test_transport_timeout_classification(kind, category, caplog):
    async def run():
        def handler(request):
            raise kind('PRIVATE_ERROR', request=request)
        provider = OllamaProvider(CONFIG, transport=httpx.MockTransport(handler))
        try:
            with pytest.raises(IATiempoAgotado):
                await provider.generate(GeneracionEntrada(prompt='PRIVATE_PROMPT'))
        finally:
            await provider.aclose()
    caplog.set_level(logging.WARNING)
    asyncio.run(run())
    assert f'category={category} stage=transport duration_s=' in caplog.text
    assert 'PRIVATE' not in caplog.text


@pytest.mark.parametrize('expires', [True, False])
def test_rag_deadline_is_distinct_from_upstream_timeout(expires, caplog):
    async def run():
        p, scope, *_, case = fixture()
        class Provider:
            async def generate_grounded(self, input):
                if expires:
                    await asyncio.sleep(1)
                raise IATiempoAgotado()
        case.provider = Provider()
        case.timeout = .01 if expires else 1
        with pytest.raises(IATiempoAgotado):
            await case.execute(p, scope.document_id, 'regularidad curricular')
    asyncio.run(run())
    expected = 'deadline' if expires else 'upstream'
    assert f'rag_timeout category={expected} stage=generation duration_s=' in caplog.text
