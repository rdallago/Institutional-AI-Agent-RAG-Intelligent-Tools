import asyncio
from dataclasses import replace
import json

import httpx
import pytest

from app.application.agent.planning import planning_context
from app.application.ia.dto import GeneracionEntrada
from app.application.ia.exceptions import IARespuestaInvalida
from app.infrastructure.llm.ollama import OllamaProvider
from app.infrastructure.llm.work_gate import MemoryModelWorkGate
from app.infrastructure.rag.planner import JSONPlanner
from tests.rag.test_adapters import CONFIG


def response(**extra):
    return {'model':'qwen3:1.7b','done':True,'done_reason':'stop',
            'response':'{"accion":"responder_llm_directo","argumentos":{}}','prompt_eval_count':100,**extra}


def test_only_planner_sets_zero_temperature_native_phases_and_safe_metadata(caplog,capsys):
    async def run():
        bodies=[];records=[]
        def handler(request):
            bodies.append(json.loads(request.content))
            return httpx.Response(200,json=response(load_duration=2_000_000_000,prompt_eval_duration=300_000_000,
                eval_duration=400_000_000,total_duration=2_800_000_000,private_field='DO_NOT_LOG'))
        idle_calls=[]
        async def idle():idle_calls.append(1)
        planner=JSONPlanner(CONFIG,MemoryModelWorkGate(),idle,transport=httpx.MockTransport(handler),observe=True)
        direct=OllamaProvider(CONFIG,transport=httpx.MockTransport(lambda req:(bodies.append(json.loads(req.content)) or
            httpx.Response(200,json=response(response='Respuesta directa')))))
        try:
            await planner.plan(planning_context('PRIVATE_QUESTION',(),[],None),timings_observer=records.append)
            await direct.generate(GeneracionEntrada(prompt='Otra consulta'))
        finally:await planner.aclose();await direct.aclose()
        assert bodies[0]['options']=={'num_ctx':4096,'num_predict':256,'temperature':0}
        assert 'temperature' not in bodies[1]['options']
        assert bodies[0]['think'] is False and bodies[0]['keep_alive']==0 and bodies[0]['stream'] is False
        assert len(idle_calls)==2 and records[0]['timeout_s']==40 and records[0]['status']=='complete'
        assert records[0]['native_load_s']==2 and records[0]['native_prompt_eval_s']==.3
        assert records[0]['native_generation_s']==.4 and records[0]['native_total_s']==2.8
        for key in ('availability_s','request_s','json_validation_s','unload_wait_s','total_s'):assert records[0][key]>=0
    asyncio.run(run())
    assert 'PRIVATE_QUESTION' not in caplog.text and 'DO_NOT_LOG' not in caplog.text
    observed=json.loads(capsys.readouterr().out.strip())
    assert len(observed)==8 and 'native_load_s' not in observed


@pytest.mark.parametrize('value',[None,-1,True,'123',10**30])
def test_missing_or_invalid_native_timings_remain_unknown(value):
    async def run():
        async def idle():pass
        records=[]
        planner=JSONPlanner(CONFIG,MemoryModelWorkGate(),idle,transport=httpx.MockTransport(
            lambda request:httpx.Response(200,json=response(load_duration=value))))
        try:await planner.plan('consulta',timings_observer=records.append)
        finally:await planner.aclose()
        assert records[0]['native_load_s'] is None and records[0]['native_generation_s'] is None
        assert records[0]['request_s'] is not None
    asyncio.run(run())


@pytest.mark.parametrize('stage',['availability','request','unload'])
def test_timeout_limits_and_partial_phase_metrics_release_gate(stage,monkeypatch):
    import app.infrastructure.rag.planner as module
    original_timeout=asyncio.timeout
    limits=[]
    def short_timeout(seconds):limits.append(seconds);return original_timeout(.02)
    monkeypatch.setattr(module.asyncio,'timeout',short_timeout)
    async def run():
        gate=MemoryModelWorkGate();records=[];idle_calls=0
        async def idle():
            nonlocal idle_calls
            idle_calls+=1
            if stage=='availability' or (stage=='unload' and idle_calls==2):await asyncio.sleep(1)
        async def handler(request):
            if stage=='request':await asyncio.sleep(1)
            return httpx.Response(200,json=response())
        planner=JSONPlanner(replace(CONFIG,timeout_seconds=30),gate,idle,transport=httpx.MockTransport(handler))
        try:
            with pytest.raises(TimeoutError):await planner.plan('consulta',timings_observer=records.append)
        finally:await planner.aclose()
        assert limits==[20]  # Reserva 10 s del presupuesto configurado de 30.
        assert records[0]['status']=='timeout' and records[0]['native_load_s'] is None
        partial={'availability':'availability_s','request':'request_s','unload':'unload_wait_s'}[stage]
        assert records[0][partial]>0
        if stage=='availability':assert records[0]['request_s'] is None
        if stage=='request':assert records[0]['json_validation_s'] is None
        gate.try_acquire().release()
    asyncio.run(run())


def test_invalid_plan_records_validation_not_unload():
    async def run():
        async def idle():pass
        records=[];gate=MemoryModelWorkGate()
        planner=JSONPlanner(CONFIG,gate,idle,transport=httpx.MockTransport(
            lambda request:httpx.Response(200,json=response(response='{}'))))
        try:
            with pytest.raises(IARespuestaInvalida):await planner.plan('consulta',timings_observer=records.append)
        finally:await planner.aclose()
        assert records[0]['status']=='error' and records[0]['json_validation_s'] is not None
        assert records[0]['unload_wait_s'] is None
        gate.try_acquire().release()
    asyncio.run(run())


def test_cancellation_records_partial_phase_and_releases_gate():
    async def run():
        entered=asyncio.Event();records=[];gate=MemoryModelWorkGate()
        async def idle():entered.set();await asyncio.sleep(10)
        planner=JSONPlanner(CONFIG,gate,idle,transport=httpx.MockTransport(lambda request:httpx.Response(200,json=response())))
        try:
            task=asyncio.create_task(planner.plan('consulta',timings_observer=records.append))
            await entered.wait();task.cancel()
            with pytest.raises(asyncio.CancelledError):await task
        finally:await planner.aclose()
        assert records[0]['status']=='cancelled' and records[0]['request_s'] is None
        gate.try_acquire().release()
    asyncio.run(run())
