# Etapa 6: API REST de usuarios

> Documento histórico: sus revisiones y comandos describen esa etapa, no el inicio actual.
> El backend vigente requiere **0003**, pruebas solo en usuarios_test:5435, cambio
> obligatorio implementado y aprovisionamiento cerrado. Seguir [la guía backend](../backend/README.md)
> y [preparación 8.6B](sprint-8-6b-preparacion.md). No ejecutar operaciones de desarrollo
> ni iniciar este código con 0001/0002 a partir de instrucciones históricas.

Documento de la etapa 6. La seguridad actual y los requisitos para ejecutar la
API se describen en [Sprint 7](sprint-7-autenticacion.md). Sus endpoints ahora
requieren Bearer y permisos; no ejecutar los ejemplos sin ese contexto.

Implementación y verificaciones del 29 de octubre de 2026. Se conservaron Domain,
Application, DTO, casos de uso y contrato UserRepository sin modificaciones.
No se avanzó a etapa 7.

## Operaciones

| Método | Ruta | Éxito | Caso de uso existente |
| --- | --- | --- | --- |
| POST | /api/v1/usuarios | 201, usuario y Location | CrearUsuario |
| GET | /api/v1/usuarios | 200, array | ListarUsuarios |
| GET | /api/v1/usuarios/{id} | 200, usuario | ObtenerUsuario |
| PUT | /api/v1/usuarios/{id} | 200, usuario | ModificarUsuario |
| DELETE | /api/v1/usuarios/{id} | 204 sin cuerpo | DarDeBajaUsuario |
| PATCH | /api/v1/usuarios/{id}/reactivar | 200, usuario | ReactivarUsuario |

Crear exige nombre, apellido y email; rol es opcional, USUARIO por defecto.
PUT exige los tres campos editables y rechaza rol, activo, identidad y fecha.
Los esquemas rechazan campos adicionales y valores que no sean cadenas en los
datos personales. El dominio mantiene validaciones y normalización; no se usa
EmailStr ni otra política de email. Las respuestas serializan UUID, Rol, booleanos
y fechas UTC. Las operaciones de estado admiten cuerpo ausente, null o `{}`,
y rechazan campos de negocio.

Listado: estado=activos, limite=20, desplazamiento=0. Estados: activos, inactivos,
todos. Límite de 1 a 100 y desplazamiento no negativo; Application valida esos
rangos. Se filtra antes de paginar y se ordena por fecha e ID. Devuelve un array
sin total. GET individual y PUT admiten usuarios inactivos.

Baja y reactivación son idempotentes. DELETE no borra filas; repetir devuelve 204.
Reactivar conserva identidad, fecha y datos. Un alta duplicada nunca reactiva al
propietario ni modifica sus datos.

## Errores y diagnóstico seguro

```json
{
  "error": {
    "codigo": "USUARIO_INACTIVO_REACTIVABLE",
    "mensaje": "El usuario está dado de baja y puede reactivarse explícitamente.",
    "usuario_id": "550e8400-e29b-41d4-a716-446655440000"
  }
}
```

- 422: estructura, tipos, UUID, filtros, paginación o reglas de dominio inválidas.
  Los errores de campos usan detalles con campo, código y mensaje saneados.
- 404: USUARIO_NO_ENCONTRADO, con usuario_id.
- 409: USUARIO_ACTIVO_EXISTENTE, USUARIO_INACTIVO_REACTIVABLE (incluye usuario_id)
  o EMAIL_EN_USO.
- 500: ERROR_PERSISTENCIA o ERROR_INTERNO, sin detalles técnicos al cliente.

Los errores Pydantic omiten input, ctx, cuerpos y nombres de campos desconocidos.
Las filas inválidas al reconstruir entidades se envuelven como ErrorPersistencia,
evitando atribuir corrupción almacenada a una solicitud válida. No se distingue
503 porque la excepción existente agrupa varios tipos de fallo técnico.

El logger app.http.errors registra código, clase, método, plantilla de ruta y
archivo/línea/función. Nunca registra mensaje original, SQL, credenciales, cuerpos
ni variables locales. Una frontera HTTP captura errores inesperados antes de que
el servidor ASGI vuelva a lanzar y registrar la excepción original. Los logs de
acceso normales siguen siendo responsabilidad de Uvicorn.

## Composición y recursos

create_app(repository=...) permite inyectar memoria o un repositorio de pruebas.
En ese modo no carga configuración PostgreSQL ni construye Engine.
Sin repositorio, lifespan reutiliza crear_persistencia_postgresql y guarda el
repositorio en app.state. Al cerrar elimina esa referencia y llama a dispose()
fuera del event loop. No hay conexión al importar main ni migración al iniciar.
Los endpoints def delegan en los casos de uso; las sesiones/commit/rollback
permanecen dentro del repositorio. Depends solo pertenece al límite HTTP.

## Pruebas manuales de escritura: solo usuarios_test

Desde la raíz, verificar primero Docker Desktop y el entorno aislado existente:

```powershell
docker compose --env-file .env.test -f compose.test.yaml ps
```

Si no está iniciado (el puerto 5435 debe estar disponible para este proyecto):

```powershell
docker compose --env-file .env.test -f compose.test.yaml up -d --wait postgres
```

El almacenamiento de pruebas es tmpfs. Si se reinició y perdió su esquema,
aplicar únicamente la migración de pruebas, desde backend:

```powershell
Set-Location backend
.\.venv\Scripts\python.exe -m alembic -x target=test upgrade head
.\.venv\Scripts\python.exe -m uvicorn app.bootstrap:create_test_database_app --factory --host 127.0.0.1 --port 8001
```

Esta fábrica carga solo TEST_POSTGRES_* desde .env.test y exige usuarios_test,
usuario de pruebas y puerto 5435. Si no coincide, falla. No reemplaza ni edita
.env. No ejecutar otra aplicación de desarrollo en el puerto 8001.

Swagger: http://127.0.0.1:8001/docs

OpenAPI: http://127.0.0.1:8001/openapi.json

En Swagger ejecutar alta, consulta, edición, baja y reactivación. Ejemplo de alta:

```json
{"nombre":"Ana","apellido":"Pérez","email":"swagger.ana@example.com","rol":"USUARIO"}
```

Desde otra terminal PowerShell:

```powershell
$apiBase = 'http://127.0.0.1:8001/api/v1/usuarios'
$apiEmail = 'manual.' + [guid]::NewGuid().ToString('N') + '@example.com'
$apiBody = @{ nombre='Ana'; apellido='Perez'; email=$apiEmail } | ConvertTo-Json
$apiUser = Invoke-RestMethod -Method Post -Uri $apiBase -ContentType 'application/json' -Body $apiBody
Invoke-RestMethod -Uri "$apiBase/$($apiUser.id)"
Invoke-RestMethod -Uri "${apiBase}?estado=todos&limite=20&desplazamiento=0"
$apiEdit = @{ nombre='Ana'; apellido='Diaz'; email=$apiEmail } | ConvertTo-Json
Invoke-RestMethod -Method Put -Uri "$apiBase/$($apiUser.id)" -ContentType 'application/json' -Body $apiEdit
Invoke-WebRequest -UseBasicParsing -Method Delete -Uri "$apiBase/$($apiUser.id)"
Invoke-RestMethod -Method Patch -Uri "$apiBase/$($apiUser.id)/reactivar"
```

Para comprobar persistencia, conectar DBeaver exclusivamente a usuarios_test,
127.0.0.1:5435, con las credenciales locales de pruebas:

```sql
SELECT current_database();
SELECT id, nombre, apellido, email, activo, rol, fecha_creacion
FROM public.usuarios ORDER BY fecha_creacion, id;
```

No hay endpoints de eliminación física. Las fixtures automatizadas limpian solo
la tabla de pruebas, por lo que una ejecución posterior puede retirar los datos
de demostración. Detener Uvicorn normalmente con Ctrl+C para ejecutar lifespan.

### Postman

Importar `docs/postman/usuarios.postman_collection.json`. Iniciar antes la fábrica
de pruebas indicada. La colección tiene seis solicitudes ordenadas; crea email
único y guarda usuarioId. Un pre-request script exige baseUrl igual a
http://127.0.0.1:8001 para evitar apuntar accidentalmente al puerto de desarrollo.
La configuración de DB queda garantizada por la fábrica, no por el puerto HTTP
por sí solo. No hay contraseñas ni tokens en la colección.

### Entrada de desarrollo

La entrada habitual funciona con .env y usuarios_dev, ya migrada a 0001:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Las instrucciones de escritura manual usan exclusivamente la fábrica de pruebas.
Las verificaciones automatizadas de escritura usaron usuarios_test; no se
escribió en desarrollo. No publicar en 0.0.0.0.
Sin login ni autorización, el rol es un dato y no restringe operaciones.

## Pruebas automatizadas y resultados

Desde backend:

```powershell
# HTTP sin Docker ni configuración PostgreSQL
.\.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider tests/http
# Toda la suite sin PostgreSQL
.\.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider -m "not postgres"
# Integración nueva, exclusivamente usuarios_test
.\.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider --run-postgres tests/integration/postgresql/test_http_usuarios.py
# Regresión completa
.\.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider --run-postgres
.\.venv\Scripts\python.exe -m pip check
```

En el entorno aislado del agente, si pytest no accede al temporal del usuario,
usar un temporal propio: `--basetemp=.venv/pytest-stage6-http` desde backend.
Ese directorio debe reservarse a pytest, que lo limpia automáticamente.

Resultados:

- 196 pruebas anteriores aprobadas.
- 52 nuevas: 50 HTTP en memoria y dos HTTP/PostgreSQL.
- Suite sin PostgreSQL: 231 aprobadas, 17 casos PostgreSQL deseleccionados.
- **248 passed in 6.16s**, una advertencia de deprecación de Starlette/TestClient
  sobre httpx. Se mantiene httpx 0.28.1, solicitado y compatible en esta ejecución;
  no se cambió la arquitectura ni se actualizó FastAPI/Starlette para ocultarla.
- Verificados códigos, Location, JSON, UTC, errores, extras, filtros y paginación.
- PostgreSQL: datos visibles entre clientes/Engines, baja sin DELETE físico,
  reactivación, conflicto con inactivos y datos almacenados inválidos como 500.
- Lifespan: dispose al cerrar, incluso cuando falla el cuerpo del contexto;
  excepciones inesperadas de HTTP no escapan con mensajes al servidor.
- OpenAPI: seis operaciones, tres rutas, esquemas/errores y DELETE sin cuerpo.
- Uvicorn temporal en 127.0.0.1:8001: GET /docs y /openapi.json devolvieron 200.
  No se enviaron escrituras a esa comprobación de arranque.
- pip check sin conflictos. Domain/Application: 20 archivos con hashes idénticos.

Dependencia directa de pruebas nueva: httpx 0.28.1. Transitivas nuevas:
httpcore 1.0.9 y certifi 2026.10.23; otras ya estaban instaladas.
La descarga inicial falló por inspección TLS Fortinet. Tras liberar el usuario
su conexión, pip instaló desde PyPI con TLS normal activo. No se usaron
trusted-host, certificados no verificados ni cambios globales de confianza.

## Inventario y límites

Nuevos: Presentation/http (`__init__.py`, dependencies.py, errors.py),
Presentation/http/usuarios (`__init__.py`, schemas.py, mappers.py, router.py),
tests/http (conftest.py y test_usuarios.py, test_validacion.py, test_errores.py,
test_lifespan.py, test_openapi.py),
tests/integration/postgresql/test_http_usuarios.py, esta guía y colección Postman.

Modificados: backend/src/app/bootstrap.py,
backend/src/app/infrastructure/persistence/repositories/sqlalchemy_user_repository.py
(solo clasificación de reconstrucción), backend/pyproject.toml, README.md,
docs/arquitectura.md y docs/etapa-5-persistencia.md (estado real de la migración).

Sin cambios en Domain, Application, DTO, casos de uso, contratos, modelos ORM,
migraciones, Compose, .env y .env.test. No se insertaron usuarios de prueba en
usuarios_dev, no se ejecutaron nuevas migraciones allí, no se modificaron otros
contenedores ni se borraron volúmenes. No hay login, JWT, frontend ni IA.
