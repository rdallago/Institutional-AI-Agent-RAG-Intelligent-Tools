# Sprint 9.2.5H-B: inferencia real Qwen3 y cierre documental

Fecha: **3 de noviembre de 2026**. **Estado final: EXITOSO para el funcionamiento
de la integración y los controles de observabilidad revisados**, según sección 8.
El responsable informó varias consultas manuales y respuesta visible; tres eventos
upstream válidos respaldan generación real. Las secciones 1–7 conservan la
preparación anterior, incluida su evidencia pendiente en aquel momento.
No certifica rendimiento sostenido ni memoria pico; Codex no envió consultas.

## 1. Autorización y alcance

El responsable autorizó una única inferencia desde React, reemplazando el bloqueo
operativo previo de H-A y retirando 2 GiB como condición automática de parada.
Mantiene vigilancia de RAM/paginación y la referencia de intervención de 0,75 GiB
sin convertirla en el único indicador. Se autorizaron el reinicio exclusivo del
backend propio y las escrituras normales inevitables de autenticación si el
responsable necesita iniciar sesión personalmente.

No se autorizan otros usuarios, cambios de roles/credenciales, migraciones,
modelos alternativos, reintentos o una segunda generación. Codex no debe pulsar
Enviar consulta: debe coordinar con el responsable cuando confirme interfaz lista.
No se reproduce en este informe el texto del prompt acordado ni una respuesta.

## 2. Preflight actual

Se releyó H-A y se revisaron lanzador, flags, modelo y proxy. Medición
**11:42:11 -03:00** mediante GetPerformanceInfo:

| Recurso | Antes del reinicio |
| --- | ---: |
| RAM física total | **7,851 GiB** |
| RAM física disponible | **1,558 GiB** |
| Memoria comprometida | **13,180 GiB** |
| Límite de compromiso | **25,851 GiB** |

Tres muestras breves de contadores formateados Windows: PagesInputPersec y
PageReadsPersec **0, 0, 3**; PagesOutputPersec y PageWritesPersec **0, 0, 0**.
No mostraron paginación intensa sostenida durante esa ventana ni fallos de
respuesta de las comprobaciones. No es un benchmark o garantía de estabilidad.

Docker: contenedor propio api-usuarios-clean-postgres-1 **running/healthy**,
publicación **127.0.0.1:5434 → 5432**. No hubo conexión SQL; identidad/revisión
0003 leídas en G son antecedentes recientes, no una nueva comprobación de filas.

Ollama: metadatos /api/version, /api/tags y /api/ps **200**; versión **0.40.13**,
modelo **qwen3:1.7b** instalado, 1359293444 bytes; digest
`8f68893c685c3ddff2aa3fffce2aa60a30bb2da65ca488b61fff134a4d1730e7`.
**Ningún modelo cargado** al observar; no hay evidencia de otra inferencia activa
en esa instantánea. No garantiza que otro cliente no comience después: reservar
la ventana para este único envío. No se enviaron generate/chat/run o embeddings.

## 3. Reinicio efectivamente realizado

Se revalidaron creación exacta, ejecutable, padres, referencia absoluta al workspace,
entrada del lanzador y listener antes de intervenir:

| Proceso previo | Identidad | Acción |
| --- | --- | --- |
| Python 18164, hijo de 17584 | Lanzador local, creado 10:56:52, C:/Python314/python.exe, listener 127.0.0.1:8000 | Detenido; se esperó su salida |
| Python 17584, padre del anterior | Entorno backend/.venv del workspace, creado 10:56:52 | Se aseguró su salida; solo podía detenerse si seguía siendo el padre propio revalidado |

El procedimiento exigió que el único listener 8000 fuera 18164 y que quedara
libre antes del nuevo inicio. No se detuvieron shells padres, React, Docker,
PostgreSQL, WSL, Ollama o procesos ajenos.

Desde backend se ejecutó:

```powershell
.\.venv\Scripts\python.exe -B -m app.presentation.cli.local_server --environment local-development --enable-llm --observe-llm --host 127.0.0.1 --port 8000
```

Start-Process oculto, sin modificar código o .env; logs de arranque en la caché
ignorada `frontend/node_modules/.cache/925hb-20261103-1142/`. No se activaron logs
de acceso, cuerpos o depuración HTTP. El futuro observador imprimirá solo metadatos.

| Proceso actual | Padre | Creación local | Verificación |
| --- | --- | --- | --- |
| **16760**, Python del entorno backend/.venv | 13100, shell de lanzamiento | **11:43:07.049569** | Lanzador del workspace, ambos flags presentes, sin aprovisionamiento |
| **17948**, intérprete Python | **16760** | **11:43:07.100986** | Mismo lanzador; listener único **127.0.0.1:8000** |
| **25700**, Node/Vite conservado | 23116 | **10:57:20.159419** | vite.development.config.ts; listener único **127.0.0.1:5173** |

El padre/hijo Python del entorno virtual no representa dos workers. El lanzador
mantiene workers=1, reload=False, proxy_headers=False y el mismo socket IPv4 real
servido. Los flags IA/observación se revalidaron por CIM; el flag administrativo
está ausente. El runtime operativo no admite una factoría falsa de pruebas.

## 4. Configuración y comprobaciones posteriores

Logs de arranque: **Local server: LLM ENABLED**, **initial provisioning DISABLED**,
**Application startup complete** y ausencia de ERROR/Traceback. El observador
está conectado por --observe-llm → llm_observe=True → observe=True, conforme al
código revisado; su emisión real aún no se comprobó porque no hubo generación.

Configuración preparada: qwen3:1.7b, URL fija 127.0.0.1:11434, think=false,
contexto 4096, salida 256 tokens, stream=false, keep_alive=0 y deadline 60 s.
Se mantienen admisión única/cuotas, límites de cuerpo, autenticación normal antes
y después y parser estricto stop/length. No se tocó el gate global ni permisos.

React no se reinició. El proxy de desarrollo existente apunta /api a 8000;
no se cambia la configuración aislada a 8001 ni se duplican instancias.

| Comprobación GET sin autenticación | Resultado |
| --- | --- |
| 8000/openapi.json | **200**, POST /api/v1/ia/consultas presente; sin imprimir documento |
| 5173/login | **200**, entrada del frontend accesible |
| Ollama /api/ps tras habilitar backend | **Sin modelos cargados** |

Medición **11:43:47 -03:00**: RAM disponible **1,614 GiB** y compromiso
**13,153 GiB**. No se usó el valor como garantía de carga del modelo. No hubo
señales graves en el inicio/comprobaciones; la vigilancia durante inferencia
sigue pendiente y debe coordinarse antes del único envío.

## 5. Estado pendiente al terminar la preparación — historial

| Evidencia requerida | Estado |
| --- | --- |
| Responsable confirma pantalla Consultar IA preparada | Pendiente |
| Única solicitud mediante Enviar consulta | **No enviada por Codex; pendiente del responsable** |
| HTTP y contrato público de generación | **NO VERIFICADO** |
| Latencia de generación real | **NO VERIFICADO** |
| Emisión de los ocho metadatos reales | **NO VERIFICADO** |
| Visualización de respuesta en React | **NO VERIFICADO** |
| RAM durante/después de generación y descarga posterior | **NO VERIFICADO** |

No se sustituye esa evidencia por los GET, marcadores o tests históricos. No se
probó POST IA para verificar conectividad y no hay una inferencia de preparación.
Los únicos HTTP ejecutados fueron GET de metadatos/diagnóstico público.

## 6. Coordinación manual y recuperación

Responsable abre http://127.0.0.1:5173, inicia sesión personalmente si hace falta
y confirma que está en Consultar IA. No enviar credenciales, JWT, capturas privadas,
cuerpos HTTP, prompt o respuesta por chat. **Antes de pulsar Enviar consulta,
coordinar la supervisión de RAM y ventana del único envío.** Codex no comparte ni
extrae la sesión del navegador y no pulsa el botón. Si hay timeout/error, no reintentar.

La siguiente observación debe registrar solo los ocho campos permitidos del evento
y las métricas de recursos, más HTTP/finalización comunicados sin contenido por
el responsable. La ausencia de evento no es prueba de éxito o de que sea seguro
repetir. Después se consultará /api/ps; no se hará una generación vacía para descargar.

Ante degradación, suspender nuevos envíos y actuar solo sobre los procesos backend
propios autorizados, después de revalidar identidad. No matar Ollama/WSL/Docker.
Si la inferencia falla, preparar restauración con el mismo lanzador sin ambos
flags, conservando cerrado aprovisionamiento; no alterar modelos o validación.
No reiniciar por rutina si finaliza correctamente y el sistema está estable.

## 7. Estado entregado al terminar la preparación — historial

**PARCIAL**: FastAPI habilitado localmente y React disponible; pendiente la
intervención manual y su supervisión para concluir la única inferencia. No hubo
generación originada por Codex, descargas, instalaciones, cambios de aplicación,
.env, contratos o DB. No se realizaron login/logout automatizados ni se crearon
usuarios/sesiones por scripts. No se inicia otro sprint. Se detiene antes del
envío y se solicita confirmación de interfaz preparada.

## 8. Cierre documental y evidencias posteriores

**3 de noviembre de 2026, revisión y medición a las 11:51:36 -03:00**.
El responsable comunicó que la cadena React → FastAPI → Ollama → Qwen3 funcionó,
que obtuvo respuestas visibles desde la interfaz y que la consulta sintética
acordada terminó con **Finalización: completa**. Es **confirmación manual del
responsable**, no observación automatizada de su navegador por Codex. No se
incorpora texto del prompt, respuestas, credenciales o datos personales.

### 8.1 Cantidad de solicitudes y alcance

El responsable informó **varias consultas manuales**. El registro contiene
**tres eventos de generación** desde la nueva instancia, coherentes con esa
confirmación. La autorización inicial contemplaba **una sola inferencia**:
se registra la diferencia expresamente, sin convertir el límite original en un
permiso retroactivo para varias o presentar los tres eventos como una sola llamada.

Codex no pulsó Enviar consulta, no hizo sondas de generación ni reintentos. La
solicitud posterior autoriza únicamente este cierre documental; **no autoriza
consultas adicionales**. La prueba técnica exitosa no modifica ese alcance.
Los eventos no incluyen identificadores o timestamps individuales; no se atribuye
cada uno a un prompt, usuario o acción particular del navegador.

### 8.2 Registro técnico existente

Se leyeron backend.stdout.log y backend.stderr.log en la caché ignorada
`frontend/node_modules/.cache/925hb-20261103-1142/`. No se imprimieron archivos
completos: cada evento se comprobó por claves y tipos antes de mostrar sus
metadatos. Líneas desconocidas o campos adicionales no se reproducirían.

| Evento, orden en archivo | HTTP upstream | Modelo coincide | done válido | done_reason | think solicitado | thinking presente | Duración s | Bytes |
| --- | ---: | --- | --- | --- | --- | --- | ---: | ---: |
| 1 | **200** | true | true | **stop** | false | false | **24,958** | **660** |
| 2 | **200** | true | true | **stop** | false | false | **11,403** | **755** |
| 3 | **200** | true | true | **stop** | false | false | **10,176** | **968** |

Cada evento contiene **exactamente**:

- http_status.
- model_matches.
- done_valid.
- done_reason.
- think_requested.
- thinking_present.
- duration_seconds.
- response_bytes.

**Cero eventos con claves adicionales o tipos inválidos**, cero líneas no vacías
sin clasificar en stdout. Además de los tres eventos, solo están los marcadores
permitidos **initial provisioning DISABLED** y **LLM ENABLED**. stderr contiene
solo tres líneas INFO de inicio reconocidas, **cero ERROR/Traceback** y cero líneas
sin clasificar. No se hallaron prompts, salidas, thinking, JWT, cookies, headers,
credenciales o identificadores de usuario en los archivos revisados.

La coincidencia de modelo es contra **qwen3:1.7b**, fijo en el adaptador preparado
y el runtime operativo. Estos son eventos del proveedor HTTP real de la instancia
habilitada; no de MockTransport o suites. El observador usa la misma llamada
/api/generate y no hace una solicitud adicional. La combinación respalda la
integración real junto con el resultado visual comunicado por el responsable.

Precisiones de interpretación:

- HTTP 200 es **del upstream Ollama**, no una captura del status público de cada
  POST del navegador. La confirmación de UI es manual; no se extrajo su sesión,
  red o cuerpos para comprobarlos independientemente.
- Las duraciones son monotónicas del adaptador, incluido cierre, **no latencia
  completa React → respuesta visible**. No hay muestra que acredite carga fría,
  caché o causa de diferencias entre llamadas.
- stop corresponde a completa en el parser estricto. El evento no certifica por
  sí solo toda la validación de response o la autorización final; la respuesta
  visible y finalización completa informadas corroboran al menos el recorrido
  manual descrito, sin atribuirlo a un evento concreto.
- think_requested=false y thinking_present=false confirman esa opción y ausencia
  del campo separado no vacío en estas respuestas; no prueban ausencia absoluta
  de cálculo interno o razonamiento incorporado al texto.
- Privacidad comprobada solo para estos registros de backend/observador, no una
  auditoría de todos los archivos de Ollama, navegador, sistema o terceros.

### 8.3 Memoria y estado actual

Medición de lectura con GetPerformanceInfo a las **11:51:36 -03:00**:

| Recurso | Valor actual |
| --- | ---: |
| RAM física total | **7,851 GiB** |
| RAM física disponible | **2,258 GiB** |
| Compromiso global | **13,317 GiB** |
| Límite de compromiso | **25,851 GiB** |

El margen actual supera la referencia de intervención de 0,75 GiB. No se
capturaron **RAM mínima/pico durante las consultas ni una serie de paginación**:
el responsable realizó los envíos antes de completar la coordinación de
supervisión prevista. No se reconstruyen esos valores a partir del estado final,
ni se certifica estabilidad sostenida o ausencia de presión durante las llamadas.

Solo GET de lectura posteriores, sin credenciales o generación:

| Control final | Resultado |
| --- | --- |
| Ollama /api/ps | **200**, **lista de modelos vacía** |
| FastAPI 8000/openapi.json | **200**, POST /api/v1/ia/consultas presente |
| React 5173/login | **200**, entrada HTML con raíz React |

La lista vacía acredita que no había modelos cargados en esa consulta posterior,
coherente con keep_alive=0. No demuestra el instante exacto de liberación ni
borrado seguro de RAM. No se envió una segunda generación para descargar nada.
Los GET confirman servicios accesibles, no una nueva prueba autenticada de negocio.

No se repitió SQL o inventario Docker: el estado saludable de PostgreSQL de la
preparación es antecedente; no se certifica nuevamente su estado interno o datos.
No hubo acción de este cierre que lo modificara. No se reiniciaron servicios por
rutina: FastAPI y React siguen disponibles; la última configuración de proceso
revalidada tenía IA/observador habilitados y aprovisionamiento cerrado. En este
cierre no se leyó memoria privada ni se cambiaron esos flags.

### 8.4 Clasificación final y limitaciones

**EXITOSO para el objetivo funcional de integración real y el contenido saneado
de los registros revisados.** Respaldo técnico: tres respuestas upstream 200 con
modelo esperado, done=true, stop, think=false y metadatos permitidos; respaldo
manual: respuestas visibles en React y finalización completa comunicadas por el
responsable. No se presenta como una ejecución automatizada observada de la UI.

Limitaciones expresas: varias consultas frente al límite autorizado de una,
sin correlación individual con la UI; sin status público capturado, medida de
latencia extremo a extremo, monitorización durante generación, pico RAM o
benchmark de carga. Ninguna de esas evidencias se simula o se presume aprobada.

No se ejecutaron tests adicionales: este cierre no cambia implementación ni
pretende validar generación mediante dobles. Único cambio: este informe.
No hubo nuevas inferencias, migraciones, instalaciones, descargas, cambios de
código/.env, modificaciones DB o login/logout por Codex. No se registró contenido
sensible ni se capturaron credenciales o respuestas completas.

Recomendación: revisar el resultado y definir por separado si se mantendrá la
instancia IA habilitada o se autorizará volver al arranque normal. No reiniciar
innecesariamente ni considerar este cierre permiso para nuevas consultas. Antes
de ampliar uso, acordar número de envíos y supervisión de recursos con el
responsable. **Sprint cerrado documentalmente; no se inicia otro sprint ni se
ejecuta una nueva inferencia.**
