# Sprint 9.3C: imagen PostgreSQL 18 con pgvector

Fecha: **3 de noviembre de 2026**, intervención aproximadamente **12:48–12:52
-03:00**. **IMPLEMENTADO Y VERIFICADO EN AISLAMIENTO**. No se reemplazó el
PostgreSQL de desarrollo. El reemplazo operativo sigue pendiente de autorización,
respaldo real ensayado y recuperación de recursos.

## 1. Archivos y decisión de construcción

Archivos nuevos:

- `infra/pgvector/Dockerfile`.
- `infra/pgvector/.dockerignore`.
- `infra/pgvector/smoke.sql`.
- `infra/pgvector/verify.ps1`.
- `docs/sprint-9-3c-pgvector-infraestructura.md`.

No había Dockerfile del proyecto en la búsqueda realizada. Se leyeron Compose de
desarrollo/pruebas y el cargador de configuración de persistencia; no se cargó
.env ni se imprimieron credenciales. Ambos Compose siguen usando `postgres:18`:
**no se editaron**. Backend, frontend, Alembic y núcleo RAG permanecen intactos.

La [fuente oficial de pgvector 0.8.2](https://github.com/pgvector/pgvector/blob/v0.8.2/Dockerfile)
deriva de la imagen oficial PostgreSQL y compila la extensión para el major elegido.
Su [changelog](https://github.com/pgvector/pgvector/blob/v0.8.2/CHANGELOG.md)
documenta soporte de PostgreSQL 18 y correcciones específicas. Se eligió una
versión publicada verificable, no un tag latest o una rama mutable.

Para evitar compilación y apt en una notebook con poca RAM, el Dockerfile final
usa dos etapas fijadas por digest:

| Elemento | Referencia inmutable |
| --- | --- |
| Base final, la misma de los contenedores actuales | `postgres:18@sha256:979bccfde35445db618c65107d27d08c6c21339d8dc3ad4c830c6633947be0e4` |
| Artefactos oficiales pgvector linux/amd64 | `pgvector/pgvector:0.8.2-pg18-trixie@sha256:77f3220c156665b2b198f3bcb859bdd6c12f6dd614e0a835f36826e21eaeb475` |

Se copian únicamente `vector.so`, archivos SQL/control de vector y documentación
con licencia. No se reemplazan ejecutables PostgreSQL, entrypoint o configuración
de la base. El build comprueba major 18, versión de extensión 0.8.2 y dependencias
dinámicas resueltas mediante ldd. La carga efectiva del binario se verificó después
con CREATE EXTENSION y operaciones SQL.

La primera candidata derivaba directamente de pgvector y reveló PostgreSQL
**18.4**. Se descartó como destino operativo por ser menor que el **18.6** actual;
el Dockerfile final preserva exactamente la base existente y utiliza solo los
artefactos de extensión PG18. La compatibilidad del binario entre esas imágenes
se comprobó en el ensayo, no se supuso por el nombre del tag. Un cambio futuro de
base, libc, arquitectura o versión exige reconstrucción y nuevas pruebas.

No se ejecutó apt, git clone o compilación local. Se descargaron las capas de la
imagen oficial pgvector necesarias para extraer los artefactos, incluidas sus
capas base; no se instalaron herramientas en Windows ni contenedores existentes.
La etapa RUN se ejecutó con red deshabilitada. Resolver imágenes desde el registro
requiere red de Docker, aunque RUN use `--network=none`.

## 2. Imagen preparada

| Propiedad | Resultado final |
| --- | --- |
| Tag local | `api-usuarios-clean/pgvector:18-0.8.2-93c` |
| Plataforma probada | linux/amd64, Debian trixie |
| PostgreSQL efectivo | **18.6 (Debian 18.6-1.pgdg13+2)** |
| pgvector efectivo | **0.8.2** |
| Digest local final | `sha256:a1336b54a1b49085474132cceb0636b314707b011fdb242afa694ae08ffcc3e6` |
| Manifest de ejecución final | `sha256:cdaa03a475355042b230fd15ca1f2758dc30774e795fec89c867257517791218` |
| Config de imagen | `sha256:7a743fd5f74ae4835b6d0bc7040b138d3afce79d41a105f46e3fcc849d43bc10` |
| Tamaño informado por Docker | **646467364 bytes** |

No se publicó la imagen en un registro externo. Ambos inputs están fijados y no
hay resolución de paquetes mutable. Los rebuilds usaron caché y mantuvieron el
manifest de ejecución/config; las atestaciones de BuildKit cambian el digest del
índice contenedor entre builds. No se promete igualdad byte a byte del índice
con sus atestaciones ni reproducibilidad multi-arquitectura. Para una entrega
futura se debe fijar/exportar el artefacto validado y verificar su hash/digest.

La imagen **no ejecuta CREATE EXTENSION al arrancar**, no contiene SQL de usuarios
ni scripts de migración del proyecto. Tener los archivos vector disponibles no
activa la extensión en bases existentes.

## 3. Aislamiento y pruebas efectivamente realizadas

Comandos ejecutados desde la raíz, además de inventarios Docker de lectura:

```powershell
docker build --platform linux/amd64 --network=none --progress=plain -t api-usuarios-clean/pgvector:18-0.8.2-93c infra/pgvector
& .\infra\pgvector\verify.ps1
```

La verificación crea un nombre UUID nuevo y conserva el ID completo. Usa:

- `--network none`, sin puertos publicados, servidor sin listener TCP.
- tmpfs propio `/var/lib/postgresql`, techo **192 MiB**, sin bind mounts o volúmenes.
- **256 MiB** de memoria y memory-swap total también 256 MiB; **0,5 CPU**.
- shared_buffers 32 MiB, work_mem 1 MiB, maintenance_work_mem 16 MiB y 10 conexiones.
- Base `rag93c_synthetic`, usuario ficticio `synthetic_admin`; autenticación trust
  solo dentro del contenedor sin red. **No trasladar trust al desarrollo**.
- SQL por docker exec/psql con ON_ERROR_STOP, sin archivos .env o credenciales reales.
- Finally que revalida etiqueta de propiedad y elimina únicamente el contenedor
  nuevo por ID. No elimina imágenes o volúmenes, ni selecciona recursos por prefijo.

El SQL se niega a ejecutarse fuera de `rag93c_synthetic` y PostgreSQL major 18.
Se hicieron dos ensayos temporales secuenciales, ambos exitosos; el segundo añadió
hash del dump, comparación de contenido restaurado y coseno después de restaurar.
No fueron tests contra usuarios_dev/usuarios_test.

| Control | Resultado |
| --- | --- |
| CREATE EXTENSION vector VERSION 0.8.2 | Aprobado |
| Columna vector(768) | Aprobado |
| Inserción de tres vectores unitarios sintéticos | Aprobado |
| Coseno de un vector consigo mismo | Distancia 0, vecino esperado ID 1 |
| Coseno de dos vectores ortogonales | Distancia 1 |
| Inserción de dimensión incorrecta | Rechazada, sin insertar una cuarta fila |
| pg_dump custom y pg_restore --list | Aprobados |
| Restauración a `rag93c_restored` dentro del mismo contenedor | Aprobada |
| Conteo/dimensión/versión restaurados | `3:768:0.8.2` |
| Huella agregada del contenido original/restaurado | Coincidente |
| Consulta coseno sobre la restauración | Vecino ID 1 correcto |
| Limpieza de los dos contenedores creados | Completada |

Marcadores finales: **SYNTHETIC_VECTOR_CHECKS_OK** y **SYNTHETIC_RESTORE_OK**.
Hash SHA-256 del último dump sintético:
`af93f51fe79d475cea46c5ff1e357767ffdd3a9e98dde684e64e7e56ff65ed6a`.
El dump temporal desapareció con su contenedor; no es un respaldo de datos reales.
No se almacenó información de usuarios en ese archivo.

IDs completos de los únicos contenedores creados y eliminados:

- `0d3704f54b0671fef8f2ba5d29b6534129e471fcce474a955a2d66df4a0c7fb5`.
- `6411e0816d2125ef25181c3e7572e6312e16bd2375fe4f6764c65f866a69fcab`.

No quedan contenedores con la etiqueta del ensayo. La prueba usa búsqueda exacta;
no se construyeron índices HNSW/IVFFlat, ni se midió rendimiento a escala. No se
repitieron suites Python: no hay cambios de aplicación y este incremento verifica
la imagen mediante SQL real exclusivamente sintético.

## 4. Estado de infraestructura existente

Inventario anterior y posterior: mismos contenedores, imagen, StartedAt y montajes.

| Recurso | Estado observado y conservación |
| --- | --- |
| Desarrollo `ce41dbdca5f0` | Running; inicio `2026-11-03T09:38:30.533051573Z`, sin reinicio |
| Pruebas `80172da97281` | Running; inicio `2026-11-03T09:38:55.177531537Z`, sin reinicio |
| Imagen de ambos | Digest postgres:18 `979bcc…be0e4`, sin reemplazo |
| Volumen desarrollo | `api-usuarios-clean_postgres_data` sigue montado en `/var/lib/postgresql` |
| Persistencia de pruebas | Sin volumen persistente en Mounts; Compose mantiene tmpfs |
| Inventario de volúmenes | Los mismos cuatro iniciales; no se crearon ni eliminaron volúmenes |

Al inicio ambos figuraban healthy. No se hicieron conexiones SQL ni docker exec
a ninguno de ellos. No se tocaron sus datos, configuración, imágenes o montajes
por este procedimiento. **No se presenta esto como comparación bit a bit de sus
datos**, ni se descartan escrituras normales de aplicaciones preexistentes:
esas no fueron inspeccionadas. usuarios_dev y usuarios_test quedaron fuera del ensayo.

Los primeros inventarios Docker devolvieron acceso denegado al pipe/config en el
sandbox; las lecturas/build/ensayos autorizados funcionaron con la revisión de
permisos de herramientas, sin cambiar permisos Windows o reiniciar Docker.

## 5. Recursos y límites

| Muestra | RAM física disponible | Compromiso global |
| --- | ---: | ---: |
| 12:48:17 -03:00, antes del build | **1,161 GiB** | **14,507 GiB** |
| Durante descarga/build, GlobalMemoryStatusEx | **1,042 GiB**, carga 86 % | No medido en esa muestra |
| 12:52:24 -03:00, ensayos ya eliminados | **0,566 GiB** | **14,402 GiB** |

Total físico 7,851 GiB y límite de compromiso 25,851 GiB. Inicio/final mediante
GetPerformanceInfo. Docker stats de los ensayos: **107,3 / 102,8 MiB** de 256 MiB
y CPU puntual **0,04 / 0,02 %**. Son muestras, no picos ni monitoreo sostenido.
El límite del contenedor no limita toda la memoria de Docker/WSL/BuildKit o cachés
del host. No se midió paginación sostenida ni puede atribuirse la caída de RAM a
una causa concreta. No hubo errores OOM o necesidad de detener servicios para
completar los ensayos.

La última RAM es muy reducida: **se suspenden actividades adicionales de build o
prueba** y no se recomienda reemplazo operativo con este margen. Solo el responsable
puede cerrar voluntariamente aplicaciones que reconozca y autorizar una nueva
evaluación. No se finalizó Docker, WSL, PostgreSQL, Ollama, FastAPI o React para
liberar recursos. No se hicieron solicitudes a Ollama o inferencias.

## 6. Procedimiento futuro de respaldo, sustitución y reversión — NO EJECUTADO

Este procedimiento requiere autorización posterior específica sobre datos reales,
ventana de mantenimiento, parada del servicio propio y cambio de Compose. No son
acciones autorizadas automáticamente por construir la imagen.

1. Recuperar recursos y medirlos de nuevo. Revalidar identidad/imagen/montaje del
   servicio de desarrollo y destino efectivo, versión menor 18.6, locale, encoding,
   extensiones y revisión Alembic esperada según repositorio. No asumir que un
   contenedor healthy acredita esquema/datos correctos. usuarios_test queda aparte.
2. Archivar imagen anterior por digest y configuración Compose efectiva en un
   destino protegido. La configuración puede contener secretos: no anexarla a logs
   o Git. Asegurar disco suficiente para dump, ensayo y volumen nuevo. Preparar
   un nombre nuevo y validar que no colisiona con ningún recurso existente.
3. Bajo permiso de mantenimiento, suspender escritores/autenticación normal y
   confirmar ausencia de escrituras durante el corte. Generar **pg_dump custom de
   usuarios_dev con cliente PostgreSQL 18 compatible**, más definiciones de roles
   necesarias con `pg_dumpall --globals-only --no-role-passwords`. Proteger ambos
   archivos, permisos y retención; incluso sin contraseñas contienen metadatos o
   datos sensibles. Provisionar las credenciales necesarias por un mecanismo
   seguro, nunca argumentos impresos o commits.
4. Evitar redirección binaria de pg_dump mediante PowerShell. Usar archivo `-f`
   dentro de un destino temporal explícitamente aprobado y copiarlo con docker cp,
   o cliente host que escriba directamente a archivo. Verificar exit codes, tamaño,
   SHA-256 y `pg_restore --list`. Un listado o checksum **no sustituye restaurar**.
5. Restaurar el dump real en un contenedor/volumen **nuevo**, aislado, con la imagen
   candidata fijada. Nunca montar el volumen original para ensayar. Restaurar roles
   de forma revisada y luego base con `pg_restore --exit-on-error`, sin privilegios
   innecesarios o propietarios cambiados accidentalmente. No restaurar sobre DB
   existente ni ejecutar Alembic como atajo. Probar consistencia con metadatos,
   restricciones, revisión y verificaciones agregadas autorizadas; no imprimir
   perfiles, hashes de credenciales, sesiones o tokens. Registrar éxito verificable.
6. Si el ensayo falla, detener el cambio sin modificar el origen. Si hubo escrituras
   después del respaldo, repetir el respaldo/ensayo final o acordar mecanismo de
   sincronización: no promover una copia desactualizada perdiendo datos.
7. Preferir sustituir el servicio con **el nuevo volumen restaurado**, conservando
   el volumen original intacto para reversión. Revisar un override Compose limitado
   a imagen y volumen de desarrollo. Mantener PostgreSQL major 18, montaje padre
   `/var/lib/postgresql`, PGDATA heredado `/var/lib/postgresql/18/docker`, puerto
   loopback 5434, healthcheck/red y credenciales autorizadas. No reutilizar a ciegas
   el PGDATA de otras versiones/distribuciones. No tocar el servicio de pruebas.
8. Solo con aprobación y corte de escritores, detener exclusivamente el servicio
   de desarrollo revalidado y arrancar el candidato con la copia ensayada. Comprobar
   destino, versión, healthcheck, esquema/autorización normales. Mantener escritores
   suspendidos hasta aceptación del cambio para permitir rollback sin divergencia.
   No habilitar RAG, aprovisionamiento o migraciones de usuarios.
9. Crear `vector` en usuarios_dev es una escritura de catálogo y requiere una
   autorización/migración específica posterior. La sustitución de imagen por sí
   sola no lo crea. Diseñar también permisos de extensión y futuras tablas RAG;
   no conceder superusuario al backend para simplificarlo.
10. **Reversión antes de reabrir escritores:** detener únicamente candidato propio,
    restaurar Compose/imagen anterior por digest y volumen original conservado,
    comprobar destino/revisión/servicio y reabrir acceso tras aceptación. No borrar
    el candidato, dump o volúmenes hasta aprobar retención y resultado.
11. **Si ya hubo escrituras en el candidato**, volver al volumen viejo perdería
    datos nuevos: suspender escritores y decidir respaldo/restauración reconciliada
    o reparación hacia adelante, con autorización. No montar una base que ya usa
    tipos vector en una imagen sin sus binarios; volver solo a una imagen compatible
    o a una copia anterior validada. Nunca usar DROP EXTENSION CASCADE como rollback.

No se propone `docker compose down -v`, prune, pg_upgrade, downgrade, restauración
sobre el volumen original o instalación manual dentro del contenedor existente.
El ensayo sintético de este sprint **no acredita que un respaldo real todavía no
realizado sea restaurable**.

## 7. Dictamen y detención

**Imagen compatible PostgreSQL 18.6 + pgvector 0.8.2 preparada y comprobada** con
vectores sintéticos y restauración aislada. Pendientes: recursos suficientes,
autorización de mantenimiento, respaldo real verificado/ensayado, sustitución
controlada y activación posterior de extensión/esquema RAG. No se inicia RAG operativo.

Se conservaron imágenes/caché de construcción; no se borraron imágenes previas.
Solo se eliminaron los dos contenedores nuevos del ensayo tras revalidar propiedad.
No hubo conexiones a usuarios_dev/usuarios_test, cambios del volumen existente,
Alembic, migraciones de usuarios, datos reales, credenciales expuestas, cambios de
código de aplicación o .env, ni intervención en servicios existentes.

**Se detiene para revisión. PostgreSQL de desarrollo NO reemplazado.**
