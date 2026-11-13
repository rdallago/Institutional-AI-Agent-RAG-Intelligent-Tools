# Diagnóstico controlado del HTTP 404

7 de noviembre de 2026. **Estado: BLOQUEADO.** Sin cambios de código, configuración,
permisos o servicios. Una única petición generativa en esta intervención; sin reintentos.

## Inspección

La integración construye POST `https://openrouter.ai/api/v1/chat/completions`.
El modelo candidato exacto es `nvidia/nemotron-3.5-super-vl:free`. La clave está
presente en el entorno; no se imprimió ni persistió. AGENT_LLM_PROVIDER,
OPENROUTER_MODEL y AGENT_LLM_TIMEOUT_SECONDS no están definidos en el entorno
de esta ejecución. El ensayo anterior seleccionó explícitamente OpenRouter y
el candidato por LLMConfig; no activó ese proveedor en el FastAPI existente.

La prueba anterior envió response_format=json_schema con el esquema Proposal del
planificador, max_tokens=256, reasoning.enabled=false y temperature=0. Las opciones
de routing fueron require_parameters=true, allow_fallbacks=false, precios máximos
de prompt/completion cero y data_collection=deny. Su cuerpo de error no fue guardado
y no puede recuperarse retrospectivamente.

El GET público del endpoint actual respondió 200 y confirma un proveedor Nvidia,
precios cero y soporte declarado de response_format/structured_outputs. Esto
descarta que el identificador no exista en el catálogo; no prueba elegibilidad
para la política de datos de la solicitud/cuenta.

## Única solicitud actual

Se mantuvo el mismo modelo, URL y restricciones de routing. Se eliminó
response_format para la comprobación mínima de texto, sin cambiar código o
configuración persistente. Sin system, historial, documentos ni datos personales.

- HTTP: **404**.
- Duración de la petición: **0,682 s**.
- RAM antes/después: **1,480 / 1,448 GiB**; sin cargar modelos locales.
- Respuesta de un modelo: **ninguna**.
- JSON estructurado: no se probó nuevamente, porque no hubo respuesta de texto válida.

Cuerpo de error saneado:

```json
{
  "message": "No endpoints found matching your data policy (Free model training). Configure: https://openrouter.ai/settings/privacy",
  "code": 404,
  "metadata": {
    "routing_funnel": [{"step": "Initial Endpoints", "endpoint_count": 1}],
    "failed_routing_step": "Filter by Data Policy"
  }
}
```

Evidencia técnica:
[openrouter-404-diagnostic-1794076426656638500.json](openrouter-404-diagnostic-1794076426656638500.json).
La tubería PowerShell→Python degradó los acentos del mensaje sintético: el payload
conservado dice `Respond? ?nicamente OK`. Se declara esta limitación sin corregir
la evidencia ni realizar otra llamada. El rechazo informado es de routing previo
al modelo; no es una evaluación del contenido del mensaje.

## Causa y clasificación

**Confirmada en la reproducción: ningún endpoint supera el filtro de política de
datos, específicamente Free model training.** El router comenzó con un endpoint
y señala Filter by Data Policy como etapa fallida.

- Ruta incorrecta: no es lo que informa el error; OpenRouter procesó el routing.
- Modelo inexistente: contradicho por catálogo y un endpoint inicial.
- Sin proveedor compatible: confirmado por filtro de política de datos.
- Restricción de configuración: política de datos de solicitud/cuenta; no puede
  aislarse cuál de ambas es suficiente por sí sola con esta única petición.
- response_format incompatible: no explica esta reproducción, que no lo envió.
- Región, facturación o clave inválida: no demostradas por esta respuesta.

La primera ejecución histórica no conserva su cuerpo: el diagnóstico actual
reproduce el 404 bajo las mismas restricciones, pero no inventa metadatos del
error anterior.

## Corrección mínima necesaria y detención

Conservar data_collection=deny y seleccionar un endpoint/modelo gratuito que sea
elegible bajo esa política y la de la cuenta. El candidato actual no queda
aceptado para este despliegue. No se buscaron alternativas mediante generaciones
ni se habilitaron modelos pagos. Activar opciones de entrenamiento o permitir
recolección de datos relajaría la protección vigente y no se hizo.

No basta cambiar /chat/completions por /responses ni desactivar JSON Schema para
resolver el filtro demostrado. Las opciones de privacidad de la cuenta deben
revisarse antes de decidir un modelo elegible; no se modifican automáticamente.

Referencia oficial: [políticas de datos y routing](https://openrouter.ai/docs/guides/routing/provider-selection),
y [configuración de privacidad indicada por el propio error](https://openrouter.ai/settings/privacy).

No se ejecutó la aceptación, no se reinició FastAPI y no se tocó RAG, PostgreSQL,
memoria, embeddings, React u Ollama. No se envió una segunda petición generativa.
