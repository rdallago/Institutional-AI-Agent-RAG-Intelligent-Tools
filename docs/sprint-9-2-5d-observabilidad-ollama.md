# Sprint 9.2.5D: observabilidad segura de Ollama

Fecha: **2 de noviembre de 2026**. Estado: **implementado y verificado en aislamiento**.
**Sin inferencia, activación operativa, conexiones PostgreSQL o reinicios.**

## 1. Revisión y archivos

Se revisaron el preflight 9.2.5C, adaptador, LLMConfig, runtime, composición en
lifespan, lanzador y pruebas existentes. Se conserva la política del proveedor:
qwen3:1.7b, think=false, URL loopback, sin reintentos ni cambios de presupuestos.

Archivos nuevos:

- `backend/src/app/infrastructure/llm/observation.py`: evento inmutable de solo
  metadatos y emisión JSON a stdout, sin destino de almacenamiento propio.
- `backend/tests/ia/test_ollama_observation.py`: pruebas MockTransport, HTTP en
  proceso, privacidad y limpieza.
- `docs/sprint-9-2-5d-observabilidad-ollama.md`: este informe.

Modificados:

- `backend/src/app/infrastructure/llm/ollama.py`: observación opcional por proveedor,
  contador de bytes y reloj monotónico, emisión al finalizar la misma solicitud.
- `backend/src/app/bootstrap.py`: parámetro explícito llm_observe, validación previa
  a persistencia y paso del opt-in al runtime compartido.
- `backend/src/app/presentation/cli/local_server.py`: flag local --observe-llm.
- `backend/tests/ia/test_local_llm_launcher.py`: selección explícita, rechazo de
  entorno inadecuado y ausencia de activación heredada.

No se modificaron Application/Domain, autenticación, roles, sesiones, barrera,
adaptador de persistencia, contratos HTTP, React, dependencias, migraciones o .env.

## 2. Habilitación y composición

Observación deshabilitada por defecto en CLI, create_app, runtime y proveedor.
El lanzador exige **--observe-llm junto con --enable-llm**, solo en
local-development; observar no habilita IA implícitamente. La falta de --enable-llm
se rechaza antes de cargar configuración operativa. production/test son rechazados
por el lanzador, incluso con ambos flags. No existe variable de entorno que active
la observación, endpoint diagnóstico o selector desde React.

La composición operativa sigue exigiendo LocalLLMContext con el mismo socket real
servido, loopback y un worker. create_app rechaza observación con IA deshabilitada
o sin la prueba local necesaria antes de construir persistencia. En pruebas se
permite la inyección explícita en configuración testing con MockTransport; no es
una vía HTTP o de entorno operativo. Estos argumentos son interfaces Python de
composición confiable, no una barrera contra alguien que modifique el propio código.

El lifespan pasa observe=True una vez al runtime compartido cuando corresponde.
Las factorías existentes sin observador mantienen su invocación anterior. No se
crea otro cliente ni se invoca una segunda generación para observar: el evento
proviene de la misma llamada generate que atiende la consulta autenticada.

## 3. Metadatos y semántica

Se imprime una línea JSON con **exactamente ocho campos**:

| Campo | Semántica |
| --- | --- |
| http_status | Entero de la respuesta recibida; null si no hubo respuesta HTTP |
| model_matches | Booleano: model coincide con el permitido, sin reproducir el nombre recibido |
| done_valid | Booleano: done es exactamente true; false incluye ausente, false o tipo inválido |
| done_reason | Solo stop, length o invalid; nunca una razón desconocida cruda |
| think_requested | Siempre false, describe el payload enviado |
| thinking_present | Booleano: campo thinking string no vacío, incluidos espacios; ausente/tipo incorrecto da false |
| duration_seconds | Duración monotónica en segundos, desde preparación de la llamada hasta limpieza de respuesta |
| response_bytes | Bytes de cuerpo observados por el adaptador, no Content-Length ni cabeceras |

Sin JSON objeto válido y completo, los booleanos derivados permanecen false y
la razón invalid. No se extraen campos de JSON parcial/malformado. El evento no
incluye un resultado público exitoso/fallido ni permite inferirlo siempre: por
ejemplo done válido no implica que response cumpla su contrato.

El contador suma chunks recibidos **antes** de comprobar exceso: puede incluir
el chunk que dispara el límite, sin incorporarlo al buffer. Si hay timeout o
cancelación contiene solo bytes observados hasta ese punto. No fuerza lectura
de cuerpos de error o resto de una respuesta excedida para medirlos. Puede ser
cero con status conocido si no se leyó el cuerpo; no es el total descargado por
todo el stack de red ni una medición de transferencia de Ollama. Respuestas
precargadas de MockTransport contabilizan su contenido ya disponible.

Se emite una vez en finally, después del intento de cierre de respuesta, también
en timeout, error de protocolo o cancelación. Sin llamada al proveedor (p. ej.
autorización/validación inicial fallida o IA deshabilitada) no hay evento de
generación. Tampoco se emite al construir/cerrar el runtime sin generar.

## 4. Privacidad, recursos y límites

El evento se construye únicamente con enteros, booleanos, float y una razón de
allowlist. No contiene request/response, payload JSON, prompt, salida, thinking,
JWT, cookies, headers, credenciales, UUID, mensajes de excepción o traceback.
No se añaden identificadores de correlación. No se usa logger con exc_info ni
contexto heredado. La serialización rechaza números no finitos.

Un fallo de escritura a stdout se descarta sin imprimir su excepción ni cambiar
el resultado o introducir reintentos. No hay cola, archivo, base, tarea de fondo
o historial del observador que deba drenarse. El evento solo existe durante emisión;
respuesta/cliente mantienen sus cierres en finally/lifespan, también por cancelación.

stdout es el único destino: el operador puede redirigirlo a logs de metadatos,
pero este módulo no crea archivos ni decide su retención. Deben mantenerse
protegidos porque tiempos/tamaños y presencia de razonamiento revelan actividad.
No se garantiza borrado seguro de RAM, anonimato frente a correlación externa,
ni ausencia de logs en Ollama, HTTPX u otros componentes ajenos al observador.
No habilitar trazas HTTP, cuerpos o captura de variables locales para el piloto.

La salida síncrona y flush pueden demorar con un destino lento; no hay cola
ilimitada ni garantía de entrega del evento si stdout falla o el proceso termina
abruptamente. Una dependencia que no coopere al cerrar puede retrasar el finally;
no se promete emisión instantánea o detención de cómputo remoto.

think_requested=false no certifica que el modelo no haya calculado razonamiento.
thinking_present solo observa el campo separado, no detecta razonamiento escrito
en response. El parser no lo concatena ni lo devuelve como sustituto de respuesta.
Se conserva done_reason estricto: un evento invalid no autoriza relajar validación.

Se mantienen cuotas/concurrencia, deadline 60 s, contexto 4096, salida 256 tokens,
stream=false, keep_alive=0 y los límites de cuerpo. No hay herramientas, comandos,
RAG, historial, persistencia de contenido o ampliación de permisos.

## 5. Pruebas

MockTransport controla respuesta/payload, stream y errores. Las pruebas verifican
silencio por defecto; campos/tipos exactos; reloj controlado; razones válidas,
ausentes, vacías/tipos desconocidos; thinking presente/ausente/vacío; modelo/done
inválidos; JSON roto, error HTTP y exceso; timeout antes y después de headers;
cancelación; cierre y fallo de stdout sin alterar resultado. Centinelas ficticios
de contenido/cookies/excepciones y JWT ficticio no aparecen en stdout.

La integración TestClient atraviesa autenticación de memoria, router, caso de uso,
lifespan y adaptador MockTransport con una sola solicitud upstream y comprueba que
la respuesta pública sigue siendo exclusivamente respuesta/finalizacion. Pruebas
de composición rechazan el opt-in sin IA/contexto antes de DB. La CLI se prueba
con servidor/configuración doblados y sockets efímeros de loopback; no hay Uvicorn
operativo ni conexiones PostgreSQL u Ollama reales.

Comandos desde backend, sin --run-postgres:

```powershell
.\.venv\Scripts\python.exe -B -m pytest -q tests/ia -p no:cacheprovider --basetemp=.pytest-tmp-925d-ia-fixed --tb=short
.\.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider --basetemp=.pytest-tmp-925d-full-final --tb=short
```

| Ejecución final | Resultado |
| --- | --- |
| Suite IA dirigida | **305 aprobadas**, **8,51 s**, sin fallos |
| Regresión backend sin PostgreSQL | **738 aprobadas, 162 omitidas**, **33,79 s**, sin fallos |
| Casos anteriores / nuevos | **697 / 41**, sin sumar repeticiones |
| Ollama real, PostgreSQL y frontend | No ejecutados |

Las omisiones PostgreSQL son intencionales, no aprobaciones. Permanece el aviso
previo de Starlette/TestClient sobre httpx, sin instalar paquetes para ocultarlo.

La primera dirigida intermedia obtuvo 300 aprobaciones. Al añadir el caso de
65537 bytes, pytest generó un ID largo que superó el límite de 32767 caracteres
de una variable de entorno en Windows (setup/teardown). La ejecución dirigida
posterior obtuvo 304 aprobadas y dos errores de preparación; la regresión
intermedia, 737 aprobadas/162 omitidas y los mismos errores. Se asignaron IDs
cortos explícitos sin modificar la comprobación de tamaño ni los límites.
Las ejecuciones intermedias no constituyen aprobación final ni casos adicionales.

## 6. Futuro piloto autorizado — NO ejecutado

Después de resolver el preflight de RAM, identidad de procesos, destino/revisión
DB y ventana operativa, una futura autorización puede usar desde backend:

```powershell
# PROPUESTO, NO EJECUTADO: requiere autorización operativa posterior.
.\.venv\Scripts\python.exe -B -m app.presentation.cli.local_server --environment local-development --enable-llm --observe-llm --host 127.0.0.1 --port 8000
```

No agregar --enable-initial-provisioning para observar IA. Confirmar inicio
completo, socket/worker y endpoint antes de que el responsable introduzca sus
credenciales en React. Acordar una única consulta sintética sin secretos; observar
solo la línea de metadatos de esa llamada, RAM/latencia y códigos HTTP. No copiar
contenido generado, cabeceras o sesión al informe. No se requiere sonda adicional.

Para deshabilitar solo observación, un futuro reinicio autorizado omite
--observe-llm. Para deshabilitar también IA, omitir ambos flags. No editar .env,
modificar bases o detener Ollama de otros usos. No se realizó ese reinicio ahora.

## 7. Punto de control

No hubo inferencia, carga/descarga de modelos, llamadas al Ollama local, acceso a
PostgreSQL, migraciones, cambios de datos, instalaciones, reinicios o detenciones
de servicios. Las pruebas fueron aisladas; no se copiaron secretos operativos.
La memoria escasa y demás bloqueos del preflight 9.2.5C no se consideran resueltos
por instrumentar el adaptador. **Piloto real no iniciado; se espera revisión.**
