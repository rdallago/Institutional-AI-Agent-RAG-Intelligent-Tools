# Sprint 9.2.2: adaptador Ollama, configuración y ciclo de vida

Fecha: **2 de noviembre de 2026**. Estado: **implementado y verificado en aislamiento**.
Alcance: infraestructura preparada y pruebas
aisladas. **No se conecta al arranque operativo, no se expone un endpoint IA y
no se ejecuta inferencia real**. No se inicia 9.2.3.

## 1. Archivos creados y modificados

Nuevos:

- `backend/src/app/infrastructure/configuration/llm.py`.
- `backend/src/app/infrastructure/llm/ollama.py`.
- `backend/constraints-httpx.txt`.
- `backend/tests/ia/test_llm_configuration.py`.
- `backend/tests/ia/test_ollama_adapter.py`.
- `docs/sprint-9-2-2-adaptador-ollama.md`.

Modificados: `backend/pyproject.toml`, que promueve HTTPX a runtime, y
`backend/README.md`, con instrucciones y alcance del bloqueo parcial.

El núcleo de 9.2.1, AuthService, JWT, roles, sesiones y aprovisionamiento no cambian.
No se modifican bootstrap, routers, React, `.env`, `.env.test`, Docker, bases o
migraciones. No se reinician servicios ni se instalan paquetes.

## 2. Configuración y aislamiento

`LLMConfig` es frozen/slots e independiente de AuthConfig. IA queda deshabilitada
por defecto. Habilitarla en una futura composición exige `enabled=True` y entorno
`local-development`; producción no admite habilitación. No se admite un selector
de proveedor externo ni fallback de modelo.

| Campo | Valor/validación |
| --- | --- |
| enabled | Booleano estricto; false por defecto |
| environment | disabled por defecto; habilitación operativa solo local-development |
| testing | Booleano estricto; exige environment=test |
| base_url | Exactamente `http://127.0.0.1:11434`, sin otras variantes |
| model | Allowlist de un elemento: `qwen2.5:1.5b` |
| timeout_seconds | Número finito positivo, máximo 60; 60 por defecto |
| max_concurrent | 1 fijo, no elegible en constructor |

`load_llm_config()` carga únicamente LLM_* del archivo operativo y esas variables
de proceso. `testing=True` usa únicamente TEST_LLM_* y `.env.test`, sin fallback a
LLM_* ni `.env`. Interpolación de dotenv deshabilitada. Errores de configuración
constantes sin reproducir valores; se prueban archivos temporales ficticios.
No se añadieron valores a los archivos operativos.

**Protección adicional de pruebas:** una configuración testing habilitada no puede
crear el adaptador sin `httpx.MockTransport`. Se rechazan transportes reales en ese
modo y overrides MockTransport en configuración operativa. Los tests de configuración
no leen archivos operativos ni abren sockets. `OLLAMA_HOST`, proxies y otras variables
no reemplazan la URL literal del adaptador.

La configuración describe el piloto local: no prueba todavía la escucha del futuro
servidor HTTP ni impone workers sobre una aplicación que no está compuesta. Esas
condiciones deberán validarse al habilitar la integración posterior; aquí no se
cambia el servidor existente ni se activa IA operativamente.

## 3. Dependencia y reproducibilidad

HTTPX **0.28.1**, ya instalado, pasa de `[project.optional-dependencies].dev` a
`[project].dependencies` con versión exacta. No se ejecutó pip install ni se
actualizó el entorno o su metadata editable.

El proyecto no tenía lock completo de transitivas Python. Se añadió
`constraints-httpx.txt` con el árbol runtime observado para Python 3.14:

| Paquete | Versión instalada y fijada |
| --- | --- |
| httpx | 0.28.1 |
| httpcore | 1.0.9 |
| anyio | 4.15.1 |
| certifi | 2026.10.23 |
| idna | 3.20 |
| h11 | 0.16.0 |
| typing_extensions | 4.16.0 |

Se verificó por metadata que las siete versiones coinciden con lo instalado.
El archivo es un **bloqueo parcial**, sin hashes ni resolución completa del proyecto:
no se presenta como lock reproducible de todas sus dependencias. En la preparación
de un entorno nuevo debe aplicarse explícitamente con `-c constraints-httpx.txt`,
como documenta backend/README.md. No introduce paquetes extra de HTTPX, SDK Ollama,
requests, aiohttp o dependencias frontend. `pip check` aprobó; no es una auditoría CVE.

## 4. Contrato exacto upstream

`OllamaProvider` implementa estructuralmente `LLMProvider`. Construye únicamente:

```text
POST http://127.0.0.1:11434/api/generate
Accept: application/json
Accept-Encoding: identity
```

```json
{
  "model": "qwen2.5:1.5b",
  "prompt": "<texto validado recibido por el puerto>",
  "stream": false,
  "options": {"num_predict": 256, "num_ctx": 4096},
  "keep_alive": 0,
  "system": "Responde en espanol con informacion breve y clara. No operas sistemas ni ejecutas acciones."
}
```

La instrucción es una constante del servidor y no contiene secretos ni incorpora
identidad. Se usa el campo `system` del endpoint, sin `raw=true`, plantillas externas,
tools o contexto anterior. La [documentación oficial de generate](https://docs.ollama.com/api/generate)
admite `system` con el prompt; la inspección de 9.1 confirmó capacidad completion
del modelo local. Esto acredita compatibilidad declarada; **no se probó una respuesta
real del modelo en este incremento**.

Se vuelve a validar el prompt al entrar al adaptador. Ningún campo de ConsultaDatos
permite cambiar URL/modelo/system/opciones; el payload usa constantes del servidor.
No se envían Principal, roles, UUID, perfiles, claves, JWT o datos PostgreSQL.

No hay otras rutas upstream, descargas, comprobaciones reales de disponibilidad,
autoarranque, administración del modelo o generación de herramientas. Una futura
revisión de metadatos no se implementó como efecto secundario de construir el cliente.

## 5. Cliente compartido y ciclo de vida

`ollama_runtime(config, transport=...)` es un context manager async que entrega
un `LLMRuntime` con proveedor, una admisión compartida y timeout total configurado.
Está preparado para que la futura composición lo abra una vez por lifespan, lo
comparta y lo cierre al salir; **no se invoca desde bootstrap todavía**.

Con IA deshabilitada entrega `DisabledLLMProvider`, que rechaza con IANoDisponible,
sin construir cliente HTTP. Habilitada, crea un único AsyncClient propiedad del
adaptador y lo reutiliza entre consultas del contexto. No recibe clientes externos
con configuración de auth/proxy desconocida.

- trust_env=False; sin redirecciones ni auth heredada.
- Una conexión máxima y una keepalive máxima; transporte sin reintentos del adaptador.
- Timeouts HTTPX: conexión 2 s, escritura 5 s, lectura 55 s, pool 1 s.
- Sin cabeceras de identidad. Authorization/Cookie se eliminan explícitamente antes
  del envío; un Set-Cookie upstream no se reutiliza en la siguiente consulta y la
  cookie jar se limpia en finally.
- Cada respuesta se cierra en finally, también ante exceso de tamaño, error o cancelación.
- El cliente/transporte se cierran al salir del contexto, incluso con errores de
  preparación de la aplicación. El cierre se protege frente a cancelaciones repetidas,
  recuperando excepciones sin exponer sus mensajes.

Se contrastó la gestión de conexiones con la [guía async de HTTPX](https://www.python-httpx.org/async/)
y el código de la versión instalada. La lectura HTTP se hace con stream=True para
acotar bytes; **no es streaming lógico de Ollama**, cuyo payload mantiene stream=false.

La admisión de 9.2.1 conserva un cupo, cuotas y enfriamiento. El pool HTTP no la
sustituye. El consumidor futuro debe usar la admisión del runtime y
`GenerarRespuesta(..., timeout_seconds=runtime.timeout_seconds)`; no crear un runtime
por solicitud ni varios workers para el piloto. La prueba de integración aislada
demuestra esa composición sin FastAPI o PostgreSQL.

## 6. Validación de respuesta y errores

Únicamente HTTP 200 entra a parsing. Se rechaza contenido comprimido no identity
en vez de descomprimir sin control. Se acumula como máximo **65536 bytes reales**,
comprobando antes de extender el buffer; Content-Length no determina la aceptación.
Se acepta exactamente ese máximo si contiene JSON válido y espacios finales.
Los mocks precargados pasan la misma cota; el transporte real usa lectura fragmentada.

Se exige UTF-8 válido y JSON objeto, sin campos duplicados ni NaN/Infinity; modelo
exacto, done booleano true, response válido y done_reason en stop/length. Se mapean
a `GeneracionSalida.finalizacion` completa/limite. Se aplican nuevamente los límites
de 9.2.1: respuesta no vacía, sin NUL/surrogates, 4096 puntos/16384 bytes. Métricas y
campos extra no usados se ignoran, nunca se devuelven como respuesta bruta.

| Fallo upstream | Excepción de Application |
| --- | --- |
| Conexión/red interrumpida, HTTP 404/429/500/502/503 | IANoDisponible |
| Timeout de HTTPX, HTTP 408/504 | IATiempoAgotado |
| Redirección, HTTP distinto de los anteriores/200, incluido 401/403 | IARespuestaInvalida |
| JSON, campos, UTF-8, tamaño, compresión o protocolo inválidos | IARespuestaInvalida |
| Fallo inesperado o fallo técnico de cierre | IARespuestaInvalida saneada |
| Cancelación de tarea | CancelledError propagado tras limpieza |

No se confunde autenticación upstream con autorización del usuario. Las respuestas
de error upstream no se copian ni se necesita consumir sus cuerpos. No se registran
prompts, respuestas o mensajes de excepciones de transporte; mensajes propios
constantes y cadenas públicas de causa suprimidas. Los tests verifican logs,
mensajes, repr y traceback formateado con centinelas ficticios.

El **deadline total lo sigue imponiendo GenerarRespuesta**, no el timeout de lectura
por fragmento. La prueba bloqueada de 10 ms comprueba cancelación, cierre, liberación
y enfriamiento de 30 s. Una cancelación externa libera sin convertirla en timeout,
conforme a 9.2.1. No se introdujeron reintentos.

## 7. Pruebas ejecutadas

Todas las pruebas nuevas usan MockTransport/dobles. Incluyen payload y URL exactos,
system fijo, ausencia de identidad/cookies, proxy ignorado, límites del cliente,
respuesta válida y length, protocolo/JSON inválido, 401/403 upstream, indisponibilidad,
timeouts, redirecciones sin segunda solicitud, máximo exacto/fragmentado/falso
Content-Length, compresión rechazada, cancelación/deadline, cierre repetidamente
cancelado, errores de cierre, configuración y ausencia de fallback operativo en tests.

Comandos desde backend:

```powershell
.\.venv\Scripts\python.exe -B -m pytest -q tests/ia -p no:cacheprovider --basetemp=.pytest-tmp-922-ia-final-20261102 --tb=short
.\.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider --basetemp=.pytest-tmp-922-regression-20261102 --tb=short
.\.venv\Scripts\python.exe -B -m pip check
```

| Comprobación | Resultado |
| --- | --- |
| Primeros casos nuevos de adaptador/configuración | **87 aprobados**, 1,98 s |
| Suite IA final, con dos casos adicionales | **170 aprobados**, 4,56 s: 81 anteriores y 89 nuevos |
| Regresión backend sin PostgreSQL | **603 aprobadas, 162 omitidas**, sin fallos, 28,35 s; 514 anteriores y 89 nuevas |
| Versiones de constraints y declaración runtime | Coinciden con las siete instaladas; sin instalaciones |
| Independencia de Application IA, AST | Sin imports HTTPX/Ollama/FastAPI/SQLAlchemy/infraestructura |
| pip check | No broken requirements found |

No se cuentan repeticiones como casos nuevos. Las **162 integraciones PostgreSQL**
quedan omitidas intencionalmente sin --run-postgres, no se informan como aprobadas.
No se ejecutaron pruebas frontend porque no hubo cambios React.
Permanece el aviso previo Starlette/TestClient sobre httpx; no se actualizaron
dependencias para ocultarlo. No hubo fallos en las ejecuciones indicadas.

## 8. Riesgos, límites y preparación de 9.2.3

No se accedió a usuarios_dev, usuarios_test o Ollama real. No se cargaron modelos,
ejecutó ollama run, descargó, generó texto, migró o reinició FastAPI/React. Las
configuraciones de práctica y la barrera de aprovisionamiento permanecen sin cambios.
Solo se consultó documentación oficial y metadata/código local de dependencias.

Cerrar HTTP no garantiza detener el cómputo del servidor. La limpieza protegida
requiere que el transporte coopere al cerrar; no existe una garantía de matar
operaciones externas o de cierre instantáneo ante un transporte defectuoso.
No se midieron RAM, tokenización efectiva, truncamiento, latencia o cancelación real
de qwen2.5. El tamaño de contexto y la instrucción tienen compatibilidad declarada;
el piloto real sigue pendiente con controles de recursos del diseño 9.1.

Para 9.2.3 quedan composición en lifespan, configuración explícita del piloto,
validación operativa de loopback/un worker, endpoint autenticado, límite HTTP de
16 KiB, no-store y traducción/documentación de errores. IA deshabilitada deberá
preservar el resto del sistema. No se adelantó ningún endpoint ni se habilitó
la configuración actual. Se detiene exclusivamente en **9.2.2**, pendiente de revisión.

## 9. Contraste con la solicitud ampliada y semántica de done_reason

Revisión adicional: **2 de noviembre de 2026**. La implementación ya existente se
contrastó con la nueva solicitud del mismo Sprint 9.2.2, sin reconstruirla ni avanzar
al incremento siguiente. Se ajustó únicamente la procedencia de los presupuestos
del payload: `num_predict` y `num_ctx` ahora toman los campos de GeneracionEntrada,
fijos en 256/4096 y no elegibles en su constructor. No se agregan parámetros del
usuario ni se cambian los contratos de Application. Se conserva la instrucción
fija del servidor aprobada en la solicitud anterior, aunque el payload orientativo
de la solicitud ampliada no la enumere.

Se verificó el protocolo mediante fuentes primarias, sin consultar el servicio
local ni ejecutar generación:

- El [tipo oficial GenerateResponse](https://github.com/ollama/ollama/blob/main/api/types.go)
  declara done_reason con `omitempty`: el protocolo puede omitirlo.
- La [conversión oficial DoneReason](https://github.com/ollama/ollama/blob/main/llm/server.go)
  identifica stop y length, y contempla razón interna de conexión cerrada sin
  convertirla necesariamente en una cadena reconocida de terminación normal.

Por tanto, **done=true sin done_reason no permite afirmar completa ni limite**.
Se mantiene el rechazo con IARespuestaInvalida si falta, está vacío o es desconocido;
no se inventa completa como valor predeterminado ni se infiere por eval_count.
Es una restricción de compatibilidad explícita de este adaptador, coherente con
el diseño aprobado, **no una afirmación de que Ollama siempre exige ese campo**.
load/unload tampoco son resultados de texto admitidos por esta operación.
Aceptar una respuesta sin razón requeriría acordar otro contrato o una política
de compatibilidad revisada; no se altera aquí el DTO de dos finalizaciones.

Las fuentes corresponden al código oficial consultado en esta fecha, no a una
certificación de cada versión instalada. No se verificó empíricamente qué razón
devuelve el servicio local 0.40.7 observado históricamente en 9.1.

Se añadieron seis casos explícitos: razón ausente, vacía, load, unload, lista y
número. La suite IA actual obtuvo **176 aprobadas**, 6,26 s. Incluye los casos
anteriores de éxito stop, límite length y respuesta desconocida. La regresión
actual obtuvo **609 aprobadas y 162 omitidas**, sin fallos, en **27,71 s**.
Las 162 PostgreSQL no se ejecutaron ni se presentan como aprobadas. Permanece el
aviso previo Starlette/TestClient sobre httpx. Los resultados de la sección 7
se conservan como ejecución anterior, no como resultados acumulados.

```powershell
.\.venv\Scripts\python.exe -B -m pytest -q tests/ia -p no:cacheprovider --basetemp=.pytest-tmp-922-review-ia-20261102 --tb=short
.\.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider --basetemp=.pytest-tmp-922-review-full-20261102 --tb=short
```

En esta revisión no se instalaron paquetes, modificaron dependencias, conectaron
bases, ejecutaron migraciones o reiniciaron servicios. No se cargaron modelos ni
se envió ningún prompt real. React, configuración operativa, autenticación y
aprovisionamiento permanecen sin cambios. **9.2.3 no iniciado**.
