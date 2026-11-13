# Sprint 9.2.5B — fase 2: preparación para Qwen3:1.7b

Fecha: **2 de noviembre de 2026**. Estado: **adaptación implementada y pruebas
aisladas aprobadas**. No se habilitó IA operativa ni se ejecutó inferencia.
Compatibilidad real, RAM y latencia siguen pendientes de piloto autorizado.

## 1. Decisión y archivos

El responsable comunicó que Qwen2.5 bloqueó la notebook y que Qwen3 funcionó en
ejecuciones locales anteriores. Se registra como evidencia comunicada, no como
observación o benchmark realizado por Codex. No demuestra que este payload,
contexto, concurrencia o carga actual sean seguros para inferencia.

Modificados:

- `backend/src/app/infrastructure/configuration/llm.py`: única constante MODEL
  permitida pasa de qwen2.5:1.5b a **qwen3:1.7b**.
- `backend/src/app/infrastructure/llm/ollama.py`: `think: false` fijo en la solicitud.
- `backend/tests/ia/test_llm_configuration.py`: allowlist, rechazo del modelo
  anterior y separación de variables operativas/de pruebas.
- `backend/tests/ia/test_ollama_adapter.py`: fixtures Qwen3, payload, respuestas
  de modelo anterior rechazadas y tratamiento del campo thinking.
- `backend/tests/ia/test_ia_lifespan.py`: respuesta ficticia Qwen3 del transporte mock.
- `backend/tests/ia/test_local_llm_launcher.py`: expectativa del modelo fijo Qwen3.
- `docs/sprint-9-2-5b-fase2-compatibilidad-qwen3.md` (nuevo): este informe.

Se inspeccionaron configuración, adaptador/runtime, lanzador, lifespan y esquemas
HTTP. No se modificaron el núcleo Application, bootstrap, lanzador, políticas de
autenticación, contratos, frontend, dependencias, migraciones o archivos .env.

### Clasificación de referencias anteriores

En código funcional la única selección literal anterior estaba en `llm.py`;
adaptador y lanzador consumen esa configuración, sin mantener una segunda lista.
Las fixtures y expectativas de los cuatro archivos de pruebas indicados se
actualizaron. Qwen2.5 permanece explícitamente en **pruebas negativas**, donde debe
rechazarse; no constituye un modelo alternativo o fallback.

Los informes `sprint-9-1-diseno-llm.md`, `sprint-9-2-2-adaptador-ollama.md` y
`sprint-9-2-5a-diagnostico-piloto-ollama.md` conservan sus referencias históricas
sin reescribir decisiones o mediciones anteriores. La búsqueda también localizó
referencias en `prompts.txt`, archivo local ignorado que no configura el runtime;
no se modificó ni se reprodujo su contenido. README principal/backend no contenían
una selección literal de Qwen2.5 que actualizar. No se inspeccionaron secretos de
.env para reemplazar textos: no fue necesario para este cambio de código.

## 2. Configuración final

Modelo permitido exactamente **qwen3:1.7b**, también cuando se carga mediante
LLM_MODEL o TEST_LLM_MODEL. Qwen2.5, nombres arbitrarios, el alias qwen3 y variantes
cloud se rechazan; no se infiere equivalencia entre tags. URL exclusivamente
`http://127.0.0.1:11434`, sin redirecciones, proxies heredados o fallback a nube.

IA continúa deshabilitada por defecto. El lanzador de fase 1 inyecta LLMConfig
inmutable y solo habilita mediante --enable-llm para local-development, con el
mismo socket real validado y servido, un worker y sin reload. No carga LLM_* o
TEST_LLM_* para activar implícitamente esa instancia. El cargador general conserva
sus namespaces separados y la exigencia de MockTransport en pruebas habilitadas.

HTTP público continúa aceptando **solo prompt**. El usuario no selecciona modelo,
URL, razonamiento, system, herramientas o presupuestos. Tampoco se añade thinking
a la respuesta pública, que conserva respuesta/finalizacion.

## 3. Razonamiento y contrato Ollama

La documentación oficial de [generación](https://docs.ollama.com/api/generate)
admite `think` en el cuerpo de `/api/generate`. La guía de
[thinking](https://docs.ollama.com/capabilities/thinking) distingue el campo
`thinking` de `response` y documenta false para solicitar salida sin razonamiento
cuando el modelo lo admite. Se consultaron fuentes oficiales, no el servicio local.

Se fija **think=false en el nivel superior**, no dentro de options, ni como texto
añadido al prompt. Evita depender del valor predeterminado de un modelo con capacidad
de razonamiento y pretende reservar el presupuesto breve para la respuesta final.
Es compatibilidad documentada del protocolo, **no prueba de que el tag instalado
o la versión local observada anteriormente honren esa opción**. No se añade
/no_think ni se modifica silenciosamente el texto del usuario. Si el servidor
rechaza la opción, no se reintenta quitándola ni se cambia a otro modelo.

El adaptador mantiene:

- HTTP 200, JSON objeto/UTF-8 válido y sin claves duplicadas o constantes no finitas.
- model exactamente qwen3:1.7b y done booleano true.
- done_reason estrictamente stop o length → completa o limite.
- response como texto no vacío, válido y acotado; no se usa thinking como respuesta.
- Campo thinking adicional ignorado, nunca reenviado o registrado. Una respuesta
  vacía con thinking presente sigue siendo inválida; no se concatena el razonamiento.

done_reason ausente, vacío o desconocido sigue produciendo IARespuestaInvalida
(502 en HTTP), incluso con done=true. No se inventa completa por defecto ni se
infiere por cantidad de tokens. Se conservan los casos negativos previos y no se
relajó el parser para adaptar las fixtures. No se garantiza detectar razonamiento
que un modelo escriba dentro de response: es texto no confiable y su conducta real
requiere observación del piloto.

## 4. Payload esperado y presupuestos

Única ruta de generación: POST `http://127.0.0.1:11434/api/generate`.

```json
{
  "model": "qwen3:1.7b",
  "prompt": "<consulta validada>",
  "stream": false,
  "think": false,
  "options": {"num_predict": 256, "num_ctx": 4096},
  "keep_alive": 0,
  "system": "Responde en espanol con informacion breve y clara. No operas sistemas ni ejecutas acciones."
}
```

No se envían JWT, roles, identidad, historial, perfiles, tools o instrucciones
de ejecución. Payload y tipos booleanos exactos quedan comprobados por MockTransport.

Se **conservan 4096 tokens de contexto y 256 de salida**, sin aumentos. Son
presupuestos acotados para consultas breves, no una declaración de viabilidad en
8 GiB. Contexto incluye plantilla/system, entrada y salida; los 1000 puntos/3000
bytes de prompt no equivalen a tokens. Reducirlo sin medir tokenización efectiva
podría dejar de admitir entradas válidas sin truncamiento; por eso no se reduce
arbitrariamente en esta fase. Una reducción posterior deberá revisar el límite
de entrada y sus pruebas. Una salida de 256 puede terminar en length: se informa
limite sin ocultar el corte ni ampliar automáticamente el presupuesto.

Permanecen: una generación por proceso, sin cola; 5 admisiones por usuario y 15
globales por minuto; deadline backend 60 s; enfriamiento 30 s tras timeout; request
HTTP 16 KiB, upstream 64 KiB reales, salida 4096 puntos/16384 bytes; stream=false,
keep_alive=0. Cerrar HTTP o descargar tras uso no garantiza detener cómputo o borrar
RAM de forma segura. No se modifican cuotas de autenticación ni se añade persistencia.

## 5. Pruebas ejecutadas

Mocks/dobles y fixtures ficticios, sin PostgreSQL u Ollama real. Las pruebas de
lanzamiento usan sockets efímeros con servidor sustituido, sin servicios persistentes.

```powershell
# Desde backend, sin --run-postgres:
.\.venv\Scripts\python.exe -B -m pytest -q tests/ia -p no:cacheprovider --basetemp=.pytest-tmp-925b-phase2-ia --tb=short
.\.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider --basetemp=.pytest-tmp-925b-phase2-full --tb=short
```

| Ejecución | Resultado |
| --- | --- |
| Dirigida IA: configuración, proveedor, HTTP, lifespan y lanzador | **264 aprobadas**, 9,54 s |
| Regresión backend sin PostgreSQL | **697 aprobadas, 162 omitidas**, 25,84 s; sin fallos |
| Casos anteriores / nuevos en regresión | **685 / 12**, sin sumar repeticiones |
| Frontend y piloto real | No ejecutados |

Los 12 nuevos casos cubren tres variantes adicionales de modelo inválido, seis
combinaciones de allowlist/aislamiento de namespaces y tres casos de thinking o
modelo anterior en la respuesta. Se actualizaron casos existentes de payload,
lifespan y lanzador. La regresión conserva autorización ADMIN/USUARIO, rechazo de
pendientes/revocados/inactivos, autenticación previa/posterior, cuotas, errores,
timeout, cancelación, cierre y limpieza. El contrato sigue sin campo de modelo.
Las 162 PostgreSQL son omisiones intencionales, no aprobaciones. Permanece el aviso
previo Starlette/TestClient sobre httpx; no se instalaron paquetes para ocultarlo.

## 6. Riesgos y validación real pendiente

El diagnóstico de baja RAM continúa siendo antecedente no resuelto; no se volvió
a medir ni se hizo inferencia para comprobarlo. El archivo Qwen3 observado en
9.2.5A era mayor que Qwen2.5; tamaño de disco no permite deducir RAM total o mejor
rendimiento. El éxito previo comunicado por el responsable no garantiza estabilidad
con FastAPI, navegador, PostgreSQL, plantilla y contexto actuales.

Pendiente: versión/tag/digest efectivos, soporte de think=false, separación de
respuesta/razonamiento, done_reason real, tokenización sin truncamiento, carga fría,
latencia, RAM/compromiso y comportamiento tras cancelación/keep_alive. No se
declara APTO el equipo por cambiar el nombre del modelo o aprobar MockTransport.

## 7. Propuesta de piloto futuro — NO ejecutada

1. Obtener autorización operativa; repetir RAM física/compromiso con servicios
   necesarios presentes y recuperar margen acordado (propuesta previa: al menos
   2 GiB disponibles, sin garantía). Posponer ante presión de memoria; no detener
   programas ajenos, modificar pagefile o forzar una inferencia de diagnóstico.
2. Revalidar identidad de backend/listeners, destino/revisión DB bajo alcance
   expresamente autorizado, Ollama loopback, Qwen3 instalado/digest y ausencia de
   otras generaciones. No usar automáticamente Qwen2.5 como fallback.
3. Preparar observación saneada de status/modelo/done/done_reason, duración y
   tamaños sin cuerpos, thinking, prompts, respuestas, JWT o credenciales. No crear
   endpoint público de diagnóstico ni habilitar trazas HTTP completas.
4. Solo con permiso, coordinar reinicio exclusivo del backend propio con el
   lanzador --environment local-development --enable-llm en 127.0.0.1:8000.
   Confirmar socket real, worker único, inicio completo y endpoint IA nuevo;
   aprovisionamiento sigue siendo una decisión independiente.
5. Responsable introduce personalmente sus credenciales en React. Aprobar una
   consulta breve ficticia y no sensible; medir latencia y RAM antes/durante/después
   y comprobar cadena React → FastAPI → Ollama, response y finalizacion.
6. Parar ante congelamiento, presión de memoria, timeout, modelo/razón inesperados
   o error de opción think. No relajar validación ni reintentar automáticamente.
   Cancelación y otras inferencias adicionales requieren alcance acordado.
7. Para revertir, tras revalidación/autorización detener solo la futura instancia
   propia y relanzar sin --enable-llm. No editar .env, modificar credenciales,
   migrar o detener Ollama de otros usos. No es necesario volver a Qwen2.5 para
   deshabilitar IA; el estado normal continúa cerrado.

## 8. Detención

No se iniciaron/detuvieron Ollama, FastAPI, React u otros servicios. No hubo
inferencia, descarga, acceso a bases, migraciones, cambios JWT/roles/sesiones,
configuración operativa o instalaciones. No se consultaron endpoints del Ollama
local; la disponibilidad reportada procede de antecedentes y confirmación del
responsable. Se modificaron solo los archivos enumerados y se consultó documentación
oficial remota. **Adaptación entregada; piloto operativo pendiente de autorización.**
