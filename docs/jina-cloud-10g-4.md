# Sprint 10G.4 — Piloto Jina preparado sin consumo real

10 de noviembre de 2026. **GO técnico de preparación; NO-GO para ejecutar el
envío mientras no se autorice y resuelvan las condiciones pendientes.**
Se revisaron 10G.1–10G.3, adaptador Jina, configuración, CloudPostgresRAG y CLI.

## 1. Preflight READ ONLY real

Conexión al destino exacto usuarios_dev/127.0.0.1:5434, connect_timeout=10,
default_transaction_read_only=on, statement_timeout=10000 y rollback. Se comprobó
transaction_read_only mediante la función pura de auditoría 10E, extraída por AST
sin ejecutar su operación de respaldo. No hubo escrituras.

- Revisión 0006_cloud_embeddings; cuatro tablas cloud presentes y vacías.
- 864 fragmentos y 864 embeddings históricos íntegros: hashes de páginas,
  fragmentos y entradas coincidentes, offsets/slices exactos y 768 componentes
  finitos de norma positiva. No se imprimió contenido ni vectores.
- Dos versiones LISTA, 72 páginas y 432 fragmentos cada una.
- Versión activa: 7cb4e79c-747d-574a-8abb-0ebcb2e07636.
- Versión anterior: 9cab30cd-9554-5679-a2d9-35d85dd5ab85.
- Propietario real consultado únicamente por UUID, activo y rol:
  32eabde4-7d17-4029-a47a-60e2e38faf05, ADMIN activo, propietario del documento.
  Revalidar esa condición antes de la operación futura; no es una credencial.
- Fingerprint Jina: 1f0482094b5531fc5d3406985eb3ba0ec870af28871c4b2b7c4c6f12b6c37ed1.
  UUID del espacio derivado: 1f048209-4b55-31fc-5d34-06985eb3ba0e.
  Modelo jina-embeddings-v3, dimensión 768, passage para documento/query para pregunta.

## 2. Simulación local del piloto

Se incorporó backend/tests/rag/test_jina_pilot_preparation.py. Ejecuta run de la
CLI real con adaptador Jina real y HTTPX MockTransport, motor/repositorio simulados
y texto inventado fijo. La persistencia/checkpoint del piloto se simula en memoria;
no se afirma que esa prueba haya confirmado un commit PostgreSQL real. La prueba
SQL sintética real de 10C ya cubrió commits/reanudación en base separada y no se repitió.

Prueba positiva: un único embedding normalizado de 768 dimensiones con tarea
retrieval.passage y un checkpoint que registra fragmento, espacio y hash. No activa.
Casos negativos CLI: 401, 402, 403, 429, 500, timeout y fallo SQL. Cada caso hace
una sola llamada simulada, no confirma un checkpoint y libera recursos; no hay
reintento ni segunda solicitud. El fallo SQL ocurre después de recibir el vector,
por lo que en una ejecución real podría haberse consumido cuota sin checkpoint.

Otra regresión usa validate_cloud/activate reales con motor simulado y una fila
de 432: ambos rechazan antes de actualizar VALIDADA o escribir un puntero.
Se reutilizaron tests existentes de modelo/dimensión/NaN/bool/norma/índice/cantidad,
JSON duplicado/truncado/límite, separación Nomic/Jina, idempotencia/publicación
y bloqueo documental. Se prohíbe crear transporte HTTP real y constructor embeddings
Ollama en la simulación CLI. No hay sockets, documentos reales o SQL de escritura.

Únicamente dentro del test se sustituye la bandera importada de la CLI para poder
recorrer el código con dobles aislados; el adaptador usa testing=True y MockTransport.
No se modifica la constante productiva ni se propone ese mecanismo para ejecutar
el piloto real. El test existente comprueba que la bandera real bloquea antes de SQL.

```powershell
Set-Location 'D:\Downloads\proyectos\api-usuarios-clean\backend'
& '.\.venv\Scripts\python.exe' -B -m pytest tests/rag/test_jina_pilot_preparation.py tests/rag/test_jina_cloud.py tests/rag/test_jina_passage_errors.py -q -p no:cacheprovider --basetemp=.pytest-tmp-10g4 --tb=short
```

**60 aprobadas, 0 fallidas, 8,17 s**, advertencia previa Starlette/HTTPX.
No sumar esta ejecución a cifras anteriores ni declararla aceptación real cloud.

## 3. Comando real preparado — NO EJECUTADO

Requiere permiso explícito para exportar UN fragmento público, consumir su cuota y
crear espacio/ingesta PREPARANDO y un checkpoint en usuarios_dev. Requiere además
autorizar un cambio revisable de DOCUMENT_EXPORT_APPROVED=False; hoy sigue False
y la CLI bloqueará cualquier acción. No hay flag/env de bypass. No usar monkeypatch
operativo, transporte privado ni SQL manual para eludirlo.

La autorización futura debe acotar la ejecución a max-chunks=1, propietario/versión
indicados y cero activación. La constante es global para embed_document: levantarla
no restringe por sí mismo el permiso a un fragmento. Aplicar el cambio únicamente
tras aprobación, no ejecutar otros indexadores y prever restaurar el bloqueo al
concluir el piloto. Revisar ambas importaciones (adaptador y CLI) en proceso nuevo.

```powershell
# NO EJECUTAR AHORA: sin autorización de exportación/escritura y gate aprobado.
Set-Location 'D:\Downloads\proyectos\api-usuarios-clean\backend'
$env:PYTHONPATH=(Join-Path (Get-Location) 'src')
& '.\.venv\Scripts\python.exe' -B -m app.presentation.cli.reindex_jina --action index --owner '32eabde4-7d17-4029-a47a-60e2e38faf05' --version '7cb4e79c-747d-574a-8abb-0ebcb2e07636' --max-chunks 1
```

La CLI selecciona el primer fragmento pendiente por ordinal. No admite pasar un
fragmento arbitrario: identificar su UUID/hash/ordinal mediante READ ONLY antes de
aprobar el piloto. No imprimir texto en informes. Revalidar fingerprints, 432 pendientes,
base/revisión/owner, RAM y exclusión local. Conserva límites existentes: 2048 bytes
entrada, 65536 respuesta, timeout global 30 s/connect 3 s, sin redirects/retries,
norma unitaria tolerancia 0,01 y guarda cloud 0,25 GiB. No cambiar esos parámetros.

## 4. Carga privada de clave y condiciones de cuenta

PowerShell sin transcripción, clave solo en memoria de esa terminal y sus hijos:

```powershell
$jinaSecure=Read-Host 'JINA_API_KEY' -AsSecureString
$jinaPtr=[Runtime.InteropServices.Marshal]::SecureStringToBSTR($jinaSecure)
try { $env:JINA_API_KEY=[Runtime.InteropServices.Marshal]::PtrToStringBSTR($jinaPtr) }
finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($jinaPtr); $jinaSecure.Dispose() }
if ([string]::IsNullOrWhiteSpace($env:JINA_API_KEY)) { throw 'Falta JINA_API_KEY' }
Write-Host 'JINA_API_KEY presente en el proceso'
# Al terminar la operación futura:
# Remove-Item Env:JINA_API_KEY -ErrorAction SilentlyContinue
```

No enviar claves al chat, escribirlas en .env/setx, argumentos, capturas o logs.
No se pidió ni cargó ninguna clave en esta preparación. El piloto no necesita
OpenRouter ni iniciar FastAPI/React. No se ha confirmado saldo actual por API.

El titular comunicó reglamento público y 9.999.541 tokens. Antes de enviar, verificar
personalmente panel/cuenta: saldo y vigencia, plan y permiso educativo/comercial,
ausencia de recarga o cargos automáticos y autorización del contenido. No encontrar
un control en el panel no certifica su estado: consultar soporte si no es verificable.
No añadir tarjeta, comprar tokens o habilitar recargas para resolver el bloqueo.
La API no tiene un tope monetario del cliente que garantice consumo exclusivamente
gratuito. Retención de textos/vectores/logs/backups y términos aplicables a esta
cuenta siguen pendientes según 10G.1/10G.2; no se investigaron de nuevo por red aquí.
No entrenamiento declarado no equivale a retención cero. No se emiten garantías
contractuales a partir de una prueba sintética o de saldo gratuito.

## 5. Consultas READ ONLY posteriores preparadas

Ejecutar únicamente después del piloto autorizado, sin imprimir vectores/textos:

```sql
BEGIN READ ONLY;
SET LOCAL statement_timeout='5s';
SELECT version_num FROM alembic_version;
SELECT count(*) AS confirmados,
       count(*) FILTER (WHERE e.dimension=768
         AND vector_dims(e.embedding)=768
         AND abs(vector_norm(e.embedding)-1)<=0.01
         AND e.hash_entrada=f.hash_texto
         AND f.hash_texto=encode(sha256(convert_to(f.texto,'UTF8')),'hex')
         AND p.hash_texto=encode(sha256(convert_to(p.texto_extraido,'UTF8')),'hex')
         AND f.pagina_inicio=f.pagina_fin
         AND f.texto=substring(p.texto_extraido FROM f.offset_inicio+1
                              FOR f.offset_fin-f.offset_inicio)) AS integros
FROM rag_cloud_embeddings e
JOIN rag_fragmentos f ON f.id=e.fragmento_id
JOIN rag_paginas p ON p.version_id=f.version_id AND p.pagina_pdf=f.pagina_inicio
WHERE f.version_id='7cb4e79c-747d-574a-8abb-0ebcb2e07636'
  AND e.espacio_id='1f048209-4b55-31fc-5d34-06985eb3ba0e';
-- Esperado confirmados=1 e integros=1; cotejar UUID/hash/ordinal con el piloto autorizado.
SELECT count(*) AS pendientes FROM rag_fragmentos f
WHERE f.version_id='7cb4e79c-747d-574a-8abb-0ebcb2e07636'
AND NOT EXISTS (SELECT 1 FROM rag_cloud_embeddings e WHERE e.fragmento_id=f.id
 AND e.espacio_id='1f048209-4b55-31fc-5d34-06985eb3ba0e');
-- Esperado 431.
SELECT fingerprint,dimension FROM rag_cloud_espacios
WHERE id='1f048209-4b55-31fc-5d34-06985eb3ba0e';
SELECT estado FROM rag_cloud_ingestas
WHERE version_id='7cb4e79c-747d-574a-8abb-0ebcb2e07636'
AND espacio_id='1f048209-4b55-31fc-5d34-06985eb3ba0e';
-- Esperado PREPARANDO.
SELECT count(*) FROM rag_cloud_activos; -- Esperado 0.
SELECT count(*) FROM rag_cloud_embeddings; -- Esperado total 1 en este primer piloto.
SELECT count(*) FROM rag_embeddings; -- Esperado histórico 864.
SELECT activa_version_id FROM rag_documentos;
ROLLBACK;
```

La consulta de norma es un control agregado, no sustituye validar finitud de los
768 componentes con el validador Python ni auditoría de filas/ACL. Comparar también
huellas de tablas históricas antes/después. No ejecutar validate/activate para
«probar» un índice de una fila: ambas son acciones de escritura, ajenas al piloto.

## 6. Continuación y decisión

Después de revisar el primer checkpoint y consumo, pedir permiso de continuación:
hasta 9 para llegar a 10; luego lotes de hasta 10, secuenciales. Cada fragmento
representa UN POST, total previsto 432 sin fallos. Se excluyen confirmados por
versión/espacio; no hay reintentos automáticos ni publicaciones al terminar lotes.
Ante error conservar estado y detenerse; llamada remota incierta puede consumir
cuota sin checkpoint. Validación completa de 432 requiere otra autorización de
escritura; activación transaccional y prueba React se autorizan después por separado.
La ingesta no modifica fragmentos, versión textual activa o vectores Nomic.

**GO técnico para presentar el piloto; ejecución BLOQUEADA** por autorización de
exportación/escritura/gate y por confirmaciones de cuenta/retención/facturación.
Antes de cualquier envío externo o checkpoint real se necesita autorización expresa
para ese único fragmento y resolución/aceptación explícita de los pendientes.
No se solicita ejecutar operaciones adicionales en este sprint.

Archivos incorporados: este informe y test_jina_pilot_preparation.py. Sin cambios
productivos, .env, datos, servicios, claves, backups, migraciones o bandera documental.
No se hicieron llamadas reales, indexación, activación ni uso de Ollama.
