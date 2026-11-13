"""Coordinación completamente simulada, sin servicios."""
import pytest
from app.presentation.cli import index_jina_all as coordinator

@pytest.mark.parametrize('start',[0,1,10,431,432])
def test_sequential_resume_432(start,capsys):
    state={'count':start};limits=[]
    def batch(n):
        assert 1<=n<=10
        limits.append(n);state['count']+=n;return 0
    assert coordinator.coordinate(lambda:state['count'],batch)==432
    assert sum(limits)==432-start
    if start==0:assert limits==[10]*43+[2]

@pytest.mark.parametrize('failure',['http','timeout','sql','progress','exception'])
def test_stop_without_second_batch(failure):
    calls=[]
    def batch(n):
        calls.append(n)
        if failure=='exception':raise TimeoutError('synthetic')
        return 0 if failure=='progress' else 2
    with pytest.raises((RuntimeError,TimeoutError)):
        coordinator.coordinate(lambda:0,batch)
    assert calls==[10]

@pytest.mark.parametrize('args',[[],['--execute'],['--execute','--approve-document-export'],
    ['--execute','--approve-document-export','--confirm-free-usage']])
def test_no_authorization_no_services(monkeypatch,args):
    monkeypatch.setattr(coordinator,'load_embedding_config',lambda:pytest.fail('No configuration/services'))
    assert coordinator.main(args)==2

@pytest.mark.parametrize('count',[-1,433,True,None])
def test_bad_progress_no_batch(count):
    with pytest.raises(RuntimeError):coordinator.coordinate(lambda:count,lambda n:pytest.fail('No batch'))
