# Sprint 9.3D: preflight del reemplazo PostgreSQL con pgvector

Fecha: **3 de noviembre de 2026, 16:17–16:18 -03:00**.
**Dictamen: BLOQUEADOS para realizar ahora el respaldo real y la sustitución.**
La imagen y el destino son compatibles y hay espacio disponible, pero la presión
actual de memoria y la ventana de mantenimiento pendiente impiden recomendar el
cambio inmediato. Solo se realizaron inspecciones y este informe.

## 1. Recursos actuales

GetPerformanceInfo, dos muestras separadas tres segundos:

| Recurso | 16:17:00 | 16:17:03 |
| --- | ---: | ---: |
| RAM física total | 7,851 GiB | 7,851 GiB |
| RAM física disponible | **0,715 GiB** | **0,738 GiB** |
| Compromiso global | 14,654 GiB | 14,575 GiB |
| Límite de compromiso | 25,851 GiB | 25,851 GiB |

Tres lecturas posteriores de contadores Windows, separadas aproximadamente un segundo:

| Contador | 1 | 2 | 3 |
| --- | ---: | ---: | ---: |
| PagesInputPersec | 3 | **2260** | **2540** |
| PageReadsPersec | 3 | **362** | **629** |
| PagesOutputPersec | 0 | 0 | 0 |
| PageWritesPersec | 0 | 0 | 0 |

Las entradas reflejan lecturas para resolver fallos de página, que pueden incluir
archivos mapeados; no se atribuyen exclusivamente al pagefile o a PostgreSQL.
No hay serie prolongada ni prueba de congelamiento, pero dos muestras elevadas
junto a menos de 0,75 GiB físicos disponibles justifican posponer trabajo adicional.
Compromiso disponible no equivale a RAM libre ni garantiza fluidez.

Procesos de mayor working set en una muestra cercana: vmmem PID 6064 **843,3 MiB**;
Chrome 24172 **513,9**, Chrome 11364 **491**, Code 20708 **415,3**, Code 17824
**261,1**, MsMpEng 5968 **225,8**, Chrome 11580 **225,5** y Chrome 9680 **216,1 MiB**.
No son consumos exclusivos sumables por páginas compartidas. No se inspeccionaron
títulos, documentos o contenido personal. El responsable puede guardar trabajo y
cerrar voluntariamente aplicaciones no necesarias que reconozca. No se propone
terminar WSL/Docker, servicios de datos o protección del sistema.

## 2. Disco y capacidad para copias

| Ubicación | Libre | Capacidad / tamaño |
| --- | ---: | ---: |
| C: | **46,616 GiB** | 155,430 GiB |
| D: | **105,221 GiB** | 309,586 GiB |
| Filesystem Docker /dev/sdd, df -Pk | **992680468 KiB**, unos 946,7 GiB virtuales | 1055762868 KiB |
| Clúster actual, du -sk /var/lib/postgresql | — | **64224 KiB**, unos 62,7 MiB |
| usuarios_dev, pg_database_size | — | **8206015 bytes**, unos 7,83 MiB |

df/du fueron ejecutados por docker exec de solo lectura en el contenedor propio,
sin abrir archivos de registros o imprimir contenido. Son cifras puntuales de
un clúster activo, no una copia consistente. El espacio virtual WSL es thin
provisioned y no sustituye el espacio físico Windows; no se determinó el archivo
VHDX exacto ni se certificaron cuotas/expansión futura de Docker Desktop.

Para esta base pequeña, reservar **al menos 10 GiB físicos** en el destino de
Docker y del respaldo es una propuesta conservadora que cubre ampliamente el
tamaño observado, dump, volumen restaurado, WAL y reversión sin borrar el original.
Ambas unidades superan esa reserva hoy. Revalidar inmediatamente antes del cambio,
confirmar ubicación real del disco Docker, permisos del destino protegido y tamaño
final del dump. No se predice una tasa exacta de compresión ni crecimiento del WAL.
**Capacidad suficiente según las mediciones; no bloquea actualmente.** No se
crearon respaldos, directorios de respaldo, bases, contenedores o volúmenes.

## 3. Docker, imagen y volumen

Motor Docker **29.8.1** responde. Desarrollo y pruebas figuran running/healthy:

| Recurso | Identidad actual |
| --- | --- |
| Contenedor desarrollo | `ce41dbdca5f0508f78ec4fbdc47b8e296f59eee93d04621a0cd5e1038a4bf749` |
| Nombre | `api-usuarios-clean-postgres-1` |
| Inicio sin cambios desde antecedentes | `2026-11-03T09:38:30.533051573Z` |
| Imagen actual | `sha256:979bccfde35445db618c65107d27d08c6c21339d8dc3ad4c830c6633947be0e4` |
| Publicación | **127.0.0.1:5434 → 5432**, sin LAN |
| Volumen original | **api-usuarios-clean_postgres_data**, driver local, rw en `/var/lib/postgresql` |
| Pruebas | `80172da97281`, healthy, 127.0.0.1:5435; solo inventario Docker, sin SQL/exec |

La imagen candidata `api-usuarios-clean/pgvector:18-0.8.2-93c` sigue disponible,
amd64, **646467364 bytes**, con identidad coincidente con 9.3C:

```text
sha256:a1336b54a1b49085474132cceb0636b314707b011fdb242afa694ae08ffcc3e6
```

9.3C comprobó PostgreSQL 18.6 + pgvector 0.8.2, vector(768), coseno y restauración
sintética. Son antecedentes verificados, no pruebas repetidas en este preflight.
No se construyó ni arrancó la imagen ahora. Compose sigue sin cambios en postgres:18.

## 4. Revalidación PostgreSQL de solo lectura

Se utilizó el cargador existente sin imprimir usuario, contraseña, URL o .env.
Antes de conectar se exigió exactamente **usuarios_dev / 127.0.0.1:5434**.
Conexión limitada a 3 s; default_transaction_read_only=on, statement_timeout=3 s
y lock_timeout=1 s. Se confirmó transaction_read_only=on antes de consultar, se
verificó current_database y se terminó con rollback. Sin privilegios adicionales.

| Metadato | Resultado |
| --- | --- |
| Identidad efectiva | **usuarios_dev** |
| PostgreSQL | **18.6 (Debian 18.6-1.pgdg13+2)** |
| Encoding | UTF8 |
| Collation / ctype | en_US.utf8 / en_US.utf8 |
| public.alembic_version | Existe |
| Revisión observada | **Una sola: 0003** |
| Revisión esperada del código leído | Cadena 0001 → 0002 → **0003**, única cabeza |
| Sesiones agregadas observadas para esa base | 1 active y 1 idle |

Se consultaron únicamente identidad/versión/tamaño/locale, versión Alembic y
conteos de conexiones por estado. La conexión activa incluye esta inspección;
no se atribuye la idle a un proceso concreto. No se leyeron consultas activas,
perfiles, usuarios, hashes, tokens, sesiones de aplicación o filas de negocio.
No se realizó auditoría completa de integridad de datos, roles, grants o índices.
La lectura coincidente de revisión no sustituye el ensayo de restauración real.

## 5. Aplicación, Ollama y posibles escritores

| Servicio | Lectura actual |
| --- | --- |
| FastAPI | PID **17948**, padre **16760**, listener 127.0.0.1:8000 |
| Lanzador | PID 16760, Python del backend/.venv del workspace; local_server, enable-llm y observe-llm presentes; aprovisionamiento ausente |
| React/Vite | PID **25700**, padre 23116, node.exe; vite.development.config.ts, listener 127.0.0.1:5173 |
| Ollama | PID **13416**, listener 127.0.0.1:11434 |
| Docker listener de desarrollo | PID 8732, 127.0.0.1:5434 |
| Puerto 8001 | Sin listener en el inventario |

Se clasificaron argumentos sin imprimir líneas completas. Ejecutables y relaciones
padre/hijo fueron revalidados por CIM. Creaciones coinciden con los antecedentes:
backend 11:43:07 y Vite 10:57:20 del mismo día. No se extrajo memoria de procesos.

Solo GET anónimos:

- 8000/openapi.json: **200**, ruta IA presente, sin publicar documento completo.
- 5173/login: **200**, frontend accesible; no equivale a navegación autenticada.
- Ollama /api/version: **200**, versión **0.40.13**.
- Ollama /api/ps: **200, cero modelos cargados** en esa instantánea.

El backend permanece IA/observador habilitado según argumentos, sin haberlos
cambiado. No se generó ninguna consulta o embedding. No se certifica que otro
cliente no use Ollama después de esa observación.

**Escritores potenciales durante mantenimiento:** FastAPI puede escribir mediante
login/logout, intentos, rehash de claves y operaciones de usuarios/credenciales.
React no conecta a PostgreSQL directamente, pero sus acciones en el navegador
pueden disparar esas operaciones. IA directa no persiste contenido, pero su acceso
requiere autenticación y base disponible. El engine tiene pool_size=5,
max_overflow=3 y pool_pre_ping: mantenerlo abierto no demuestra ausencia de
escrituras. No se identificaron otros Python/Node servidores en el inventario
filtrado, pero eso no excluye clientes SQL, shells u otros equipos/procesos.

La próxima ventana debe acordar no usar la UI, suspender **el backend propio
revalidado** y controlar conexiones/transacciones antes del dump definitivo.
Detener Vite es opcional, no suficiente para impedir escritores. No se detuvo
ninguno ahora ni se inspeccionaron contenidos de pg_stat_activity.query.

## 6. Plan ejecutable propuesto — NO EJECUTADO

Todos los nombres/PIDs deben revalidarse al ejecutar; no actuar solo por los
históricos de este informe. Los comandos siguientes son plantillas para una
ventana futura autorizada, no un script aprobado para ejecutar sin controles.

1. Responsable libera voluntariamente recursos. Repetir RAM/paginación durante
   una ventana breve; exigir margen acordado para dump y un PostgreSQL adicional.
   Referencia propuesta: acercarse a 2 GiB libres y evitar lecturas de páginas
   intensas sostenidas, sin convertir una cifra en garantía. Acordar condición
   de parada y limpieza exclusiva de recursos nuevos si la memoria empeora.
2. Revalidar destino/revisión, imagen, contenedor, volumen y espacio; elegir un
   directorio protegido fuera de Git y nombres nuevos sin colisiones. Por ejemplo
   `api-usuarios-clean-pgvector-93d-data` y `api-usuarios-clean-93d-restore`; no se
   verificó ni reservó su disponibilidad en esta etapa. Registrar image ID anterior
   y candidata, configuración protegida y receta exacta de arranque sin secretos.
3. Con autorización de mantenimiento, suspender backend propio y escritores
   acordados, sin tocar Docker/WSL/Ollama o usuarios_test. Mantener el bloqueo de
   uso de la aplicación hasta la aceptación final. Revisar sesiones y transacciones
   mínimas autorizadas; una sola instantánea de cero conexiones no impide futuros
   accesos, por lo que también debe coordinarse el acceso de todos los clientes.
4. Crear dump custom y roles necesarios en rutas temporales aprobadas. Ejemplo
   de comandos **NO EJECUTADOS**, que no exponen contraseñas:

```powershell
# DEV_ID revalidado; BACKUP_DIR existente, protegido y aprobado previamente.
docker exec $DEV_ID sh -c 'exec pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc -f /tmp/usuarios-dev-93d.dump'
docker exec $DEV_ID sh -c 'exec pg_dumpall -U "$POSTGRES_USER" --globals-only --no-role-passwords -f /tmp/roles-93d.sql'
docker cp "${DEV_ID}:/tmp/usuarios-dev-93d.dump" (Join-Path $BACKUP_DIR 'usuarios-dev-93d.dump')
docker cp "${DEV_ID}:/tmp/roles-93d.sql" (Join-Path $BACKUP_DIR 'roles-93d.sql')
Get-FileHash -Algorithm SHA256 (Join-Path $BACKUP_DIR 'usuarios-dev-93d.dump')
```

   Comprobar cada exit code, permisos, tamaños, hashes y pg_restore --list. No usar
   redirección PowerShell para bytes del dump. Estos comandos escribirían archivos
   temporales y leerían datos reales: **no están autorizados en este preflight**.
   Roles sin passwords todavía son información protegida; no imprimir su archivo.
5. Crear **solo después del permiso** un volumen nuevo y un contenedor candidato
   por digest, sin red/puertos durante restauración. Montar únicamente el nuevo
   volumen en `/var/lib/postgresql`, mantener PGDATA 18/docker y PostgreSQL 18.6.
   Usar credenciales existentes por inyección segura revisada, no comandos con
   passwords literales. No reutilizar trust del ensayo sintético en un servicio real.
6. Restaurar roles requeridos con revisión explícita de conflictos del usuario
   inicial; no ignorar errores. `--no-role-passwords` exige configurar de forma
   segura la contraseña DB existente para preservar conectividad. Restaurar el
   dump con pg_restore --exit-on-error y preservar propietarios/grants, encoding
   y locale. Elegir creación de DB restaurada compatible con el dump; no usar
   silenciosamente --no-owner ni DROP de bases existentes. No ejecutar Alembic.
7. Verificar metadatos, revisión única 0003, tablas/constraints/grants, conteos y
   comparaciones agregadas autorizadas contra la línea base congelada. No imprimir
   datos personales o hashes de credenciales; cualquier huella debe quedar en
   archivos protegidos o compararse sin publicarla. El ensayo real debe terminar
   correctamente; un hash del dump o pg_restore --list no basta. No crear vector.
8. Preparar y revisar un override Compose **futuro** que cambie solo imagen y
   volumen del servicio postgres de desarrollo. El volumen nuevo debe declararse
   external/name explícito para no montar otro vacío por error. Mantener 5434
   loopback, red, healthcheck, PGDATA, variables y PostgreSQL major. Validar que la
   configuración combinada sustituye el montaje en el mismo destino y no agrega
   uno duplicado; no imprimir compose config con secretos. El Compose de pruebas
   queda excluido por nombre/proyecto/archivo.
9. Detener solo contenedor original revalidado, conservar su volumen e imagen,
   parar el contenedor de ensayo de restauración y promover ese **mismo volumen
   restaurado** mediante el servicio de desarrollo. Nunca arrancar dos PostgreSQL
   con el mismo PGDATA. Antes del cambio guardar el ID de cada recurso nuevo.
10. Con escritores aún suspendidos, comprobar listener/healthcheck, destino,
    versión/revisión y disponibilidad de archivos de vector (sin CREATE EXTENSION).
    Revisar identidad/montaje original conservado y medir RAM/paginación. GET
    públicos no certifican permisos DB: pactar una comprobación de conectividad
    de lectura con el usuario efectivo. Solo tras aceptar abrir la aplicación.
    Un login de prueba necesita permiso explícito por sus escrituras normales.
11. **Reversión antes de reabrir escritores:** detener exclusivamente el candidato,
    restaurar servicio por digest anterior y volumen original, revalidar lecturas
    y reabrir aplicación. No eliminar dump, imagen ni volumen candidato. No alterar
    el original para preparar la reversión.
12. **Después de reabrir escritores**, retornar al volumen antiguo perdería cambios
    nuevos. Si aparece un fallo, congelar escritores y acordar reconciliación,
    respaldo/restauración adicional o reparación hacia adelante. No hacer rollback
    automático a una copia vieja. Si una etapa posterior crea vector/tablas RAG,
    exigir binarios compatibles para cualquier imagen de reversión, sin CASCADE.

No ejecutar compose down -v, prune, upgrade/stamp/downgrade o limpieza de recursos
por prefijo. Retención y eliminación de archivos temporales o recursos nuevos
deben quedar identificadas y autorizadas; no usar volúmenes previos como scratch.

## 7. Autorizaciones pendientes y dictamen

Se requiere autorización posterior para:

- Nueva medición tras liberar recursos y criterios de parada del trabajo adicional.
- Ventana de mantenimiento y suspensión/reinicio del backend y PostgreSQL propios.
- Respaldo real de usuarios_dev y roles, destino/retención/permisos de archivos.
- Creación de volumen/contenedor aislado y restauración de datos reales.
- Comparaciones de integridad agregadas y permisos/credenciales necesarias.
- Override Compose, sustitución únicamente del servicio de desarrollo y reversión.
- Eventual login de aceptación con sus escrituras; no asumirlo incluido en GET.

CREATE EXTENSION, migraciones/tablas RAG e inicialización o cambios de usuarios_test
permanecen fuera de ese cambio salvo autorización separada. No se necesita cambiar
la versión mayor ni descargar otra imagen según el inventario actual.

**BLOQUEADOS ahora:** RAM física reducida y lecturas elevadas de páginas; no hay
ventana/corte de escritores ni autorización para ejecutar respaldo y reemplazo.
**Preparación técnica favorable:** imagen fijada disponible, PostgreSQL 18.6,
revisión 0003 coincidente, contenedor/volumen identificados y espacio suficiente.
Resolver recursos y autorizar la ejecución del plan; no se requiere reconstruir
la base original ni asumir que el respaldo todavía inexistente es restaurable.

No se ejecutaron tests o builds: no se cambió implementación y ya existe evidencia
sintética en 9.3C. No hubo backup, CREATE EXTENSION, Alembic, inferencia, modelos
cargados, contenedores/volúmenes creados o modificados, Compose/.env alterados,
login/logout o datos de usuarios consultados. Solo metadatos en READ ONLY,
inventarios, GET y el presente informe. Servicios existentes conservados.

**Preflight entregado. Se detiene antes de cualquier cambio operativo.**
