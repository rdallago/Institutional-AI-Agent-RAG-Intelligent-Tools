# Sprint 9.2.5B — fase 1: preparación del lanzador local

Fecha: **2 de noviembre de 2026**. Estado: **implementado y verificado en
aislamiento**. No se habilitó IA operativa, reinició el backend ni ejecutó inferencia.
La fase 2 queda pendiente de autorización.

## 1. Revisión y archivos

Se leyeron el diagnóstico 9.2.5A, local_server.py, bootstrap.py, LLMConfig,
LocalLLMContext y las pruebas existentes de lanzamiento, guardas y lifespan.
Se conserva el dictamen operativo del diagnóstico: preparar código no resuelve
la falta de RAM ni actualiza el servidor que ya está ejecutándose.

Archivos modificados/creados:

- `backend/src/app/presentation/cli/local_server.py`: opt-in IA, composición del
  contexto con el socket servido y configuración explícita de Uvicorn.
- `backend/tests/ia/test_local_llm_launcher.py` (nuevo): **20 casos aislados**.
- `docs/sprint-9-2-5b-fase1-lanzador-local.md` (nuevo): este informe.

No se modificaron bootstrap, políticas LLM, adaptador Ollama, React, dependencias,
JWT, contratos HTTP, modelos, migraciones, archivos .env o configuración operativa.

## 2. Integración y opt-in

El lanzador conserva su validación inicial de entorno local-development, host
exactamente 127.0.0.1 y destino configurado usuarios_dev / 127.0.0.1:5434.
Después de bind/listen construye:

```python
LocalLLMContext(listener=listener, workers=1)
```

Ese contexto pasa la guarda real require_local_runtime y se entrega a create_app
junto con LLMConfig. **El mismo objeto listener** se pasa después a
`server.run(sockets=[listener])`: no se abre otro socket para justificar el permiso.
El lifespan existente repite su propia validación antes de componer persistencia
y administra el runtime compartido. No se omitió ninguna guarda.

El nuevo argumento **--enable-llm** es independiente de
--enable-initial-provisioning. Construye configuración inmutable habilitada en
local-development solo para esa invocación. Sin el argumento se inyecta LLMConfig
deshabilitada; no se cargan LLM_* ni TEST_LLM_* de archivos o entorno para decidir
esta habilitación. Así una variable heredada no activa IA accidentalmente ni cambia
URL/modelo/presupuestos de este lanzador. No se escriben variables de entorno.
El cargador general load_llm_config y la composición de pruebas no cambian.

Se fijan explícitamente `workers=1` y `reload=False` en Uvicorn, manteniendo
`proxy_headers=False` y `access_log=False`. La CLI no acepta --workers ni --reload.
Con opt-in, WEB_CONCURRENCY distinto de ausente/1 se rechaza mediante la guarda
existente; no se corrige o elimina esa variable silenciosamente.

Comando preparado para una **futura ejecución expresamente autorizada**, no ejecutado:

```powershell
# Desde backend; NO ejecutar durante esta fase.
.\.venv\Scripts\python.exe -B -m app.presentation.cli.local_server --environment local-development --enable-llm --host 127.0.0.1 --port 8000
```

Ese comando no habilita aprovisionamiento. No se requiere editar .env ni añadir
LLM_ENABLED=true. El marcador de arranque informa LLM ENABLED/DISABLED sin datos
sensibles; un marcador por sí solo no certifica inferencia o inicio completo.
El código no inicia Ollama, descarga modelos ni realiza sondas de generación.

## 3. Seguridad, independencia y limpieza

- IPv4 y loopback se verifican con el socket real: familia AF_INET, dirección
  127.0.0.1 y SO_ACCEPTCONN. Socket cerrado, no escuchando o contexto con más
  workers se rechazan al habilitar IA.
- URL literal, modelo permitido, deadline y límites continúan en LLMConfig y
  componentes ya aprobados; no hay opciones nuevas para parámetros del proveedor.
- El mecanismo de aprovisionamiento conserva su flag, verificación de identidad
  y gate por instancia. IA no lo habilita ni lo sustituye. Sus tests anteriores
  siguen aprobando; no se modifica la barrera normal.
- Ante fallo de composición o servidor, se cierra el listener. Si falla la
  verificación de aprovisionamiento se dispone el engine temporal y se cierra el
  socket. El cierre del socket queda en un finally interno para que se intente
  incluso si dispose del engine falla. No se afirma recuperación de un engine
  defectuoso ni borrado seguro de memoria.
- El cierre normal del runtime HTTP sigue perteneciendo al lifespan existente;
  el lanzador no duplica clientes ni cuotas. No se alteraron autenticación,
  revalidaciones, sesiones o políticas de recursos.

## 4. Pruebas y resultados

Las pruebas nuevas sustituyen cargas de configuración DB/Auth con valores ficticios,
create_app y Uvicorn.Server. No ejecutan Server.run real, lifespan operativo o
conexiones a bases. Reservan sockets efímeros de loopback para comprobar metadatos
e identidad, cerrados al terminar; no se sirven solicitudes HTTP sobre ellos.
Los tests de guardas y lifespan existentes usan memoria/MockTransport.

Cobertura: deshabilitación normal; opt-in explícito; ausencia de lectura/herencia
LLM_* y TEST_LLM_*; mismo socket validado/servido; workers/reload/proxy/logging;
rechazo de entorno/host/argumentos inseguros, WEB_CONCURRENCY múltiple, socket
cerrado/no-listening y configuración inválida; fallos de composición, servidor o
inicio no completado; independencia del gate y limpieza tras fallo de verificación.

Comandos desde backend, sin --run-postgres:

```powershell
.\.venv\Scripts\python.exe -B -m pytest -q tests/ia/test_local_llm_launcher.py tests/ia/test_ia_lifespan.py tests/security/test_local_provisioning.py tests/http/test_lifespan.py -p no:cacheprovider --basetemp=.pytest-tmp-925b-phase1-target-final --tb=short
.\.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider --basetemp=.pytest-tmp-925b-phase1-full --tb=short
```

| Ejecución | Resultado |
| --- | --- |
| Dirigida final: lanzador, guardas, aprovisionamiento y lifespan | **62 aprobadas, 2 omitidas**, 1,94 s |
| Regresión backend final sin PostgreSQL | **685 aprobadas, 162 omitidas**, 34,50 s; sin fallos |
| Casos anteriores / nuevos en regresión | **665 / 20**, sin sumar repeticiones |
| PostgreSQL, Ollama real y frontend | No ejecutados |

La primera recolección dirigida detectó un parámetro enabled omitido en la firma
de una prueba nueva; se corrigió la firma. La siguiente obtuvo 61 aprobadas y 2
omitidas; se añadió después el caso de limpieza por fallo de verificación y ambas
ejecuciones finales anteriores incluyen los 20 nuevos casos.
Permanece el aviso previo Starlette/TestClient sobre httpx, sin actualizar paquetes.
Las omisiones PostgreSQL son intencionales y no se cuentan como aprobaciones.

## 5. Ausencia de intervención operativa

No se detuvo, inició o reinició FastAPI, React, Ollama, Docker o PostgreSQL ni se
intervino sobre PIDs existentes. No se accedió a usuarios_dev o usuarios_test;
no hubo migraciones, datos reales, credenciales de operador, modelos descargados,
ollama run, solicitudes de generación o inferencia. No se habilitó IA en el entorno
operativo. Los sockets de prueba y dobles no constituyen evidencia de piloto real.

## 6. Pendientes y reversión futura

La fase 1 resuelve el suministro del contexto confiable **en disco**. No certifica
que la instancia activa haya cambiado; no se consultó ni reinició para probarlo.
La RAM de 9.2.5A no se volvió a medir y su bloqueo no se presume resuelto.

Antes de la primera inferencia: revisión de este cambio, autorización operativa,
nueva medición de RAM/compromiso, identidad actual de procesos, destino/revisión
de desarrollo, modelo/digest y escucha de Ollama, ventana de reinicio y arranque
con opt-in. Confirmar un worker, socket real y endpoint IA en el servidor nuevo.
Preparar observación saneada de done_reason, latencia y memoria y la prueba manual
React → FastAPI → Ollama con prompt no sensible; conservar validación estricta de
protocolo y no registrar contenido/JWT. No se adelantó esa instrumentación.

Reversión preparada: tras autorización y revalidación de identidad, detener solo
la futura instancia propia y relanzar el mismo lanzador **sin --enable-llm**.
El flag de aprovisionamiento se decide separadamente conforme a su autorización;
no se agrega o retira para activar IA. No hay cambios persistentes LLM_* que
deshacer. Deshabilitar IA no exige detener Ollama usado por otras aplicaciones.

**Fase 1 entregada para revisión. No se ejecuta fase 2 ni piloto real.**
