"""Pasos explicitos de mantenimiento 93E; sin ejecucion al importar.

Estado/dumps privados fuera del repositorio. Nunca imprime contenido, credenciales
o huellas. Cada fase se invoca por separado; cualquier fallo detiene esa invocacion.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import subprocess
import time

import psycopg
from psycopg import sql

from app.infrastructure.configuration.database import load_database_config

ROOT = Path(__file__).resolve().parents[2]
PRIVATE = Path('D:/Downloads/api-usuarios-clean-backups/93e-20261103')
SOURCE = 'ce41dbdca5f0508f78ec4fbdc47b8e296f59eee93d04621a0cd5e1038a4bf749'
OLD_IMAGE = 'sha256:979bccfde35445db618c65107d27d08c6c21339d8dc3ad4c830c6633947be0e4'
IMAGE = 'sha256:a1336b54a1b49085474132cceb0636b314707b011fdb242afa694ae08ffcc3e6'
VOLUME = 'api-usuarios-clean-pgvector-93e-data'
RESTORE = 'api-usuarios-clean-93e-restore'
BOOTSTRAP = 'maintenance_93e_bootstrap'

# Allowlist de dos pares completos, no un normalizador SQL general. En PostgreSQL
# el cast varchar[] -> text[] aplica el mismo cast a cada elemento y preserva NULL
# y forma del array. Estas constantes escalares usan la misma collation/igualdad.
CHECK_VARIANTS = {
    ('usuarios', 'ck_usuarios_rol'): frozenset({
        "CHECK (((rol)::text = ANY ((ARRAY['ADMIN'::character varying, 'USUARIO'::character varying])::text[])))",
        "CHECK (((rol)::text = ANY (ARRAY[('ADMIN'::character varying)::text, ('USUARIO'::character varying)::text])))",
    }),
    ('auth_intentos', 'ck_intentos_ambito'): frozenset({
        "CHECK (((ambito)::text = ANY ((ARRAY['ip'::character varying, 'email_ip'::character varying])::text[])))",
        "CHECK (((ambito)::text = ANY (ARRAY[('ip'::character varying)::text, ('email_ip'::character varying)::text])))",
    }),
}


def constraints_equivalent(table, name, left, right):
    if left == right:
        return True
    allowed = CHECK_VARIANTS.get((table, name), frozenset())
    return left in allowed and right in allowed


def snapshots_equal(left, right):
    if left.keys() != right.keys():
        return False
    if any(left[key] != right[key] for key in left if key != 'constraints'):
        return False
    a, b = left['constraints'], right['constraints']
    return len(a) == len(b) and all(
        x[:2] == y[:2] and constraints_equivalent(*x[:2], x[2], y[2])
        for x, y in zip(a, b))


def run(args, *, input=None, env=None):
    result = subprocess.run(args, input=input, capture_output=True, env=env)
    if result.returncode:
        # Solo archivos privados, no consola. No guardar input potencialmente secreto.
        (PRIVATE / 'last-error.private').write_bytes(result.stderr)
        raise RuntimeError('Comando de mantenimiento fallido; fase detenida.')
    return result.stdout.decode('utf-8')


def docker(*args, **kwargs):
    return run(['docker', *args], **kwargs)


def config():
    c = load_database_config()
    if (c.host, c.port, c.database) != ('127.0.0.1', 5434, 'usuarios_dev'):
        raise RuntimeError('Destino no autorizado.')
    return c


def connection():
    c = config()
    return psycopg.connect(host=c.host, port=c.port, dbname=c.database,
                          user=c.username, password=c.password, connect_timeout=5,
                          options='-c default_transaction_read_only=on -c statement_timeout=10000 -c lock_timeout=1000')


def query_container(container, query, *, database='usuarios_dev', user=None):
    c = config()
    return docker('exec', '-i', container, 'psql', '-X', '-qAt', '-v', 'ON_ERROR_STOP=1',
                  '-U', user or c.username, '-d', database, input=query.encode())


def snapshot(fetch, *, expected_revision='0003'):
    data = {}
    queries = {
        'database': "SELECT current_database(),current_setting('server_version'),pg_encoding_to_char(encoding),datcollate,datctype,pg_get_userbyid(datdba),datacl::text FROM pg_database WHERE datname=current_database()",
        'columns': "SELECT table_name,column_name,ordinal_position,data_type,udt_name,is_nullable,column_default,collation_name FROM information_schema.columns WHERE table_schema='public' ORDER BY table_name,ordinal_position",
        'constraints': "SELECT c.relname,k.conname,pg_get_constraintdef(k.oid) FROM pg_constraint k JOIN pg_class c ON c.oid=k.conrelid JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' ORDER BY c.relname,k.conname",
        'indexes': "SELECT tablename,indexname,indexdef FROM pg_indexes WHERE schemaname='public' ORDER BY tablename,indexname",
        'permissions': "SELECT c.relname,pg_get_userbyid(c.relowner),c.relacl::text FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND c.relkind IN ('r','S') ORDER BY c.relname",
        'schema_permissions': "SELECT nspname,pg_get_userbyid(nspowner),nspacl::text FROM pg_namespace WHERE nspname='public'",
        'roles': "SELECT rolname,rolsuper,rolinherit,rolcreaterole,rolcreatedb,rolcanlogin,rolreplication,rolbypassrls,rolconnlimit,rolvaliduntil::text FROM pg_roles WHERE rolname !~ '^pg_' AND rolname <> 'maintenance_93e_bootstrap' ORDER BY rolname",
        'revision': 'SELECT version_num FROM public.alembic_version ORDER BY version_num',
    }
    for key, query in queries.items():
        data[key] = fetch(query)
    if data['revision'] != [[expected_revision]]:
        raise RuntimeError('Revision inesperada.')
    tables = fetch("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename")
    records = {}
    for (table,) in tables:
        ident = '"' + table.replace('"', '""') + '"'
        rows = fetch(f'SELECT row_to_json(t)::text FROM public.{ident} t')
        # Comparacion exacta multiconjunto en memoria; nunca se guardan filas.
        hashes = sorted(hashlib.sha256(row[0].encode()).hexdigest() for row in rows)
        records[table] = {'count': len(rows), 'digest': hashlib.sha256(''.join(hashes).encode()).hexdigest()}
    data['records'] = records
    return data


def source_snapshot(*, expected_revision='0003'):
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute('SHOW transaction_read_only')
            if cur.fetchone()[0] != 'on': raise RuntimeError('Falta READ ONLY.')
            cur.execute("SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() AND pid<>pg_backend_pid() AND backend_type='client backend'")
            if cur.fetchone()[0] != 0: raise RuntimeError('Otros clientes presentes; no respaldar.')
            def fetch(query):
                cur.execute(query)
                return [list(row) for row in cur.fetchall()]
            result = snapshot(fetch, expected_revision=expected_revision)
        conn.rollback()
    return result


def target_snapshot():
    def fetch(query):
        wrapped = 'BEGIN READ ONLY; SELECT coalesce(json_agg(row_to_json(x)),\'[]\'::json) FROM (' + query + ') x; ROLLBACK;'
        rows = json.loads(query_container(RESTORE, wrapped).strip())
        return [list(row.values()) for row in rows]
    return snapshot(fetch)


def backup():
    metadata = json.loads(docker('inspect', SOURCE))[0]
    if metadata['Image'] != OLD_IMAGE or metadata['Name'] != '/api-usuarios-clean-postgres-1':
        raise RuntimeError('Contenedor origen inesperado.')
    if [m.get('Name') for m in metadata['Mounts']] != ['api-usuarios-clean_postgres_data']:
        raise RuntimeError('Volumen origen inesperado.')
    if (PRIVATE / 'usuarios_dev.dump').exists(): raise RuntimeError('No sobrescribir respaldo.')
    baseline = source_snapshot()
    c = config()
    if c.username == BOOTSTRAP or not any(r[0] == c.username and r[1] for r in baseline['roles']):
        raise RuntimeError('Permisos de restauracion incompatibles.')
    (PRIVATE / 'baseline.private.json').write_text(json.dumps(baseline), encoding='utf-8')
    docker('exec', SOURCE, 'pg_dump', '-U', c.username, '-d', c.database, '-Fc', '-f', '/tmp/usuarios-dev-93e.dump')
    docker('exec', SOURCE, 'pg_dumpall', '-U', c.username, '--globals-only', '--no-role-passwords', '-f', '/tmp/roles-93e.sql')
    docker('cp', SOURCE + ':/tmp/usuarios-dev-93e.dump', str(PRIVATE / 'usuarios_dev.dump'))
    docker('cp', SOURCE + ':/tmp/roles-93e.sql', str(PRIVATE / 'roles.sql'))
    docker('exec', SOURCE, 'pg_restore', '--list', '/tmp/usuarios-dev-93e.dump')
    if baseline != source_snapshot(): raise RuntimeError('Origen cambio durante respaldo.')
    results = {}
    for name in ['usuarios_dev.dump', 'roles.sql']:
        content = (PRIVATE / name).read_bytes()
        if not content: raise RuntimeError('Respaldo vacio.')
        results[name] = {'bytes': len(content), 'sha256': hashlib.sha256(content).hexdigest()}
    (PRIVATE / 'backup-manifest.private.json').write_text(json.dumps(results), encoding='utf-8')
    print('BACKUP_OK: destino, revision, ausencia de clientes, archivos y SHA256 verificados; sin imprimir huellas.')


def restore():
    manifest = json.loads((PRIVATE / 'backup-manifest.private.json').read_text())
    for name, expected in manifest.items():
        if hashlib.sha256((PRIVATE / name).read_bytes()).hexdigest() != expected['sha256']:
            raise RuntimeError('Integridad del respaldo incorrecta.')
    existing_volumes = docker('volume', 'ls', '--format', '{{.Name}}').splitlines()
    existing_names = docker('ps', '-a', '--format', '{{.Names}}').splitlines()
    if VOLUME in existing_volumes or RESTORE in existing_names: raise RuntimeError('Recurso ya existe.')
    docker('volume', 'create', '--label', 'app.sprint=93e', VOLUME)
    env = os.environ.copy()
    env['POSTGRES_PASSWORD'] = secrets.token_urlsafe(32)
    docker('run', '-d', '--name', RESTORE, '--label', 'app.sprint=93e', '--network', 'none',
           '--memory', '256m', '--memory-swap', '256m', '--cpus', '0.5', '--shm-size', '16m',
           '--mount', f'type=volume,source={VOLUME},target=/var/lib/postgresql',
           '-e', 'POSTGRES_PASSWORD', '-e', 'POSTGRES_USER='+BOOTSTRAP, '-e', 'POSTGRES_DB=postgres',
           IMAGE, 'postgres', '-c', 'listen_addresses=', '-c', 'shared_buffers=32MB',
           '-c', 'work_mem=1MB', '-c', 'maintenance_work_mem=16MB', '-c', 'max_connections=10', env=env)
    for _ in range(60):
        ready = subprocess.run(['docker','exec',RESTORE,'pg_isready','-q','-U',BOOTSTRAP,'-d','postgres'],capture_output=True)
        if ready.returncode == 0: break
        time.sleep(1)
    else: raise RuntimeError('Restauracion no disponible.')
    docker('cp', str(PRIVATE/'roles.sql'), RESTORE+':/tmp/roles.sql')
    docker('cp', str(PRIVATE/'usuarios_dev.dump'), RESTORE+':/tmp/usuarios_dev.dump')
    docker('exec',RESTORE,'psql','-X','-v','ON_ERROR_STOP=1','-U',BOOTSTRAP,'-d','postgres','-f','/tmp/roles.sql')
    c = config()
    # Literal/identificador SQL citados por psycopg; solo stdin, nunca argumentos/logs.
    command = sql.SQL('ALTER ROLE {} PASSWORD {};').format(sql.Identifier(c.username),sql.Literal(c.password)).as_string()
    query_container(RESTORE,command,database='postgres',user=BOOTSTRAP)
    docker('exec',RESTORE,'pg_restore','-U',BOOTSTRAP,'-d','postgres','--create','--exit-on-error','/tmp/usuarios_dev.dump')
    baseline=json.loads((PRIVATE/'baseline.private.json').read_text())
    if not snapshots_equal(target_snapshot(), baseline): raise RuntimeError('Restauracion difiere del origen; NO sustituir.')
    # PostgreSQL impide quitar SUPERUSER al rol bootstrap inicial (OID 10).
    # Deshabilitar login/password y comprobar que no haya miembros en su lugar.
    query_container(RESTORE,sql.SQL('ALTER ROLE {} NOLOGIN CONNECTION LIMIT 0 PASSWORD NULL;').format(sql.Identifier(BOOTSTRAP)).as_string())
    (PRIVATE/'restore-verified.txt').write_text('OK',encoding='ascii')
    print('RESTORE_OK: todas las filas, tablas, constraints, indices, propietarios, ACL, roles y revision coinciden.')


def cutover():
    """Promover solo tras aprobacion explicita; rollback antes de reabrir clientes."""
    if not (PRIVATE/'restore-verified.txt').exists():
        raise RuntimeError('Copia no aprobada.')
    baseline = json.loads((PRIVATE/'baseline.private.json').read_text())
    if not snapshots_equal(source_snapshot(), target_snapshot()):
        raise RuntimeError('Copia no vigente.')
    original = json.loads(docker('inspect', SOURCE))[0]
    if original['Image'] != OLD_IMAGE or original['Mounts'][0]['Name'] != 'api-usuarios-clean_postgres_data':
        raise RuntimeError('Origen incorrecto.')
    (PRIVATE/'original-container.private.json').write_text(json.dumps(original),encoding='utf-8')
    docker('stop','--timeout','20',RESTORE)
    docker('stop','--timeout','20',SOURCE)
    try:
        docker('compose','-f','compose.yaml','-f','compose.override.yaml','up','-d','--no-deps','--pull','never','postgres')
        for _ in range(30):
            state = json.loads(docker('inspect','api-usuarios-clean-postgres-1'))[0]
            if state['State'].get('OOMKilled') or state['State']['Status'] != 'running':
                raise RuntimeError('Candidato no estable.')
            if state['State'].get('Health',{}).get('Status') == 'healthy':
                break
            time.sleep(1)
        else: raise RuntimeError('Healthcheck no disponible.')
        if state['Image'] != IMAGE or [x.get('Name') for x in state['Mounts']] != [VOLUME]:
            raise RuntimeError('Imagen/volumen candidato incorrectos.')
        if not snapshots_equal(source_snapshot(), baseline):
            raise RuntimeError('Datos promovidos no coinciden.')
        (PRIVATE/'cutover-verified.txt').write_text(state['Id'],encoding='ascii')
        print('CUTOVER_APPROVED: PostgreSQL 18.6, password existente, datos y permisos coinciden, healthy.')
    except Exception:
        # Compose base vuelve al volumen original y su imagen conservada.
        docker('compose','-f','compose.yaml','up','-d','--no-deps','--pull','never','postgres')
        print('CUTOVER_FAILED: rollback solicitado al servicio/volumen originales; no reabrir clientes sin verificar.')
        raise


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('phase',choices=['backup','restore','cutover'])
    args=parser.parse_args()
    try:
        if not PRIVATE.is_dir(): raise RuntimeError('Directorio privado ausente.')
        config()
        {'backup':backup,'restore':restore,'cutover':cutover}[args.phase]()
    except Exception:
        print('FASE DETENIDA: fallo de comprobacion u operacion. No continuar automaticamente.')
        raise SystemExit(1)
