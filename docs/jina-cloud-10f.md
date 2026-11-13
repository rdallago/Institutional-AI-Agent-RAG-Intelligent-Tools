# Sprint 10F — Migración estructural Jina: preflight detenido

## Ejecución autorizada 10F.3 — resultado final

10 de noviembre de 2026. **Migración estructural APROBADA: revisión actual
0006_cloud_embeddings.** Esta sección sustituye los estados históricos de
«migración no ejecutada» conservados debajo.

Se recibió autorización expresa para aplicar únicamente 0006 en usuarios_dev,
127.0.0.1:5434, incluyendo locks breves dentro de la transacción y límites de
2 s / 15 s. Se ejecutó UN intento, sin reintentos, downgrade ni restauración.

### Precondiciones revalidadas

- Docker: contenedor esperado healthy, puerto publicado 127.0.0.1:5434.
- RAM disponible: 738.164 KiB, aproximadamente 0,70 GiB. Margen bajo registrado;
  no se cargaron modelos ni se duplicaron fragmentos/vectores para este DDL breve.
- Destino validado por configuración y SELECT current_database en conexión efectiva.
- Auditoría READ ONLY previa: revisión 0005, tablas cloud inexistentes, 864
  fragmentos/vectores íntegros, versiones y UUID activo correctos.
- Sin otras transacciones de usuarios_dev, transacciones preparadas ni locks
  pendientes de esa base al comprobar.
- Dump 10E disponible; SHA-256 recalculado coincidente con manifest.json:
  93e1316a5c934b7e5e70008015db772a0b7b556f31e36ece996be648fb16c91b.

### Comando y control transaccional efectivos

```powershell
& '.\backend\.venv\Scripts\python.exe' -B '.\infra\_run_10f3_authorized.py'
```

El ejecutor operativo conservado contiene un único
`alembic.command.upgrade(config, '0006_cloud_embeddings')`, con argumento
allow-development=true. NO volver a ejecutarlo automáticamente. No se modificaron
env.py, migraciones o configuración permanente. El ejecutor utiliza un wrapper
de build_engine exclusivamente en memoria del proceso para instrumentar su evento
begin. La transacción inicial de comprobación de destino se revierte normalmente;
la siguiente es la de migración y conserva locks hasta su commit/rollback.

En la conexión real se ejecutaron SET LOCAL lock_timeout='2s' y SET LOCAL
statement_timeout='15s', y ambos se comprobaron con SHOW. Se bloquearon las
17 tablas public existentes, incluida alembic_version, con un único LOCK TABLE
en orden determinista, modo SHARE ROW EXCLUSIVE. Con los locks tomados se volvió
a comprobar revisión 0005 y coincidencia completa de huellas de las tablas
preexistentes antes de permitir el DDL Alembic. No hubo commit entre locks y DDL.
El COMMIT de la migración liberó los locks; no se detuvieron servicios.

**Código de salida del proceso y resultado Alembic: 0. Estado VERIFIED.**
Duración del recorrido Python, incluida auditoría: **1,712 segundos**. No representa
solo tiempo DDL. No hubo excepción o intento adicional.

### Verificación posterior READ ONLY

| Comprobación | Resultado |
|---|---|
| Revisión | 0006_cloud_embeddings |
| rag_cloud_espacios | Vacía; PK 1, UNIQUE 2, CHECK 2 |
| rag_cloud_embeddings | Vacía; PK 1, FK 2, CHECK 3 |
| rag_cloud_ingestas | Vacía; PK 1, FK 2, CHECK 1 |
| rag_cloud_activos | Vacía; PK 1, FK 1 |
| Tipo embedding cloud | vector(768) |
| Restricciones de tablas nuevas | Todas convalidated=true |
| Fragmentos / embeddings históricos | 864 / 864, íntegros |
| Hashes de páginas/fragmentos, offsets/slices y hashes de entrada | Sin errores |
| Valores de vectores históricos | 768 componentes finitos, norma positiva |
| Datos preexistentes de todas las tablas public | Huellas de filas coincidentes |
| Cambio esperado en datos preexistentes | Solo alembic_version: 0005 → 0006 |

Las huellas completas incluyen usuarios, autenticación, conversaciones y vectores;
no se imprimieron esas filas ni sus contenidos sensibles. Se compararon en memoria.
No se atribuye a esta auditoría una prueba semántica de recuperación RAG.

Ambas versiones siguen LISTA, 72 páginas y 432 fragmentos cada una:

- Activa: 7cb4e79c-747d-574a-8abb-0ebcb2e07636, sin cambios.
- Anterior: 9cab30cd-9554-5679-a2d9-35d85dd5ab85, conservada.

Las únicas tablas añadidas son las cuatro cloud; están vacías y no existe ningún
espacio cloud activado. No hubo acceso de escritura a usuarios_test, restauración
10E o base sintética 10C. No se borraron respaldos ni otros artefactos. No se
modificaron .env, servicios, prompts/modelos ni DOCUMENT_EXPORT_APPROVED=False.
No hubo llamadas a Jina, OpenRouter u Ollama, indexación ni activación del RAG.
Archivos incorporados/actualizados: infra/_run_10f3_authorized.py y este informe.

### Decisión

**GO estructural para preparar el Sprint 10G.** PostgreSQL ya permite almacenar
el espacio Jina separado. Esto NO autoriza enviar textos, levantar el bloqueo
documental, reindexar o publicar. Esas operaciones siguen pendientes de condiciones
de privacidad/cuenta y autorización propia. Revalidar recursos antes de continuarlas.

## Preflight final 10F.2 — 10 de noviembre de 2026

**GO técnico para solicitar autorización de 0006; migración NO ejecutada.**
Esta sección sustituye los estados históricos de conectividad/preflight inferiores.

| Verificación READ ONLY | Resultado actual |
|---|---|
| Destino configurado y current_database | usuarios_dev, 127.0.0.1:5434 |
| PostgreSQL / pgvector | 18.6 / 0.8.2 |
| Docker | Contenedor esperado healthy, puerto publicado correcto |
| Revisión Alembic | 0005_agent_memory, comprobada por auditoría |
| Tablas rag_cloud_* | Ninguna |
| Integridad en origen y restauración | 864 fragmentos y 864 vectores válidos en cada base |
| SHA-256 de páginas/fragmentos y slices/offsets | Sin errores en ambas bases |
| Embeddings | Hash de entrada correcto, 768 valores finitos y norma positiva |
| Comparación de todas las tablas public entre ambas bases | Sin diferencias de huellas de filas |
| Propietarios y ACL de relaciones/esquema auditados | Coincidentes |
| Otras sesiones / transacciones en usuarios_dev | 0 / 0 al comprobar |
| Locks pendientes / transacciones preparadas de usuarios_dev | 0 / 0 |
| Conexiones de servidor | 9 de máximo 100 |
| Tiempo de auditoría origen / copia | 1,246 / 1,212 segundos |

Ambas versiones siguen LISTA, con 72 páginas y 432 fragmentos cada una; la
comparación completa de embeddings y filas también coincide:

- Activa: 7cb4e79c-747d-574a-8abb-0ebcb2e07636.
- Conservada: 9cab30cd-9554-5679-a2d9-35d85dd5ab85.

Respaldo: carpeta privada 10e-8ec23d77c150417db136e68c0a0f2d05 bajo
D:\Downloads\api-usuarios-clean-backups; usuarios_dev.dump de 3.680.756 bytes.
SHA-256 calculado y comparado con manifest.json:
93e1316a5c934b7e5e70008015db772a0b7b556f31e36ece996be648fb16c91b.
ACL de carpeta/archivos: únicamente operador y SYSTEM. Se revalidó realmente la
base rag_restore_10e_8ec23d77c150417db136e68c0a0f2d05, sin escribirla.

Las conexiones usaron connect_timeout=10, default_transaction_read_only=on,
statement_timeout=10000, REPEATABLE READ, comprobación de transaction_read_only y
rollback. Se reutilizó solo la función pura de auditoría de 10E mediante AST:
NO se importó/ejecutó su operación de respaldo/restauración. Datos sensibles y
vectores se compararon exclusivamente en memoria, sin imprimirlos.

### Recursos

Windows informó 1.817.236 KiB disponibles al inicio (1,73 GiB) y 1.114.768 KiB
al final (1,06 GiB), sobre 8.232.504 KiB totales. No se confirma estabilidad de
los 1,99 GB comunicados por el usuario. La auditoría terminó sin error; la
migración propuesta es de cuatro tablas vacías, sin carga de modelos, indexación
ni copias de 864 vectores. Hay margen para preparar ese DDL breve, pero no es
una garantía contra presión futura. Revalidar RAM/Docker inmediatamente antes;
detener si aparecen presión crítica o fallos. No cambiar guardas o inventar un
umbral permanente de RAM para esta operación SQL.

### Estrategia de bloqueo propuesta, todavía NO ejecutada

Tras autorización, ejecutar exclusivamente upgrade 0006 desde revisión 0005,
con lock_timeout=2 s y statement_timeout=15 s en la conexión efectiva. Verificar
estos valores con SHOW; no depender solo de PGOPTIONS porque build_engine pasa
también opciones de conexión explícitas. Sin cambios persistentes ni .env.

La ventana se garantiza con LOCK TABLE de todas las tablas public preexistentes,
incluida alembic_version, en orden determinista, modo SHARE ROW EXCLUSIVE, en la
MISMA conexión/transacción del DDL Alembic. Impide INSERT/UPDATE/DELETE y otros
migradores sobre esas tablas; SELECT ordinarios pueden continuar. Los locks se
liberan en commit/rollback. Una adquisición que exceda 2 s aborta sin reintento.
No adquirirlos en un proceso separado, ni hacer commit entre locks y upgrade.
La adquisición puede ser escalonada: no ejecutar DDL hasta poseerlos todos.

env.py crea y administra su conexión; por tanto, la ejecución futura debe conectar
el control transaccional a ese engine (instrumentación operativa temporal en el
proceso Alembic), no asumir que acepta una conexión externa por Config.attributes.
No hace falta modificar migraciones ni código permanente para ese control.
Verificar nuevamente destino/revisión dentro del recorrido protegido antes de DDL.
La autorización solicitada debe incluir el breve bloqueo de escrituras. No se
detendrá FastAPI, PostgreSQL u otros servicios. No prometer que una mera consulta
previa de sesiones impide escritores nuevos; se usarán los locks citados.

Después del único intento, consultar READ ONLY revisión, tablas/constraints/tipos,
vacío cloud y huellas de datos históricos/usuarios/conversaciones. Ante anomalía,
conservar estado y evidencia, sin downgrade, restauración sobre origen o reintentos.

### Decisión y punto de autorización

Preflight integral APROBADO en este instante; recursos sujetos a revalidación por
su variación. Se solicita permiso expreso para aplicar SOLO 0006_cloud_embeddings
en usuarios_dev con la ventana de locks y límites anteriores. Hasta recibirlo,
NO ejecutar Alembic o adquirir locks de escritura. Este GO no autoriza exportar
documentos, indexar, activar cloud ni cambiar DOCUMENT_EXPORT_APPROVED=False.
Solo se actualizó este informe; no se modificaron bases, servicios, configuración
o respaldos y no se hicieron llamadas a Jina/OpenRouter/Ollama.

## Diagnóstico 10F.1 — Conectividad PostgreSQL

### Actualización tras recuperación externa del motor — 10/11/2026

**GO para repetir el preflight READ ONLY de 10F. No autoriza DDL.**
Esta actualización supersede el NO-GO de conectividad registrado más abajo.
No se inició ni reinició ningún servicio durante el diagnóstico.

- Docker Server respondió versión 29.8.1; docker ps mostró el contenedor
  api-usuarios-clean-postgres-1 saludable, iniciado aproximadamente un minuto antes
  de la comprobación. No se atribuye ese arranque a una acción de este diagnóstico.
- Windows escucha en 127.0.0.1:5434 mediante com.docker.backend, PID 13992.
  Test-NetConnection devolvió TcpTestSucceeded=true.
- pg_isready dentro del contenedor: exit 0, accepting connections.
- Logs recientes disponibles: marcadores de recuperación tras interrupción y de
  disponibilidad; sin marcadores de demasiadas conexiones ni out of memory en
  las últimas 80 líneas. Es un resumen limitado, no descarta eventos anteriores.
- Se ejecutó UNA conexión Python con connect_timeout=10, READ ONLY verificado,
  statement_timeout=5000 y rollback. Conectó a usuarios_dev en **0,020 segundos**.
- Revisión actual: **0005_agent_memory**. Ninguna de las cuatro tablas cloud existe.
- La base rag_restore_10e_8ec23d77c150417db136e68c0a0f2d05 figura en pg_database con
  datallowconn=true. No se abrió una segunda conexión ni se revalidó su integridad;
  esa comprobación corresponde al preflight completo.
- Servidor: 9 conexiones de máximo 100; ninguna otra transacción en usuarios_dev,
  cero locks pendientes en esa base y cero transacciones preparadas. No se observó
  escritor concurrente en ese instante; no constituye una ventana garantizada.
- RAM disponible al finalizar: 519.036 KiB, aproximadamente **0,495 GiB**, de
  8.232.504 KiB totales; CPU observada 7 %. Margen operativo bajo: revalidar recursos
  antes de cualquier migración. No ejecutar inferencias bajo este diagnóstico.

**Conclusión:** conectividad recuperada. La evidencia anterior mostraba un motor
Docker no operativo pese al listener TCP; ahora PostgreSQL responde rápidamente.
No hay evidencia para atribuir el fallo original a un timeout de 3 segundos
insuficiente. La causa interna de la interrupción de Docker sigue sin determinarse.
No se recomienda cambiar .env ni el timeout persistente con estos resultados.
Siguiente paso: repetir el preflight integral, incluida integridad de restauración,
respaldo y recursos; después pedir autorización expresa para 0006 y su ventana sin
escritores. No se aplicó ninguna corrección de servicios, migración o configuración.

Comprobación del 10 de noviembre de 2026. **NO-GO para repetir el preflight SQL
hasta recuperar y comprobar el motor Docker.** No se modificaron servicios.

| Comprobación | Resultado real |
|---|---|
| docker version (servidor) | Error: `Docker Desktop is unable to start` |
| docker ps filtrado al contenedor esperado | Mismo error; estado del contenedor no verificable |
| Listener Windows | 127.0.0.1:5434, PID 13992, com.docker.backend |
| Test-NetConnection | TcpTestSucceeded=true |
| pg_isready dentro del contenedor | No ejecutable: Docker devuelve el mismo error |
| docker logs --tail 30 | Exit code 1, mismo error del motor; registros no recuperables |
| Conexión Python connect_timeout=10 | NO EJECUTADA: no se cumple la precondición de PostgreSQL disponible |
| RAM física total / disponible | 8.232.504 / 1.337.124 KiB; aproximadamente 7,85 / 1,28 GiB |
| Carga CPU observada | 6 % |
| Procesos Docker Desktop/backend | Presentes; su presencia no demuestra motor operativo |
| Saturación de conexiones, locks y escritores | No comprobables sin acceso SQL |
| Revisión, cuatro tablas cloud y base restaurada | Estado actual no comprobado; no sustituir con resultados históricos |

**Causa inmediata confirmada del bloqueo de diagnóstico:** el motor Docker no
responde operativamente y comunica que Docker Desktop no puede arrancar. El
backend de Docker conserva un listener TCP, de modo que una conexión TCP exitosa
no acredita un handshake PostgreSQL ni disponibilidad del contenedor.

Esto es compatible con el timeout psycopg anterior, pero no demuestra que Docker
estuviera en idéntico estado en aquel instante. No hay evidencia para afirmar que
el plazo de 3 segundos fuera insuficiente ni que aumentarlo resuelva el problema.
Tampoco se ha identificado la causa interna de fallo de Docker Desktop: los
registros del contenedor no son accesibles. RAM disponible baja es una observación,
no una causa probada. No se leyeron contraseñas, tokens ni consultas privadas.

**Intervención recomendada:** revisar en la interfaz de Docker Desktop el error de
arranque y su diagnóstico. Recuperar/iniciar o reiniciar Docker Desktop requiere
autorización expresa y puede afectar otros contenedores del equipo. No se hizo
ninguna de esas operaciones y no se propone reiniciar PostgreSQL a ciegas.
Después de recuperar el motor, verificar contenedor y pg_isready; únicamente si
responden, hacer una sola conexión Python READ ONLY con connect_timeout=10 para
consultar revisión, tablas cloud, disponibilidad de la base restaurada y escritores.
No ejecutar Alembic, reiniciar FastAPI o cambiar .env durante ese diagnóstico.

No se reintentó automáticamente ninguna conexión SQL ni operación fallida del
motor. Se completaron lecturas independientes de recursos y del listener. El
respaldo y las bases se conservaron; DOCUMENT_EXPORT_APPROVED sigue sin cambios.

Fecha: 10 de noviembre de 2026, America/Buenos_Aires.
**NO-GO: no se ejecutó Alembic ni DDL. Autorización de fase 2 no solicitada aún.**

## 1. Alcance y autorización

El pedido autoriza preflight READ ONLY y exige confirmación adicional antes de
`upgrade 0006_cloud_embeddings`. No se interpretó como autorización de escritura.
No se reiniciaron servicios ni se cambiaron .env, permisos o datos.

## 2. Comprobaciones efectivas

| Comprobación | Resultado |
|---|---|
| Configuración de conexión | Verificada: usuarios_dev, 127.0.0.1:5434 |
| Archivo del respaldo 10E | Disponible; 3.680.756 bytes |
| SHA-256 contra manifest.json | Coincide: 93e1316a5c934b7e5e70008015db772a0b7b556f31e36ece996be648fb16c91b |
| ACL de carpeta y archivos de respaldo | Solo usuario actual y SYSTEM |
| Conexión READ ONLY a usuarios_dev | FALLÓ: psycopg.errors.ConnectionTimeout, plazo 3 s |
| PostgreSQL/pgvector actuales, revisión, tablas cloud, conteos | No comprobados por fallo de conexión |
| Integridad actual de base restaurada | No comprobada: no se alcanzó esa etapa |
| Escritores, transacciones preparadas y locks | No comprobados |
| Puerto FastAPI 8000 | Escucha en 127.0.0.1, PID 19020; no detenido ni reiniciado |

La lectura del respaldo y verificación SHA-256 se completaron antes del intento
SQL. La primera conexión, dirigida a usuarios_dev, agotó connect_timeout=3 con
default_transaction_read_only=on y statement_timeout=10000. No se reintentó.
El fallo ocurrió antes de poder ejecutar la auditoría. No demuestra pérdida de
datos ni permite atribuir causa a Docker, PostgreSQL, firewall o recursos sin más
evidencia. Los resultados históricos de 10E no sustituyen este preflight actual.

## 3. Revisión estática de migración y transacción

Se leyó el código exacto de 0006_cloud_embeddings y migrations/env.py.
0006 depende de 0005_agent_memory y contiene exclusivamente cuatro CREATE TABLE:
rag_cloud_espacios, rag_cloud_embeddings, rag_cloud_ingestas y rag_cloud_activos.
No modifica fragmentos, embeddings Nomic o puntero textual. Define vector(768),
PK/FK y restricciones; VALIDADA/completitud también requieren control de aplicación.
Downgrade rechaza eliminación automática.

env.py comprueba la base y ejecuta las revisiones en transacción PostgreSQL.
No se ejecutó Alembic, ni siquiera current, durante este preflight.
Antes de la ejecución futura deberán revalidarse host/puerto y revisión 0005,
para que upgrade a 0006 no aplique revisiones previas inesperadas.

## 4. Ventana sin escritores propuesta, pendiente de aprobación

Una consulta puntual de pg_stat_activity no garantiza que no entren escritores
durante la migración. No hay autorización para detener FastAPI u otros servicios.
Propuesta: adquirir locks de tabla que bloqueen DML sobre todas las tablas de
aplicación existentes, incluida alembic_version, en orden determinista y **en la
misma conexión y transacción que ejecutará Alembic**. Mantenerlos hasta commit o
rollback; SELECT ordinarios pueden continuar. Configurar SET LOCAL lock_timeout
y statement_timeout antes de adquirirlos; detener sin reintentos si no se obtienen.
Esto requiere aprobación explícita del breve bloqueo de escrituras; no ejecutarlo
en otra conexión que bloquee al propio Alembic. Revisar también transacciones
preparadas y escritores DDL fuera del procedimiento. Si no puede garantizarse
esta coordinación, no migrar ni detener servicios unilateralmente.

La implementación concreta del control transaccional y sus tiempos debe
presentarse junto con el preflight aprobado antes del punto de autorización.
No se ha aplicado ningún lock ni cambiado configuración persistente.

## 5. Resultado y siguiente paso

**Resultado Alembic: NO EJECUTADO; sin código de salida de migración.**
No hay verificaciones posteriores de 0006 porque no se aplicó. No se tocó
usuarios_test, la base restaurada o la base sintética 10C; no se enviaron textos
a Jina/OpenRouter ni se ejecutó Ollama. DOCUMENT_EXPORT_APPROVED no se modificó.

Primero resolver o verificar disponibilidad de PostgreSQL/puerto 5434 y autorizar
un nuevo preflight. No iniciar/reiniciar servicios automáticamente. Tras comprobar
todos los requisitos, solicitar autorización para aplicar exclusivamente 0006 y
para su ventana transaccional sin escritores. Indexación y activación siguen fuera
de alcance, aun si posteriormente aprueba la migración estructural.
