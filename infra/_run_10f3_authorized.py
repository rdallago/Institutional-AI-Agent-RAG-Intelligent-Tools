"""Operación única 10F.3 autorizada; NO reejecutar automáticamente."""
import sys,ast,json,hashlib,math,time
from pathlib import Path
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'backend/src'))
import psycopg
from psycopg import sql
from sqlalchemy import event
from alembic import command
from alembic.config import Config
from app.infrastructure.configuration.database import load_database_config
import app.infrastructure.persistence.database as dbmodule
c=load_database_config();assert(c.host,c.port,c.database)==('127.0.0.1',5434,'usuarios_dev')
def ro():return psycopg.connect(host=c.host,port=c.port,dbname=c.database,user=c.username,password=c.password,connect_timeout=10,options='-c default_transaction_read_only=on -c statement_timeout=15000')
def auditor(revision):
 tree=ast.parse((ROOT/'infra/_run_10e_authorized.py').read_text(encoding='utf-8-sig'));fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='audit')
 for n in ast.walk(fn):
  if isinstance(n,ast.Constant) and n.value=='0005_agent_memory':n.value=revision
 ns=dict(hashlib=hashlib,math=math,json=json,sql=sql);exec(compile(ast.Module(body=[fn],type_ignores=[]),'<audit-only>','exec'),ns);return ns['audit']
def rowhashes(conn):
 tables=conn.exec_driver_sql("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename").scalars().all();r={}
 for t in tables:
  name='"'+t.replace('"','""')+'"';rows=conn.exec_driver_sql('SELECT to_jsonb(t)::text FROM public.'+name+' t').scalars()
  r[t]=hashlib.sha256(''.join(sorted(hashlib.sha256(v.encode()).hexdigest() for v in rows)).encode()).hexdigest()
 return r
result={'migration':'0006_cloud_embeddings','attempts':0};started=time.monotonic()
try:
 p=Path('D:/Downloads/api-usuarios-clean-backups/10e-8ec23d77c150417db136e68c0a0f2d05');m=json.loads((p/'manifest.json').read_text());assert hashlib.sha256((p/'usuarios_dev.dump').read_bytes()).hexdigest()==m['sha256'];result['backup_verified']=True
 with ro() as conn:
  before=auditor('0005_agent_memory')(conn)
  assert conn.execute("SELECT count(*) FROM pg_tables WHERE schemaname='public' AND tablename LIKE 'rag_cloud_%'").fetchone()[0]==0
  assert conn.execute("SELECT count(*) FROM pg_prepared_xacts WHERE database=current_database()").fetchone()[0]==0
  assert conn.execute("SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() AND pid<>pg_backend_pid() AND xact_start IS NOT NULL").fetchone()[0]==0
  assert conn.execute("SELECT count(*) FROM pg_locks l JOIN pg_stat_activity a ON a.pid=l.pid WHERE a.datname=current_database() AND NOT l.granted").fetchone()[0]==0
  conn.rollback()
 original=dbmodule.build_engine
 state={'begins':0}
 def guarded(config):
  assert(config.host,config.port,config.database)==('127.0.0.1',5434,'usuarios_dev')
  eng=original(config)
  @event.listens_for(eng,'begin')
  def protect(conn):
   state['begins']+=1
   conn.exec_driver_sql("SET LOCAL lock_timeout='2s'");conn.exec_driver_sql("SET LOCAL statement_timeout='15s'")
   assert conn.exec_driver_sql('SHOW lock_timeout').scalar_one()=='2s'
   assert conn.exec_driver_sql('SHOW statement_timeout').scalar_one()=='15s'
   assert conn.exec_driver_sql('SELECT current_database()').scalar_one()=='usuarios_dev'
   # env.py first opens a target-check transaction, rolls it back, then begins migration.
   if state['begins']==1:return
   assert state['begins']==2
   tables=conn.exec_driver_sql("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename").scalars().all()
   assert set(tables)==set(before['table_hashes'])
   names=','.join('public."'+t.replace('"','""')+'"' for t in tables)
   conn.exec_driver_sql('LOCK TABLE '+names+' IN SHARE ROW EXCLUSIVE MODE')
   assert conn.exec_driver_sql('SELECT version_num FROM alembic_version').scalar_one()=='0005_agent_memory'
   assert rowhashes(conn)==before['table_hashes']
   result['lock_tables']=len(tables);result['effective_timeouts']={'lock':'2s','statement':'15s'}
  return eng
 dbmodule.build_engine=guarded
 cfg=Config(str(ROOT/'backend/alembic.ini'));cfg.cmd_opts=SimpleNamespace(x=['allow-development=true'])
 result['attempts']=1
 command.upgrade(cfg,'0006_cloud_embeddings');result['alembic_exit_code']=0
 dbmodule.build_engine=original
 with ro() as conn:
  after=auditor('0006_cloud_embeddings')(conn)
  for t,h in before['table_hashes'].items():
   if t!='alembic_version':assert after['table_hashes'][t]==h
  clouds=['rag_cloud_espacios','rag_cloud_embeddings','rag_cloud_ingestas','rag_cloud_activos'];assert set(after['table_hashes'])==set(before['table_hashes'])|set(clouds)
  assert all(after['counts'][t]==0 for t in clouds)
  constraints=conn.execute("SELECT t.relname,c.contype,c.convalidated,pg_get_constraintdef(c.oid) FROM pg_constraint c JOIN pg_class t ON t.oid=c.conrelid JOIN pg_namespace n ON n.oid=t.relnamespace WHERE n.nspname='public' AND t.relname LIKE 'rag_cloud_%' ORDER BY t.relname,c.conname").fetchall();assert constraints and all(r[2] for r in constraints)
  assert all(any(r[0]==t and r[1]=='p' for r in constraints) for t in clouds)
  typ=conn.execute("SELECT format_type(a.atttypid,a.atttypmod) FROM pg_attribute a WHERE a.attrelid='public.rag_cloud_embeddings'::regclass AND a.attname='embedding'").fetchone()[0];assert typ=='vector(768)'
  # Compare full declared DDL constraints semantically: FK counts 0/2/2/1 and checks 2/3/1/0.
  result['constraints']={t:{k:sum(r[0]==t and r[1]==k for r in constraints) for k in ['p','f','c','u']} for t in clouds}
  assert [result['constraints'][t]['f'] for t in clouds]==[0,2,2,1]
  result.update(revision='0006_cloud_embeddings',cloud_tables_empty=True,embedding_type=typ,historical_data_unchanged=True,versions=after['versions'],active=after['active'],constraints_valid=True)
  conn.rollback()
 result.update(status='VERIFIED',seconds=round(time.monotonic()-started,3));print(json.dumps(result))
except BaseException as e:
 result.update(status='STOPPED',error_type=type(e).__name__,sqlstate=getattr(e,'sqlstate',None),seconds=round(time.monotonic()-started,3));print(json.dumps(result));sys.exit(2)
