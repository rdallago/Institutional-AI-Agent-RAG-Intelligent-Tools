# Etapa 4: PostgreSQL local con Docker Compose

> Documento histórico: sus revisiones y comandos describen esa etapa, no el inicio actual.
> El backend vigente requiere **0003**, pruebas solo en usuarios_test:5435, cambio
> obligatorio implementado y aprovisionamiento cerrado. Seguir [la guía backend](../backend/README.md)
> y [preparación 8.6B](sprint-8-6b-preparacion.md). No ejecutar operaciones de desarrollo
> ni iniciar este código con 0001/0002 a partir de instrucciones históricas.

PostgreSQL funciona separado del backend. Python 3.14.3, el dominio, los casos
de uso y el repositorio en memoria conservan su comportamiento. No se instalan
SQLAlchemy ni Alembic y no se crean tablas de aplicación.

## Configuración

Desde la raíz del proyecto, Docker Desktop debe estar iniciado con contenedores
Linux. Verificar `docker info`, `docker compose version` y disponibilidad del
puerto con `Get-NetTCPConnection -LocalPort 5434 -ErrorAction SilentlyContinue`.

`compose.yaml` define el proyecto `api-usuarios-clean` y un servicio `postgres`:

- Imagen oficial `postgres:18`, sin actualización automática de versión mayor.
- Acceso publicado únicamente en `127.0.0.1:5434`, puerto interno 5432.
- Volumen `api-usuarios-clean_postgres_data` montado en `/var/lib/postgresql`,
  ubicación correspondiente a la imagen PostgreSQL 18.
- Red bridge `api-usuarios-clean_desarrollo`, administrada por Compose.
- Reinicio `unless-stopped`: respeta detenciones manuales.
- Healthcheck TCP mediante `pg_isready`; no sustituye autenticación ni consultas.
  Un estado unhealthy no reinicia por sí solo el contenedor.

`.env.example` es una plantilla sin contraseña. `.env` contiene la configuración
local y está excluido por `.gitignore`. No mostrar su contenido ni compartir
salidas de `docker compose config` o inspecciones que expongan credenciales.
Para validar sin imprimir secretos se usa `docker compose config --quiet`.

En una instalación nueva copiar `.env.example` a `.env` únicamente si no existe
y completar una contraseña aleatoria fuerte antes de iniciar. La implementación
inicial genera localmente 32 bytes criptográficamente aleatorios, sin imprimirlos.
No sobrescribir `.env` existente. Las variables del proceso PowerShell pueden
prevalecer sobre `.env`.

`POSTGRES_USER` crea un administrador local de inicialización. En la etapa 5 se
diseñará un rol de aplicación con permisos limitados. Cambiar la contraseña en
`.env` no cambia la contraseña de un volumen ya inicializado.

## Operación desde PowerShell

Todos los comandos se ejecutan desde la raíz:

```powershell
Set-Location D:\Downloads\proyectos\api-usuarios-clean
docker info
docker compose config --quiet
docker compose pull postgres
docker compose up -d --wait --wait-timeout 120 postgres
docker compose ps
docker compose logs --tail 100 postgres
Test-NetConnection -ComputerName 127.0.0.1 -Port 5434
```

Conexión TCP autenticada, ingresando la contraseña local cuando psql la solicite.
Desde el contenedor se usa `postgres`, el nombre DNS del servicio en la red;
el loopback interno puede estar permitido sin contraseña por la imagen oficial.
Desde Windows el host continúa siendo `127.0.0.1` y el puerto 5434:

```powershell
docker compose exec postgres psql -h postgres -U usuarios_dev_admin -d usuarios_dev -W
```

```sql
SELECT version();
SELECT current_database();
SELECT current_user;
SHOW timezone;
SELECT table_schema, table_name
FROM information_schema.tables
WHERE table_schema NOT IN ('pg_catalog', 'information_schema');
```

No deben existir tablas de aplicación. Salir con `\q`.

```powershell
docker compose stop postgres
docker compose up -d --wait postgres
docker compose restart postgres
docker compose ps
```

Después de `restart`, comprobar que vuelva a healthy. Para recrear exclusivamente
el contenedor de este servicio conservando el volumen:

```powershell
docker compose up -d --force-recreate --no-deps --wait postgres
```

No ejecutar limpiezas globales ni `down -v`: elimina datos. Un volumen no es un
respaldo. No cambiar la versión mayor sin plan de migración.

## Comprobación de persistencia sin tablas

Comprobar primero que la base no tenga un comentario que deba conservarse:

```sql
SELECT shobj_description(oid, 'pg_database')
FROM pg_database WHERE datname = current_database();
COMMENT ON DATABASE usuarios_dev IS 'verificacion-etapa-4-persistencia';
```

Salir de psql, detener e iniciar con los comandos anteriores y consultar de
nuevo el comentario. Repetir después de recrear exclusivamente el servicio.
La marca debe conservarse en ambos casos. Al finalizar:

```sql
COMMENT ON DATABASE usuarios_dev IS NULL;
```

Esta marca es una comprobación de infraestructura, sin tablas de aplicación.
En la etapa 5 todo el esquema de aplicación se administrará exclusivamente
mediante migraciones versionadas Alembic, sin `Base.metadata.create_all()`.
La futura conexión SQLAlchemy desde Windows usará el dialecto
`postgresql+psycopg`, host `127.0.0.1` y puerto 5434, construyendo la URL sin
concatenar credenciales. Un futuro servicio en esta red usará `postgres:5432`.
Las versiones se validarán para Python 3.14.3 antes de instalar dependencias.

## Regresión y aceptación

```powershell
Set-Location backend
.\.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider
.\.venv\Scripts\python.exe -B examples\usuarios_en_memoria.py
```

Se requiere healthy, consultas autenticadas correctas, ausencia de tablas de
aplicación, persistencia tras ambas operaciones, 161 pruebas aprobadas y ejemplo
satisfactorio. Los contenedores ajenos deben mantener sus identidades y estados.

## Problemas en Windows

- Motor inaccesible: verificar Docker Desktop, contexto Docker y WSL 2.
- Puerto ocupado o reservado: no detener otros servicios; acordar otro puerto.
- Acceso denegado desde un entorno aislado: la CLI instalada no implica acceso
  al motor; comprobar desde una terminal con permisos adecuados.
- Evitar bind mounts de datos PostgreSQL en carpetas Windows: usar el volumen.
- Reiniciar Docker Desktop o borrar sus datos puede afectar otros proyectos;
  no hacerlo como parte de esta etapa.

## Resultados verificados el 28 de octubre de 2026

- PostgreSQL 18.6 (Debian 18.6-1.pgdg13+2), x86_64, zona `Etc/UTC`.
- Imagen descargada:
  `postgres@sha256:979bccfde35445db618c65107d27d08c6c21339d8dc3ad4c830c6633947be0e4`.
- Contenedor `api-usuarios-clean-postgres-1`: healthy, `127.0.0.1:5434->5432/tcp`.
- Base `usuarios_dev`, usuario `usuarios_dev_admin`, cero tablas de aplicación.
- Contraseña inválida rechazada por conexión TCP al servicio; contraseña local
  válida aceptada. No se imprimió la contraseña generada.
- Puerto publicado accesible desde Windows.
- Marca conservada tras stop/inicio y tras force-recreate; identidad del
  contenedor cambió y el volumen siguió siendo `api-usuarios-clean_postgres_data`.
  La marca se retiró al terminar.
- Regresión: 161 passed in 0.78s con Python 3.14.3. Ejemplo en memoria correcto.
- Contenedores ajenos conservan identidades y estados previos; no se ejecutaron
  operaciones sobre ellos ni limpiezas globales.
- `.gitignore` ya excluye `.env` y permite `.env.example`; no fue modificado.
- Etapa 4 completada. Etapa 5 pendiente de autorización explícita.

