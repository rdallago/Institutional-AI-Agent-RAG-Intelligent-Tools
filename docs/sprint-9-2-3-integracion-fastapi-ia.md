# Sprint 9.2.3: integración FastAPI del servicio IA

Fecha: **2 de noviembre de 2026**. Estado: **implementado y verificado en aislamiento**
el endpoint y su composición. **IA deshabilitada por defecto**, sin inferencia real
ni activación operativa. No se inicia 9.2.4.

## 1. Arquitectura y archivos

Se revisaron los informes aprobados 9.2.1/9.2.2, su diseño y el código real de
Application, runtime Ollama, composición, autenticación, errores y pruebas.
La integración reutiliza GenerarRespuesta, AuthServiceNormalAccessAuthorizer,
MemoryGenerationAdmission y ollama_runtime. No copia reglas de seguridad o generación.
Application y Domain permanecen sin dependencias HTTP.

Archivos nuevos:

- `backend/src/app/presentation/http/ia/__init__.py`.
- `backend/src/app/presentation/http/ia/schemas.py`.
- `backend/src/app/presentation/http/ia/dependencies.py`.
- `backend/src/app/presentation/http/ia/router.py`.
- `backend/src/app/presentation/http/ia/middleware.py`.
- `backend/src/app/infrastructure/configuration/llm_local.py`.
- `backend/tests/ia/test_http_ia.py`.
- `backend/tests/ia/test_ia_lifespan.py`.
- `docs/sprint-9-2-3-integracion-fastapi-ia.md`.

Modificados:

- `backend/src/app/bootstrap.py`: composición/lifespan y registro del router/middleware.
- `backend/src/app/presentation/http/errors.py`: traducciones IA, documentación de
  estados y campo prompt en la allowlist saneada de validación.
- `backend/tests/http/test_lifespan.py`: configuración IA de prueba explícita para
  el caso que simula un engine sin repositorio inyectado; evita leer LLM operativo.
- `backend/README.md`: estado actual del endpoint y cierre por defecto.

No se modificaron AuthService, JWT, roles, sesiones, barrera de aprovisionamiento,
adaptador Ollama o núcleo IA. Tampoco React, dependencias, scripts de arranque,
`.env`, `.env.test`, Docker, modelos, migraciones o datos.

## 2. Endpoint y esquemas

**POST `/api/v1/ia/consultas`**, Bearer obligatorio. Solicitud JSON estricta:

```json
{"prompt":"Explicame qué es una API REST"}
```

Único campo admitido: prompt como SecretStr, oculto además del repr del esquema.
Campos adicionales prohibidos; sin modelo, URL, tools, opciones, timeout o contexto.
La conversión a ConsultaDatos ocurre dentro del endpoint mediante el valor secreto;
no se imprime ni se devuelve. El núcleo conserva todas sus validaciones: no vacío
ni solo espacios, 1000 puntos/3000 bytes, Unicode válido sin NUL y sin truncamiento.

Respuesta **200**, exactamente:

```json
{"respuesta":"Texto generado","finalizacion":"completa"}
```

Finalización admite completa o limite. El resultado ya fue validado en Application;
el esquema de respuesta usa texto estricto y oculta el contenido en repr. No se
devuelve el prompt, identidad, modelo interno o respuesta upstream completa.
El endpoint figura en OpenAPI con seguridad Bearer y errores documentados.

## 3. Seguridad y límite de lectura

`get_current_user` reutiliza authenticate y exige acceso normal. Al ser una
dependencia síncrona, FastAPI la ejecuta en su threadpool. El caso de uso vuelve a
comprobar acceso mediante el adaptador async antes y después de generar, sin UoW
abierta durante inferencia. ADMIN y USUARIO normales tienen el mismo permiso IA;
sesiones pendientes, revocadas, vencidas e inactivos conservan 403/401 existentes.

`IABodyLimitMiddleware` es ASGI y precede al parser de cuerpo de FastAPI. Para
POST a la ruta IA (incluida su variante con slash final), lee mensajes del canal
receive y comprueba longitud acumulada **antes de añadir cada fragmento**. Solo
almacena hasta **16384 bytes** y rechaza el exceso con 413 sin seguir consumiendo
fragmentos. No confía en Content-Length, incluso si es falso o falta.

Con un cuerpo admisible comprueba un único Content-Type application/json —admite
parámetros, por ejemplo charset— y bytes UTF-8 válidos. Tipo incorrecto/ausente o
UTF-8 inválido devuelven 422 SOLICITUD_INVALIDA. FastAPI/Pydantic procesan después
el JSON/estructura acotados; JSON malformado, tipos incorrectos y extras producen
422 saneado sin input/ctx ni nombres desconocidos de campos. La regla semántica
de prompt pertenece al caso de uso y conserva PROMPT_INVALIDO.

Se admite exactamente 16 KiB si el JSON y su prompt cumplen el contrato, por
ejemplo con espacios finales. El límite de cuerpo no reemplaza al de 3000 bytes
del prompt. La capa HTTP puede rechazar tamaño/tipo antes de autenticar: no se
promete prioridad de 401 sobre 413/422 en una solicitud de transporte inválida.

Todas las respuestas bajo `/api/v1/ia/` llevan **Cache-Control: no-store** mediante
envoltura de send ASGI, incluidos éxito, 401/403, validación, errores de proveedor,
413 temprano y 500 saneado. No depende solo del camino exitoso del endpoint.
La comprobación de límite no protege de toda carga previa del servidor HTTP ni
es un timeout de lectura para clientes lentos; acota lo que acumula la aplicación.

## 4. Traducción de errores

| HTTP / código | Causa |
| --- | --- |
| 401 AUTENTICACION_REQUERIDA | Token/sesión ausentes, inválidos, revocados o vencidos; usuario inactivo |
| 403 CAMBIO_PASSWORD_REQUERIDO | Sesión pendiente, incluidos ADMIN |
| 413 SOLICITUD_DEMASIADO_GRANDE | Más de 16 KiB reales de cuerpo |
| 422 SOLICITUD_INVALIDA | JSON, Content-Type, UTF-8 de transporte o esquema incorrectos |
| 422 PROMPT_INVALIDO | Reglas de contenido del prompt incumplidas |
| 429 IA_LIMITE_INTENTOS | Cuota de IA agotada; Retry-After |
| 429 IA_OCUPADA | Concurrencia/enfriamiento/capacidad de admisión; Retry-After |
| 502 IA_RESPUESTA_INVALIDA | Resultado inválido o error de protocolo/proveedor saneado |
| 503 IA_NO_DISPONIBLE | Módulo deshabilitado o proveedor no disponible |
| 504 IA_TIEMPO_AGOTADO | Deadline/timeout del proveedor |
| 500 ERROR_INTERNO | Fallo inesperado de la aplicación saneado |

Se conserva `{error:{codigo,mensaje,detalles?}}`, WWW-Authenticate en 401 y la
semántica actual de autenticación. Retry-After refleja el valor disponible en las
excepciones de admisión; no se inventa una espera para 503 sin esa información.
No se copian mensajes de HTTPX/Ollama o excepciones desconocidas al cliente.

**Precisión respecto de 9.1:** esta solicitud 9.2.3 exige 429 para ocupación, por
lo que IAOcupada se traduce a 429, junto con cuotas; el diseño inicial proponía
503. No se modificó la excepción o su política de admisión. OpenAPI de IA muestra
ambos ejemplos 429 específicos, sin confundirlos con LIMITE_INTENTOS de login.

## 5. Composición y lifespan

create_app admite configuración IA y una factoría runtime inyectable de pruebas.
En lifespan selecciona y valida configuración, compone autenticación/persistencia,
abre **una sola** instancia runtime mediante AsyncExitStack y construye
GenerarRespuesta con proveedor, admisión y timeout_seconds de ese runtime.
Las dependencias de requests recuperan el mismo servicio de app.state; no crean
clientes o cuotas por solicitud.

Al salir del lifespan se cierra el runtime antes de disponer el engine, y se
retiran ia_service, llm_runtime, auth_service y user_repository. Un fallo después
de abrir el runtime también lo cierra y limpia estado. Los tests comprueban el
cliente/transporte reales de HTTPX con MockTransport, sin red, en ambos caminos.

Con IA deshabilitada se usa DisabledLLMProvider y no se construye AsyncClient
Ollama. Una consulta válida autorizada recibe 503; como en otros fallos admitidos,
siguen aplicando las cuotas de 9.2.1. Login/me/usuarios continúan funcionando.

Con repositorio de memoria inyectado, la configuración por defecto es testing
deshabilitada sin leer LLM operativo. create_test_database_app pide explícitamente
configuración TEST_LLM, sin habilitarla ni conectar Ollama por sí mismo. Una
factoría runtime alternativa se permite **solo en configuración testing**. Si se
usa el runtime real con testing habilitado, 9.2.2 sigue exigiendo MockTransport.

Para configuración operativa habilitada se exige además LocalLLMContext:
socket IPv4 real ya vinculado y escuchando en **127.0.0.1**, número de workers
exactamente 1 y WEB_CONCURRENCY ausente/1. Se rechazan socket cerrado, wildcard,
no-listening y múltiples workers. La etiqueta de entorno y URL siguen validadas
por LLMConfig. Esto se comprueba antes de componer PostgreSQL.

El contexto lo debe suministrar una futura composición local confiable a partir
de su socket y configuración de servidor reales; no es un dato HTTP ni prueba
independiente de todos los procesos del equipo. Los scripts actuales no lo
suministran y **no se modificaron**: solo poner LLM_ENABLED=true en .env no basta
para habilitar el arranque. No se activó el piloto ni se reinició el servidor para
probarlo. Las cuotas siguen siendo por instancia compartida/worker, no distribuidas.

## 6. Cómo se verifica sin activar Ollama

Las pruebas HTTP crean AuthService y SecurityUnitOfWork reales **de memoria**,
con cuentas, claves y JWT exclusivamente ficticios. Inyectan una factoría async
de pruebas que entrega LLMRuntime con FakeLLMProvider, reloj controlado y admisión.
TestClient atraviesa router, dependencias JWT, esquemas y caso de uso reales.
No se sustituye autorización por un booleano ni se configuran claves operativas.

Otras pruebas inyectan ollama_runtime con **HTTPX MockTransport**, verifican dos
requests sobre el mismo cliente, y comprueban su cierre normal y ante fallo de
composición. HTTPX ASGITransport sirve para solicitudes fragmentadas, concurrencia
y cancelación dentro del proceso: no inicia Uvicorn ni usa sockets HTTP reales.
La guarda operativa usa sockets efímeros solo para comprobar metadatos de enlace;
no se hacen solicitudes sobre ellos ni se inicia un servicio persistente.

Cobertura nueva:

- Éxito ADMIN/USUARIO, forma de salida, OpenAPI, runtime compartido y cierre.
- IA deshabilitada sin cliente y compatibilidad con me/listado existentes.
- JWT ausente/inválido, roles pendientes, revocados, vencidos e inactivos.
- Prompt/estructura, extras, Unicode, Content-Type y JSON inválidos.
- Exactamente 16 KiB y exceso; fragmentos con Content-Length ausente/falso sin
  consumir un fragmento posterior al exceso.
- 429/502/503/504, Retry-After, no-store, 500 y ausencia de centinelas sensibles.
- Concurrencia HTTP, cancelación de tarea ASGI, liberación y reintento explícito
  posterior; revocación durante generación que impide entregar el resultado.
- Lifespan con MockTransport, fallo de composición, limpieza y ausencia de lectura
  operativa para la composición de memoria.
- Rechazo de habilitación sin socket confiable antes de componer DB, y comprobaciones
  de host/worker/contexto sin recursos operativos.

Comandos desde backend:

```powershell
.\.venv\Scripts\python.exe -B -m pytest -q tests/ia -p no:cacheprovider --basetemp=.pytest-tmp-923-ia-final --tb=short
.\.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider --basetemp=.pytest-tmp-923-regression-final --tb=short
```

| Verificación | Resultado |
| --- | --- |
| Ejecución inicial HTTP nueva | **42 aprobadas**, 6,11 s |
| Suite IA intermedia | **230 aprobadas**, 7,69 s; anterior a dos casos adicionales de JSON/UTF-8 |
| Regresión intermedia sin PostgreSQL | **663 aprobadas, 162 omitidas**, 30,63 s |
| Regresión final | **665 aprobadas, 162 omitidas**, sin fallos, **31,86 s**; 609 anteriores y 56 nuevas |

No se suman repeticiones como pruebas nuevas. Las 162 pruebas PostgreSQL se omiten
intencionalmente y no se presentan como aprobadas. No se ejecuta frontend porque
no se modificó. El aviso existente de Starlette/TestClient sobre httpx se mantiene;
no se cambiaron dependencias para ocultarlo.

## 7. Riesgos, límites y detención

No hubo conexiones a usuarios_dev, usuarios_test u Ollama real, migraciones,
inferencia, cargas/descargas de modelos, cambios de datos o servicios operativos.
No se habilitó IA en ningún archivo de configuración. Las mutaciones de pruebas
solo afectan fixtures ficticias de memoria. No se copiaron secretos de desarrollo.

La cancelación se verifica sobre tareas ASGI aisladas; no se afirma que toda
desconexión de navegador/TCP cancele inmediatamente la inferencia. El deadline
del caso de uso y las limitaciones de cierre/cómputo externo de 9.2.2 se mantienen.
No se evaluaron RAM, rendimiento del modelo o comportamiento de su servicio real.

La interfaz React y los nuevos códigos de error todavía requieren 9.2.4. No se
modificó el cliente anterior ni se afirma una experiencia IA disponible en él.
El piloto operativo, los recursos locales y la composición con socket real
necesitan su autorización posterior. No se ejecutan como efecto secundario de
registrar el router en disco.

Se entrega exclusivamente **9.2.3** para revisión y se detiene antes de **9.2.4**.
