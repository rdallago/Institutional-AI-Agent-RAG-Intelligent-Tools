# Backend: preparación y operación aislada

FastAPI, Python **3.14.3**, SQLAlchemy 2.x, Psycopg 3, Alembic, Argon2id y JWT.
Usar el entorno `.venv` existente sin cambiar políticas PowerShell. Solo para
preparar un entorno nuevo, desde backend:

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -c constraints-httpx.txt -e ".[dev]"
.\.venv\Scripts\python.exe -m pip check
```

No recrear el entorno existente ni instalar globalmente. Dependencias directas
fijadas en pyproject.toml; no existe lock completo de transitivas Python.

En 9.2.2 HTTPX 0.28.1 pasa a dependencia runtime. `constraints-httpx.txt` fija su
árbol instalado para Python 3.14; es un bloqueo parcial de ese árbol, no del proyecto
completo. No instala paquetes por sí mismo. Desde 9.2.3 existe el endpoint protegido
`POST /api/v1/ia/consultas`, con IA **deshabilitada por defecto** y sin crear cliente
Ollama en ese estado. El piloto habilitado requiere contexto de socket local y un
worker en la composición; los scripts actuales no lo activan. No se debe habilitar
con solo editar `.env`. Ver [informe 9.2.3](../docs/sprint-9-2-3-integracion-fastapi-ia.md).

## Habilitación local explícita (8.6D)

El arranque habitual y la CLI de bootstrap/asignación permanecen cerrados.
Solo para la instancia local de práctica autorizada, con `usuarios_dev` en
`127.0.0.1:5434` y revisión efectiva `0003`, desde backend:

```powershell
.\.venv\Scripts\python.exe -B -m app.presentation.cli.local_server --environment local-development --enable-initial-provisioning --host 127.0.0.1 --port 8000
```

No ejecutar mientras otro proceso ocupe 8000. El lanzador reserva el socket real
en loopback, verifica identidad y revisión mediante lectura de la base y luego
inyecta la política únicamente en el servicio administrativo de esa instancia.
Rechaza `test`/`production`, otros destinos y hosts. No lee una variable `.env`
para abrir la barrera ni modifica claves JWT. Los tests conservan su configuración
aislada; nunca usar este lanzador para pruebas automatizadas.

Para volver a cerrar: detener solo esa instancia propia y arrancar sin
`--enable-initial-provisioning`, o utilizar el arranque habitual
`uvicorn app.bootstrap:create_app --factory --host 127.0.0.1 --port 8000
--no-proxy-headers --no-access-log`. No requiere cambios en datos o configuración
persistente. Cerrar la barrera no revoca credenciales ya emitidas ni elimina su
obligación de cambio. No publicar esta habilitación fuera del equipo local.

## PostgreSQL y configuración

**El backend actual requiere esquema 0003. Nunca iniciarlo contra 0001/0002.**
No migra automáticamente ni utiliza create_all. Compose usa PostgreSQL 18.
Pruebas: `usuarios_test`, `usuarios_test_admin`, **127.0.0.1:5435**, servicio Docker
aislado existente. No modificar ni borrar contenedores/volúmenes ajenos.

Pruebas cargan únicamente `.env.test`, prefijos `TEST_POSTGRES_*` y `TEST_AUTH_*`.
Desarrollo carga `.env`, prefijos `POSTGRES_*`/`AUTH_*`, fuera de estos comandos.
Los archivos locales están ignorados; no incorporar valores en ejemplos o logs.
Auth requiere JWT_KEYS_JSON (mapa kid a clave base64), JWT_CURRENT_KID y LIMITER_KEY
base64, con el prefijo de entorno. JWT/limitador usan claves independientes de al
menos 32 bytes. No hay claves predeterminadas ni reutilización de las de desarrollo.

Verificar **por lectura antes de integrar o arrancar**:

```powershell
@'
from sqlalchemy import text
from app.infrastructure.configuration.database import load_database_config
from app.infrastructure.persistence.database import build_engine
c = load_database_config(testing=True)
c.require_test_database()
assert (c.host, c.port, c.database) == ('127.0.0.1', 5435, 'usuarios_test')
engine = build_engine(c)
try:
    with engine.connect() as connection:
        assert tuple(connection.execute(text('SELECT current_database(), current_user')).one()) == ('usuarios_test', 'usuarios_test_admin')
        assert connection.execute(text('SELECT version_num FROM public.alembic_version')).scalar_one() == '0003'
finally:
    engine.dispose()
print('Destino de pruebas y revision 0003 confirmados')
'@ | .\.venv\Scripts\python.exe -
```

Si falla, detenerse, sin fallback a desarrollo. Un esquema de pruebas distinto
necesita un procedimiento autorizado de migración de pruebas antes del inicio.
No ejecutar el backend sobre él ni debilitar las protecciones.

## Inicio de la API aislada

Con preflight satisfactorio:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.bootstrap:create_test_database_app --factory --host 127.0.0.1 --port 8001 --no-proxy-headers
```

Swagger http://127.0.0.1:8001/docs, OpenAPI /openapi.json. Ctrl+C detiene el proceso
propio. La raíz devuelve 404. El limitador usa Request.client, sin confianza en
cabeceras arbitrarias de proxy.

El login requiere una cuenta ficticia existente/autorizada. Las suites limpian
sus fixtures y no dejan cuentas para un servidor posterior. **Bootstrap, alta y
asignación inicial están bloqueados por código**. No sortearlo mediante SQL o
datos reales. Los arneses preparan cuentas solo dentro de las pruebas aisladas.

## Seguridad y persistencia

Sesiones persistidas/revocables de 900 s; JWT ligado a usuario activo y credencial.
ADMIN pendiente no administra. Me entrega perfil normal más false o contexto
mínimo id/true. Password actual/nueva permite cambio obligatorio/voluntario, revoca
todas las sesiones y exige nuevo login, sin promover una sesión restringida.
Login y cambio comparten límites; un fallo técnico no debe crear una sesión sin
entregar. Errores no exponen secretos, hashes, SQL o cuerpos originales.

La composición ocurre durante lifespan. UoW confirma/revierte operaciones
compuestas, rehash conserva flags/antecedente e inserción inicial es estricta.
No hay reset, refresh, historial general ni TTL de inicial. La barrera no tiene
opción CLI/entorno para abrirse.

## Verificaciones

```powershell
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider --basetemp=.pytest_cache/unit-temp
.\.venv\Scripts\python.exe -m pytest -q --run-postgres -p no:cacheprovider --basetemp=.pytest_cache/full-temp
.\.venv\Scripts\python.exe -m alembic -x target=test current
.\.venv\Scripts\python.exe -m alembic -x target=test check
```

Integraciones limpian tablas y prueban reversiones solo en usuarios_test; sin
--run-postgres se omiten. Los arneses necesitan navegadores/Node instalados,
puertos loopback libres y destino comprobado. No ejecutar pruebas en desarrollo.

## Desarrollo y despliegue: todavía no ejecutar

Usuarios_dev en 5434 no se consulta, migra ni inicia durante esta preparación.
Requiere autorización y la lista de [8.6B](../docs/sprint-8-6b-preparacion.md),
basada en [8.6A](../docs/sprint-8-6a-auditoria.md). Migración futura explícita a
0003, respaldo, mantenimiento, integridad y versiones coordinadas. No hacer
downgrade ni mezclar workers viejos con credenciales/sesiones nuevas.
La autorización de migrar no abre el aprovisionamiento.
