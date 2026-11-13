# Sprint 9.1: diseño de integración LLM con FastAPI

Fecha: **1 de noviembre de 2026**. **Propuesta pendiente de revisión**.
Solo diseño, documentación e inspección local. No se implementan endpoints,
servicios, formularios, dependencias, migraciones ni configuración operativa.

## 1. Alcance y decisión propuesta

Incorporar consultas individuales de texto: un usuario con acceso normal envía un
prompt desde React y FastAPI obtiene una respuesta de **Ollama local**, inicialmente
con **qwen2.5:1.5b**. ADMIN y USUARIO tienen el mismo permiso de consulta; una sesión
pendiente no puede acceder. No se usa la barrera de aprovisionamiento para autorizar IA.

Primera versión sin streaming al navegador, historial persistente, conversación
multiturno, adjuntos, RAG, embeddings, acceso a perfiles, navegación web, herramientas
o ejecución de código. Cada solicitud lleva solo su prompt y una instrucción fija
del servidor. No se guarda contenido en PostgreSQL: no hace falta migración.

El [cierre de Sprint 8](sprint-8-cierre.md) registra las ocho verificaciones manuales
comunicadas por el responsable. No se presenta esa evidencia como automatización.

## 2. Arquitectura existente y ubicación propuesta

Se inspeccionaron `bootstrap.py`, puertos y servicios de Application, dependencias
Bearer, routers/errores, configuración, pyproject y fixtures. En React se revisaron
AuthProvider, transporte, contratos, API de usuarios y rutas protegidas.

| Componente propuesto | Responsabilidad y conexión con el código actual |
| --- | --- |
| `application/ia/ports.py`: `LLMProvider` | Protocolo asíncrono de generación; no importa HTTPX, SDK, FastAPI ni SQLAlchemy |
| `application/ia/dto.py` | Entrada/salida inmutables y acotadas; contenido fuera de repr; sin objetos HTTP o JWT |
| `application/ia/use_cases/generar_respuesta.py` | Autorizar, validar, admitir carga, invocar proveedor y comprobar acceso antes de devolver |
| `application/ia/ports.py`: `NormalAccessAuthorizer`, `GenerationAdmission` | Separar autorización y admisión del proveedor; permitir dobles deterministas |
| `application/ia/exceptions.py` | Errores propios: prompt inválido, ocupación, indisponibilidad, timeout, respuesta inválida |
| `infrastructure/llm/ollama.py` | Adaptador HTTP de Ollama; mapea DTO, límites, protocolo y errores saneados |
| `infrastructure/llm/admission.py` | Cupo y límites de IA por proceso; sin reutilizar contadores de login/password |
| `infrastructure/configuration/llm.py` | Configuración independiente validada; nunca dentro de AuthConfig |
| `presentation/http/ia/schemas.py`, `router.py`, `dependencies.py` | Contratos Pydantic, endpoint, get_current_user y servicio en app.state |
| `bootstrap.py` | Componer proveedor/admisión/autoridad y cerrar cliente HTTP en lifespan |
| `frontend/src/features/ia/api/iaApi.ts` | POST mediante AuthContext.mutate y validación de respuesta unknown |
| `frontend/src/features/ia/pages/ConsultaIAPage.tsx` | Formulario, respuesta textual, carga, cancelación y errores |
| Router/AppShell y contratos compartidos | Ruta lazy `/ia` dentro de ProtectedRoute; enlace para ambos roles |

No se necesita inventar una entidad de dominio para una generación sin persistencia.
Domain conserva sus modelos actuales; las reglas de este flujo pertenecen a
Application. Solo el adaptador conoce el dialecto Ollama; permite sustituir proveedor
sin cambiar el caso de uso. No se importa un SDK en capas internas.

```mermaid
sequenceDiagram
    actor U as Usuario con acceso normal
    participant R as React /ia
    participant F as FastAPI /api/v1/ia/consultas
    participant A as Caso de uso y autorización
    participant P as Puerto LLM / adaptador HTTP
    participant O as Ollama 127.0.0.1:11434
    U->>R: Escribir consulta
    R->>F: POST JSON + Bearer
    F->>A: Principal y prompt validado
    A->>A: Revalidar acceso y adquirir cupo
    A->>P: Generar con límites del servidor
    P->>O: POST /api/generate, stream=false
    O-->>P: JSON de generación
    P-->>A: Resultado acotado o error saneado
    A->>A: Revalidar acceso; liberar cupo en finally
    A-->>F: Resultado permitido
    F-->>R: 200 JSON, no-store
    R-->>U: Mostrar texto sin ejecutar contenido
```

## 3. Interfaces, autorización y transacciones

Firmas orientativas, no código implementado:

- `LLMProvider.generate(input: GeneracionEntrada) -> Awaitable[GeneracionSalida]`.
  Entrada: prompt y límites del servidor; salida: texto y terminación normal/por límite.
- `NormalAccessAuthorizer.require_normal(principal)` valida estado actual de usuario,
  credencial y sesión. Se implementará mediante un método público de AuthService
  que encapsule `_normal` dentro de una UoW corta; no llamar métodos privados desde IA.
- `GenerationAdmission.try_acquire(principal)` devuelve una concesión o error de
  cupo. La concesión se libera en finally, incluso ante cancelación o fallo.
- `GenerarRespuesta.ejecutar(principal, datos)` coordina sin conocer HTTP ni Ollama.

Usar `get_current_user`, que ya exige acceso normal, y revalidar además en el caso
de uso antes de consumir recursos y antes de entregar la respuesta. Las pruebas
directas del caso de uso deben demostrar que saltarse HTTP no evita autorización.
Si revocan la sesión, desactivan el usuario o aparece obligación durante generación,
se descarta el resultado y se devuelve el 401/403 existente. No se entrega contexto
al proveedor sobre nombre, email, rol, UUID, JWT, sesiones o base de datos.

Las comprobaciones síncronas de AuthService/UoW se ejecutarán fuera del event loop
mediante el mecanismo de threadpool existente; no mantener transacciones, conexiones
de UoW o advisory lock durante la inferencia. El adaptador usará I/O asíncrono.
Sigue existiendo la pequeña carrera entre comprobación final y entrega HTTP, igual
que en otras lecturas autorizadas; no se promete revocación instantánea de bytes enviados.

## 4. Contrato HTTP propuesto

**POST `/api/v1/ia/consultas`**, Bearer obligatorio y JSON estricto:

```json
{"prompt":"Explicá brevemente qué es una API REST."}
```

Único campo aceptado: `prompt`. Sin usuario_id, modelo, URL, historial, system,
tools, opciones, credenciales o elección de límites desde el cliente.
Prompt requerido, string, no vacío ni solo espacios, Unicode válido sin NUL:
máximo **1000 puntos de código y 3000 bytes UTF-8**. Se comprueba vacío con una
vista sin espacios, pero se conserva el texto original válido; no truncar ni
normalizar silenciosamente. Máximo cuerpo HTTP **16 KiB**, comprobado por bytes
reales incluso si falta Content-Length o se usa transferencia fragmentada.

Respuesta **200**:

```json
{"respuesta":"Una API REST permite…","finalizacion":"completa"}
```

`respuesta`: texto no vacío, Unicode válido, hasta **4096 puntos/16 KiB UTF-8**.
`finalizacion`: `completa` o `limite`, para informar corte por presupuesto. No
devolver prompt, identidad, modelo interno, métricas brutas o respuesta upstream.
`Cache-Control: no-store` en éxito y errores de IA. JSON normal; no SSE/NDJSON público.

| HTTP / código propuesto | Tratamiento |
| --- | --- |
| 401 AUTENTICACION_REQUERIDA | JWT/sesión inválidos, revocados, vencidos o usuario inactivo; autoridad actual |
| 403 CAMBIO_PASSWORD_REQUERIDO | Sesión pendiente, también ADMIN; no invocar proveedor |
| 413 SOLICITUD_DEMASIADO_GRANDE | Límite real de cuerpo excedido |
| 422 PROMPT_INVALIDO | Contenido vacío, longitud o Unicode no válidos |
| 422 SOLICITUD_INVALIDA | Campos extra, ausentes o tipos incorrectos; formato existente saneado |
| 429 IA_LIMITE_INTENTOS | Límite de consultas; Retry-After en segundos |
| 503 IA_OCUPADA | Generación concurrente o período de enfriamiento; Retry-After |
| 503 IA_NO_DISPONIBLE | Módulo deshabilitado, modelo ausente, conexión fallida o proveedor sin capacidad |
| 504 IA_TIEMPO_AGOTADO | Deadline del proveedor vencido |
| 502 IA_RESPUESTA_INVALIDA | JSON/estructura/tamaño/contenido upstream inválido o fallo de protocolo |
| 500 ERROR_INTERNO | Fallo inesperado saneado |

Reutilizar envoltorio `{error:{codigo,mensaje,detalles?}}`; jamás copiar mensaje,
cuerpo o traceback del proveedor. No mapear un 401 upstream a 401 del usuario.
Se ampliarán explícitamente `documented_errors`, allowlists de campos/códigos y
validadores React: actualmente no contemplan todos estos estados ni `body.prompt`.
El exceso de cuerpo se limita antes de acumularlo; con cuerpo admisible, autorización
normal precede al uso de IA. No se exige un orden entre 413 y 401 ante cuerpo abusivo.

## 5. Ollama, protocolo y configuración prevista

Proponer HTTP nativo con HTTPX, sin SDK Ollama. El adaptador usará
`POST http://127.0.0.1:11434/api/generate`, `stream=false`, modelo fijo del servidor,
`options.num_predict=256`, `options.num_ctx=4096` y `keep_alive=0`.
La [API oficial](https://docs.ollama.com/api/generate) documenta el formato de
generación; los parámetros de presupuesto/contexto se contrastan con
[Modelfile](https://docs.ollama.com/modelfile). Son propuestas, no ajustes aplicados.

No enviar contexto anterior, herramientas ni campos de pensamiento; no consumir
ni ejecutar tool calls aunque el modelo anuncie esa capacidad. Instrucción fija
breve: responder en español como texto informativo, sin pretender operar el sistema.
Su contenido será público, sin secretos, y no sustituye controles de autorización.

Validar status 200, JSON objeto, modelo esperado, `done=true`, `response` string
no vacío y límites; mapear terminación `stop`/`length` a completa/límite, rechazar
terminación desconocida. Limitar **64 KiB de cuerpo upstream** durante la lectura,
no confiar solo en Content-Length ni acumular un JSON ilimitado. Aunque Ollama no
emita streaming lógico, HTTPX puede leer chunks para hacer cumplir ese máximo.
Ignorar métricas/campos adicionales no usados sin reenviarlos al cliente.

Contexto total incluye plantilla, instrucción, prompt y salida. El máximo textual
no equivale a un conteo exacto de tokens. Validar en 9.2 los casos extremos con
tokenización del modelo y acotar el prompt si no cabe; no habilitar un flujo que
dependa de truncamiento oculto de Ollama. El límite de salida lo impone num_predict
y se verifica además el tamaño textual recibido; caracteres y tokens son distintos.

| Configuración propuesta | Valor inicial / validación |
| --- | --- |
| LLM_ENABLED / TEST_LLM_ENABLED | false por defecto; pruebas usan proveedor falso inyectado |
| LLM_PROVIDER | ollama local; sin fallback automático a nube |
| LLM_BASE_URL | Exactamente http://127.0.0.1:11434 para el piloto; sin usuario, path, query, DNS o redirecciones |
| LLM_MODEL | qwen2.5:1.5b, allowlist del servidor; verificar existencia, registrar digest de modelo para reproducibilidad cuando se implemente |
| LLM_MAX_PROMPT_CHARS / BYTES | 1000 / 3000; no admitir aumentos fuera de techos aprobados |
| LLM_MAX_OUTPUT_TOKENS / NUM_CTX | 256 / 4096; nunca valores ilimitados como -1 |
| LLM_MAX_CONCURRENT | 1, proceso único; no configurable al alza en el piloto |
| LLM_TIMEOUT_SECONDS | 60, deadline total; no confundir con timeout por fragmento |
| LLM_KEEP_ALIVE | 0 para liberar tras respuesta; no equivale a garantizar borrado seguro de RAM |

Crear `LLMConfig` separado con carga TEST_LLM_* independiente; no leer configuración
operativa al ejecutar pruebas de IA. Nada se añade a `.env` en 9.1. IA deshabilitada
no debe impedir login ni resto de la aplicación. Con IA habilitada, un proveedor
ausente da 503 para IA sin tumbar los servicios de usuarios.

Cliente `httpx.AsyncClient` único por lifespan, `trust_env=False`, sin redirecciones,
sin cookies/Authorization de usuario ni hooks de cuerpos; conexión 2 s, pool 1 s,
escritura 5 s, lectura 55 s y deadline exterior **60 s** con cancelación estructurada.
Frontend espera hasta 70 s. [HTTPX distingue timeouts por operación](https://www.python-httpx.org/advanced/timeouts/),
por lo que el timeout de lectura no limita por sí solo toda una generación.
Su [cliente asíncrono](https://www.python-httpx.org/async/) permite integrar I/O sin
bloquear el event loop. Se cerrará en lifespan, también ante fallo de arranque.

No arrancar Ollama, descargar modelos ni cambiarlo desde FastAPI. Las únicas rutas
upstream de la integración serán generación y verificaciones de metadatos; nunca
pull/create/delete, ejecución, web search o administración. React no llama a 11434
ni requiere abrir CORS de Ollama. Mantener bind loopback y comprobarlo antes del
piloto; sin proxy público hacia Ollama, túneles o LAN.

## 6. Consumo de recursos y experiencia React

Un solo worker FastAPI para el piloto; un cupo global de generación y sin cola
de espera dentro de la aplicación. Adquisición atómica no bloqueante: la segunda
solicitud recibe 503 inmediatamente y no llega a Ollama. Un límite de conexiones
HTTPX por sí solo no sustituye este control.

Límites de IA separados de autenticación: **5 solicitudes admitidas por usuario y
15 globales por minuto**, ventanas monotónicas; solo consumir tras validación y
adquisición del cupo. Los fallos de proveedor también consumen para evitar tormentas
de reintentos. Contadores en memoria, TTL y máximo 1024 entradas; si se llena el
registro, rechazar nuevas admisiones sin expulsar un cupo activo para eludir límites.
No guardar prompts ni IDs en logs. Reiniciar borra estos límites: limitación aceptable
para el piloto local, no solución distribuida. No reutilizar AuthService.limiter ni
sus claves, ventanas o tabla auth_intentos.

Ante timeout/cancelación cerrar transporte y liberar concesiones en finally;
introducir enfriamiento global de 30 s tras timeout para evitar reenvíos inmediatos.
Cerrar HTTP no prueba que Ollama haya detenido su cálculo; no prometer aislamiento
duro de CPU/RAM ni límite global sobre otros clientes del servicio. Si el piloto
muestra generaciones que sobreviven a cancelación, bloquear nuevas inferencias y
resolver supervisión/cancelación antes de ampliar uso. No matar procesos desde IA.

La pantalla `/ia` mantiene un único formulario y respuesta actual, sin historial.
Etiqueta visible, contador de longitud, estado accesible de carga y botón Cancelar.
Respuesta como texto escapado con saltos de línea, sin HTML/Markdown ejecutable ni
links automáticos. Advertir que puede equivocarse y que no se deben enviar secretos.
No usar dangerouslySetInnerHTML, eval ni interpretar JSON del modelo como acciones.

Reutilizar `useAuth().mutate('/ia/consultas','POST',...,200)`; verificar el contrato
de respuesta. `AuthProvider` ya cancela por logout/cambio de generación y bloquea
sesiones pendientes: conservar ese camino, no exponer el token ni crear otro cliente
autenticado. Los errores 401/403 mantienen semántica actual; 502/503/504 de IA no
destruyen una sesión válida. Registrar códigos en ApiError, no mensajes arbitrarios.
No reenviar automáticamente tras timeout/red, aunque no haya escritura de negocio:
puede seguir consumiendo recursos upstream. Limpiar prompt/respuesta al abandonar
la página, logout o cambio de sesión; sin localStorage, URL, analítica o persistencia.

## 7. Inspección local efectivamente realizada

Inspección de lectura el **1 de noviembre de 2026**; no prueba de generación.

| Elemento | Observado |
| --- | --- |
| Ollama instalado | Sí, ejecutable en PATH y ubicación local convencional |
| Servicio ya existente | ollama.exe, PID 228; listener **127.0.0.1:11434** |
| GET /api/version | Responde; versión **0.40.7** |
| GET /api/tags | Modelos disponibles listados en tabla siguiente |
| GET /api/ps | Ningún modelo cargado al consultar |
| POST /api/show del candidato | Solo metadatos: completion y tools, arquitectura qwen2, contexto declarado 32768 |
| Sistema | Windows 10 Pro x64 |
| CPU | Intel Core i7-8565U, 4 núcleos / 8 hilos |
| RAM visible / libre | **7,85 GiB / 567 MiB** aproximadamente; muestra variable |
| GPU física observada | Intel UHD Graphics 620; Windows informa 1 GiB de AdapterRAM, no prueba de VRAM dedicada o aceleración compatible |
| Espacio libre C: / D: | Aproximadamente **44,2 / 111,4 GiB**, variable |

| Modelo ya disponible | Tamaño en disco observado | Cuantización |
| --- | ---: | --- |
| qwen2.5:1.5b | 986061892 bytes, unos 940 MiB | Q4_K_M |
| qwen3:1.7b | 1359293444 bytes | Q4_K_M |
| nomic-embed-text:latest | 274302450 bytes | F16 |

El candidato existe localmente y ofrece completion; la
[biblioteca oficial](https://ollama.com/library/qwen2.5) publica esa variante.
Esto acredita disponibilidad y compatibilidad declarada del protocolo, **no una
inferencia exitosa o rendimiento suficiente**. El modelo de embeddings no sustituye
al generador y no se incorpora en esta etapa.

**Evaluación:** CPU es el punto de partida conservador; no se certifica aceleración
de UHD 620 ni se instalarán drivers. La [guía oficial de hardware](https://docs.ollama.com/gpu)
requiere comprobar compatibilidad específica. Tamaño de archivo no equivale a RAM
total de ejecución: runtime, contexto, sistema, navegador, FastAPI y PostgreSQL suman.
Con solo 567 MiB libres, **no se recomienda iniciar inferencia real en el estado
observado**. Antes del piloto recuperar margen; proponer al menos 2 GiB libres
como control operativo inicial, sujeto a medición, sin garantizar suficiencia.
No se cerraron programas ni se cargó/descargó ningún modelo para medirlo.

La [API de modelos](https://docs.ollama.com/api/tags) permite listar sin generar.
La inspección se limitó a comandos de inventario, metadatos de Python y esas cuatro
rutas de metadatos; /api/show usa POST de consulta y no carga ni altera el modelo.
No se consultaron prompts, respuestas, archivos personales o datos de usuarios.

## 8. Dependencias y pruebas previstas

En el entorno virtual existente: **httpx 0.28.1**, FastAPI 0.162.0 y Uvicorn 0.54.0
instalados; SDK `ollama`, `requests` y `aiohttp` no instalados. No se instaló nada.
HTTPX figura actualmente solo en el extra `dev` de pyproject; para usarlo en ejecución
habrá que declararlo como dependencia runtime explícita, inicialmente la misma
versión instalada y sin forzar actualizaciones. Revisar compatibilidad antes de
aprobar ese cambio en 9.2; no depender accidentalmente del extra de tests.
No se propone SDK, LangChain, base vectorial ni dependencia frontend nueva.

| Nivel / escenario | Criterio previsto |
| --- | --- |
| Application con proveedor falso | Respuesta exitosa y límites entregados al puerto; sin HTTP real |
| Validación | Vacío, espacios, 1000/1001 puntos, bytes límite, astrales, Unicode inválido, NUL y campos extra |
| HTTP sin sesión | 401; proveedor nunca llamado |
| ADMIN/USUARIO normal y pendiente | Ambos normales permitidos; ambos pendientes 403; casos directos sin transporte |
| Revocación/baja durante generación | Resultado descartado en comprobación final; sin fuga al cliente |
| Error de conexión/modelo ausente | 503 saneado; ninguna respuesta upstream expuesta |
| Timeout / cancelación | 504 o cancelación del cliente; cierre de transporte, liberación y enfriamiento, sin reintento |
| Proveedor inválido | JSON roto, done=false, texto vacío/tipo incorrecto, terminación desconocida o exceso real de bytes → 502 |
| Concurrencia | Falso bloqueado con barreras/eventos: uno admitido, siguiente 503 sin llamada; recuperación tras liberar |
| Límites de IA | Reloj controlado, ventanas, TTL/cota, 429/Retry-After y separación total de contadores auth |
| Adaptador con HTTPX MockTransport | Payload exacto, URL fija, sin JWT/cookies, num_predict/num_ctx, error, cuerpo fragmentado grande y redirects rechazados |
| Logs/errores/repr | Cadenas centinela ficticias de prompt/respuesta/token nunca reproducidas |
| React/MSW | Éxito, carga, validación, cancelación, errores, respuestas tardías, logout y eliminación de contenido entre usuarios |
| Aislamiento | Unidad sin configuración operativa; cualquier integración DB solo usuarios_test:5435 tras require_test_database y lectura real |

Tests no deben llamar al Ollama real ni asumir que está instalado. Sustituir
proveedor, transportes, configuración, reloj y admisión; usar eventos sin sleeps
largos. No instalar pytest-asyncio automáticamente: diseñar tests con herramientas
existentes, asyncio.run para unidades y TestClient para HTTP.
Los tests HTTP de IA se compondrán con AuthService en memoria y proveedor falso;
no requieren nuevas tablas. Nunca fixtures o pruebas automatizadas en usuarios_dev.

Una futura prueba real de inferencia será opt-in, con texto ficticio, sin datos
de usuarios ni consulta a desarrollo y tras controlar RAM. Medirá carga fría,
latencia, memoria, límites y cancelación. No se ejecutó aquí ni se confunde con
los GET/POST de metadatos. Las regresiones de Sprint 8 no se reejecutaron en 9.1.

## 9. Riesgos y controles

| Riesgo | Control o limitación |
| --- | --- |
| Eludir cambio obligatorio/rol | Acceso normal en dependencia y caso de uso, antes y después de inferencia |
| Agotar RAM/CPU | Un cupo, sin cola, contexto/salida acotados, límites separados, margen de RAM y benchmark antes de piloto |
| SSRF o salida a nube | URL literal loopback, modelo allowlist local, sin redirects ni trust_env, sin endpoints arbitrarios |
| Prompt injection o salida maliciosa | Modelo sin herramientas, datos privados ni permisos; respuesta tratada solo como texto no confiable |
| Fuga entre usuarios | Sin memoria conversacional, caché compartida de respuestas, historial ni contexto de perfiles; limpieza por sesión |
| Logs sensibles | DTO repr oculto, SecretStr en transporte de entrada, sin dumps de validación/input/ctx, cuerpos, analítica ni trazas HTTP |
| Falsa confidencialidad | Prohibir secretos en UI; auditar también logs propios de Ollama antes del piloto; no se afirma haber verificado retención del servicio |
| Falsa exactitud | Aviso de respuesta generada, sin uso como autorización ni decisión crítica automática |
| Cancelación incompleta | No prometer detener cómputo por cerrar conexión; enfriamiento, observar y bloquear ampliación si persiste |
| Múltiples workers/clientes Ollama | Controles de memoria solo por proceso; piloto de un worker, sin otros generadores concurrentes; diseño distribuido futuro |
| Arranque o caída de Ollama | Login/usuarios independientes; IA deshabilitable y 503 saneado; sin autoarranque o autodownload |

La [FAQ oficial](https://docs.ollama.com/faq) describe bind local, retención en RAM
y controles del servicio. No se cambiaron variables OLLAMA_*, configuración cloud,
colas, paralelismo o logs; la aplicación futura no debe asumir que controla otros
clientes ni que el funcionamiento local demuestra ausencia de registro sensible.
Verificar licencia del modelo y riesgos de dependencias antes de ampliar distribución.

## 10. Implementación incremental propuesta para 9.2

| Incremento futuro | Entrega | Aceptación |
| --- | --- | --- |
| 9.2.1 Puertos y caso de uso | DTO, errores, autorización normal pública, proveedor falso y admisión | Sin frameworks internos; límites/auth/concurrencia probados sin Ollama/DB real |
| 9.2.2 Adaptador/configuración | HTTPX runtime declarado, LLMConfig y cliente lifespan | URL/modelo cerrados, timeout total, tamaños, cancelación y MockTransport aprobados |
| 9.2.3 FastAPI | POST, esquemas, DI, no-store y errores documentados | Matriz de acceso normal/pendiente y sesión cambiada; sin nuevos permisos ni tablas |
| 9.2.4 React | Ruta protegida, formulario y salida textual | Misma sesión/cliente, MSW, validación, limpieza por logout y errores accesibles |
| 9.2.5 Integración local opt-in | Inferencia ficticia y medición con RAM disponible | Modelo existente, sin pull, sin acceso a usuarios_dev por pruebas y presupuesto estable |

Antes de implementar, aprobar endpoint/DTO, límites propuestos, promoción runtime de
HTTPX, política de IA de un worker y manejo de cancelación. El benchmark puede
obligar a reducir salida o ajustar deadline mediante revisión; no elevar límites
automáticamente ni instalar un modelo alternativo. Si no hay margen de RAM,
continuar únicamente con dobles y dejar el piloto real pendiente.

**Entregables de 9.1:** actualización de 8.6D, cierre breve de Sprint 8 y este
diseño con inspección. No se modificaron código funcional, dependencias, bases o
configuración, ni se iniciaron/reiniciaron servicios. No se enviaron prompts ni
se ejecutaron tests, benchmarks o generaciones. Se detiene el trabajo y se espera
revisión del diseño antes de comenzar **Sprint 9.2**.
