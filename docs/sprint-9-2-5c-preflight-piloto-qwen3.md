# Sprint 9.2.5C: preflight final del piloto Qwen3

Fecha: **2 de noviembre de 2026**, mediciones **18:02:35–18:02:38 -03:00**.
**Dictamen: NO APTO PARA EJECUCIÓN INMEDIATA.** Inspección de lectura; sin
inferencia, reinicios o conexiones PostgreSQL. El piloto no se ejecutó.

## 1. Mediciones actuales y viabilidad

| Medición | Primera | Segunda, 3 s después |
| --- | ---: | ---: |
| RAM física total | 7,851 GiB | 7,851 GiB |
| RAM física disponible | **0,521 GiB** | **0,532 GiB** |
| Memoria comprometida global | 21,248 GiB | 21,180 GiB |
| Límite de compromiso | 29,015 GiB | 29,015 GiB |

GetPerformanceInfo mediante ctypes del Python existente proporcionó las dos
muestras; no se estimaron a partir de informes anteriores. Aproximadamente 93 %
de la RAM física estaba ocupada en ambas. El compromiso no representa RAM
residente: su margen restante no garantiza ausencia de paginación o congelamiento.
No se midieron fallos de página, tasa de paginación ni CPU bajo carga; no se afirma
que los 21 GiB estén residentes ni que se conozca su distribución completa.

Procesos de mayor working set en la muestra:

| PID | Proceso | Working set MiB | Private bytes MiB |
| --- | --- | ---: | ---: |
| 9100 | chrome | 530,2 | 646,6 |
| 1736 | Code | 499,0 | 681,5 |
| 12776 | vmmem | 484,1 | 4001,0 |
| 3528 | Code | 437,8 | 827,5 |
| 16040 | Code | 315,2 | 432,8 |
| 33016 | chrome | 267,5 | 376,2 |
| 10684 | chrome | 208,1 | 260,8 |
| 23372 | chrome | 173,6 | 515,7 |
| 6068 | MsMpEng | 150,6 | 382,4 |
| 11592 | chrome | 148,8 | 188,6 |

Working sets pueden compartir páginas; private bytes tampoco equivale a RAM
física residente. No se suman como consumo exclusivo. No se consultaron títulos,
documentos, pestañas o información personal de esos procesos.

Se considera favorable la experiencia previa con Qwen3 comunicada por el usuario,
sin convertirla en un benchmark observado. La evaluación actual combina dos
muestras de margen muy reducido, compromiso elevado, modelo aún descargado de
RAM y necesidad de mantener Windows, PostgreSQL/Docker, FastAPI, Vite y un
navegador durante el recorrido. El modelo pesa **1359293444 bytes en disco**;
runtime/contexto añaden memoria y el peso no determina su coste residente.
Por tanto no se aconseja cargarlo ahora para comprobar si alcanza.

Acciones exclusivamente manuales y voluntarias: guardar trabajo, cerrar pestañas
o aplicaciones no esenciales reconocidas por el responsable, elegir una ventana
de menor carga o posponer el piloto. No detener vmmem/Docker/PostgreSQL, servicios
de protección ni procesos ajenos para forzarlo. No vaciar cachés ni modificar
pagefile. Repetir dos mediciones con la pila necesaria abierta después de esas
acciones. El margen propuesto previamente de 2 GiB es una referencia conservadora,
no una prueba automática de suficiencia; evaluar estabilidad y presión conjuntamente.

## 2. Servicios, modelo e identidad

| Puerto | Listener | PID | Identidad básica observada |
| --- | --- | --- | --- |
| 8000 | 127.0.0.1 | **25604** | Python, C:/Python314/python.exe; inicio 01/11 18:47:44 local |
| 8001 | Sin listener observado | — | No se presume destino de pruebas |
| 5173 | 127.0.0.1 | **12376** | Node, C:/Program Files/nodejs/node.exe; inicio 01/11 16:32:00 local |
| 11434 | 127.0.0.1 | **228** | Ollama, instalación local del usuario; inicio 27/10 17:52:24 local |

También existe Python **31616**, ejecutable del entorno virtual de este workspace,
inicio 01/11 18:47:44 local. Working sets observados posteriormente:
Node 16,6 MiB; Ollama 15,3 MiB; Python 25604 14,6 MiB; Python 31616 2,2 MiB.
Estas cifras puntuales no incluyen el coste de un modelo cargado ni permiten
sumar todos los procesos del servicio como memoria exclusiva.

La consulta CIM para obtener padres/argumentos devolvió acceso denegado o servicio
no disponible; **no se obtuvieron esos campos**. No se pidió elevación ni se
imprimieron líneas de comando completas. El informe 8.6D atribuye históricamente
estos Python al lanzador local con --enable-initial-provisioning. Esa atribución
y el comando histórico **no están revalidados actualmente**. Coincidencia de PID,
hora o ejecutable genérico no autoriza detenerlos por sí sola. Resolver identidad
y comando efectivo es condición previa a una futura sustitución.

GET de metadatos con proxy deshabilitado y timeout 3 s:

| Consulta | Resultado |
| --- | --- |
| Ollama /api/version | **200**, versión **0.40.7** |
| Ollama /api/tags | **200**, qwen3:1.7b instalado; también Qwen2.5 y nomic-embed-text |
| Ollama /api/ps | **200**, **cero modelos cargados** |
| Backend /openapi.json | **200**, **sin POST /api/v1/ia/consultas** |

Digest Qwen3 actual:
`8f68893c685c3ddff2aa3fffce2aa60a30bb2da65ca488b61fff134a4d1730e7`.
Coincide con el observado en 9.2.5A. Es metadato del modelo, no credencial.
No se leyeron respuestas de usuarios ni se hicieron consultas de generación,
login o auth/me. OpenAPI se procesó en memoria y solo se imprimió presencia de
la ruta/estado, no el documento completo. Ausencia de modelo cargado es una
instantánea, no exclusión de que otro cliente lo utilice después.

## 3. Código y configuración verificados

- Lanzador local: requiere --environment local-development y host 127.0.0.1;
  --enable-llm es explícito y distinto de --enable-initial-provisioning.
- LLMConfig inmutable se construye por invocación, sin heredar LLM_* o TEST_LLM_*.
  Sin flag IA queda false; no hace falta editar .env.
- Socket AF_INET creado con bind/listen; el mismo objeto se usa en
  LocalLLMContext(listener=listener, workers=1) y Server.run(sockets=[listener]).
  La guarda exige socket abierto/escuchando en 127.0.0.1 y WEB_CONCURRENCY ausente/1.
- Uvicorn fija workers=1, reload=False, proxy_headers=False y access_log=False.
  Lifespan revalida contexto y compone un runtime/admisión compartidos; cierra
  recursos al salir. Son propiedades de código en disco, no prueba de arranque nuevo.
- Modelo único qwen3:1.7b, URL literal http://127.0.0.1:11434 y think=false en
  payload. Se conservan contexto 4096, salida 256 tokens, deadline 60 s,
  stream=false, keep_alive=0, límites de cuerpos y parser estricto stop/length.
- Ruta React lazy /ia bajo ProtectedRoute; cliente autenticado existente.
  vite.development.config.ts dirige /api a 8000; vite.config.ts aislado conserva
  8001. Ambos usan loopback/5173 estricto. Argumentos efectivos de Node no
  certificados en esta inspección: verificar su selección antes de la cadena real.
- Barrera normal require_initial_provisioning_enabled rechaza incondicionalmente.
  El lanzador solo inyecta gate administrativo con su propio flag y controles.
  No se activó, invocó por HTTP ni se certificó el gate de la instancia ya activa.
  El plan propuesto omite --enable-initial-provisioning: el nuevo proceso quedaría
  cerrado para aprovisionamiento, sin alterar usuarios o credenciales existentes.

Los 697 casos backend/162 PostgreSQL omitidos y 189 frontend son antecedentes
aprobados. No se reejecutaron tests o build en este preflight.

## 4. PostgreSQL: configuración sin conexión

Se leyó código de configuración/persistencia/bootstrap y se ejecutó exclusivamente
load_database_config(), sin construir engine ni abrir socket DB. Se confirmó
coincidencia configurada **usuarios_dev / 127.0.0.1:5434**; no se imprimió URL,
usuario, contraseña o archivo .env. El loader combina POSTGRES_* del archivo
operativo con overrides de proceso, sin interpolación. No se cargó configuración
ni se accedió al destino de pruebas.

El lanzador pasa el mismo DatabaseConfig a create_app. Durante lifespan,
crear_persistencia_postgresql llama build_engine y crea repositorio/sesiones;
la autenticación utiliza ese engine y UoW independientes. SQLAlchemy conecta
de forma diferida al adquirir conexión para una operación. pool_pre_ping=true,
pool_size=5, max_overflow=3, pool_timeout=10, connect_timeout=5, echo=false y
hide_parameters=true no equivalen a una comprobación de esquema/identidad.
El arranque sin gate de aprovisionamiento **no verifica por sí mismo Alembic 0003**.

Antes de sustituir el servidor se necesita autorización adicional para una
conexión de lectura: revalidar destino configurado y efectivo, current_database,
current_user esperado sin secretos, revisión única 0003 y metadatos estructurales
necesarios. Sin perfiles, credenciales, hashes, tokens, conteos innecesarios o
fixtures. La revisión 0003 de informes anteriores es antecedente, no comprobación
actual. No se propone migrar si hay diferencia: parar y diagnosticar.
Login/logout manuales posteriores implican escrituras normales de sesiones e
intentos y también deben estar incluidos en la autorización operativa futura.

## 5. Bloqueos pendientes

1. Margen físico actual muy reducido en las dos muestras; evaluar nuevamente tras
   acciones voluntarias del responsable.
2. Identidad/comando/padres del backend y configuración efectiva de Vite sin
   revalidación suficiente para detener/reemplazar procesos.
3. Backend activo sin endpoint IA: requiere reinicio autorizado, no edición de
   archivos ni inferencia a modo de diagnóstico.
4. Identidad/revisión efectiva DB pendiente de autorización de lectura.
5. Observación de done_reason y comportamiento de think=false sin instrumentación
   disponible. La API pública solo expone finalizacion: no acredita por sí sola
   el campo upstream ni la desactivación real del razonamiento.

### Instrumentación mínima propuesta, NO implementada

Solicitar autorización antes de añadir un observador opt-in local al adaptador/
composición del piloto, deshabilitado por defecto y probado con MockTransport.
Debe emitir solo un evento acotado de la consulta: status numérico, coincidencia
del modelo como booleano, done validado, reason en allowlist stop/length/invalid,
think_requested=false, presencia de thinking no vacío como booleano, duración
monotónica y tamaño. Nunca valores desconocidos crudos, prompt/response/thinking,
excepciones, headers, identidad o JWT. Sin endpoint nuevo, trazas HTTP o persistencia
de contenidos. Se mantienen parser y límites sin reintentos/fallback.

El observador debe recoger metadatos de **la misma única generación** iniciada desde
React, sin sonda directa adicional. Una petición con think=false y thinking vacío
constituye evidencia limitada de comportamiento de esa respuesta, no garantía de
ausencia de cómputo interno. Si aparece razonamiento separado, respuesta vacía o
reason desconocida, parar y diagnosticar sin cambiar validación para obtener éxito.
No basta registrar el flag del payload como prueba de que el servidor lo respetó.

## 6. Plan exacto futuro — comandos NO EJECUTADOS

Todos los pasos operativos siguientes requieren autorización posterior; esta
inspección no la presume.

1. Guardar trabajo, acordar ventana y no lanzar otros generadores. Repetir recursos
   e identidad y completar preflight DB de lectura autorizado. Revisar/aprobar e
   implementar por separado el observador mínimo, con pruebas aisladas.
2. Responsable revalida comando completo localmente sin publicarlo, PID, creación,
   padre/hijos, workspace, socket y ausencia de procesos ajenos. Si no puede
   acreditarlo, mantener el bloqueo. No reutilizar ciegamente 25604/31616.
3. Solo con permiso de parada, cerrar exclusivamente backend propio verificado;
   no tocar PostgreSQL, Ollama, Docker, Vite ni terminales ajenas. Esperar cierre
   de solicitudes, verificar padre/hijos y 8000 libre; no matar por puerto.

```powershell
# NO EJECUTADO: solo tras identidad revalidada y autorización.
# Sustituir con el PID actual acreditado, nunca copiar el PID histórico del informe.
Stop-Process -Id <PID_ACTUAL_BACKEND_PROPIO_VERIFICADO>
```

El marcador anterior es deliberadamente no ejecutable hasta completar identidad.
No hay un PID actual autorizado para detener a partir de esta inspección limitada.

4. Desde backend, nueva instancia local, sin aprovisionamiento automático:

```powershell
# NO EJECUTADO. Desde D:\Downloads\proyectos\api-usuarios-clean\backend
.\.venv\Scripts\python.exe -B -m app.presentation.cli.local_server --environment local-development --enable-llm --host 127.0.0.1 --port 8000
```

5. Exigir inicio completo sin errores, listener único 127.0.0.1:8000, socket real,
   worker único, sin reload, sin confianza en proxies; confirmar OpenAPI con POST IA
   sin volcar documento. Marcador LLM ENABLED no sustituye esas verificaciones.
   React puede conservarse si se verifica proxy efectivo a 8000; no reiniciarlo
   por rutina. Ollama ya responde: no es necesario iniciarlo o descargar nada.
6. Responsable abre http://127.0.0.1:5173, introduce credenciales personalmente y
   confirma acceso normal. No enviar claves por chat ni extraer tokens/cookies;
   no modificar usuarios para conseguir acceso. Si hay cambio obligatorio, resolver
   el alcance con el responsable antes de continuar, no alterar políticas.
7. En /ia, realizar **UNA** consulta sintética breve acordada, redactada personalmente
   en la interfaz, sin secretos. No copiar su texto o respuesta a consola, archivos
   o informe. No recargar la página durante la sesión ni reintentar automáticamente.
8. Muestrear RAM disponible, compromiso y working sets de Ollama/modelo/backend
   antes, durante y después (por ejemplo cada segundo), con marcas monotónicas.
   Registrar solo metadatos, latencia, status/finalizacion y evento saneado del
   observador. Verificar stop/completa o length/limite y comportamiento think=false.
   No ampliar presupuestos para conseguir éxito; la primera consulta no mide
   todos los extremos de tokenización, permisos o cancelación.
9. Parar ante deterioro de respuesta del equipo, presión de memoria, timeout,
   error de think, reason/modelo inesperados o contenido en logs. No reenviar la
   creación de una generación de resultado incierto. Mantener diagnóstico saneado.
   El cierre de HTTP/backend no garantiza detener un cálculo ya iniciado en Ollama;
   no matar el servicio o modelos usados por otros clientes sin autorización.

### Reversión preparada

10. Tras revalidar identidad y con permiso, terminar solo la futura instancia IA
    propia. Reiniciar el lanzador normal, sin --enable-llm ni flag de aprovisionamiento:

```powershell
# NO EJECUTADO. Desde backend, solo con autorización operativa.
.\.venv\Scripts\python.exe -B -m app.presentation.cli.local_server --environment local-development --host 127.0.0.1 --port 8000
```

11. Confirmar inicio, loopback y marcador LLM DISABLED; la configuración inyectada
    no crea cliente Ollama. No se necesita editar .env, volver a Qwen2.5, descargar
    modelos o modificar DB. Retirar únicamente el observador temporal conforme al
    cambio aprobado. Deshabilitar IA no requiere detener Ollama existente.
12. Comprobar navegación normal y logout/protección de rutas mediante intervención
    personal autorizada. Informar solo estados/códigos, sin cuerpos o capturas con
    datos personales. La reversión no revoca por sí misma sesiones ni borra datos.

## 7. Entrega y ausencia de cambios operativos

Único archivo creado: este informe. No se modificaron código, .env, políticas,
dependencias o configuración operativa. No se reiniciaron/detuvieron procesos,
inició modelo, descargó, generó texto, accedió a PostgreSQL, ejecutaron migraciones,
tests, login/logout o acciones de aprovisionamiento. Las lecturas HTTP se limitaron
a metadatos Ollama y OpenAPI; no se imprimieron cuerpos completos ni secretos.

**NO APTO actualmente**: recuperar margen y revalidar condiciones antes de decidir
la ejecución. Se requiere autorización posterior para lectura DB, instrumentación
mínima, parada/arranque y la única consulta real. Se entrega el plan y se detiene.
