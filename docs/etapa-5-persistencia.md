# Etapa 5: persistencia PostgreSQL

> Documento histórico: sus revisiones y comandos describen esa etapa, no el inicio actual.
> El backend vigente requiere **0003**, pruebas solo en usuarios_test:5435, cambio
> obligatorio implementado y aprovisionamiento cerrado. Seguir [la guía backend](../backend/README.md)
> y [preparación 8.6B](sprint-8-6b-preparacion.md). No ejecutar operaciones de desarrollo
> ni iniciar este código con 0001/0002 a partir de instrucciones históricas.

Implementación verificada el 29 de octubre de 2026. El primer punto de control
se completó exclusivamente en `usuarios_test`. Posteriormente, con la segunda
autorización explícita, se aplicó 0001 a `usuarios_dev`: tablas usuarios y
alembic_version creadas, revisión 0001, sin diferencias con el modelo y sin insertar
usuarios. No se ejecutó downgrade en desarrollo. La etapa 6 está documentada aparte.

## Arquitectura

Domain y Application, sus contratos y los seis casos de uso permanecen intactos.
`SQLAlchemyUserRepository` implementa exactamente `UserRepository`. El modelo
ORM vive en Infrastructure y el mapeador reconstruye entidades independientes
con `Usuario.reconstruir`, `Email` y `Rol`. No devuelve objetos ORM al llamador.
El repositorio en memoria y su ejemplo siguen disponibles.

`configuration/database.py` carga variables del proceso sobre un archivo local
explícito. No modifica `os.environ` ni interpola secretos. `.env` es desarrollo;
`.env.test` se usa exclusivamente para pruebas y solo acepta `TEST_POSTGRES_*`.
Los dos archivos están ignorados por las reglas existentes de `.gitignore`.
La plantilla versionada `.env.example` no contiene contraseñas.

La URL se construye mediante `URL.create` con `postgresql+psycopg`. Desde Windows
se usa `127.0.0.1`; puertos 5434 para desarrollo y 5435 para pruebas. El host
predeterminado evita tener que modificar `.env`. No se modificó `compose.yaml`.
No imprimir archivos locales, URLs completas ni salidas de Compose con secretos.

Un Engine por composición, pool acotado y `pool_pre_ping`. Las conexiones se
abren al usarse; las sesiones son independientes por método. Cada escritura
confirma antes de retornar y revierte al fallar. El cierre libera recursos al
pool; el dueño del Engine llama a `dispose()` al finalizar.
`crear_persistencia_postgresql` en bootstrap compone explícitamente engine y
repositorio; `create_app()` continúa sin conectar a la base ni ejecutar DDL.

La unicidad se garantiza al escribir, además de las consultas de los casos de
uso. SQLSTATE 23505 y nombres de restricciones permiten traducir conflictos a
las excepciones existentes. Después de rollback, una sesión nueva consulta UUID
y estado del propietario del email. Si el propietario liberó el email entre
ambos pasos, se reintenta como máximo tres veces. Otros errores SQLAlchemy se
convierten en `ErrorPersistencia`, error técnico saneado de Infrastructure.

Las transacciones abarcan una operación del repositorio, no todo un caso de uso.
Las modificaciones concurrentes de una misma identidad conservan la política de
última escritura válida del adaptador en memoria. No hay campo de versión ni
Unit of Work. Operaciones futuras con varias escrituras requerirán otro diseño.

## Modelo y migración

`public.usuarios` tiene siete columnas obligatorias: UUID `id`, nombre y apellido
de hasta 100 caracteres, email de hasta 254, booleano activo, rol de hasta siete
caracteres y fecha `TIMESTAMPTZ`. Identidad y fecha provienen del dominio, sin
defaults de servidor. La sesión PostgreSQL usa UTC.

Restricciones: `pk_usuarios`, `uq_usuarios_email`, longitudes de nombre/apellido,
email normalizado y rol ADMIN/USUARIO. El email usa collation C y UNIQUE global,
incluyendo inactivos. Los índices `(fecha_creacion, id)` y
`(activo, fecha_creacion, id)` acompañan listado y filtros.

La validación completa sigue en Domain; los CHECK no replican todo Python.
PostgreSQL text/varchar tiene limitaciones de representación (por ejemplo NUL y
surrogates Unicode aislados), aunque Python permita esas cadenas. Un fallo de
representación se informa como error técnico; no se agregó validación al dominio.

La revisión inicial `0001` declara explícitamente tabla, restricciones e índices;
su downgrade elimina únicamente esos objetos. No hay generación automática de
esquema al ejecutar la aplicación ni uso de `Base.metadata.create_all()`.
Alembic administra además su tabla técnica de versión.
Autogenerate está limitado a la tabla de aplicación para no proponer eliminaciones
de tablas ajenas. Las revisiones candidatas siempre se revisan antes de aplicar.

## Dependencias verificadas en Python 3.14.3 / Windows x64

| Dependencia directa fijada | Versión |
| --- | --- |
| SQLAlchemy | 2.0.55 |
| psycopg y psycopg-binary | 3.3.6 |
| Alembic | 1.20.1 |
| python-dotenv | 1.2.4 |

Transitivas instaladas: greenlet 3.5.6, tzdata 2026.6, Mako 1.4.3 y MarkupSafe
3.0.4; typing-extensions 4.16.0 ya estaba instalado. Para actualizar la instalación
editable se incorporaron setuptools 84.2.1 y wheel 0.48.0 al entorno virtual.
No se modificó Python global ni se actualizó pip 25.3.
Las dependencias directas están fijadas; no hay un lock completo de transitivas.

### Incidencia TLS e instalación segura

pip consultó el índice oficial pero falló al validar certificados de
files.pythonhosted.org. Se comprobaron el intérprete y pip de `.venv`: Python
3.14.3 y pip 25.3. No había variables de proxy/certificados ni un índice alternativo
configurado en pip. Tanto el almacén Windows como el bundle de pip fallaron en
ese cliente; no se confirmó la causa exacta de la diferencia de confianza.

OpenSSL de Git verificó correctamente la cadena pública GlobalSign del servidor.
Se descargaron metadatos de `https://pypi.org` y wheels oficiales de
`https://files.pythonhosted.org` con curl de Git, sin deshabilitar TLS. Cada SHA-256
se verificó contra los metadatos oficiales antes de instalar. pip instaló desde
la caché local con `--no-index --find-links`, sin ejecutar paquetes no verificados.
No se utilizó `--trusted-host` para descargar o instalar, ni se cambió la
configuración global de certificados. No fue necesario un servidor alternativo.

Las ruedas verificadas y ayudas de descarga quedaron dentro de `.venv`, fuera de
Git. Para reinstalar en este entorno con esa caché:

```powershell
.\backend\.venv\Scripts\python.exe -m pip install --no-index --find-links backend/.venv/etapa5-wheels --no-build-isolation -e ".\backend[dev]"
.\backend\.venv\Scripts\python.exe -m pip check
```

En un entorno con TLS normal, usar la instalación editable habitual del README.
No desactivar validación HTTPS para resolver problemas futuros.

## PostgreSQL aislado de pruebas

`.env.test` contiene contraseña aleatoria independiente (32 bytes criptográficos),
base `usuarios_test`, usuario `usuarios_test_admin`, host 127.0.0.1 y puerto 5435.
`compose.test.yaml` usa un proyecto/red independientes y almacenamiento tmpfs.
No usa volúmenes de desarrollo. Al detener el contenedor tmpfs se pierde; al
iniciar de nuevo, pytest aplica las migraciones en el entorno vacío.

Antes de habilitar por primera vez, verificar que 5435 esté libre. Desde la raíz:

```powershell
Get-NetTCPConnection -LocalPort 5435 -State Listen -ErrorAction SilentlyContinue
docker compose --env-file .env.test -f compose.test.yaml config --quiet
docker compose --env-file .env.test -f compose.test.yaml up -d --wait --wait-timeout 120 postgres
docker compose --env-file .env.test -f compose.test.yaml ps
```

Las fixtures rechazan cualquier destino distinto de la base, usuario y puerto de
pruebas esperados, incluyendo expresamente `usuarios_dev`. Antes de TRUNCATE se
verifican `current_database()` y `current_user`. No se usan credenciales de
desarrollo como fallback. La configuración programática de Alembic exige el mismo
destino de pruebas; una prueba unitaria verifica el rechazo de desarrollo antes
de conectar. Esta suite no está diseñada para ejecución paralela entre procesos:
limpia la tabla y prueba downgrade de toda la aplicación en esa base exclusiva.

```powershell
Set-Location backend
# Solo pruebas sin PostgreSQL
.\.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider -m "not postgres"
# Suite completa, habilitando explícitamente integración
.\.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider --run-postgres
# Solo PostgreSQL; falla si falta configuración/conexión
.\.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider --run-postgres -m postgres
.\.venv\Scripts\python.exe -B -m alembic -x target=test current
.\.venv\Scripts\python.exe -B -m alembic -x target=test check
.\.venv\Scripts\python.exe -B examples\usuarios_postgresql.py
```

Sin `--run-postgres`, pytest omite los casos marcados postgres y no abre sus
fixtures. La regresión original de 161 pruebas no requiere Docker.
El ejemplo PostgreSQL está limitado a pruebas y deja un usuario de demostración
con email aleatorio; no aplica migraciones automáticamente.

Para detener solo el entorno de pruebas, desde la raíz:

```powershell
docker compose --env-file .env.test -f compose.test.yaml stop postgres
```

## Migraciones y punto de control de desarrollo

Los siguientes comandos son operativos en pruebas, desde backend:

```powershell
.\.venv\Scripts\python.exe -m alembic -x target=test upgrade head
.\.venv\Scripts\python.exe -m alembic -x target=test downgrade base
.\.venv\Scripts\python.exe -m alembic -x target=test upgrade head
.\.venv\Scripts\python.exe -m alembic -x target=test check
```

`downgrade base` destruye los datos de usuarios: solo utilizarlo en la base de
pruebas descartable. Para una revisión posterior, generar sobre una base de
pruebas actualizada y revisar el archivo resultante:

```powershell
.\.venv\Scripts\python.exe -m alembic -x target=test revision --autogenerate -m "descripcion del cambio"
```

**Bloque aplicado tras la segunda autorización explícita, verificando antes el destino.**
Se ejecutó desde backend sobre `usuarios_dev`:

```powershell
.\.venv\Scripts\python.exe -m alembic -x allow-development=true upgrade head
.\.venv\Scripts\python.exe -m alembic -x allow-development=true current
.\.venv\Scripts\python.exe -m alembic -x allow-development=true check
```

El argumento es una confirmación operativa, no un mecanismo de permisos ni una
autorización del usuario por sí mismo. Sin ese argumento Alembic no migra el
destino de desarrollo por defecto. No hay migraciones al arrancar FastAPI.

Consultas de revisión en DBeaver (pruebas ahora; desarrollo solo tras migrarlo):

```sql
SELECT current_database(), current_user;
SELECT version_num FROM public.alembic_version;
SELECT id, nombre, apellido, email, activo, rol, fecha_creacion
FROM public.usuarios ORDER BY fecha_creacion, id;
SELECT conname, pg_get_constraintdef(oid)
FROM pg_constraint WHERE conrelid = 'public.usuarios'::regclass;
SELECT indexname, indexdef FROM pg_indexes
WHERE schemaname = 'public' AND tablename = 'usuarios';
```

## Resultados y alcance

- 161 pruebas existentes aprobadas sin modificaciones.
- 35 pruebas nuevas: 18 casos de contrato (9 por adaptador), 11 unitarias y seis
  de integración/migraciones. Total: **196 passed in 2.56s**, sin advertencias.
- Upgrade, downgrade a base y nuevo upgrade correctos en `usuarios_test`.
- Alembic `0001 (head)`; check: `No new upgrade operations detected.`
- Persistencia visible desde otro Engine; rollback y operaciones posteriores
  correctas; carreras concurrentes de email verificadas en ambos adaptadores.
- Ejemplos en memoria y PostgreSQL satisfactorios; `pip check` correcto.
- Contenedor de pruebas healthy en `127.0.0.1:5435`; desarrollo conserva identidad
  de contenedor, puerto y estado. Los demás proyectos no se modificaron.
- En el primer punto de control no había tablas en desarrollo; tras la segunda
  autorización se aplicó 0001 sin insertar usuarios. Los endpoints posteriores
  corresponden a etapa 6 y se describen en su documentación específica.

En el entorno aislado del agente, pytest no pudo acceder al directorio temporal
del usuario creado por otra ejecución. Se verificó la suite sin PostgreSQL con
`--basetemp=.venv/pytest-stage5-local`, dentro del backend, sin cambiar permisos
globales ni configuración del proyecto. En una terminal normal no se requiere
ese argumento. Alembic también emitió inicialmente un aviso de configuración;
se agregó `path_separator = os` y la suite completa terminó sin advertencias.

## Inventario de archivos

Creados:

- `compose.test.yaml` y `.env.test` local (excluido de Git).
- `backend/alembic.ini`, `backend/migrations/env.py`,
  `backend/migrations/script.py.mako`, `backend/migrations/versions/0001_crear_usuarios.py`.
- `backend/src/app/infrastructure/configuration/__init__.py` y `database.py`.
- `backend/src/app/infrastructure/persistence/database.py`.
- `backend/src/app/infrastructure/persistence/models/__init__.py`, `base.py` y `usuario.py`.
- `backend/src/app/infrastructure/persistence/mappers/__init__.py` y `usuario.py`.
- `backend/src/app/infrastructure/persistence/repositories/sqlalchemy_user_repository.py`.
- `backend/examples/usuarios_postgresql.py`.
- `backend/tests/conftest.py`, `backend/tests/postgres_support.py`.
- `backend/tests/contracts/test_user_repository.py`.
- `backend/tests/unit/infrastructure/test_database_configuration.py` y `test_usuario_mapper.py`.
- `backend/tests/integration/postgresql/test_repository.py` y `test_migrations.py`.
- `docs/etapa-5-persistencia.md`.

Modificados: `backend/pyproject.toml`, `backend/src/app/bootstrap.py`,
`.env.example`, `README.md`, `docs/arquitectura.md`.

Sin cambios: `.env` de desarrollo, `.gitignore`, `compose.yaml`, Domain,
Application y los archivos de las 161 pruebas anteriores. Las instalaciones,
caché de wheels y metadatos editables son artefactos locales ignorados por Git.
