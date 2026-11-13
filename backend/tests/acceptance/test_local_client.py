"""Solo dobles en memoria: no HTTP, SQL, Ollama, procesos o credenciales reales."""
import importlib.util
import json
import os
from pathlib import Path
import sys
from uuid import uuid4

import pytest

SCRIPT = Path(__file__).resolve().parents[3] / 'infra' / 'acceptance_agent.py'
spec = importlib.util.spec_from_file_location('acceptance_agent_tested', SCRIPT)
client = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = client
spec.loader.exec_module(client)


class FakeHTTP:
    def __init__(self, handler):
        self.handler, self.calls = handler, []

    def request(self, method, path, token=None, body=None, **kwargs):
        self.calls.append((method, path, token, body))
        return self.handler(method, path, token, body)


def state():
    return {'schema': 1, 'run_id': str(uuid4()), 'identities': {}, 'conversations': {},
            'results': {}, 'phase': 'turns'}


def turn_reply(conversation, request_id, strategy='RAG', status='FUNDAMENTADA', text='Texto [F1].', sources=None):
    return client.Reply(200, {'conversacion_id': conversation, 'solicitud_id': request_id,
        'herramienta': None, 'resultado': {'respuesta': text, 'estrategia': strategy,
        'estado': status, 'fuentes': sources if sources is not None else [{'id': 'F1', 'pagina': 11}]}}, .25)


def test_login_real_contract_verified_and_no_secrets_saved(tmp_path):
    identity = str(uuid4())
    def handler(method, path, token, body):
        if path == '/auth/login':
            assert body == {'email': 'test@example.com', 'password': 'privado-123'}
            return client.Reply(200, {'access_token': 'solo-memoria', 'debe_cambiar_password': False}, .1)
        if path == '/auth/me':
            assert token == 'solo-memoria'
            return client.Reply(200, {'id': identity, 'rol': 'ADMIN', 'email': 'test@example.com',
                                     'activo': True, 'debe_cambiar_password': False}, .1)
        return client.Reply(204, None, .1)
    http = FakeHTTP(handler)
    account = client.Account('ADMIN', 'ADMIN')
    answers = iter(['test@example.com', 'privado-123'])
    account.login(http, lambda _: next(answers))
    assert account.user_id == identity and account.token == 'solo-memoria'
    run = client.Run(tmp_path/'informe.json', state(), http)
    run.accounts['ADMIN'] = account
    run.save()
    saved = run.path.read_text(encoding='utf-8')
    assert all(secret not in saved for secret in ['solo-memoria', 'privado-123', 'test@example.com'])
    account.logout(http)
    assert account.token is None


@pytest.mark.parametrize('role,email,uid', [
    ('USUARIO', 'test@example.com', None), ('ADMIN', 'otro@example.com', None),
    ('ADMIN', 'test@example.com', str(uuid4()))])
def test_identity_mismatch_stops(role, email, uid):
    identity = str(uuid4())
    http = FakeHTTP(lambda method, path, token, body: client.Reply(200,
        {'access_token': 'memory', 'debe_cambiar_password': False} if path.endswith('login') else
        {'id': identity, 'rol': role, 'email': email, 'activo': True, 'debe_cambiar_password': False}, .1))
    account = client.Account('ADMIN', 'ADMIN')
    account.user_id = uid
    with pytest.raises(client.Stop):
        answers = iter(['test@example.com', 'private'])
        account.login(http, lambda _: next(answers))


def run_with_success(tmp_path, monkeypatch):
    monkeypatch.setattr(client.time, 'sleep', lambda _: None)
    def handler(method, path, token, body):
        if path == '/api/ps':
            return client.Reply(200, {'models': []}, .1)
        if path == '/ia/conversaciones':
            return client.Reply(200, {'id': body['conversacion_id']}, .1)
        return turn_reply(path.split('/')[3], body['solicitud_id'])
    run = client.Run(tmp_path/'informe.json', state(), FakeHTTP(handler), memory=lambda: 2.)
    run.accounts['ADMIN'].user_id = str(uuid4())
    run.accounts['ADMIN'].token = 'solo-memoria'
    return run


def test_completed_requests_not_repeated_on_resume(tmp_path, monkeypatch):
    run = run_with_success(tmp_path, monkeypatch)
    spec = client.matrix()[0]
    run.turn(spec)
    assert run.state['results']['A1']['status'] == 'APROBADO'
    count = len(run.http.calls)
    resumed = client.Run(run.path, json.loads(run.path.read_text(encoding='utf-8')), run.http, memory=lambda: 2.)
    resumed.turn(spec)
    assert len(run.http.calls) == count
    assert len(resumed.state['conversations']) == 1


def test_inflight_not_retried(tmp_path):
    data = state()
    data['results']['A1'] = {'status': 'INFLIGHT', 'request_id': str(uuid4())}
    http = FakeHTTP(lambda *_: pytest.fail('No debe enviar solicitudes'))
    client.Run(tmp_path/'informe.json', data, http).turn(client.matrix()[0])
    assert not http.calls


def test_memory_insufficient_before_creation_no_http(tmp_path):
    http = FakeHTTP(lambda *_: pytest.fail('No debe enviar solicitudes'))
    run = client.Run(tmp_path/'informe.json', state(), http, memory=lambda: 1.)
    run.turn(client.matrix()[0])
    assert run.state['results']['A1']['status'] == 'BLOQUEADO'
    assert not http.calls and not run.state['conversations']


def test_unsent_resource_block_can_resume(tmp_path, monkeypatch):
    run = run_with_success(tmp_path, monkeypatch)
    run.memory = lambda: 1.
    run.turn(client.matrix()[0])
    run.memory = lambda: 2.
    run.turn(client.matrix()[0])
    assert run.state['results']['A1']['status'] == 'APROBADO'
    assert sum(c[0] == 'POST' and c[1].endswith('/mensajes') for c in run.http.calls) == 1


def test_model_loaded_prevents_post(tmp_path):
    http = FakeHTTP(lambda *_: client.Reply(200, {'models': [{'name': 'model'}]}, .1))
    run = client.Run(tmp_path/'informe.json', state(), http, memory=lambda: 2.)
    run.turn(client.matrix()[0])
    assert run.state['results']['A1']['status'] == 'BLOQUEADO'
    assert not any(c[0] == 'POST' for c in http.calls)


def test_http_failure_never_retried(tmp_path, monkeypatch):
    run = run_with_success(tmp_path, monkeypatch)
    original = run.http.handler
    def handler(method, path, token, body):
        if path.endswith('/mensajes'):
            return client.Reply(502, {'error': {'codigo': 'IA_RESPUESTA_INVALIDA'}}, .1)
        return original(method, path, token, body)
    run.http.handler = handler
    run.turn(client.matrix()[0])
    run.turn(client.matrix()[0])
    assert run.state['results']['A1']['status'] == 'FALLIDO'
    assert sum(c[0] == 'POST' and c[1].endswith('/mensajes') for c in run.http.calls) == 1


def test_uncertain_transport_keeps_key_and_never_retries(tmp_path, monkeypatch):
    run = run_with_success(tmp_path, monkeypatch)
    original = run.http.handler
    def handler(method, path, token, body):
        if path.endswith('/mensajes'):
            checkpoint = json.loads(run.path.read_text(encoding='utf-8'))
            assert checkpoint['results']['A1']['request_id'] == body['solicitud_id']
            raise client.Stop('Timeout')
        return original(method, path, token, body)
    run.http.handler = handler
    with pytest.raises(client.Stop):
        run.turn(client.matrix()[0])
    run.turn(client.matrix()[0])
    assert run.state['results']['A1']['uncertain'] is True
    assert sum(c[0] == 'POST' and c[1].endswith('/mensajes') for c in run.http.calls) == 1


def test_creation_uuid_checkpoint_before_post(tmp_path, monkeypatch):
    run = run_with_success(tmp_path, monkeypatch)
    original = run.http.handler
    def handler(method, path, token, body):
        if path == '/ia/conversaciones':
            checkpoint = json.loads(run.path.read_text(encoding='utf-8'))
            assert checkpoint['conversations']['ADMIN:academica']['id'] == body['conversacion_id']
        return original(method, path, token, body)
    run.http.handler = handler
    run.turn(client.matrix()[0])


@pytest.mark.parametrize('code,status', [(401,'BLOQUEADO'),(429,'BLOQUEADO'),(503,'BLOQUEADO'),(502,'FALLIDO')])
def test_failure_classification(code, status):
    assert client.classify(client.Reply(code, {'error': {'codigo': 'CODE'}}, .1), 'RAG')[0] == status


def test_citations_memory_and_partial_acceptance():
    reply = turn_reply('c','r',text='Respuesta parcial: Texto [F1].')
    assert client.classify(reply,'RAG')[0] == 'APROBADO'
    reply.data['resultado']['respuesta'] = 'Texto sin cita.'
    assert client.classify(reply,'RAG')[0] == 'FALLIDO'
    reply = turn_reply('c','r','LLM_DIRECTO','GENERADA','Anteriormente me preguntaste por el Rectorado.', [])
    assert client.classify(reply,'MEMORIA')[0] == 'APROBADO'
    reply.data['resultado']['estado'] = 'ACLARACION'
    assert client.classify(reply,'MEMORIA')[0] == 'FALLIDO'


def test_diagnostic_association_no_literal_duplication(tmp_path, monkeypatch):
    monkeypatch.setattr(client, 'private_directory', lambda *_args, **_kw: None)
    (tmp_path/'agent-private-one.json').write_text(json.dumps({
        'request_id':'wanted','stage':'generation','json_valid':True,'literal_json':'private-content'}), encoding='utf-8')
    (tmp_path/'agent-private-two.json').write_text(json.dumps({'request_id':'other'}), encoding='utf-8')
    records = client.associated_diagnostics(tmp_path,'wanted')
    assert len(records) == 1 and records[0]['json_valid'] is True
    assert 'private-content' not in json.dumps(records)


def test_report_redacts_secrets(tmp_path):
    run = client.Run(tmp_path/'informe.json', state(), FakeHTTP(lambda *_: None))
    run.record('x', response='Bearer abcdef eyJabc.def.ghi password=private', access_token='private',
               authorization='Bearer private')
    saved = run.path.read_text(encoding='utf-8')
    assert all(s not in saved for s in ['abcdef','eyJabc','password=private','Bearer private','access_token'])


def test_redirects_and_remote_destinations_not_allowed():
    assert client.NoRedirect().redirect_request(None,None,None,None,None,None) is None
    with pytest.raises(client.Stop):
        client.HTTP().request('GET','/auth/me',base='https://example.com')


def test_private_directory_required_before_writes(tmp_path, monkeypatch):
    from app.application.agent import diagnostics
    monkeypatch.setattr(diagnostics,'restricted_directory',lambda _: False)
    with pytest.raises(client.Stop):
        client.private_directory(tmp_path)


def test_cross_user_denial_and_persistence_hash(tmp_path, monkeypatch):
    data = state()
    ids = [str(uuid4()), str(uuid4())]
    owners = [str(uuid4()), str(uuid4())]
    history = [{'id':1,'rol':'user','contenido':'prueba'}, {'id':2,'rol':'assistant','contenido':'respuesta'}]
    for alias, identity, owner in zip(['ADMIN','COMUN'],ids,owners):
        data['conversations'][alias+':test'] = {'id':identity,'owner':owner,'created':True}
    def handler(method, path, token, body):
        own = ids[0] if token == 'admin-memory' else ids[1]
        if path == '/ia/conversaciones':
            return client.Reply(200,[{'id':own}],.1)
        return client.Reply(200,history,.1) if own in path else client.Reply(403,None,.1)
    run = client.Run(tmp_path/'informe.json', data, FakeHTTP(handler))
    for alias, owner, token in zip(['ADMIN','COMUN'],owners,['admin-memory','common-memory']):
        run.accounts[alias].user_id, run.accounts[alias].token = owner, token
    monkeypatch.setattr(client,'database_snapshot',lambda _: {'readonly':True})
    run.safety_and_snapshot('before_logout')
    run.safety_and_snapshot('after_login')
    run.safety_and_snapshot('after_restart')
    assert all(v['status'] == 'APROBADO' for v in run.state['results'].values())
    history.append({'id':3,'rol':'user','contenido':'cambio inesperado'})
    with pytest.raises(client.Stop):
        run.safety_and_snapshot('after_restart')


def test_catalog_denial_not_bypassed(tmp_path):
    data = state()
    data['document_access'] = {'COMUN':False}
    http = FakeHTTP(lambda *_: pytest.fail('Sin acceso no se envía RAG'))
    run = client.Run(tmp_path/'informe.json',data,http)
    run.turn(next(s for s in client.matrix() if s[0]=='U1'))
    assert run.state['results']['U1']['status'] == 'BLOQUEADO' and not http.calls


def test_fresh_memory_drop_prevents_creation(tmp_path):
    readings = iter([2.,1.4])
    http = FakeHTTP(lambda *_: client.Reply(200, {'models':[]}, .1))
    run = client.Run(tmp_path/'informe.json',state(),http,memory=lambda: next(readings))
    run.turn(client.matrix()[0])
    assert run.state['results']['A1']['status'] == 'BLOQUEADO'
    assert not any(c[0]=='POST' for c in http.calls)


def test_article52_cannot_pass_with_article24_citations(tmp_path,monkeypatch):
    run = run_with_success(tmp_path,monkeypatch)
    run.state['results']['A1'] = {'status':'APROBADO','request_id':str(uuid4())}
    run.turn(client.matrix()[1])
    assert run.state['results']['A2']['status'] == 'FALLIDO'
    assert 'páginas' in run.state['results']['A2']['reason']


def test_independent_conversations_and_reuse_only_same_group(tmp_path,monkeypatch):
    run = run_with_success(tmp_path,monkeypatch)
    run.accounts['COMUN'].user_id = str(uuid4())
    run.accounts['COMUN'].token = 'common-memory'
    first = run.conversation('ADMIN','academica')
    second = run.conversation('ADMIN','memoria')
    third = run.conversation('COMUN','propia')
    assert len({first,second,third}) == 3
    assert run.conversation('ADMIN','academica') == first
    assert sum(c[0]=='POST' for c in run.http.calls)==3


def test_restart_identity_requires_local_project(monkeypatch):
    from types import SimpleNamespace
    def fake(*args,**kwargs):
        assert kwargs['env']['ACCEPTANCE_PROJECT_ROOT']==str(client.ROOT)
        return SimpleNamespace(returncode=0,stdout=json.dumps({
            'pid':123,'started':'now','project':False,'local_launcher':True}))
    monkeypatch.setattr(client.subprocess,'run',fake)
    with pytest.raises(client.Stop):
        client.backend_identity()


def test_sql_only_readonly_scoped_metadata(monkeypatch):
    import sqlalchemy
    from app.infrastructure.configuration import database
    from types import SimpleNamespace
    statements=[]
    class Result:
        def __init__(self,query):self.query=query
        def scalar_one(self):return 'on'
        def mappings(self):return self
        def one(self):
            if 'rag_documentos' in self.query:
                return {'version':client.VERSION,'estado':'LISTA','fragments':432,'embeddings':432}
            return {'owner':'authorized','messages':2,'complete':1,'pending':0,'failed':0}
    class Connection:
        def __enter__(self):return self
        def __exit__(self,*_):pass
        def execute(self,query,params=None):
            query=str(query)
            statements.append((query,params))
            assert query.lstrip().upper().startswith(('SELECT','SHOW'))
            return Result(query)
        def rollback(self):pass
    class Engine:
        def connect(self):return Connection()
        def dispose(self):pass
    def create(*_,**kwargs):
        assert 'default_transaction_read_only=on' in kwargs['connect_args']['options']
        assert kwargs['hide_parameters'] is True
        return Engine()
    monkeypatch.setattr(sqlalchemy,'create_engine',create)
    monkeypatch.setattr(database,'load_database_config',lambda:SimpleNamespace(
        host='127.0.0.1',port=5434,database='usuarios_dev',url=lambda:'not-real'))
    result=client.database_snapshot([{'id':'controlled','owner':'authorized','message_count':2}])
    assert result['conversations'][0]['complete']==1
    assert any(params=={'id':'controlled'} for _,params in statements)


def test_auth_failure_no_retry_no_secret_output(capsys):
    http=FakeHTTP(lambda *_:client.Reply(401,{'error':{'codigo':'AUTH'}},.1))
    answers=iter(['email-private','password-private'])
    with pytest.raises(client.Stop):
        client.Account('ADMIN','ADMIN').login(http,lambda _:next(answers))
    assert len(http.calls)==1
    assert 'private' not in capsys.readouterr().out


def test_permission_failure_identifies_path_and_reason(tmp_path, monkeypatch):
    from app.application.agent import diagnostics
    monkeypatch.setattr(diagnostics, 'restricted_directory', lambda _: False)
    monkeypatch.setattr(client, 'permission_rejection', lambda _: 'herencia activa')
    with pytest.raises(client.Stop) as caught:
        client.private_directory(tmp_path)
    assert str(tmp_path.absolute()) in str(caught.value)
    assert 'herencia activa' in str(caught.value)


@pytest.mark.skipif(os.name != 'nt', reason='ACL nativa de Windows')
def test_new_windows_directory_passes_real_production_check(tmp_path):
    from app.application.agent.diagnostics import restricted_directory
    directory = tmp_path / ('run-' + uuid4().hex)
    client.private_directory(directory, create=True)
    assert restricted_directory(directory) is True
    assert not directory.is_symlink() and not directory.is_junction()
    # La creación debe ser exclusiva: nunca modifica ACL de un directorio existente.
    with pytest.raises(client.Stop):
        client.private_directory(directory, create=True)
    assert restricted_directory(directory) is True


@pytest.mark.skipif(os.name != 'nt', reason='Inicialización nativa de Windows')
def test_initialize_only_creates_private_checkpoint_without_services(tmp_path, monkeypatch, capsys):
    from app.application.agent.diagnostics import restricted_directory
    diagnostics = tmp_path / 'private-diagnostics'
    client.private_directory(diagnostics, create=True)
    def forbidden(*args, **kwargs):
        pytest.fail('initialize-only no debe autenticar ni contactar servicios')
    monkeypatch.setattr(client.Account, 'login', forbidden)
    monkeypatch.setattr(client.HTTP, 'request', forbidden)
    monkeypatch.setattr(client, 'database_snapshot', forbidden)
    output = tmp_path / 'acceptance-results'
    assert client.main(['--initialize-only', '--output-root', str(output),
                        '--diagnostic-dir', str(diagnostics)]) == 0
    assert restricted_directory(output)
    directories = list(output.glob('run-*'))
    assert len(directories) == 1 and restricted_directory(directories[0])
    report = json.loads((directories[0] / 'informe.json').read_text(encoding='utf-8'))
    assert report['identities'] == {} and report['conversations'] == {}
    assert all(row['status'] == 'NO EVALUADO' for row in report['results'].values())
    assert 'INICIALIZACIÓN APROBADA' in capsys.readouterr().out


def test_remote_general_not_blocked_by_local_model_threshold(tmp_path):
    data=state();data['provider']='openrouter'
    http=FakeHTTP(lambda *_:pytest.fail('General remoto no consulta Ollama'))
    run=client.Run(tmp_path/'report.json',data,http,memory=lambda:.8)
    assert run.resource_check('GENERAL')==.8
    with pytest.raises(client.Stop):run.resource_check('RAG')


def test_remote_rag_keeps_local_embedding_safety(tmp_path):
    data=state();data['provider']='openrouter'
    http=FakeHTTP(lambda *_:client.Reply(200,{'models':[]},.1))
    run=client.Run(tmp_path/'report.json',data,http,memory=lambda:1.2)
    assert run.resource_check('RAG')==1.2
    assert len(http.calls)==1


def test_cloud_rag_never_checks_ollama(tmp_path):
    data=state();data['provider']='openrouter';data['embedding_provider']='jina'
    http=FakeHTTP(lambda *_:pytest.fail('Jina no requiere Ollama'))
    run=client.Run(tmp_path/'report.json',data,http,memory=lambda:.8)
    assert run.resource_check('RAG')==.8
    run.memory=lambda:.2
    with pytest.raises(client.Stop):run.resource_check('RAG')
