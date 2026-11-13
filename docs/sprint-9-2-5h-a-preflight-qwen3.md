# Sprint 9.2.5H-A: preflight del piloto local Qwen3

Fecha: **3 de noviembre de 2026**, medición **11:08:19 -03:00**.
**Resultado: BLOQUEADO para inferencia.** Solo diagnóstico y planificación.
La reevaluación de RAM posterior a cierres voluntarios está en la **sección 10**;
las mediciones del diagnóstico inicial se conservan como antecedentes.
FastAPI y React responden, pero el margen físico actual es muy reducido y no
hay evidencia de memoria/latencia del modelo con esta pila. IA no se habilitó.

## 1. Antecedentes y conclusión

Se localizaron y revisaron los documentos reales:

- `sprint-9-2-5d-observabilidad-ollama.md`.
- `sprint-9-2-5e-preflight-operativo-qwen3.md`.
- `sprint-9-2-5f-recursos-postgresql.md`.
- `sprint-9-2-5g-arranque-local-fastapi-react.md`, especialmente sección 8.

Los bloqueos iniciales de G no representan su estado final: allí se logró el
arranque sin IA con RAM final de 1,146 GiB. **Ahora se observaron 0,602 GiB**;
el antecedente no se reutiliza como medida actual. La experiencia favorable con
Qwen3 comunicada por el responsable tampoco equivale a benchmark con la carga actual.

Recomendación: no autorizar una inferencia inmediata. Preferir liberar
voluntariamente aplicaciones no esenciales y repetir preflight con la pila
necesaria, antes de considerar la alternativa A. B/C requieren además resolver
un método autenticado seguro sin React; no permiten saltarse permisos ni usar
tokens extraídos del navegador.

## 2. Recursos actuales

Medición mediante GetPerformanceInfo del Python existente:

| Recurso | Observado |
| --- | ---: |
| RAM física total | **7,851 GiB** |
| RAM física disponible | **0,602 GiB** |
| Compromiso global | **14,182 GiB** |
| Límite de compromiso | **25,851 GiB** |

Alrededor de 92 % de RAM física ocupada. Compromiso no equivale a memoria
residente; su margen no garantiza fluidez. Una lectura CIM posterior de contadores
formateados informó PagesInputPersec, PagesOutputPersec, PageReadsPersec y
PageWritesPersec **0**. Es una muestra, no un registro sostenido: no prueba ausencia
de paginación anterior/futura ni margen para cargar el modelo. No se hizo carga
deliberada, benchmark o segunda medición para elegir un resultado favorable.

Grupos relevantes de procesos en una muestra cercana:

| Grupo | Cantidad | Working set agregado MiB | Private bytes MiB |
| --- | ---: | ---: | ---: |
| chrome | 20 | **2615,1** | 2277,0 |
| Code | 12 | **1342,2** | 1615,8 |
| codex | 1 | 137,2 | 96,6 |
| codex-code-mode-host | 1 | 16,7 | 10,3 |
| codex-command-runner | 1 | 8,3 | 1,6 |
| Docker Desktop | 5 | 245,8 | 337,3 |
| com.docker.backend | 2 | 142,1 | 245,2 |
| com.docker.build | 1 | 24,6 | 57,2 |
| docker-agent | 1 | 32,3 | 67,8 |
| vmmem | 1 | **473,4** | 4017,2 |
| node, Vite | 1 | **277,8** | 731,2 |
| python, backend padre/hijo | 2 | **96,6** | 78,8 |
| ollama | 1 | 17,5 | 55,1 |

No sumar working sets como consumo exclusivo: hay páginas compartidas y memoria
virtual/no residente. Private bytes tampoco equivale a RAM física. No se
inspeccionaron títulos de pestañas, documentos o datos personales. La agrupación
no identifica qué ventana de VS Code o Chrome podría cerrarse sin perder trabajo.

El margen actual es inferior al mínimo posterior de 0,75 GiB utilizado en G.
**Este sprint prohíbe finalizar procesos**, por lo que no se aplicó ninguna parada
automática de los servicios anteriores. Se informa al responsable y se conservan
sin intervención. Puede guardar trabajo y cerrar voluntariamente ventanas/pestañas
innecesarias que reconozca; no se propone matar Docker, WSL/vmmem o protección del
sistema, cambiar pagefile o vaciar cachés. Revaluar el uso sostenido, no solo una cifra.

## 3. Servicios e identidad actual

Lecturas CIM/listeners permitidas fuera de la restricción de herramientas,
sin cambiar permisos Windows. Solo se publicaron ejecutables, creación, padres
y argumentos reconocidos; no líneas completas con posibles secretos.

| Servicio | PID / padre | Creación local | Listener |
| --- | --- | --- | --- |
| Lanzador Python del workspace | **17584 / 31380** | 03/11 **10:56:52** | Padre del intérprete |
| Intérprete FastAPI | **18164 / 17584** | 03/11 **10:56:52** | **127.0.0.1:8000** |
| Node/Vite | **25700 / 23116** | 03/11 **10:57:20** | **127.0.0.1:5173** |
| Docker backend | **8732** | No revalidada en esta lectura | **127.0.0.1:5434** |
| Ollama | **13416** | Antecedente 06:35:01, no revalidado aquí | **127.0.0.1:11434** |

Python 17584 usa el ejecutable del entorno backend/.venv del workspace; 18164
usa C:/Python314/python.exe y conserva referencia al workspace/entrada del
lanzador. Argumentos no sensibles del comando activo, reconstruidos de los campos
revalidados, coinciden con:

```powershell
.\.venv\Scripts\python.exe -B -m app.presentation.cli.local_server --environment local-development --host 127.0.0.1 --port 8000
```

**No** figuran --enable-llm, --observe-llm ni --enable-initial-provisioning.
El código de ese lanzador inyecta IA/observación deshabilitadas y gate cerrado.
No se inspeccionó memoria privada del servidor para extraer app.state o JWT.

Node usa C:/Program Files/nodejs/node.exe; se reconocen el host loopback y
vite.development.config.ts. Su comando contiene rutas relativas, sin referencia
absoluta al workspace; creación/PID/configuración coinciden con el inicio
registrado en G. No se afirma una nueva lectura del directorio de trabajo interno.
Comando registrado en G y consistente con los argumentos actuales:

```powershell
& 'C:\Program Files\nodejs\node.exe' node_modules/vite/bin/vite.js --config vite.development.config.ts --host 127.0.0.1
```

GET 8000/openapi.json: **200**, POST /api/v1/ia/consultas presente. Solo se imprimió
el booleano de presencia, no OpenAPI completo. GET 5173/login: **200**, entrada HTML
React; no acredita ejecución JS, sesión autenticada o todos los casos de uso.
No hubo GET de perfiles, login/logout ni POST a la aplicación.

Docker inspect limitado al contenedor propio: api-usuarios-clean-postgres-1,
**running/healthy**, publicación **127.0.0.1:5434 → 5432**. No se abrió conexión
PostgreSQL. La revisión 0003 comprobada en G es un antecedente reciente, no una
comprobación SQL nueva; salud no demuestra identidad/revisión/integridad de filas.

## 4. Modelo y configuración

GET /api/version, /api/tags y /api/ps de Ollama: **200**, sin proxies del entorno,
timeout 3 s y salida limitada a metadatos. No se consultaron generate/chat,
embeddings o show, ni se cargó un modelo.

| Elemento | Observado / verificado en código |
| --- | --- |
| Servicio Ollama | **0.40.13**, 127.0.0.1:11434 |
| Modelo permitido e instalado | **qwen3:1.7b** |
| Tamaño en disco | **1359293444 bytes**, aproximadamente 1,27 GiB |
| Digest | `8f68893c685c3ddff2aa3fffce2aa60a30bb2da65ca488b61fff134a4d1730e7` |
| Formato / familia / cuantización en tags | **GGUF / qwen3 / Q4_K_M** |
| parameter_size reportado por tags | **2.0B**; se conserva la etiqueta instalada 1.7b, sin inferir equivalencia por nombre |
| Contexto declarado en tags | **40960**; no es el contexto asignado por la aplicación |
| Contexto solicitado por la aplicación | **4096** |
| Salida máxima solicitada | **256 tokens** |
| think / stream / keep_alive | **false / false / 0** |
| Deadline backend / espera UI | **60 s / 70 s** |
| Timeouts HTTPX | connect 2, write 5, read 55, pool 1 s |
| Modelos actualmente cargados | **Ninguno** |

También están instalados Qwen2.5 y nomic-embed-text; no son fallback ni se usan.
El tamaño del archivo no equivale al consumo RAM: pesos residentes, runtime,
contexto, buffers y sistema compiten. No se certificó GPU o offloading. El modelo
instalado es mayor que el margen libre y eso, unido a la carga observada, aumenta
el riesgo; no se usa esa comparación por sí sola como estimación de pico.

## 5. Flujo React → FastAPI → Ollama

1. /ia está bajo ProtectedRoute para ADMIN/USUARIO normales; una sesión pendiente
   no entra. Formulario valida 1000 puntos/3000 bytes, sin NUL/Unicode inválido.
2. createIAApi usa useAuth().mutate para POST **/api/v1/ia/consultas**, solo
   `{prompt}`. JWT se mantiene en memoria y se añade con el transporte existente.
   Proxy de desarrollo /api → 127.0.0.1:8000; React no llama a Ollama directamente.
3. Dependencia Bearer exige acceso normal. GenerarRespuesta revalida antes y
   después con UoW cortas mediante asyncio.to_thread, sin transacción abierta
   durante inferencia. Revocación/baja/restricción impide entregar resultado.
4. Lifespan selecciona LLMConfig, valida LocalLLMContext cuando IA está habilitada
   y comparte runtime/admisión/caso de uso. El lanzador solo abre IA por --enable-llm
   y observación por el flag adicional --observe-llm, con socket real loopback,
   workers=1, sin reload y sin variables heredadas que activen esa instancia.
5. IA deshabilitada usa DisabledLLMProvider, sin cliente Ollama. Una consulta válida
   autorizada produciría **503 IA_NO_DISPONIBLE**, conservando sesión; consume
   admisión conforme a la política existente. **No se envió esa consulta aquí.**
6. Ollama desconectado/modelo ausente da 503 saneado; timeout da 504 y enfriamiento
   global de 30 s. Protocolo inválido da 502. Ocupación/cuotas dan 429, Retry-After.
   Un cupo por proceso, 5 admisiones/usuario y 15 globales/minuto; sin cola.
7. El adaptador hace una sola llamada /api/generate a URL fija, sin JWT/cookies,
   reintentos, tools o identidad. Exige model exacto, done=true, done_reason
   stop/length y respuesta válida; límites request 16 KiB/upstream 64 KiB.
8. UI muestra solo texto escapado, completa/límite y errores fijos. No interpreta
   HTML/acciones. Tiene lock contra doble envío, AbortController, secuencias para
   ignorar respuestas tardías, limpieza por salida/logout y ningún reintento
   automático. 503 no expira sesión; 401/403 mantienen semántica de autenticación.
9. Observador apagado ahora. Al habilitarse emite exactamente http_status,
   model_matches, done_valid, done_reason normalizado, think_requested=false,
   thinking_present, duration_seconds y response_bytes. Sin contenido, identidad,
   JWT o headers. Es la misma generación, no una sonda adicional.
10. El caso IA no persiste consultas/respuestas ni modifica perfiles/sesiones;
    autenticación y revalidaciones leen su estado actual. **Login/logout normales
    sí pueden escribir sesiones/intentos y rehash en login**. Autorizar una consulta
    no permite inferir permiso para esas acciones o exigir cero escrituras a todo
    un recorrido que necesite autenticarse. No se deben eludir mediante JWT extraído.

## 6. Alternativas evaluadas — ninguna ejecutada

| Alternativa | Ventaja | Limitaciones y riesgo | Valoración actual |
| --- | --- | --- | --- |
| A: React + FastAPI + PostgreSQL + Ollama | Una única consulta desde la UI verifica la cadena completa con transporte/auth existentes | Mayor concurrencia de recursos; navegador, Vite y modelo añaden presión. Con 0,602 GiB libres no hay margen razonable demostrado | **Bloqueada ahora**; preferible tras liberar aplicaciones y revalidar |
| B: liberar aplicaciones; mantener FastAPI/DB y detener Vite si se autoriza | Puede recuperar parte del working set de Vite y aplicaciones voluntariamente cerradas | No promete liberar todo su working set; parar Vite rompe el proxy /api, incluso en una SPA ya abierta. Necesita un cliente directo autenticado seguro aún no definido | **Condicional al diseño del cliente y autorización**; no acredita React completo |
| C: proveedor vía FastAPI primero; liberar modelo; restaurar React después | Separa picos temporales y permite medir proveedor sin mantener Vite | Tiene el mismo requisito de cliente autenticado seguro. React después puede comprobar formulario/navegación, pero no una segunda generación ni toda la cadena con la única ya realizada | **Condicional**; alcance parcial frente a A |

No se propone curl con tokens en argumentos/variables impresas, un endpoint sin
Bearer, proveedor directo saltando AuthService, TestClient operativo o extraer
la sesión del navegador. B/C requieren acordar y revisar un cliente interactivo
con secretos solo en memoria y permiso de autenticación; no existe aquí una nueva
implementación aprobada para ello. No se creará como efecto secundario del plan.

Restaurar React en C no permite enviar otra consulta con el pretexto de validar
la pantalla: sería una segunda inferencia y requeriría autorización adicional.
Si el objetivo sigue siendo una sola generación React → API → Ollama, elegir A
después de resolver recursos, sin fingir esa evidencia con dobles o respuestas guardadas.

## 7. Condiciones propuestas para H-B

Antes de autorizar, resolver conjuntamente:

- Responsable guarda trabajo y libera voluntariamente aplicaciones no esenciales;
  nueva medición con servicios necesarios y un único navegador/pestaña de práctica.
  Proponer **al menos 2 GiB libres como referencia inicial**, sin garantía ni
  tratarla como único criterio: comparar compromiso, tendencia, paginación y
  respuesta del equipo. La memoria pico del modelo sigue siendo desconocida.
- Observar una línea base breve de tasas de entrada/salida de páginas y RAM con
  herramientas de lectura, sin abrir tareas pesadas. No aceptar una sola lectura
  de 0 páginas/s como certificación. Posponer ante paginación sostenida o lentitud.
- Revalidar PIDs/creación/comandos, puertos, workspace y propietario del backend;
  decidir expresamente qué procesos propios se pueden detener/restaurar. Para
  Vite con rutas relativas, corroborar directorio/configuración antes de tocarlo.
- Confirmar PostgreSQL healthy y destino/revisión 0003 con autorización de lectura
  controlada si se requiere nueva conexión; sin migraciones ni datos personales.
- Un worker, socket real loopback, qwen3:1.7b/digest esperado, ningún otro cliente
  generando; IA y observador habilitados solo para la nueva instancia autorizada,
  sin --enable-initial-provisioning. Mantener estrictos parser y presupuestos.
- Definir monitorización durante ejecución y autorización de parada de **esa
  instancia backend propia** si hay degradación. Proponer 0,75 GiB como suelo
  conservador de interrupción del ensayo, sujeto a aprobación específica H-B,
  no como garantía ni como margen suficiente para comenzar. Parar también antes
  de ese suelo ante respuesta lenta, caída rápida o paginación intensa.
- Reconocer que deadline 60 s cierra espera/transporte, **no garantiza matar el
  cómputo remoto**. keep_alive=0 solicita liberación tras uso; comprobar /api/ps
  después sin exigir liberación instantánea o borrado seguro. Si sigue cargado/
  trabajando, no repetir ni mandar una generación vacía para descargar: solicitar
  instrucciones, sin terminar Ollama usado por terceros.
- Acordar alcance de autenticación manual y sus escrituras normales si hacen
  falta. No crear usuarios, restablecer claves o alterar roles para la prueba.

Faltan memoria suficiente demostrada, tendencia bajo condiciones más ligeras y
una decisión operativa de parada/recuperación. Por ello el dictamen global sigue
**BLOQUEADO**, no APTO por disponer de modelo y API saludables.

## 8. Propuesta exacta H-B — NO ejecutada

1. Obtener autorización expresa sobre alternativa, servicios, recursos, una sola
   consulta y autenticación de práctica. Repetir condiciones anteriores y reservar
   ventana sin otras generaciones. Docker/PostgreSQL y Ollama local deben permanecer
   disponibles; en A también Vite y la pestaña React. Aplicaciones ajenas solo las
   cierra voluntariamente su responsable.
2. Revalidar backend propio y detener exclusivamente su instancia autorizada,
   no por PID histórico o puerto. No tocar shells padres, Docker, WSL o DB.
3. Desde backend, comando futuro **NO EJECUTADO**:

```powershell
.\.venv\Scripts\python.exe -B -m app.presentation.cli.local_server --environment local-development --enable-llm --observe-llm --host 127.0.0.1 --port 8000
```

4. Exigir inicio completo, socket único 127.0.0.1:8000, workers=1/sin reload,
   marcadores/configuración IA explícitos y gate cerrado. GET /openapi.json solo
   para presencia de POST IA, sin publicar documento. GET me anónimo puede comprobar
   rechazo si está incluido en el alcance; no probar POST IA antes de la consulta.
5. Para A, conservar Vite si identidad/proxy son correctos. Responsable introduce
   personalmente credenciales en la interfaz únicamente si la autorización permite
   login y sus efectos. No pedir claves por chat, HAR, capturas privadas o extraer
   tokens. Una sesión pendiente/vencida exige resolver alcance, no eludir controles.
6. Escribir una consulta sintética breve no sensible acordada, personalmente en
   /ia, y pulsar enviar **una vez**. No copiar su contenido a informes/consola.
   Mantener pestaña sin recargar, sin otro cliente/solicitud ni reintento después
   de timeout. El lock UI y admisión ayudan, pero no son permiso para intentos extra.
7. Medir reloj monotónico, RAM física/compromiso y working sets antes, durante
   (por ejemplo cada segundo) y después, junto con tasas de paginación/fluidez.
   Mantener eventos de metadatos separados de los cuerpos; no habilitar trazas HTTP.
8. Evidencia de llamada real: configuración operativa no admite runtime falso;
   esperar un solo evento del adaptador con status, model_matches/done_valid,
   stop/length, think_requested=false y tamaños/duración, más estado público y
   finalización coherentes. Distinguir error de API, validación o proveedor; un
   evento no certifica éxito si el contrato fue rechazado. No emitir una segunda
   sonda al modelo para demostrar procedencia.
9. Revisar la allowlist de las ocho claves y tipos en la línea de observación sin
   anexar log completo o contenido generado. No mostrar thinking aunque aparezca;
   registrar solo presencia booleana. stop → completa y length → limite; invalid
   requiere parar, no inventar razón o modificar presupuestos.
10. Ante degradación, cancelar la espera y suspender nuevos envíos; detener solo
    backend propio si está autorizado. No reintentar un resultado incierto. Esperar
    liberación con keep_alive=0 y verificar metadatos /api/ps; si no sucede, parar
    el procedimiento y pedir instrucciones sin matar procesos remotos.
11. Para restaurar estado anterior, tras identidad revalidada iniciar backend sin
    opt-ins, **comando propuesto NO EJECUTADO**:

```powershell
.\.venv\Scripts\python.exe -B -m app.presentation.cli.local_server --environment local-development --host 127.0.0.1 --port 8000
```

12. Si B/C incluyeron parada de Vite, restaurar solo con autorización y proxy
    original de desarrollo, usando el comando existente **NO EJECUTADO aquí**:

```powershell
npm.cmd run dev -- --config vite.development.config.ts
```

13. Confirmar GET públicos, LLM/observación deshabilitados, listener loopback y
    memoria recuperada. No editar .env ni volver a Qwen2.5 para deshabilitar IA.
    Reiniciar backend no revoca por sí solo sesiones. Logout, si se necesita,
    debe estar incluido expresamente por su escritura normal. No hacer downgrade,
    limpiar tablas o borrar volúmenes ante errores.

## 9. Límites y detención

Único entregable creado: este informe. No se modificó código, .env, dependencias,
contratos, Windows o infraestructura. No hubo inferencia, embeddings, modelos
cargados deliberadamente, descargas, login/logout, credenciales, consultas de datos
personales, SQL o migraciones. No se inició/reinició/detuvo un servicio o proceso.
Los GET se limitaron a metadatos Ollama, OpenAPI y HTML de entrada React.

No se repitieron suites: sin cambios funcionales, las pruebas históricas no aportan
medida real de memoria o inferencia. 9.2.5D/F/G son antecedentes diferenciados de
las observaciones actuales. No se probaron las tres alternativas ni la UI autenticada.

**BLOQUEADO para inferencia con la carga actual.** Revisar recursos y permisos de
recuperación antes de autorizar H-B. La RAM baja actual se comunica al responsable;
esta etapa no permite finalizar los servicios existentes. Se entrega y se detiene.

## 10. Reevaluación tras cierres voluntarios comunicados

**3 de noviembre de 2026, 11:13:14 -03:00**. El responsable comunicó haber cerrado
varias aplicaciones y solicitó una nueva evaluación. Medición independiente con
GetPerformanceInfo, sin iniciar/detener procesos ni cargar modelos:

| Recurso | Valor actual |
| --- | ---: |
| RAM física total | **7,851 GiB** |
| RAM física disponible | **1,600 GiB** |
| Compromiso global | **13,081 GiB** |
| Límite de compromiso | **25,851 GiB** |

El margen aumentó aproximadamente **0,998 GiB** respecto de los 0,602 GiB de la
muestra inicial. Supera la referencia de 1,5 GiB usada para arrancar la aplicación
**sin IA** en G y el suelo posterior de 0,75 GiB; esos valores no acreditan margen
para cargar Qwen3. Queda por debajo de los 2 GiB propuestos como referencia para
el piloto, que tampoco serían garantía de suficiencia por sí solos.

Esta actualización solo reevalúa RAM/compromiso; no repite identidad de procesos,
GET, modelos cargados, PostgreSQL o paginación. No certifica tendencia estable ni
consumo pico del modelo. **No se habilitó IA u observador ni se realizó inferencia.**
La mejora permite revisar la preparación con menos presión que antes, pero el
piloto permanece pendiente de las condiciones conjuntas y autorización expresa
de H-B. No se inicia automáticamente otra etapa ni se cambia el umbral a partir
de una muestra favorable. Único cambio: esta actualización documental.
