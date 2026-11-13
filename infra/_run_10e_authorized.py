import sys,os,json,subprocess,hashlib,uuid,time,math
from pathlib import Path
sys.path.insert(0,str(Path.cwd()/'backend/src'))
import psycopg
from psycopg import sql
from app.infrastructure.configuration.database import load_database_config
C='api-usuarios-clean-postgres-1'
c=load_database_config(); assert(c.host,c.port,c.database)==('127.0.0.1',5434,'usuarios_dev')
runid=uuid.uuid4().hex
folder=Path('D:/Downloads/api-usuarios-clean-backups')/('10e-'+runid)
db='rag_restore_10e_'+runid
dump='/tmp/usuarios-dev-10e-'+runid+'.dump'
result={'folder':str(folder),'database':db,'container_dump':dump,'status':'STARTED'}
def cmd(args):
 p=subprocess.run(args,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
 if p.returncode: raise RuntimeError('command_failed:'+args[0]+':'+str(p.returncode))
 return p.stdout

def connect(name,ro=True):
 return psycopg.connect(host=c.host,port=c.port,dbname=name,user=c.username,password=c.password,connect_timeout=5,options='-c statement_timeout=60000'+(' -c default_transaction_read_only=on' if ro else ''))
def audit(conn):
 q=conn.cursor(); q.execute('SHOW transaction_read_only'); assert q.fetchone()[0]=='on'
 q.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename")
 tables=[r[0] for r in q.fetchall()]; hashes={}; counts={}
 for table in tables:
  q.execute(sql.SQL('SELECT to_jsonb(t)::text FROM public.{} t').format(sql.Identifier(table)))
  vals=sorted(hashlib.sha256(r[0].encode()).hexdigest() for r in q)
  hashes[table]=hashlib.sha256(''.join(vals).encode()).hexdigest();counts[table]=len(vals)
 q.execute('SELECT texto_extraido,hash_texto FROM rag_paginas'); assert all(hashlib.sha256(t.encode()).hexdigest()==h for t,h in q)
 q.execute('SELECT f.texto,f.hash_texto,p.texto_extraido,f.offset_inicio,f.offset_fin,f.pagina_inicio=f.pagina_fin,e.hash_entrada,e.embedding::text FROM rag_fragmentos f JOIN rag_paginas p ON p.version_id=f.version_id AND p.pagina_pdf=f.pagina_inicio JOIN rag_embeddings e ON e.fragmento_id=f.id')
 n=0
 for t,h,p,a,b,s,eh,v in q:
  assert s and p[a:b]==t and hashlib.sha256(t.encode()).hexdigest()==h==eh
  vec=json.loads(v);assert len(vec)==768 and all(math.isfinite(x) for x in vec) and sum(x*x for x in vec)>0;n+=1
 assert n==864 and counts['rag_fragmentos']==864 and counts['rag_embeddings']==864
 q.execute('SELECT v.id::text,v.estado,v.paginas,count(f.id) FROM rag_versiones v JOIN rag_fragmentos f ON f.version_id=v.id GROUP BY v.id ORDER BY v.id'); versions=q.fetchall()
 q.execute('SELECT activa_version_id::text FROM rag_documentos'); active=q.fetchall();assert active==[('7cb4e79c-747d-574a-8abb-0ebcb2e07636',)]
 q.execute('SELECT version_num FROM alembic_version');assert q.fetchall()==[('0005_agent_memory',)]
 q.execute("SELECT c.relname,c.relkind,pg_get_userbyid(c.relowner),c.relacl::text FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' ORDER BY c.relname,c.relkind"); acl=q.fetchall()
 q.execute("SELECT nspname,pg_get_userbyid(nspowner),nspacl::text FROM pg_namespace WHERE nspname='public'");acl+=q.fetchall()
 return {'table_hashes':hashes,'counts':counts,'versions':versions,'active':active,'acl':acl}
try:
 tools=cmd(['docker','exec',C,'pg_dump','--version']).decode().strip();assert '18.6' in tools
 assert '18.6' in cmd(['docker','exec',C,'pg_restore','--version']).decode()
 cmd(['docker','exec',C,'df','-k','/tmp','/var/lib/postgresql'])
 import shutil
 assert shutil.disk_usage(folder.parent).free>1024**3
 source=connect('usuarios_dev');source.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ')
 q=source.cursor();q.execute("SELECT rolsuper,rolcreatedb FROM pg_roles WHERE rolname=current_user"); assert q.fetchone()==(True,True)
 q.execute("SELECT count(*) FROM pg_stat_activity WHERE datname='usuarios_dev' AND pid<>pg_backend_pid() AND (xact_start IS NOT NULL OR state='active')");assert q.fetchone()[0]==0
 q.execute('SELECT pg_export_snapshot()'); snapshot=q.fetchone()[0]
 before=audit(source)
 q.execute("SELECT encoding,datcollate,datctype,datlocprovider,datlocale,pg_get_userbyid(datdba),datacl::text FROM pg_database WHERE datname=current_database()"); meta=q.fetchone()
 with connect('postgres') as check:
  assert not check.execute('SELECT 1 FROM pg_database WHERE datname=%s',(db,)).fetchone()
 # Create only the authorized fresh directory; restrict ACL before any sensitive file.
 ps="$ErrorActionPreference='Stop'; $p='"+str(folder)+"'; if(Test-Path -LiteralPath $p){throw 'exists'}; [void][IO.Directory]::CreateDirectory($p); $sid=[Security.Principal.WindowsIdentity]::GetCurrent().User; $acl=New-Object Security.AccessControl.DirectorySecurity; $acl.SetOwner($sid); $acl.SetAccessRuleProtection($true,$false); foreach($s in @($sid,(New-Object Security.Principal.SecurityIdentifier('S-1-5-18')))){ $r=New-Object Security.AccessControl.FileSystemAccessRule($s,'FullControl','ContainerInherit,ObjectInherit','None','Allow'); $acl.AddAccessRule($r) }; Set-Acl -LiteralPath $p -AclObject $acl; $v=Get-Acl -LiteralPath $p; if(!$v.AreAccessRulesProtected -or $v.Access.Count -ne 2){throw 'acl'}; foreach($r in $v.Access){if($r.IdentityReference.Translate([Security.Principal.SecurityIdentifier]).Value -notin @($sid.Value,'S-1-5-18')){throw 'principal'}}"
 cmd(['powershell','-NoProfile','-Command',ps])
 script='umask 077; test ! -e "$1" && exec pg_dump -U "$2" -d usuarios_dev --format=custom --lock-wait-timeout=5s --snapshot="$3" --file="$1"'
 started=time.monotonic();cmd(['docker','exec',C,'sh','-c',script,'sh',dump,c.username,snapshot]);result['dump_created']=True
 assert cmd(['docker','exec',C,'stat','-c','%a',dump]).strip()==b'600'
 listing=cmd(['docker','exec',C,'pg_restore','--list',dump]);assert listing
 (folder/'catalogo.txt').write_bytes(listing)
 cmd(['docker','cp',C+':'+dump,str(folder/'usuarios_dev.dump')])
 file=folder/'usuarios_dev.dump';assert file.stat().st_size>0
 sha=hashlib.sha256(file.read_bytes()).hexdigest();remote=cmd(['docker','exec',C,'sha256sum',dump]).decode().split()[0];assert sha==remote
 result.update(sha256=sha,size=file.stat().st_size,tools=tools)
 admin=connect('postgres',False);admin.autocommit=True
 create=sql.SQL('CREATE DATABASE {} WITH TEMPLATE template0 OWNER {} ENCODING {} LC_COLLATE {} LC_CTYPE {} LOCALE_PROVIDER {}').format(sql.Identifier(db),sql.Identifier(meta[5]),sql.Literal('UTF8'),sql.Literal(meta[1]),sql.Literal(meta[2]),sql.SQL({'c':'libc','i':'icu','b':'builtin'}[meta[3]]))
 if meta[3]=='i':create+=sql.SQL(' ICU_LOCALE {}').format(sql.Literal(meta[4]))
 elif meta[3]=='b':create+=sql.SQL(' BUILTIN_LOCALE {}').format(sql.Literal(meta[4]))
 admin.execute(create);result['database_created']=True;admin.close()
 with connect(db) as empty:assert empty.execute("SELECT count(*) FROM pg_tables WHERE schemaname='public'").fetchone()[0]==0
 cmd(['docker','exec',C,'pg_restore','-U',c.username,'--exit-on-error','--single-transaction','-d',db,dump]);result['restore_completed']=True
 with connect(db) as restored:
  after=audit(restored)
  assert before==after
  rmeta=restored.execute('SELECT encoding,datcollate,datctype,datlocprovider,datlocale,pg_get_userbyid(datdba),datacl::text FROM pg_database WHERE datname=current_database()').fetchone();assert meta==rmeta
 # source retained the dump snapshot; fresh source check detects post-dump changes without exposing content.
 source.rollback();source.close()
 with connect('usuarios_dev') as fresh: assert audit(fresh)==before
 result.update(status='VERIFIED',all_public_tables_equal=True,object_owners_acl_equal=True,database_owner_acl_locale_equal=True,source_unchanged_at_final_audit=True,fragments=864,embeddings=864,versions=before['versions'],seconds=round(time.monotonic()-started,3))
 (folder/'manifest.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
 print(json.dumps(result))
except BaseException as e:
 result.update(status='STOPPED',error_type=type(e).__name__)
 if folder.exists():
  # Directory ACL is established before sensitive artifacts; failure record contains no bodies or credentials.
  (folder/'failure-safe.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
 print(json.dumps(result));sys.exit(2)
