# Sprint 10D — Preparación segura de migración Jina

Fecha: 9 de noviembre de 2026. **NO-GO para migración real y exportación.**
Esta intervención solo inspeccionó código y efectuó SELECT en usuarios_dev,
con `default_transaction_read_only=on`, verificación de ese estado, timeout de
sentencias de 5 segundos y rollback. No hubo respaldo, DDL, embeddings, llamadas
OpenRouter, reinicios, cambios de configuración ni publicación.

## 1. Estado real auditado

Destino verificado antes de conectar: usuarios_dev, 127.0.0.1:5434.

| Comprobación | Resultado real |
|---|---:|
| Revisión Alembic | 0005_agent_memory |
| Documentos / versiones | 1 / 2 |
| Fragmentos / vectores históricos totales | 864 / 864 |
| Tablas rag_cloud_* | 0 |
| Fragmentos sin versión | 0 |
| Errores SHA-256 de páginas / fragmentos | 0 / 0 |
| Errores de slice y offsets de fragmentos | 0 |
| Hash de entrada de vector distinto del fragmento | 0 |
| Vectores con dimensión distinta de 768 o norma no positiva/acotada | 0 |

Versión activa: `7cb4e79c-747d-574a-8abb-0ebcb2e07636`, LISTA, 72 páginas,
432 fragmentos y 432 vectores. Anterior conservada:
`9cab30cd-9554-5679-a2d9-35d85dd5ab85`, LISTA, 72 páginas, 432 fragmentos/vectores.
La prueba de norma histórica no exige norma unitaria Jina ni prueba pertinencia
semántica. Los textos se procesaron en memoria para comprobar hashes/slices;
no se imprimieron textos, usuarios, conversaciones, credenciales ni vectores.

Total UTF-8 de fragmentos activos con solapamientos: 159.779 bytes; mínimo 64,
máximo 400. No se volvió a ejecutar extracción, OCR ni tokenización de proveedor.
Se mantiene la base sintética `rag_jina_10c_2f38fd284c20454eb9acadf1def9205f`:
no se conectó a ella, reutilizó ni eliminó en esta intervención.

## 2. Auditoría de migración

`0006_cloud_embeddings` depende de `0005_agent_memory`, que depende de 0004.
Crea cuatro tablas paralelas: espacios, embeddings, ingestas y activos cloud.
No actualiza, elimina ni altera tablas históricas. vector(768) coincide en
dimensión, pero Jina y Nomic son espacios incompatibles: nunca mezclar vectores.
Las PK/FK vinculan fragmento, espacio, dimensión y pareja versión/espacio.
La FK del puntero no exige VALIDADA: completitud y estado los verifica la
aplicación en la misma transacción de activación. Evitar SQL administrativo manual.

`migrations/env.py` verifica destino y usa transacción Alembic. PostgreSQL permite
rollback de este DDL; verificar revisión y objetos después de cualquier error,
sin asumir resultado ante desconexión. No usar downgrade: explícitamente rechaza
el borrado. Crear FK toma locks sobre tablas referenciadas y puede esperar a
transacciones concurrentes; suspender escrituras de aplicación durante el corte
autorizado y fijar lock_timeout/statement_timeout. No se mantienen transacciones
SQL abiertas mientras se espera una respuesta HTTP de Jina.

El ensayo PostgreSQL de 10C aprobó 1 test real en 15,75 s con 432 vectores
sintéticos, checkpoints, restricciones, ACL y publicación. No equivale a migración
aplicada ni aceptación del reglamento real. No se repitió en 10D. Las 185 pruebas
locales y los tres fallos heredados documentados en 10B conservan su alcance;
no se declara aprobada toda la suite.

## 3. Respaldo previo obligatorio — comandos NO ejecutados

Contenedor identificado: `api-usuarios-clean-postgres-1`, puerto host 5434.
Se ejecutaron únicamente `pg_dump --version` y `pg_restore --version`: ambos
PostgreSQL 18.6 (Debian 18.6-1.pgdg13+2). No hay pg_dump nativo en PATH.
No utilizar contenedores PostgreSQL 15/16 de otros proyectos.

Tras autorización, preparar un directorio NUEVO bajo
`D:\Downloads\api-usuarios-clean-backups\10d-<UUID32>` con ACL privada para el
operador y SYSTEM (Administradores solo si la política aprobada lo permite).
Comprobar propietario/ACL, espacio libre y ausencia de archivos antes de escribir.
Los comandos siguientes requieren un rol ya autorizado con lectura completa;
se utiliza POSTGRES_USER del contenedor, sin mostrarlo ni leer su contraseña.
Si la autenticación local requiere contraseña, detenerse y utilizar entrada privada
del operador, nunca argumentos, chat o archivos de credenciales.

```powershell
# FUTURO, previa autorización; comprobar cada ExitCode y detenerse ante error.
$backupRun = [guid]::NewGuid().ToString('N')
$backupDir = "D:\Downloads\api-usuarios-clean-backups\10d-$backupRun"
# Crear y restringir ACL de $backupDir antes de continuar; no sobrescribir.
$containerDump = "/tmp/usuarios-dev-10d-$backupRun.dump"
docker exec api-usuarios-clean-postgres-1 sh -c 'exec pg_dump -U "$POSTGRES_USER" -d usuarios_dev --format=custom --lock-wait-timeout=5s --file="$1"' sh $containerDump
docker exec api-usuarios-clean-postgres-1 pg_restore --list $containerDump
docker cp "api-usuarios-clean-postgres-1:$containerDump" "$backupDir\usuarios_dev.dump"
Get-FileHash -Algorithm SHA256 -LiteralPath "$backupDir\usuarios_dev.dump"
```

pg_dump toma snapshot consistente sin detener PostgreSQL. Comparar SHA-256 de
origen y copia, comprobar tamaño no cero y conservar manifiesto privado con hora,
versión de herramientas, revisión, conteos y UUID activo. El dump completo contiene
credenciales hash y conversaciones: nunca adjuntarlo a informes ni repositorio.
El dump incluye objetos y ACL de la base, pero no crea roles globales ni conserva
el PDF externo. Respaldar por separado el PDF inmutable y su SHA-256; inventariar
roles/propietarios sin secretos. Si se requiere respaldo global, necesita alcance
explícito y `pg_dumpall --globals-only --no-role-passwords`, no ejecutado aquí.

**Restaurabilidad:** `pg_restore --list` es necesario, pero insuficiente. Autorizar
otra base vacía con nombre UUID, en PostgreSQL 18.6 con pgvector 0.8.2 disponible,
y restaurar con `pg_restore --exit-on-error --single-transaction -U <rol_autorizado>
-d <base_nueva> <dump>`. Nunca usar --clean ni apuntar a usuarios_dev/test.
Verificar restauración de roles/ACL, revisión 0005, 864 vectores, hashes, offsets,
432 elementos de versión activa y UUID original. Resolver previamente propiedad
y permisos del rol de restauración; no omitir ACL para declarar fidelidad total.
Conservar dump y base restaurada; su borrado requiere autorización.

**Fallo de migración:** detener, inspeccionar rollback/revisión READ ONLY. Si sigue
0005 sin tablas cloud y con integridad intacta, conservar el estado y corregir la
causa antes de pedir otro intento. No restaurar encima de desarrollo ni bajar
revisiones a ciegas. Ante daño confirmado, restaurar el respaldo en base nueva,
verificarlo y autorizar por separado el cambio de destino. No hay rollback
automático ni fallback operativo hacia Nomic.

## 4. Indexación propuesta

1. Resolver privacidad/cuenta, autorizar respaldo y verificar restauración.
2. Autorizar por separado DDL en usuarios_dev, verificar snapshot y ausencia de
   ingesta concurrente. Aplicar solo 0006; comprobar cuatro tablas vacías,
   revisión, versión textual y vectores históricos intactos.
3. Autorizar explícitamente exportación y el cambio controlado del bloqueo
   `DOCUMENT_EXPORT_APPROVED=False`. Hoy todas las acciones CLI están bloqueadas;
   no hay variable/flag de bypass y este informe NO autoriza levantarlo.
4. Fijar identidad de configuración, fingerprint e identificador de espacio antes
   del primer lote. El alias Jina no tiene digest inmutable comprobado: registrar
   evidencia sintética de referencia y detenerse si el proveedor cambia el modelo.
5. La CLI lee pendientes de la versión activa existente: no vuelve a fragmentar.
   Cada lote es hasta 10 fragmentos, pero cada fragmento es UNA solicitud HTTP,
   secuencial, seguida de checkpoint transaccional. Son 43 lotes de 10 y uno de 2
   si no hay interrupciones; no son 44 llamadas batch a Jina.
6. Antes del transporte valida hash de página y fragmento y slice autorizado.
   Jina recibe solo texto del fragmento, modelo, tarea passage, dimensión y
   normalización; no PDF completo, usuarios ni conversaciones.
7. Valida modelo, cantidad/orden, 768 valores numéricos finitos, norma unitaria
   con tolerancia 0,01, límites de bytes y JSON estricto. No renormaliza ni repara.
   El checkpoint conserva hash/espacio; duplicado idéntico es idempotente,
   contradictorio se rechaza sin sobrescribir. Reanudación excluye confirmados.
8. Ante 401/402/403/429/5xx, timeout o fallo de integridad: detener sin reintento.
   Confirmar pendientes mediante lectura antes de otra ejecución autorizada.
   Un timeout puede consumir cuota sin checkpoint: no hay idempotencia de cobro
   garantizada, aunque sí persistencia idempotente. No cambiar modelo a mitad.
9. Validar exactamente 432 vectores con hashes, slices y norma. `validate` no
   publica. `activate` repite validación y publica puntero cloud en transacción
   bajo lock del documento. No cambia el UUID textual ni elimina Nomic.

El mutex CLI excluye trabajo en esta máquina; no garantiza coordinación entre
varias máquinas. Mantener un único operador y evitar escritores externos.

## 5. Configuración y comandos futuros NO ejecutados

Cambios necesarios, aún NO aplicados a .env:

```dotenv
EMBEDDING_PROVIDER=jina
EMBEDDING_MODEL=jina-embeddings-v3
EMBEDDING_DIMENSIONS=768
EMBEDDING_TIMEOUT_SECONDS=30
EMBEDDING_MAX_INPUT_BYTES=2048
EMBEDDING_MAX_RESPONSE_BYTES=65536
```

Conservar AGENT_LLM_PROVIDER=openrouter y
OPENROUTER_MODEL=dots-studio/dots-3-note-preview:free, AtlasCloud exclusivo,
data_collection=deny, precio máximo cero, sin fallback.
JINA_API_KEY y OPENROUTER_API_KEY se leen exclusivamente del entorno del proceso:
introducir mediante entrada privada en PowerShell y eliminar referencias al cerrar
la sesión; no setx, .env, argumentos, transcripciones ni impresión de configuración.
Las variables del proceso prevalecen sobre .env: comprobar valores efectivos sin
imprimir claves antes del futuro arranque.

```powershell
# NO EJECUTAR AHORA. Previamente: respaldo probado y autorizaciones de DDL/exportación.
Set-Location 'D:\Downloads\proyectos\api-usuarios-clean\backend'
$env:PGOPTIONS='-c lock_timeout=2000 -c statement_timeout=15000'
& '.\.venv\Scripts\python.exe' -B -m alembic -x allow-development=true upgrade 0006_cloud_embeddings
# Restaurar PGOPTIONS al valor anterior al concluir, incluso ante error.
# Solo tras autorizar exportación y configurar Jina; OWNER es ADMIN propietario verificado.
$ownerId='<UUID_ADMIN_PROPIETARIO_AUTORIZADO>'
$versionId='7cb4e79c-747d-574a-8abb-0ebcb2e07636'
& '.\.venv\Scripts\python.exe' -B -m app.presentation.cli.reindex_jina --action index --owner $ownerId --version $versionId --max-chunks 10
# Revisar cada lote antes del siguiente; no bucle/reintento automático.
& '.\.venv\Scripts\python.exe' -B -m app.presentation.cli.reindex_jina --action validate --owner $ownerId --version $versionId
# ACTIVACIÓN requiere aprobación separada después de revisar la validación.
& '.\.venv\Scripts\python.exe' -B -m app.presentation.cli.reindex_jina --action activate --owner $ownerId --version $versionId
```

Ejecutar módulos con el mecanismo existente de instalación/PYTHONPATH=src del
proyecto; verificar importación local antes del corte. Los placeholders son
deliberadamente no ejecutables. No inferir autorización por aparecer un comando.

El arranque operativo nuevo exige Jina+OpenRouter; con el default legacy Ollama
falla antes de construir clientes. No reiniciar el backend actual con expectativa
de RAG funcional hasta configurar y publicar. CloudPostgresRAG exige activo VALIDADA
en el espacio configurado, revalida ACL y no consulta un índice incompleto ni
retrocede a Nomic. Un fallo del primer corte implica indisponibilidad controlada,
no recuperación local automática. Preparar ventana y comunicar esa limitación.

## 6. Privacidad y consumo

Evidencia documental previa fechada en 10B, no consultada nuevamente en 10D:
[FAQ Jina](https://jina.ai/embeddings/) declara ausencia de entrenamiento con
entradas/salidas; [legal](https://jina.ai/legal/) permite almacenamiento necesario
para el servicio y remite a Elastic. No se verificó plazo exacto de retención de
esta cuenta ni acuerdo aplicable al plan gratuito. El
[DPA](https://www.elastic.co/pdf/v100623-0-elastic-customer-dpa.pdf) no demuestra
por sí solo un plazo universal para esta API. Éxito sintético no resuelve contrato.

El titular debe confirmar retención de textos/vectores/logs/backups, eliminación,
región/subprocesadores, autorización para exportar el reglamento y condiciones
educativas/no comerciales del plan. También saldo real, vencimiento y recarga
automática DESHABILITADA; no suponer facturación cero por anunciar tokens gratis.
No se accedió al panel ni se cambiaron sus políticas.

159.779 bytes sugieren 40.000–80.000 tokens con heurística 2–4 bytes/token; no es
tokenización Jina medida. Reservar inicialmente 200.000 tokens más consultas y
verificaciones; comparar con saldo real y consumo informado antes/después de cada
lote. Los 10M anunciados previamente son una oferta inicial por confirmar, no cuota
mensual garantizada. HTTP de saldo insuficiente se detiene, no compra ni recarga.
La discrepancia oficial previa de RPM/TPM no afecta el plan de un solo envío a la
vez; ante 429 detener sin esperar/reintentar automáticamente. No se entrenan ni
ajustan parámetros de modelos durante esta migración.

## 7. Aceptación y decisiones pendientes

Para cerrar el corte: respaldo restaurado y auditado; 0006 aplicada; 432 fragmentos
originales y 432 vectores Jina válidos en espacio exacto; cero hashes/slices
incorrectos y duplicados contradictorios; versión textual original y 864 vectores
históricos conservados. Comprobar reanudación sin repetir confirmados y rechazo de
publicación incompleta. Validar búsquedas de artículos 24 y 52, continuidad sin
mezclar artículos, respuesta Dots3 fundamentada/citas/páginas y abstención segura.
Probar ACL y aislamiento multiusuario y funcionamiento sin clientes/servidor Ollama.
Las pruebas semánticas y generación consumen API y necesitan autorización aparte;
después ejecutar los 15 escenarios existentes y registrar cobertura parcial RAG.

**GO:** planificación, auditoría READ ONLY y evidencia SQL sintética previa.
**NO-GO actual:** migración real, exportación, indexación y activación. Faltan
confirmaciones contractuales/cuenta, respaldo restaurable y autorizaciones
específicas de DDL, levantamiento del bloqueo documental, envío y publicación.
No se ejecutaron tests nuevos en 10D porque no hubo cambios de implementación.
Único archivo incorporado: este informe. No se modificaron .env, código, servicios,
bases, modelos, vectores, permisos o el bloqueo documental.
