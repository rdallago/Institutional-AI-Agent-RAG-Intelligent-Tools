# Sprint 10G.7 — Autorización documental CLI limitada

## Finalización: coordinador completo implementado

Se completó el código, no solo el informe. Se incorporaron además:

- backend/src/app/presentation/cli/index_jina_all.py: coordinación secuencial
  mediante el CLI oficial en subprocesos, sin cambiar su límite de diez.
- backend/tests/rag/test_jina_all_coordinator.py: regresiones de coordinación.
- test_document_export_scope.py: límite efectivo de diez fragmentos distintos.

El coordinador consulta PostgreSQL READ ONLY antes/después de cada lote: destino,
revisión, versión/propietario ADMIN, 432 fragmentos, conteo histórico 864, cero
activos y checkpoints del fingerprint indicado con hash/dimensión/finitud/norma.
No genera vectores por sí mismo. Cada subproceso CLI recibe la clave únicamente
por entorno heredado, nunca por argumentos/archivos; el coordinador no imprime
stdout/stderr del hijo, cuerpos HTTP, vectores o secretos. Los fallos se presentan
de forma genérica con salida 2. El subproceso tiene timeout de 660 s; si expira,
se detiene la batería y se revisa el resultado incierto sin reenviar automáticamente.

Procesa min(10, pendientes), exige exactamente ese incremento confirmado y luego
continúa. Desde cero son 43 lotes de diez y uno de dos. Desde 1, 10 o 431
confirmados recalcula automáticamente los pendientes; con 432 no ejecuta hijos.
Un error HTTP/timeout/SQL del CLI o avance inesperado detiene inmediatamente.
No marca VALIDADA ni activa, y no invoca OpenRouter/Ollama. La guarda de recursos
del adaptador se conserva para cada llamada. No se impone un rate limiter nuevo:
429 detiene sin reintento; la cuota debe estar confirmada antes de ejecutar.

### Comando definitivo preparado (NO ejecutado)

Desde la terminal privada donde el usuario ya cargó JINA_API_KEY, **solo después
de autorización expresa de llamadas/escrituras y confirmaciones de cuenta**:

```powershell
Set-Location 'D:\Downloads\proyectos\api-usuarios-clean\backend'
$env:PYTHONPATH=(Join-Path (Get-Location) 'src')
& '.\.venv\Scripts\python.exe' -B -m app.presentation.cli.index_jina_all --execute --approve-document-export --confirm-free-usage --confirm-data-policy
if ($LASTEXITCODE -ne 0) { throw 'Detenido: revisar checkpoints y llamadas inciertas; no reenviar automáticamente' }
```

Este comando sustituye el bucle interactivo histórico de abajo y no pide
confirmación por cada lote. El entrypoint autorizado sigue siendo reindex_jina
para cada envío: el coordinador no puede emitir una capacidad por sí mismo.
No se comprueba aquí la clave del proceso Codex porque no es necesaria para mocks.

### Reanudación

Interrumpir con Ctrl+C detiene la coordinación; puede haber un checkpoint o una
llamada remota en curso. Tras revisar ese estado READ ONLY y obtener permiso para
continuar, ejecutar el mismo comando: solo procesa faltantes confirmados por la
base. No hay checkpoint de inferencia remoto ni garantía de facturación idempotente;
si una llamada falló después de ser recibida por Jina, puede consumir tokens aunque
no exista su checkpoint SQL. Nunca relanzar automáticamente ante ese caso.

### Pruebas finales

Ejecutada la batería siguiente desde backend:

```powershell
& '.\.venv\Scripts\python.exe' -B -m pytest tests/rag/test_jina_all_coordinator.py tests/rag/test_document_export_scope.py tests/rag/test_jina_pilot_preparation.py tests/rag/test_jina_cloud.py tests/rag/test_jina_10c_storage.py tests/rag/test_jina_passage_errors.py tests/rag/test_jina_10b_audit.py tests/ia/test_dots_openrouter.py -q -p no:cacheprovider --basetemp=.pytest-tmp-10g7-complete --tb=short
```

Resultado: **141 aprobadas, 0 fallidas, 18,23 s**, advertencia Starlette/HTTPX.
Después se añadió y ejecutó aisladamente la regresión de diez fragmentos distintos
con rechazo del undécimo: **1 aprobada en 1,61 s**. No se suman repeticiones de tests.
No hubo servicios, SQL real, consumo de créditos o llamadas externas en las pruebas.
La conservación histórica se cubre mediante separación de repositorios/SQL y
ausencia de rutas de escritura Nomic; no se afirma haber vuelto a auditar datos
reales durante esta intervención. Los tests de coordinación usan progreso y CLI
simulados: no son indexación real ni prueba de latencia cloud.

**Estado final: técnicamente preparado para solicitar UNA autorización de ejecución
de los pendientes hasta completar 432, sin activación.** Persisten confirmaciones
de uso gratuito/retención/derechos antes de utilizar los flags; estos registran
declaraciones del operador, no verifican automáticamente saldo o contrato remoto.
No se envió ningún documento ni se escribió ningún embedding en usuarios_dev.
Los apartados inferiores conservan el diseño y las pruebas previas como antecedente.

10 de noviembre de 2026. **IMPLEMENTADA y verificada con mocks. NO EJECUTADA
contra Jina o PostgreSQL.** No se concedió autorización operativa de exportación.

## Diseño y alcance

DOCUMENT_EXPORT_APPROVED=False permanece intacto y ya no constituye un mecanismo
de aprobación global para el adaptador. El método público embed_document operativo
niega llamadas sin una capacidad DocumentExportPermit emitida para el proceso CLI.
FastAPI no recibe esa capacidad ni una variable de entorno que pueda reutilizar.
El flujo retrieval.query no cambia; este permiso solo cubre retrieval.passage.

Identidades fijas autorizables:

- Documento: 8ac0c745-1307-5bb4-9d56-93dfbee0b3b8.
- Versión: 7cb4e79c-747d-574a-8abb-0ebcb2e07636.
- Propietario: 32eabde4-7d17-4029-a47a-60e2e38faf05.
- Espacio: 1f0482094b5531fc5d3406985eb3ba0ec870af28871c4b2b7c4c6f12b6c37ed1.

El emisor exige el módulo __main__.__spec__.name de reindex_jina, las identidades
anteriores y un manifiesto de exactamente 432 UUID/hash. export_manifest obtiene
las filas mediante SQL de lectura filtrado por documento/versión activa LISTA,
relación versión-documento y propietario ADMIN activo, documento no archivado.
Verifica 432 elementos únicos, SHA-256 de cada texto/página y offsets/slices.
El CLI vuelve a leer/comparar el manifiesto y ACL antes de cada envío. Checkpoint
conserva su guard, validación transaccional, PK y control de contradicciones originales.

La capacidad queda ligada al adaptador concreto, PID, tarea asyncio y manifiesto
inmutable de hashes. Caduca a los diez minutos, admite solo 1–10 envíos y prohíbe
reutilizar un fragmento. Se consume antes de HTTP: un resultado incierto no permite
reenviar usando el mismo permiso. Se revoca en finally y no se guarda ni se pasa
por entorno. Cambiar texto, ID, espacio, proceso, tarea o adaptador causa denegación.

Esto protege los recorridos previstos, **no es un sandbox contra código Python
malicioso dentro del mismo intérprete** ni una firma emitida por un sistema externo.
No promete impedir a un administrador del equipo modificar el programa. El rol
DB/ACL y el permiso operativo del usuario siguen siendo requisitos independientes.
Existe una ventana inevitable entre lectura de ACL y envío remoto; no se mantienen
locks SQL durante HTTP. Una revocación posterior no puede retirar texto ya enviado;
el checkpoint vuelve a validar antes de persistir y se detiene si cambió el permiso.

## Requisitos de invocación y denegación por defecto

Solo action=index admite esta autorización. Exige conjuntamente:

- --approve-document-export: autorización externa previa del envío y escrituras.
- --confirm-free-usage: el operador confirmó cuota/condiciones sin cargos.
- --confirm-data-policy: el operador confirmó derechos y tratamiento de datos.
- Owner/version exactos, max-chunks entero entre 1 y 10, destino dev exacto,
  proveedor Jina/fingerprint correcto, clave no vacía y revisión 0006.

Sin alguno de ellos se rechaza antes del engine o de HTTP, según la etapa. Los
flags no inspeccionan saldo, no validan contratos ni garantizan ausencia de cargos:
son confirmaciones explícitas del operador y NO deben usarse sin verificar esas
condiciones. No hay clave nueva, exportación habilitada por .env o permiso automático.

action=validate y action=activate permanecen denegadas en esta CLI aun con los
tres flags: el permiso de exportación no autoriza sus escrituras. Se conservan los
métodos de repositorio, pero habilitar su operación futura requiere autorización
y un control separado. El help conserva los nombres de acciones históricas;
seleccionarlas no salta el guard. No habrá publicación automática al completar 432.

## Archivos modificados

1. backend/src/app/infrastructure/rag/document_export.py: nuevo emisor/capacidad.
2. backend/src/app/infrastructure/rag/jina.py: capacidad requerida para documentos
   operativos; consulta y validación HTTP/vector intactas.
3. backend/src/app/infrastructure/rag/cloud_postgres.py: lectura de manifiesto con
   identidad, ACL y hashes; no se cambió esquema/checkpoint/publicación.
4. backend/src/app/presentation/cli/reindex_jina.py: flags, scope, manifiesto y
   revocación; limpieza de engine/mutex incluso ante fallo de cierre del cliente.
5. backend/tests/rag/test_document_export_scope.py: nuevas regresiones de seguridad.
6. backend/tests/rag/test_jina_pilot_preparation.py: piloto sintético adaptado al
   permiso real, sin activar la bandera global.
7. docs/jina-cloud-10g-7.md: este informe.

No se modificaron .env, credenciales, FastAPI, React, historial, migraciones, datos
o embeddings. No se ejecutó SQL, APIs externas, Ollama o reinicios en esta intervención.

## Pruebas automatizadas

```powershell
Set-Location 'D:\Downloads\proyectos\api-usuarios-clean\backend'
& '.\.venv\Scripts\python.exe' -B -m pytest tests/rag/test_document_export_scope.py tests/rag/test_jina_pilot_preparation.py tests/rag/test_jina_cloud.py tests/rag/test_jina_10c_storage.py tests/rag/test_jina_passage_errors.py tests/rag/test_jina_10b_audit.py tests/ia/test_dots_openrouter.py -q -p no:cacheprovider --basetemp=.pytest-tmp-10g7-final --tb=short
```

**123 aprobadas, 0 fallidas, 7,19 s**, advertencia Starlette/HTTPX.
Primer intento desde raíz tuvo error de importación de tests; desde backend se
detectó un AttributeError por args vacíos, corregido a denegación controlada.
La ejecución final anterior es el resultado válido; no se suman repeticiones.

Cobertura: piloto CLI real con adaptador MockTransport y checkpoint en memoria,
una llamada y parada ante 401/402/403/429/500/timeout/SQL; manifiesto completo y
alterado; IDs/scope/owner incorrectos; token vencido/cerrado/repetido, PID/tarea/
adaptador distintos; emisión fuera del CLI; falta de confirmaciones/clave o espacio
incorrecto antes de engine; activación/validación denegadas; índice 1/432 rechazado;
composición sin Ollama y separación histórica. El modo testing del adaptador sigue
exigiendo MockTransport. Los tests sustituyen la comprobación del entrypoint para
simular el CLI, nunca se aplica esa sustitución a ejecución operativa.

No es aceptación real de la API ni de commits en usuarios_dev. El ensayo SQL previo
de 10C conserva su alcance; no se repitió y no se tocaron bases de prueba.

## Comandos preparados — NO ejecutar sin autorización posterior

Primero cargar JINA_API_KEY solo en memoria privada conforme a 10G.2; comprobar
presencia booleana. No escribirla en .env, argumentos, chat, setx o logs. No necesita
OPENROUTER_API_KEY: este indexador no invoca generación. Revalidar versión/owner,
fingerprint, pendientes, recursos, backup y exclusión de otros indexadores antes.

Una invocación limitada a diez pendientes:

```powershell
Set-Location 'D:\Downloads\proyectos\api-usuarios-clean\backend'
$env:PYTHONPATH=(Join-Path (Get-Location) 'src')
& '.\.venv\Scripts\python.exe' -B -m app.presentation.cli.reindex_jina --action index --owner '32eabde4-7d17-4029-a47a-60e2e38faf05' --version '7cb4e79c-747d-574a-8abb-0ebcb2e07636' --max-chunks 10 --approve-document-export --confirm-free-usage --confirm-data-policy
if ($LASTEXITCODE -ne 0) { throw 'Detenido: revisar checkpoints; no reintentar' }
```

Para un piloto inicial, reemplazar max-chunks por 1, solo si ese es el alcance
autorizado. Para 432 pendientes confirmados y autorización global, la secuencia
es de 43 invocaciones de diez y una de dos. Cada fragmento implica UN POST.
Ejemplo de coordinación, preparado pero NO ejecutado:

```powershell
# Solo desde backend, después de confirmar EXACTAMENTE 432 pendientes y autorización.
foreach ($batchLimit in ((@(10) * 43) + @(2))) {
    & '.\.venv\Scripts\python.exe' -B -m app.presentation.cli.reindex_jina --action index --owner '32eabde4-7d17-4029-a47a-60e2e38faf05' --version '7cb4e79c-747d-574a-8abb-0ebcb2e07636' --max-chunks $batchLimit --approve-document-export --confirm-free-usage --confirm-data-policy
    if ($LASTEXITCODE -ne 0) { throw 'Parada segura: no reenviar llamadas inciertas' }
    # Revisar progreso y cuota antes de iniciar otro lote.
    Read-Host 'Revisá checkpoint/cuota; Enter continúa, Ctrl+C detiene'
}
```

La pausa es control del operador, no una solicitud de autorización nueva por lote.
Si se autoriza una coordinación no interactiva, el ejecutor debe verificar progreso
y cuota entre lotes y detenerse ante errores, no limitarse a ignorar ExitCode.
Al reanudar, recalcular pendientes; no usar el ejemplo fijo de 432 si ya hubo piloto.
La CLI solo envía faltantes, pero no garantiza idempotencia de facturación remota.
No reintentar automáticamente tras timeout o resultado incierto.

## Pendientes para ejecución real

1. Autorización expresa del usuario de llamadas y escrituras para esta versión,
   alcance total o piloto. No se interpreta este sprint de código como ese permiso.
2. Clave disponible en proceso ejecutor; no se verificó/solicitó su valor aquí.
3. Confirmar saldo vigente, uso educativo/comercial permitido, retención aceptada,
   derechos de exportación y ausencia de cargos/recargas para la cuenta. Declaración
   previa de créditos y ningún medio de pago no se convierte en garantía del cliente.
4. Preflight READ ONLY actual de checkpoints y recursos antes del futuro envío.

**GO técnico del control limitado. NO-GO para ejecutar llamadas/escrituras ahora.**
No se activa el índice; validación final/publicación y posterior prueba React siguen
siendo operaciones separadas. La denegación global permanece por defecto y la
capacidad solo existe durante una invocación CLI explícitamente aprobada.
