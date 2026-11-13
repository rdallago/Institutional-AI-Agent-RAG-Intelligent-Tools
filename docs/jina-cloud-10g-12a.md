# Sprint 10G.12A — Diagnóstico de document_unavailable

11 de noviembre de 2026, America/Buenos_Aires.
**Corte identificado; causa concreta del turno pendiente de correlación.**
No se declara corregido ni funcional el RAG real sin repetir la consulta autorizada manualmente.

## Recorrido y condición demostrada

React ConversationPanel → POST /api/v1/ia/conversaciones/{id}/mensajes →
get_current_user → Conversations.turn → Agent.execute → Agent._execute.
El principal autenticado se transmite al catálogo y al servicio RAG; no se sustituye
por el ADMIN propietario del reglamento.

agent.py, rama DocumentProposal: selected busca documento_id del plan dentro de
las filas del catálogo autorizado. document_unavailable se devuelve cuando:

- selected es None (catálogo vacío o plan sin documento seleccionado), o
- documento_solicitado no coincide con titulo ni aliases del seleccionado.

matches_document compara identidad normalizada exacta, no similitud temática.
Ese retorno ocurre ANTES de skill.execute, ResponderConDocumento y embed_query.
El log aportado demuestra ese corte; no demuestra un fallo de Jina ni búsqueda
vectorial vacía. Un UUID explícito ajeno al catálogo produce IARespuestaInvalida,
no ese resultado. Los errores SQL se propagan como IANoDisponible.

## Composición y ACL

bootstrap.py carga EmbeddingConfig al inicio. En operación habilitada con proveedor
jina construye JinaEmbeddings y CloudPostgresRAG; con OpenRouter construye también
OpenRouterGroundedProvider. El control previo exige Jina+OpenRouter para el RAG
operativo. No se encontró un flag adicional que seleccione Nomic en esa combinación.
La consulta efectiva usa retrieval.query; CloudPostgresRAG exige puntero VALIDADA
y espacio configurado, redirige SQL vectorial cloud y conserva ACL del repositorio.

La composición en código no acredita por sí sola el objeto vivo de un proceso ya
iniciado. No se inspeccionó memoria ni entorno privado del servidor.

Lectura real SQL protegida por default_transaction_read_only=on, timeout de conexión
10 s, sentencias 5 s y rollback:

- Título público: Reglamento académico.
- Visibilidad: PRIVATE.
- Propietario: 32eabde4-7d17-4029-a47a-60e2e38faf05.
- Versión activa: 7cb4e79c-747d-574a-8abb-0ebcb2e07636.
- Permisos explícitos puede_leer adicionales: 0.

La ACL permite propietario, visibilidad AUTHENTICATED o permiso explícito; ADMIN
no concede acceso universal. Un usuario distinto del propietario no ve este
documento PRIVATE. No se modificó ACL. Se buscó exclusivamente la respuesta de
error exacta reportada en mensajes persistidos para correlacionar propietario y
permiso mediante booleanos; no hubo coincidencias. No se imprimieron mensajes ni
identidades privadas. Esto no demuestra que la prueba no ocurriera: pudo usar otra
ruta, persistencia o contenido distinto. No se conoce la cuenta del turno original.

## Corrección mínima aplicada

No se encontró evidencia suficiente para cambiar selección, permisos o adaptador.
Sí se corrigió la falta de distinción del diagnóstico operativo: el log del mismo
retorno ahora incluye reason y authorized_catalog_count, sin nombres ni preguntas:

- empty_authorized_catalog
- planner_document_not_selected
- requested_title_mismatch

La denegación y el contrato HTTP permanecen intactos. No se permite inferir o
sustituir silenciosamente un documento por el único disponible.

Archivos modificados/incorporados:

1. backend/src/app/application/agent/agent.py.
2. backend/tests/rag/test_document_unavailable_diagnostics.py.
3. docs/jina-cloud-10g-12a.md.

## Pruebas locales

Desde backend:

```powershell
& '.\.venv\Scripts\python.exe' -B -m pytest tests/rag/test_document_unavailable_diagnostics.py tests/rag/test_jina_cloud.py tests/rag/test_jina_10c_storage.py -q -p no:cacheprovider --basetemp=.pytest-tmp-10g12a --tb=short
```

**54 aprobadas, 0 fallidas, 3,84 s.** Advertencia previa Starlette/HTTPX.
Nuevos casos: catálogo autorizado con citas y página, catálogo vacío por denegación
o ausencia, título distinto, selección ausente, fallo de embeddings simulado y
fallo de catálogo SQL simulado. Los errores técnicos no se convierten en ausencia.
Las suites cloud existentes cubren MockTransport Jina, ACL, recuperación, espacio
activo y composición sin cliente Ollama. No son una consulta E2E real.
Una primera invocación tuvo rutas duplicadas backend/backend y no ejecutó pytest;
se corrigió el directorio/comando, sin acciones externas.

## Servidor y siguiente comprobación

Proceso identificado mediante lectura: puerto 8000, PID 24256,
C:\Python314\python.exe; argumentos corresponden al proyecto y al lanzador
app.presentation.cli.local_server (no se imprimieron argumentos completos).
No se reinició: la clave Jina está en la terminal privada del operador y no en
este proceso ejecutor; detener el servidor aquí impediría garantizar su reposición
con las mismas credenciales. No se intentó extraerlas de su memoria.

Para cargar el nuevo diagnóstico, en la terminal privada que mantiene las claves,
detener solo ese backend con Ctrl+C y arrancar nuevamente:

```powershell
Set-Location 'D:\Downloads\proyectos\api-usuarios-clean\backend'
$env:PYTHONPATH = (Join-Path (Get-Location) 'src')
& '.\.venv\Scripts\python.exe' -B -m app.presentation.cli.local_server --environment local-development --enable-llm --observe-llm --host 127.0.0.1 --port 8000
```

No iniciar otra instancia si el puerto sigue ocupado. En React, abrir
http://127.0.0.1:5173/ia y comprobar privadamente que la cuenta autenticada sea la
del propietario del documento (no compartir contraseña/token). Crear una nueva
conversación y enviar una vez: «¿Qué establece el artículo 24 del reglamento académico?».
Si vuelve a fallar, aportar únicamente reason, authorized_catalog_count y request
ID del turno, sin tokens ni mensajes privados. Si es empty_authorized_catalog con
una cuenta distinta, se necesita autorización específica para conceder lectura;
no se cambiará ACL automáticamente. Si aparece otro reason, correlacionar selección
y nombre solicitado antes de modificar el comportamiento.

**Pendiente:** confirmar identidad del usuario del turno o capturar la nueva razón
acotada. No se afirma una causa raíz particular sin esa evidencia. Índice/embeddings,
.env, DOCUMENT_EXPORT_APPROVED y ACL permanecen sin cambios. No hubo APIs externas,
reindexación, migraciones, escrituras SQL ni nuevas consultas funcionales.
