# Sprint 10C — PostgreSQL/pgvector y ruta cloud

Fecha: **9 de noviembre de 2026**, America/Buenos_Aires.
**Ensayo PostgreSQL desechable APROBADO.** Se mantiene **NO-GO para migración
real, reindexación y activación operativa**, pendientes de autorización y privacidad.

## 1. Resumen ejecutivo

PostgreSQL y pgvector están disponibles y el tipo histórico es compatible con
768 dimensiones. No se aplicó SQL de escritura a ninguna base existente.
Se corrigió la posibilidad de construir embeddings locales por configuración
legacy: el RAG operativo debe seleccionar Jina + OpenRouter o falla antes de
crear clientes. No se seleccionó Jina automáticamente ni se modificó `.env`.

El ensayo SQL cloud se preparó para una base NUEVA, vacía y explícitamente
autorizada. Ya no utiliza usuarios_test ni su fixture con migraciones automáticas.
En la preparación no existía tal base y se omitió el ensayo. Tras la autorización
posterior se creó UNA base y el ensayo real aprobó; resultados en la sección 9.

## 2. Arquitectura definitiva y estado efectivo

Flujo previsto tras publicación autorizada:

```text
React → FastAPI → Jina retrieval.query → PostgreSQL/pgvector (espacio Jina)
      → Dots3-Note/OpenRouter → FastAPI → React
```

Documentos: Jina retrieval.passage, 768 dimensiones. Consultas: retrieval.query.
Las pruebas sintéticas reales de ambas tareas son evidencia comunicada por el
usuario; passage: HTTP 200, valid=true, finite=true, norm=1, 1,714 s.
No se repitieron. No equivalen a aceptación de los 432 fragmentos.

Estado de configuración de un proceso nuevo observado en lectura:

- LLM: openrouter, dots-studio/dots-3-note-preview:free.
- Embeddings: todavía ollama por la configuración/default existente.
- El campo model de EmbeddingConfig contiene jina-embeddings-v3 incluso cuando
  provider=ollama: no confundir ese campo con selección operativa cloud.

**Con el nuevo control, esa combinación se rechaza al arrancar RAG operativo.**
El backend ya ejecutándose no fue reiniciado y no cambia por este ajuste en disco.
Antes del futuro reinicio se deberá autorizar la configuración Jina y completar
la preparación/publicación. No ejecutar un reinicio ahora esperando un RAG usable.

Históricos: no se borraron clases/helpers Ollama ni Nomic; importarlos para parsers,
constantes históricas o herencia no inicia procesos ni ejecuta modelos. En modo
Jina no se construye Embeddings local, no se consulta /api/ps ni /api/tags y no
hay fallback local. El gate compartido usado por reindex_jina es exclusión de
trabajo mediante archivo, no cliente Ollama ni protección RAM para pesos locales.

## 3. Comprobación previa de solo lectura (antes del ensayo)

Conexión exclusivamente a usuarios_dev/127.0.0.1:5434, forzada con
default_transaction_read_only=on, connect_timeout=3 y statement_timeout=3000.
Se verificó SHOW transaction_read_only y se terminó con rollback.

| Metadato | Resultado |
|---|---|
| PostgreSQL | 18.6 |
| pgvector | 0.8.2 |
| Columna histórica rag_embeddings.embedding | vector(768) |
| Revisión aplicada | 0005_agent_memory |
| Tablas rag_cloud_* | 0 |
| Bases candidatas con patrón dedicado | Ninguna |
| JINA_TEST_DATABASE en el proceso | No configurada |

No se inspeccionaron credenciales, mensajes, usuarios privados o vectores completos.
No se volvió a auditar el conteo/integridad de los 432 vectores: se conservan sin
operaciones de escritura. La inspección fue de metadatos, no prueba de inserción.
No se accedió a usuarios_test ni se usó como entorno de ensayo.

## 4. Auditoría del almacenamiento y migración

Grafo en disco: 0006_cloud_embeddings → 0005_agent_memory → 0004_rag; una cabeza.
0006 sigue preparada y NO aplicada. Sus cuatro tablas paralelas preservan las
restricciones y datos Nomic sin ALTER/DROP/UPDATE de objetos históricos.

| Aspecto | Comprobado estáticamente/con mocks | Pendiente de SQL desechable |
|---|---|---|
| vector(768) | Mismo tipo/dimensión del esquema histórico, validación de finitud/norma en aplicación | Inserción y lectura cloud |
| Relaciones | FK a fragmentos, espacios y versiones; activo referencia pareja versión/espacio de ingesta | Rechazos FK/PK por PostgreSQL |
| Separación | Fingerprint distinto, tablas cloud independientes y filtros por espacio antes del top-k | Comparar búsqueda con vectores históricos sintéticos distintos |
| Documento/versiones | Reutiliza fragmentos y offsets, conserva activa_version_id documental | Confirmar asociación y puntero original después de publicar |
| Duplicados | PK(fragmento,espacio), ON CONFLICT sin sobrescritura; compara vector/hash | Idempotencia real y rechazo de vector contradictorio |
| Publicación | Valida 432 filas, hashes, slices, finitud y norma bajo lock y misma transacción del puntero cloud | Commit/rollback reales |
| Reanudación | missing_cloud excluye checkpoints del mismo espacio | Cerrar pool, reabrir conexión y continuar desde checkpoint confirmado |
| ACL | Reutiliza filtros del repositorio y revalida activo antes/después de buscar | Usuario ajeno, incluso ADMIN, rechazado |

Límite declarativo: la FK del puntero asegura que existe la pareja de ingesta,
pero no que su estado sea VALIDADA. Esa condición y la completitud las impone
la aplicación. Las escrituras administrativas directas podrían eludirla y no
forman parte del procedimiento autorizado. No afirmar que el DDL por sí solo
demuestra que existen 432 embeddings íntegros.

La revisión no modifica 0006. Falta probarla realmente antes de aplicar a desarrollo.
Downgrade rechaza borrar datos; no existe rollback cloud automático ni fallback.
Volver por configuración a Nomic ya no es el camino operativo admitido por este
sprint: cualquier recuperación extraordinaria requeriría revisión y autorización
de código/configuración. Conservar vectores históricos no significa utilizarlos.

## 5. Diseño del ensayo SQL aislado

Se sustituyó la fixture antigua del test cloud. El nuevo soporte exige:

1. Base creada por separado, nueva y vacía, nombre rag_jina_10c_<32 hex>.
2. JINA_TEST_DATABASE y JINA_TEST_ALLOW_SCHEMA con el mismo nombre.
3. Host literal 127.0.0.1 y credenciales solo del proceso.
4. Coincidencia de current_database(), pgvector 0.8.2 previamente instalado en
   public y ausencia de tablas/vistas/secuencias/foreign tables de aplicación en public.
5. --run-postgres explícito para recolectar ese test como ejecutable.

Nombres usuarios_dev, usuarios_test, postgres y nombres fuera del patrón se
rechazan ANTES de construir motor o enviar SQL. Sin autorización, no hay conexión.
No crea bases ni extensiones, no trunca tablas ni elimina datos, no ejecuta DROP.
Una base no vacía se rechaza, aunque tenga el nombre autorizado. El nombre UUID
y la comprobación de vacío son barreras, no sustituyen la autorización del operador.

En el entorno desechable autorizado, el soporte construye el esquema de las revisiones
0001–0006 mediante Alembic Operations dentro de una transacción; no ejecuta env.py
ni usa la configuración de usuarios_test. Comprueba DDL real, pero no registra una
tabla alembic_version ni simula una migración aplicada a usuarios_dev.
Conserva la base al finalizar para inspección: no hay limpieza destructiva automática.

El test crea únicamente documentos/usuarios/vectores sintéticos dentro de esa base.
Los checkpoints usan transacciones reales del repositorio y sobreviven al cierre
del pool. Incluye cosenos 1/0, dimensión errónea, NaN/Infinity, PK/FK, reintento
idempotente, conflicto sin sobrescritura, publicación incompleta rechazada, ACL y
conservación de un vector Nomic sintético. No llama Jina/Ollama/OpenRouter.

No ejecutar otros tests PostgreSQL con --run-postgres: sus fixtures históricas
siguen dirigidas a usuarios_test, fuera de la autorización de este sprint.

## 6. Pruebas locales ejecutadas durante la preparación

Resultado final: **185 aprobadas, 1 omitida**, 10,14 s, aviso previo Starlette/TestClient.
La omitida en esa ejecución era el ensayo PostgreSQL real, ejecutado posteriormente
según sección 9. No se suman repeticiones anteriores.

Cobertura ejecutada:

- Rechazo de bases existentes/no autorizadas y destinos no vacíos antes de DDL.
- Lifespan FastAPI con Jina y fallo si se construyen embeddings Ollama.
- Rechazo temprano de OpenRouter+embeddings Ollama y Jina+LLM Ollama, sin runtimes.
- Query/passage con MockTransport, errores y secretos, JSON/vector inválido.
- Separación de SQL Nomic/Jina, ACL, validación y publicación con mocks.
- Esquemas/routing Dots3-Note y ausencia de fallback.
- Cliente de aceptación cloud sin solicitudes de estado a Ollama.
- Grafo Alembic y DDL aditivo inspeccionados sin base real.

Comando reproducible sin servicios:

```powershell
Set-Location 'D:\Downloads\proyectos\api-usuarios-clean\backend'
& '.\.venv\Scripts\python.exe' -B -m pytest tests/rag/test_jina_10c_storage.py tests/rag/test_jina_cloud.py tests/rag/test_jina_10b_audit.py tests/rag/test_jina_passage_errors.py tests/ia/test_dots_openrouter.py tests/ia/test_openrouter.py tests/ia/test_ia_lifespan.py tests/ia/test_local_llm_launcher.py tests/acceptance/test_local_client.py tests/integration/postgresql/test_cloud_embeddings.py -k 'not native' -q -p no:cacheprovider --basetemp=.pytest-tmp-jina-10c-final --tb=short
```

Los tres fallos documentados en 10B no se corrigieron ni se repitió toda la regresión:
esta cifra no significa que toda la suite del repositorio esté aprobada.

## 7. Archivos modificados/incorporados en 10C

- backend/src/app/bootstrap.py: requisito cloud operativo antes de crear runtimes.
- backend/tests/integration/postgresql/test_cloud_embeddings.py: sustituye usuarios_test
  por base nueva autorizada; commits/checkpoints reales y casos de almacenamiento.
- backend/tests/jina_disposable_support.py: nuevo soporte con barreras previas.
- backend/tests/rag/test_jina_10c_storage.py: nuevas pruebas locales de seguridad/composición.
- docs/jina-cloud-10c.md: este informe.

No se modificaron .env, adaptador Jina, DOCUMENT_EXPORT_APPROVED=False,
Dots3-Note, migración 0006, permisos, modelos, credenciales o datos existentes.
No se reiniciaron servicios ni se ejecutaron inferencias o las 15 E2E.

## 8. Próximos pasos y autorización requerida

**NO-GO para migración real.** El motor existente dispone de pgvector y vector(768),
 y el ensayo sintético de tablas cloud/transacciones ya aprobó en la base desechable.
Persisten las condiciones pendientes de privacidad/cuenta de 10B; el éxito de
passage sintético no autoriza exportar el reglamento. El alias Jina no está fijado
a un digest inmutable verificado y requiere control operativo de cambios.

La creación de UNA base desechable y la instalación de pgvector fueron autorizadas
y ejecutadas posteriormente. No crear otra ni repetir el ensayo automáticamente.
Se conserva la base para inspección; no se autoriza borrarla.

Plantilla histórica de ejecución (NO repetir sobre la base conservada: no está vacía):

```powershell
$env:JINA_TEST_DATABASE='rag_jina_10c_<UUID32_AUTORIZADO>'
$env:JINA_TEST_ALLOW_SCHEMA=$env:JINA_TEST_DATABASE
$env:JINA_TEST_HOST='127.0.0.1'
$env:JINA_TEST_PORT='5434'
$env:JINA_TEST_USER='<ROL_AUTORIZADO>'
# Introducir JINA_TEST_PASSWORD mediante Read-Host -AsSecureString y pasar solo
# a la memoria de este proceso; nunca argumentos, archivos, chat o setx.
Set-Location 'D:\Downloads\proyectos\api-usuarios-clean\backend'
& '.\.venv\Scripts\python.exe' -B -m pytest tests/integration/postgresql/test_cloud_embeddings.py --run-postgres -q -p no:cacheprovider --tb=short
```

El placeholder no es un nombre ejecutable válido. No iniciar el comando hasta
autorizar expresamente la creación del esquema y datos sintéticos en esa base.
No aplicar 0006 a desarrollo hasta revisar el resultado real. Reindexación de
432 fragmentos, publicación y configuración operativa necesitan autorizaciones
posteriores separadas. No se avanza automáticamente aunque el ensayo SQL apruebe.

## 9. Ejecución real autorizada — resultado final

**9 de noviembre de 2026. APROBADO: 1 prueba, 0 fallidas, 0 omitidas.**

Antes de crear se comprobó el servidor mediante conexión de metadatos a la base
de mantenimiento postgres: PostgreSQL 18.6, credencial existente con CREATEDB y
superusuario, extensión vector 0.8.2 disponible. No fue necesaria otra credencial.
No se crearon usuarios/roles del servidor ni se modificaron permisos de cuentas.

Se generó y comprobó un nombre UUID inexistente; se creó exclusivamente:

`rag_jina_10c_2f38fd284c20454eb9acadf1def9205f`

Base UTF-8 desde template0, propiedad del rol existente. Antes de cualquier DDL
de aplicación se comprobó current_database y vacío; se habilitó vector 0.8.2
únicamente en esta base. El soporte volvió a comprobar las barreras de destino.

Se ejecutó exclusivamente:

```text
backend/.venv/Scripts/python.exe -B -m pytest tests/integration/postgresql/test_cloud_embeddings.py --run-postgres -q -p no:cacheprovider --basetemp=<directorio temporal único> --tb=short
```

JINA_TEST_* y la credencial estuvieron solo en el entorno temporal del proceso
de prueba, sin argumentos con secretos, archivos de credenciales o cambios `.env`.
Salida real: **1 passed in 15.75s**, exit code 0. Duración global de creación,
extensión y ejecución: **19,325 segundos**. No hubo reintentos ni correcciones
durante el ensayo. La base se conservó; no se ejecutó DROP ni limpieza posterior.

El único test incluye estas comprobaciones reales (no se cuentan como tests separados):

- Construcción transaccional del DDL 0001–0006 en destino vacío mediante Alembic
  Operations; no env.py ni migración de bases existentes.
- Inserción de 432 fragmentos sintéticos y vectores cloud de 768 dimensiones.
- Checkpoint confirmado e idempotente; cierre de pool y reanudación con 431 pendientes.
- Rechazo y rollback de un checkpoint contradictorio, sin sobrescribir el previo.
- Rechazo SQL de dimensión incorrecta, NaN, Infinity, PK duplicada y FK inexistente.
- Publicación incompleta rechazada, sin puntero activo.
- Validación completa y publicación sintética dentro de la base desechable.
- Búsqueda por coseno: primer resultado 1, siguiente 0, identidad de fragmento correcta.
- ACL: ADMIN ajeno sin permiso rechazado.
- Puntero textual original y vector histórico Nomic sintético conservados.

Verificación posterior en READ ONLY exclusivamente sobre la base desechable:

| Comprobación | Cantidad |
|---|---:|
| Fragmentos sintéticos | 432 |
| Vectores cloud sintéticos | 432 |
| Vectores históricos sintéticos | 1 |
| Ingestas cloud VALIDADA | 1 |
| Punteros cloud sintéticos activos | 1 |
| Vectores cloud con dimensión 768 y norma válida | 432 |

El puntero activo anterior es exclusivamente de prueba; **no se activó el RAG
del reglamento ni ningún espacio en usuarios_dev**. Los vectores son sintéticos:
no se realizaron llamadas a Jina/OpenRouter/Ollama ni se generaron embeddings reales.

En esta ejecución las conexiones SQL fueron únicamente a postgres (administración)
y a la base nueva. No hubo conexiones a usuarios_dev/usuarios_test para ejecutar
el ensayo ni modificaciones en ellas. No se volvió a auditar su integridad:
la conservación se sustenta en no haber dirigido escrituras a esos destinos.

Único archivo del proyecto actualizado en esta ejecución: este informe (además de
artefactos temporales de pytest). No se modificó implementación o migraciones.

**Decisión actual:** validación SQL aislada superada; **NO-GO para migración real**
hasta resolver privacidad/cuenta, revisar el corte y obtener las autorizaciones
correspondientes para DDL en desarrollo, exportación del reglamento y publicación.
No se avanzó a ninguna de esas operaciones.
