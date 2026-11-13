# Jina cloud 10A: implementación preparada, sin publicación

Fecha: 9 de noviembre de 2026. No se modificó `.env`, PostgreSQL, servicios,
432 fragmentos o vectores Nomic. Sin llamadas Jina/Ollama/OpenRouter reales.
Dots3-Note, su restricción AtlasCloud y sus parámetros permanecen sin cambios.

## Configuración

Variables admitidas, con prioridad del entorno sobre `.env` salvo la clave:

| Variable | Predeterminado / límite |
|---|---|
| EMBEDDING_PROVIDER | ollama; seleccionar jina explícitamente |
| EMBEDDING_MODEL | jina-embeddings-v3, único modelo cloud permitido |
| EMBEDDING_DIMENSIONS | 768, única dimensión permitida |
| EMBEDDING_TIMEOUT_SECONDS | 30; >0 y <=55 |
| EMBEDDING_MAX_INPUT_BYTES | 2048; entre 1 y 8192 |
| EMBEDDING_MAX_RESPONSE_BYTES | 65536; entre 16384 y 65536 |
| JINA_API_KEY | Solo entorno del proceso, nunca se carga del archivo |

Testing ignora variables operativas y exige MockTransport para Jina. Un solo
input por POST, tareas retrieval.query/retrieval.passage, normalized=true y
embedding_type=float. Se rechazan cantidades, índices, dimensiones, tipos,
valores no finitos o norma fuera de tolerancia 0,01. No se normaliza ni repara
silenciosamente. Sin redirects, proxies heredados, cookies, reintentos o fallback.
401/402/403/429/5xx conservan indisponibilidad; timeout se distingue.

El fingerprint identifica modelo, tareas, dimensión y política; no inventa un
digest de pesos. La API no ofrece aquí una revisión inmutable comprobada:
un cambio upstream del alias debe provocar una revisión operativa, no mezclar
automáticamente vectores antiguos y nuevos. Registrar una muestra sintética
de referencia al autorizar la migración real.

## Convivencia y publicación

0006_cloud_embeddings agrega únicamente cuatro tablas rag_cloud_*:
espacios, embeddings, ingestas y activos. No cambia las restricciones Nomic,
ni su versión documental, tablas o datos. vector(768) y clave fragmento/espacio.
La selección activa cloud se asocia a la misma versión textual: conserva los
UUID de fragmentos, OCR, offsets y citas históricas. Nomic sigue disponible por
configuración explícita; no existe fallback automático si Jina falla.

CloudPostgresRAG reutiliza recuperación/continuidad/ACL existentes y redirige
solo las tablas vectoriales. Exige publicación VALIDADA para el espacio
configurado, antes y después de buscar. Configurar Jina antes de migrar/publicar
deja RAG indisponible deliberadamente; no devuelve resultados Nomic como cloud.

El reindexador usa la versión activa LISTA y propietario ADMIN activo explícito;
no crea usuarios, documentos, páginas o fragmentos. Lee pendientes por espacio,
verifica hashes de fragmento/página y slice antes de enviar; cada checkpoint es
transaccional e idempotente. Publicación separada, nunca automática al último lote.
La activación revalida los 432 vectores bajo el mismo lock y transacción que cambia
el puntero cloud. Mantiene el puntero documental original y todos los vectores Nomic.

Sin Ollama en ruta cloud: composición exige OpenRouter, construye Jina y repositorio
cloud; no crea Embeddings local, ni llama /api/ps, /api/tags o /api/embed. El cliente
de aceptación omite esos requisitos con EMBEDDING_PROVIDER=jina y exige el espacio
publicado. Se conserva una reserva de 0,25 GiB para el proceso; no se desactiva
globalmente AGENT_ENFORCE_MEMORY_GUARD. La ruta legacy conserva sus protecciones.

## Privacidad: indexación real bloqueada

Revisión de fuentes oficiales el 9/11/2026:

- https://jina.ai/legal/ informa que las condiciones anteriores pueden estar
  desactualizadas y remite al DPA y políticas de Elastic tras su adquisición.
- https://www.elastic.co/legal/privacy-statement distingue datos del sitio de
  contenido procesado por cuenta del cliente; no basta para prometer retención
  cero o ausencia de entrenamiento de la API Jina de esta cuenta.
- https://docs.jina.ai/ documenta el endpoint técnico; no acredita por sí mismo
  la retención contractual de entradas y vectores devueltos.
- El DPA enlazado oficialmente es https://www.elastic.co/pdf/v100623-0-elastic-customer-dpa.pdf;
  encuadra el procesamiento en el acuerdo aplicable y las instrucciones del cliente,
  pero no confirma por sí solo las condiciones específicas del endpoint de esta cuenta.

No se verificaron de forma concluyente plazo de retención y uso para entrenamiento
aplicables al servicio/cuenta. DOCUMENT_EXPORT_APPROVED permanece false en código:
embed_document operativo y TODAS las acciones del reindexador se bloquean antes
de exportar o escribir. No hay flag ni variable que permita saltarse este bloqueo.
Las pruebas de retrieval.passage son simuladas. El éxito sintético de query
comunicado por el usuario no equivale a autorización para exportar el reglamento.

Pendiente: confirmar términos vigentes de entradas/salidas, retención, entrenamiento,
subprocesadores y cuota gratuita restante. Esta API no tiene el filtro max_price de
OpenRouter: no prometer gratuidad ilimitada. No se activan facturación o recargas.

## PowerShell: preparar clave sin mostrarla

Solo en terminal privada, sin transcripción ni grabación:

```powershell
$jinaSecret = Read-Host 'Clave Jina' -AsSecureString
$jinaPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($jinaSecret)
try { $env:JINA_API_KEY = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($jinaPointer) }
finally {
  [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($jinaPointer)
  Remove-Variable jinaSecret,jinaPointer
}
```

No usar setx, argumentos ni archivos para la clave. Quitarla de la terminal al
terminar con Remove-Item Env:JINA_API_KEY. Los hijos ya iniciados conservan su copia.

## Comandos futuros: NO ejecutar sin autorización posterior

1. Respaldar y ensayar restauración en un destino aislado; los scripts históricos
   maintenance_93e.py contienen destinos fijos y requieren revisión antes de usarlos.
2. Revisar y aprobar SQL 0006; aplicar solo posteriormente con el mecanismo Alembic
   existente en usuarios_dev. No se aplicó en esta entrega.
3. Resolver privacidad y autorizar expresamente exportación y eliminación del bloqueo
   de documentos; comprobar retrieval.passage con información sintética primero.
4. Configurar la terminal del reindexador, sin cambiar todavía el backend activo:

```powershell
Set-Location 'D:\Downloads\proyectos\api-usuarios-clean\backend'
$env:EMBEDDING_PROVIDER='jina'
$env:EMBEDDING_MODEL='jina-embeddings-v3'
$env:EMBEDDING_DIMENSIONS='768'
# La clave debe estar previamente disponible solo en esta terminal.
& '.\.venv\Scripts\python.exe' -B -m app.presentation.cli.reindex_jina --action index --owner '<UUID_ADMIN_PROPIETARIO>' --version '7cb4e79c-747d-574a-8abb-0ebcb2e07636' --max-chunks 10
```

Cada ejecución procesa como máximo diez pendientes. No reintenta llamadas fallidas.
Antes de reanudar, revisar fallos; checkpoints confirmados se conservan. Una llamada
que terminó remotamente sin checkpoint puede volver a consumir cuota: no hay
idempotencia de facturación garantizada por Jina. No ejecutar clientes en paralelo.

Tras los 432, usar --action validate; luego probar búsquedas administrativas de
artículos 24 y 52 sin alterar ACL ni publicar. Preparar esas pruebas antes de activar.
Solo con aprobación posterior ejecutar --action activate con el mismo propietario
y versión. Mientras exista el bloqueo de privacidad, ambos comandos también fallan
cerrados. No existe activación automática.

5. Solo después de publicar, iniciar/reiniciar FastAPI con el lanzador local habitual,
   clave Jina y variables EMBEDDING_*; conservar AGENT_LLM_PROVIDER=openrouter y
   Dots3-Note. Configurar diagnósticos privados como antes. No iniciar Ollama.
6. Después autorizar aceptación de los 15 escenarios y revisar cobertura/citas.

Recuperación: no publicar ante errores; conservar avances y espacio Nomic.
Para volver al runtime previo, seleccionar explícitamente EMBEDDING_PROVIDER=ollama
y reiniciar solo FastAPI; Nomic requerirá Ollama disponible. No se elimina el espacio
cloud ni se cambia historial. El downgrade automático de 0006 rechaza borrar datos.

## Pruebas

MockTransport para query/passage, errores, índices/cantidad/modelo, JSON defectuoso,
límites, secretos y timeout; SQL simulado para ACL/espacio/publicación; lifespan real
FastAPI con dependencias simuladas que falla si construye embeddings Ollama.
Integración PostgreSQL preparada exclusivamente para usuarios_test, marcada postgres,
omitida sin --run-postgres. No equivale a validación SQL real de esta entrega.

Resultado final dirigido: **128 aprobadas, 1 omitida**, 18,66 s. Un aviso previo
Starlette/TestClient. La prueba omitida es la integración PostgreSQL cloud preparada.
No se suman ejecuciones repetidas.

Regresión ampliada rag/ia/acceptance: **817 aprobadas, 3 fallidas, 1 omitida y
7 excluidas**, 105,14 s. Fallos conservados sin cambios fuera de alcance:

- test_agent::test_auto_academic_selects_authorized_document_and_applies_real_skill:
  espera una lectura de catálogo y observa dos.
- test_agent::test_multiple_documents_require_selection_not_random_choice:
  el doble de catálogo carece de titulo y provoca KeyError en explicit_document.
- test_relevance::test_academic_evidence_and_real_page: la respuesta fixture queda
  SIN_EVIDENCIA por answer_not_supported, frente a expectativa FUNDAMENTADA.

Esos casos usan repositorios/embeddings ficticios y no pasan por Jina, repositorio
cloud ni composición operativa modificada. No se ejecutó una revisión anterior
como baseline; no afirmar una comparación temporal de regresión que no se midió.
No se declara toda la suite aprobada ni aceptación real completada.
