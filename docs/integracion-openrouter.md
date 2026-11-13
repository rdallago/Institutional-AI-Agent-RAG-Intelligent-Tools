# OpenRouter: integración y resultado de verificación

7 de noviembre de 2026. **Implementación en disco; aceptación real BLOQUEADA.**
No se reinició FastAPI ni se modificó `.env`. El servidor existente conserva su
configuración anterior hasta un reinicio explícito. No se seleccionó un modelo
de pago ni se cambió automáticamente de proveedor.

## Antes y después

Antes: router/reglas y planificador JSON → Ollama para planificación, generación
fundamentada y respuesta general. Nomic local genera embeddings de consulta.

Ahora: las mismas interfaces y recorridos admiten OpenRouter HTTPS para esas tres
operaciones generativas. `AGENT_LLM_PROVIDER` selecciona el proveedor; Ollama
permanece disponible por configuración. No hay fallback automático entre ambos.
Planificación reutiliza JSONPlanner y ToolRegistry; generación fundamentada reutiliza
GroundedProvider, schema/parse, selección por afirmación y validación final existentes.
No se cambian SYSTEM, ACL, continuidad, SQL de recuperación ni contratos HTTP.
No hay dependencias nuevas: HTTPX ya estaba instalado.

Los embeddings siguen siendo `nomic-embed-text`, con el mismo digest, espacio y
432 vectores documentales. Cada consulta RAG aún necesita un embedding local;
OpenRouter no elimina ese coste. No se realizó ningún embedding en esta intervención.

## Modelo: evidencia y límite

Candidato concreto: `nvidia/nemotron-3.5-super-vl:free`, sin selección aleatoria.
El catálogo público consultado en esta fecha informó proveedor Nvidia, precio de
entrada/salida cero, y parámetros response_format, structured_outputs, reasoning,
max_tokens. No exige razonamiento obligatorio según el catálogo general.

Fuentes oficiales:

- [Endpoints del candidato](https://openrouter.ai/api/v1/models/nvidia/nemotron-3.5-super-vl:free/endpoints).
- [Catálogo de modelos](https://openrouter.ai/api/v1/models).
- [Salida estructurada](https://openrouter.ai/docs/guides/features/structured-outputs).
- [Routing, precios y política de datos](https://openrouter.ai/docs/guides/routing/provider-selection).

Antes de enviar contenido se verifica el catálogo del modelo: sufijo :free, precio
cero y soporte declarado de parámetros. El POST fija require_parameters=true,
allow_fallbacks=false, max_price de prompt/completion cero y data_collection=deny.
No se relajan estas condiciones cuando faltan endpoints. Son controles de routing;
la publicación en el catálogo no garantiza disponibilidad real ni calidad semántica.

### Una única prueba real

Había una clave en el entorno; no se imprimió ni se guardó. Se ejecutó el planificador
real con su esquema Proposal y una pregunta general sobre API REST, catálogo vacío
e historial vacío. Sin Principal, documentos, credenciales de usuario o JWT.

| Dato | Resultado |
|---|---|
| GET de verificación de endpoint | Una consulta, completada |
| POST generativo | Uno, HTTP 404 |
| Duración total | 0,673 s |
| RAM antes/después | 1,274 / 1,271 GiB |
| Error público interno | PlanificadorNoDisponible |
| Plan/JSON validado | Ninguno |
| Reintentos / fallback | Cero |
| Pruebas de dos usuarios | No ejecutadas, dependencia generativa bloqueada |

Evidencia: [openrouter-smoke-1794076095112519300.json](openrouter-smoke-1794076095112519300.json).
El cuerpo del error no se conservó: no se atribuye el 404 a una política de cuenta,
privacidad, parámetros o disponibilidad específica sin evidencia. Tampoco confirma
por sí solo que la clave sea válida. El modelo queda como candidato configurado,
**no como modelo gratuito aceptado funcionalmente**. No se ensayaron alternativas
ni se enviaron fragmentos privados para buscar un resultado favorable.

## Variables, recursos y seguridad

| Variable | Uso |
|---|---|
| AGENT_LLM_PROVIDER | openrouter u ollama; por compatibilidad, omitir mantiene ollama |
| OPENROUTER_API_KEY | Solo variable de entorno del proceso; no se carga desde .env ni frontend |
| OPENROUTER_MODEL | ID gratuito concreto; candidato predeterminado indicado arriba |
| OLLAMA_MODEL | Selección local; conserva compatibilidad con LLM_MODEL |
| AGENT_LLM_TIMEOUT_SECONDS | Mayor que cero y hasta 60 s; sin ampliar deadlines globales |
| AGENT_ENFORCE_MEMORY_GUARD | Protección local existente; no se modificó su configuración |
| AGENT_PRIVATE_DIAGNOSTIC_DIR | Directorio privado existente del servidor |
| AGENT_PRIVATE_CAPTURE_RAG_JSON | Captura explícita existente, conservada |

Ollama conserva la guarda de generación/planificación de 1,5 GiB y Nomic la de
1,0 GiB. OpenRouter reserva 0,25 GiB para el proceso, sin exigir memoria para pesos
que no carga. El cliente exige 1,0 GiB para RAG remoto por Nomic y 0,25 GiB para
turnos remotos no documentales. Antes de RAG comprueba que Ollama esté idle.
Se conservan admisión compartida, cuotas, gate, ejecución secuencial y checkpoints.
Testing no hereda proveedor ni claves del entorno operativo; HTTPX MockTransport
es obligatorio para transporte habilitado en tests.

La clave solo se adjunta al POST HTTPS fijo de OpenRouter. No hay redirects,
proxies heredados, cookies o reintentos. Respuestas acotadas a 64 KiB, parsers con
rechazo de claves duplicadas, comprobación del modelo y de la finalización, límites
de salida existentes de 256 tokens. No se acepta una referencia solo porque el
proveedor devolvió JSON. HTTP 401/402/429/5xx conservan carácter técnico y no
disparan Ollama. Timeout conserva su categoría. No se imprimen cuerpos upstream.

Solo llegan los prompts ya acotados de las interfaces existentes: pregunta/historial
limitado de planificación, contexto directo limitado y fuentes autorizadas del RAG.
No se envía el historial completo ni UUID del propietario. Se rechazan patrones
conocidos de credenciales antes del transporte; no es un detector universal de secretos.

## Archivos modificados

- backend/src/app/infrastructure/configuration/llm.py: selección, clave oculta en repr,
  timeout y aislamiento de configuración.
- backend/src/app/presentation/cli/local_server.py: aplica configuración y muestra
  proveedor/modelo, sin secretos.
- backend/src/app/infrastructure/llm/openrouter.py: nuevo transporte y adaptadores.
- backend/src/app/bootstrap.py: selección de runtime, grounded y planner.
- backend/src/app/infrastructure/rag/models.py, planner.py y ollama.py: guardas
  diferenciadas y habilitación del mismo contrato estructurado para OpenRouter.
- infra/acceptance_agent.py: recursos y preflight según proveedor, misma matriz.
- backend/tests/ia/test_openrouter.py: pruebas nuevas.
- backend/tests/ia/test_local_llm_launcher.py: aislamiento explícito del modelo en
  una expectativa antigua que leía el .env operativo.
- backend/tests/acceptance/test_local_client.py: pruebas de recursos por proveedor.
- Este informe y la evidencia no sensible de la única solicitud real.

No se modificaron agentes, validadores, prompts, PostgreSQL, permisos documentales,
indexación, embeddings, React, credenciales ni los checkpoints previos.

## Pruebas automatizadas

- Grupo proveedor/configuración/lanzador/RAG/planificación/cliente: **181 aprobadas**,
  8,06 s; dos pruebas nativas de permisos excluidas por filtro, ajenas a esta integración.
- Grupo lifespan/HTTP/auth/adaptador Ollama/observación: **180 aprobadas**, 3,82 s.
- Total de estos grupos distintos: **361 aprobadas**. Aviso Starlette preexistente.

Cubren selección explícita, aislamiento de testing, clave ausente, esquema válido e
inválido, claves duplicadas, fuentes desconocidas, citas y afirmaciones inventadas,
401/402/429/5xx, red, timeout, secretos, límites y rechazo de catálogos no gratuitos.
No son aceptación de calidad del modelo remoto ni prueba de React.

## Comandos para revisión y posterior activación

**No ejecutar la batería hasta resolver/revisar el 404.** Estos comandos no fueron
ejecutados para cambiar el backend existente. No agregan secretos a archivos ni
usan `setx`; las variables pertenecen a la terminal y sus procesos hijos.

PowerShell del backend, tras un cierre controlado únicamente de FastAPI:

```powershell
Set-Location 'D:\Downloads\proyectos\api-usuarios-clean'
$env:AGENT_LLM_PROVIDER='openrouter'
$env:OPENROUTER_MODEL='nvidia/nemotron-3.5-super-vl:free'
$env:OLLAMA_MODEL='qwen2.5:1.5b'
$env:AGENT_LLM_TIMEOUT_SECONDS='60'
$env:AGENT_ENFORCE_MEMORY_GUARD='true'
$env:AGENT_PRIVATE_DIAGNOSTIC_DIR='D:\Downloads\api-usuarios-clean-backups\93e-20261103\agent-final-20261107-113501-255e2678'
$env:AGENT_PRIVATE_CAPTURE_RAG_JSON='true'
$orSecret=Read-Host 'Clave OpenRouter' -AsSecureString
$orPointer=[Runtime.InteropServices.Marshal]::SecureStringToBSTR($orSecret)
try { $env:OPENROUTER_API_KEY=[Runtime.InteropServices.Marshal]::PtrToStringBSTR($orPointer) }
finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($orPointer); Remove-Variable orPointer,orSecret }
Set-Location '.\backend'
& '.\.venv\Scripts\python.exe' -B -m app.presentation.cli.local_server --environment local-development --enable-llm --observe-llm --host 127.0.0.1 --port 8000
```

El backend debe mostrar provider=openrouter y el modelo elegido. No cerrar Docker,
PostgreSQL, Ollama o React. Para iniciar React si está detenido, en otra terminal:

```powershell
Set-Location 'D:\Downloads\proyectos\api-usuarios-clean\frontend'
& 'C:\Program Files\nodejs\node.exe' node_modules/vite/bin/vite.js --config vite.development.config.ts --host 127.0.0.1 --port 5173 --strictPort
```

Cliente, en otra PowerShell, con el MISMO proveedor que el backend (no necesita clave):

```powershell
Set-Location 'D:\Downloads\proyectos\api-usuarios-clean'
$env:AGENT_LLM_PROVIDER='openrouter'
$env:OPENROUTER_MODEL='nvidia/nemotron-3.5-super-vl:free'
$env:AGENT_LLM_TIMEOUT_SECONDS='60'
& '.\backend\.venv\Scripts\python.exe' -B '.\infra\acceptance_agent.py' --resume '.\.acceptance-private\run-b3513ed2f07c494881d83c66c7240e3a\informe.json' --diagnostic-dir 'D:\Downloads\api-usuarios-clean-backups\93e-20261103\agent-final-20261107-113501-255e2678'
```

Ese checkpoint no había enviado solicitudes; conserva identidad y reanuda sin
duplicaciones. Si después existen solicitudes fallidas o inciertas, siguen sin
reenviarse automáticamente. El usuario común no tiene acceso al ROM según la
aceptación previa: debe permanecer denegado. Login/logout se realiza interactivamente;
Codex no conoce las credenciales y no ejecutó la batería de dos usuarios.

Para volver a Ollama por configuración, establecer `AGENT_LLM_PROVIDER=ollama` y
`OLLAMA_MODEL=qwen2.5:1.5b` en ambas terminales y reiniciar solo FastAPI de manera
controlada. No hay conmutación automática ante errores de OpenRouter.

**Estado final:** integración automatizada comprobada; selección efectiva del modelo
gratuito y aceptación funcional real pendientes por HTTP 404. Se detiene aquí, sin
otro modelo, otro ensayo o una ronda automática de correcciones.
