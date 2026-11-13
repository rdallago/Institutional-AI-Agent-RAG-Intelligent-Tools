# Sprint 9.2.5G: arranque local controlado de FastAPI y React

Fecha: **3 de noviembre de 2026**. **Resultado vigente: COMPLETO para el arranque
y las comprobaciones anónimas autorizadas**, según la **sección 8**.
FastAPI y React quedan funcionando exclusivamente en loopback, con IA, observador
y aprovisionamiento deshabilitados. Las secciones 1–7 conservan los intentos
anteriores bloqueados como historial; no describen el resultado final.

## 1. Alcance y condición de parada

Se recibió autorización condicionada para iniciar backend y frontend sin LLM,
observador o aprovisionamiento. La sección 2 de la solicitud exige detenerse y
solicitar autorización si la RAM está por debajo de la referencia inicial de
aproximadamente 2 GiB. La primera medición quedó por debajo; no se interpretó el
permiso condicionado como dispensa de ese control.

Se revisaron los antecedentes 9.2.5E/9.2.5F/9.2.5D y los comandos del lanzador
local, package.json y configuración Vite de desarrollo. Los controles posteriores
de configuración efectiva, PostgreSQL, procesos y puertos no se ejecutaron al
activarse esta condición temprana de parada. Los estados de informes anteriores
no se presentan como comprobaciones actuales.

## 2. Medición inicial

Medición **08:33:00 -03:00**, mediante GetPerformanceInfo con el Python existente:

| Recurso | Observado |
| --- | ---: |
| RAM física total | **7,851 GiB** |
| RAM física disponible | **1,816 GiB** |
| Memoria comprometida global | **11,888 GiB** |
| Límite de compromiso global | **25,851 GiB** |

Es una muestra actual, sin carga deliberada de servicios/modelos. La cifra mejora
el antecedente, pero sigue aproximadamente 0,184 GiB por debajo de la referencia.
La memoria comprometida no equivale a RAM residente; tampoco se midió paginación.
No se afirma que este margen cause por sí solo congelamiento, ni que alcanzar
2 GiB garantice suficiencia. Se detiene por el control explícito de la solicitud.

## 3. Comandos identificados — NO EJECUTADOS

Desde `D:\Downloads\proyectos\api-usuarios-clean\backend`:

```powershell
.\.venv\Scripts\python.exe -B -m app.presentation.cli.local_server --environment local-development --host 127.0.0.1 --port 8000
```

El código del lanzador fija un worker, sin reload, proxy_headers o access_log.
Sin --enable-llm, --observe-llm y --enable-initial-provisioning, inyecta IA y
observación deshabilitadas y no abre el gate de aprovisionamiento. No hereda
variables LLM_* para habilitar esa instancia. Esto es inspección de código,
**no confirmación de una instancia operativa**.

Desde `D:\Downloads\proyectos\api-usuarios-clean\frontend`:

```powershell
npm.cmd run dev -- --config vite.development.config.ts
```

package.json usa Vite con host 127.0.0.1. La configuración explícita de desarrollo
compone el proxy /api hacia **http://127.0.0.1:8000**; mantiene separado el destino
aislado 8001. No se modificaron scripts o configuración ni se instaló nada.

## 4. Resultado de etapas

| Control o etapa | Resultado actual |
| --- | --- |
| RAM previa | Medida: **1,816 GiB**; condición de parada activada |
| Docker/PostgreSQL saludables | No revalidados en esta intervención |
| Destino efectivo y revisión 0003 | No se abrió conexión; antecedente de 9.2.5F, no verificación nueva |
| Puertos 8000/5173 e identidad de procesos | Pendientes, no se afirma que estén libres |
| Ollama sin modelos cargados | No revalidado; no se cargó nada por esta intervención |
| Inicio backend / frontend | **No ejecutados** |
| OpenAPI y GET anónimos/proxy | **No ejecutados** |
| RAM después de FastAPI/React y comprobaciones | No aplica: las etapas no comenzaron; no se repitió medición |
| Procesos iniciados / detenidos por este sprint | **Ninguno / ninguno** |
| Activación LLM/observador/aprovisionamiento | No realizada |

No se ejecutaron pruebas: no hubo cambios ni arranque cuya verificación aislada
aportara evidencia nueva frente al bloqueo. Las suites anteriores no se cuentan
como ejecuciones de este sprint.

## 5. Reanudación y estado final

Se requiere decisión expresa del responsable: liberar voluntariamente recursos
y autorizar repetir el precheck, o autorizar excepcionalmente continuar el arranque
sin inferencia con el margen observado y vigilancia de memoria. No se considera
que el transcurso del tiempo o un mensaje sin autorización resuelvan la condición.

Después de esa decisión, repetir RAM y completar Docker/salud, destino/revisión
DB por lectura, puertos, identidad y modelos cargados antes de iniciar nada.
Si se autoriza el arranque, medir también tras backend, frontend y comprobaciones;
solo GET anónimos, sin login/logout, POST o credenciales. Conservar ambos servicios
únicamente si funcionan y el margen resulta aceptable; ante problemas, intervenir
solo sobre los procesos propios recién iniciados con identidad confirmada.

No se finalizaron aplicaciones ajenas ni se cambiaron permisos, memoria virtual,
infraestructura, archivos de aplicación, .env o datos. No hubo conexiones DB,
migraciones, solicitudes de inferencia, descargas, login o escrituras de sesiones.
Único entregable creado: este informe. Los servicios preexistentes se dejaron
sin intervenir; no se afirma su estado actual sin inspección.

**Trabajo detenido en el precheck; se espera autorización para reanudar.**

## 6. Reanudación autorizada: RAM inferior al nuevo mínimo

El responsable autorizó excepcionalmente continuar con un margen cercano a
1,816 GiB, estableciendo **1,5 GiB como mínimo previo al arranque** y **0,75 GiB
como condición de parada después de iniciar cada componente**. La autorización
no habilita inferencia, observador, aprovisionamiento, escrituras o migraciones.
Reemplaza para esta reanudación la referencia anterior de 2 GiB, pero no elimina
el control previo de memoria.

Se repitió primero la medición a las **08:42:59 -03:00 del 3 de noviembre**:

| Recurso | Medición de reanudación |
| --- | ---: |
| RAM física total | **7,851 GiB** |
| RAM física disponible | **0,847 GiB** |
| Memoria comprometida global | **12,919 GiB** |
| Límite de compromiso | **25,851 GiB** |
| ¿Cumple mínimo previo de 1,5 GiB? | **No** |

El resultado procede de GetPerformanceInfo, con comparación del valor sin
redondear frente al umbral autorizado. Es una muestra nueva: no se atribuye su
variación a una aplicación específica ni se afirma haber medido paginación.

**Se detuvo la reanudación antes de iniciar servicios**, conforme a la instrucción
expresa de solicitar nueva autorización si el margen cae por debajo de 1,5 GiB.
La autorización para aproximadamente 1,816 GiB no se interpreta como permiso para
continuar con 0,847 GiB. Tampoco se aplica el umbral posterior de 0,75 GiB como si
sustituyera al precheck: aún no se inició ningún componente.

| Control solicitado | Resultado de esta reanudación |
| --- | --- |
| Docker/PostgreSQL saludables | No revalidados: parada en el primer control |
| usuarios_dev / 5434 / revisión 0003 | No se abrió conexión; verificaciones anteriores siguen siendo antecedentes |
| Puertos e identidad de procesos preexistentes | No revalidados |
| Modelos cargados en Ollama | No consultados nuevamente; no se cargó ninguno por esta intervención |
| Inicio y GET de FastAPI | No ejecutados |
| Inicio y GET de React/proxy | No ejecutados |
| RAM posterior a backend/frontend | No aplica: no hubo arranque |
| Procesos iniciados y sus PIDs | **Ninguno** |
| Procesos detenidos | **Ninguno** |

No hubo solicitudes POST/PUT/PATCH/DELETE, login/logout, creación de sesiones,
consultas de datos personales, migraciones o escrituras deliberadas. No se
introdujeron credenciales ni se enviaron solicitudes de generación. Ningún proceso
con LLM/observador/aprovisionamiento fue iniciado; no se certifica el estado de
servicios ajenos no inspeccionados. Docker, PostgreSQL, Ollama y otros procesos
permanecieron sin intervención. Única modificación: este informe.

**Recomendación:** el responsable puede guardar trabajo y liberar voluntariamente
recursos de aplicaciones que reconozca como innecesarias, y confirmar después que
se repita el preflight. Si desea cambiar el mínimo de 1,5 GiB, requiere una nueva
autorización explícita; no se recomienda arrancar automáticamente con el margen
actual. No hay procesos propios nuevos que deban detenerse ni servicios iniciados
por este sprint que dejar disponibles.

**Estado final: BLOQUEADO por RAM previa insuficiente.** Se espera decisión del
responsable; no se inicia Sprint 9.2.5H ni el piloto.

## 7. Nueva medición independiente tras optimización comunicada

Fecha: **3 de noviembre de 2026, 10:27:37 -03:00**.
El responsable comunicó haber optimizado VS Code y una medición externa de
**1,68 GiB disponibles**. Esa cifra es evidencia comunicada, no una medición de
esta intervención; no se reemplaza con ella el control independiente solicitado.

Se autorizó repetir el precheck y continuar solo si la nueva medición alcanza
**1,5 GiB**, conservando el límite posterior de **0,75 GiB** y las restricciones
de ausencia de inferencia, observador, aprovisionamiento, migraciones y escrituras
deliberadas.

Resultado de GetPerformanceInfo mediante el entorno Python existente:

| Recurso | Medición independiente actual |
| --- | ---: |
| RAM física total | **7,851 GiB** |
| RAM física disponible | **1,153 GiB** |
| Memoria comprometida global | **12,760 GiB** |
| Límite de compromiso | **25,851 GiB** |
| Comparación sin redondear contra 1,5 GiB | **Inferior; no cumple** |

La muestra es posterior a la optimización comunicada, pero no permite atribuir
la diferencia respecto de la medición externa a un proceso o causa específica.
No se repitieron mediciones para seleccionar una más favorable, ni se confundió
el margen virtual con RAM física disponible.

**Se detuvo la operación en el primer control**, como exige la nueva solicitud:

| Etapa | Resultado de esta intervención |
| --- | --- |
| Precheck RAM | Ejecutado; **1,153 GiB**, condición de parada |
| Docker/salud PostgreSQL | No revalidados tras la parada |
| Destino efectivo y revisión Alembic | No se abrió conexión; no hay nueva comprobación |
| Puertos y procesos del proyecto | No inspeccionados nuevamente |
| Estado de modelos cargados en Ollama | No consultado nuevamente |
| Arranque FastAPI / React | **No ejecutados** |
| GET backend/frontend/proxy | No ejecutados |
| RAM después de cada arranque | No aplica: ningún componente iniciado |
| Procesos iniciados o detenidos | **Ninguno** |

No se alteraron servicios, datos, código, .env, permisos o infraestructura. No
hubo solicitudes HTTP, inferencia, login/logout, migraciones o aprovisionamiento.
Los estados documentados anteriormente de Docker/PostgreSQL/Ollama son históricos
y no se presentan como verificaciones de esta reanudación. Único cambio: actualizar
este informe y su referencia al resultado vigente.

**Resultado vigente: BLOQUEADO antes del arranque por RAM inferior al mínimo
autorizado.** Para reanudar, el responsable podrá confirmar nuevos ajustes
voluntarios y solicitar otra medición; no se modificó el umbral ni se avanzó al
Sprint 9.2.5H. Se entrega el resultado y se detiene.

## 8. Reanudación: preflight satisfactorio y arranque completado

Fecha: **3 de noviembre de 2026, 10:56–10:58 -03:00**. El responsable comunicó
el cierre de una ventana Codex Diff, consumo de VS Code de 1912 MB y una medición
externa de 1,63 GiB. Esos antecedentes no sustituyeron la única nueva medición
inicial independiente autorizada. Se mantuvieron los mínimos **1,5 GiB antes de
iniciar** y **0,75 GiB después de cada arranque**, sin inferencia ni escritura
deliberada de datos.

### 8.1 Mediciones de memoria

GetPerformanceInfo comparó valores sin redondear contra cada umbral:

| Etapa / hora local | RAM disponible GiB | Compromiso GiB | Resultado |
| --- | ---: | ---: | --- |
| Precheck, **10:56:14** | **1,522** | 12,324 | Cumple mínimo previo 1,5 |
| Después de FastAPI, **10:57:03** | **1,410** | 12,374 | Cumple mínimo posterior 0,75 |
| Después de React, **10:57:35** | **1,101** | 13,143 | Cumple mínimo posterior 0,75 |
| Final de comprobaciones, **10:58:06** | **1,146** | 13,121 | Cumple mínimo posterior 0,75 |

RAM física total **7,851 GiB**, límite de compromiso **25,851 GiB**. Solo hubo una
medición inicial; las posteriores corresponden a las etapas autorizadas. No se
repitieron muestras para elegir una más favorable. El margen quedó por encima
del mínimo en las comprobaciones, sin fallo o lentitud grave observada en ellas;
no se midió paginación ni estabilidad prolongada y no hay garantía de rendimiento.

### 8.2 Preflight completado antes del arranque

- Docker Engine **29.8.1** respondió. Contenedor propio
  api-usuarios-clean-postgres-1 **running/healthy**, puerto publicado únicamente
  **127.0.0.1:5434 → 5432**. No se inició o detuvo un contenedor.
- Se cargó configuración de desarrollo sin mostrar secretos y se exigió destino
  exacto usuarios_dev / 127.0.0.1:5434. Una conexión Psycopg con read_only=True y
  default_transaction_read_only=on, connect_timeout=5, statement_timeout=10000 y
  lock_timeout=2000 confirmó current_database, usuario efectivo igual al configurado
  y transaction_read_only=on. Se leyó únicamente version_num de alembic_version:
  **una fila, 0003**. El head local, leído con ScriptDirectory sin ejecutar env.py,
  también era **0003**. La conexión terminó con rollback y cierre.
- No se consultaron registros de usuarios, credenciales, sesiones o intentos,
  ni se accedió a usuarios_test o se ejecutó Alembic current/check/upgrade.
- Inventario de listeners y procesos Python/Node, con lectura CIM permitida,
  confirmó **8000, 8001 y 5173 libres**, sin Uvicorn/lanzador/Vite preexistentes.
  No hubo procesos antiguos que detener. PostgreSQL conservaba su listener Docker.
- GET /api/ps de Ollama confirmó **ningún modelo cargado** antes del arranque.
  No se invocó generate/chat ni se arrancó o detuvo Ollama.

### 8.3 Backend iniciado

Desde backend se ejecutó el comando ya existente:

```powershell
.\.venv\Scripts\python.exe -B -m app.presentation.cli.local_server --environment local-development --host 127.0.0.1 --port 8000
```

Start-Process oculto, con logs de arranque en el directorio ignorado
`frontend/node_modules/.cache/925g-20261103-1056/`, sin logs de accesos/cuerpos.
No se pasaron --enable-llm, --observe-llm o --enable-initial-provisioning.

Identidad revalidada mediante creación, parentesco, ejecutables, referencia al
workspace y entrada del lanzador:

| Proceso | PID / padre | Creación local | Ejecutable / memoria observada al final |
| --- | --- | --- | --- |
| Lanzador Python del entorno | **17584** / 31380 | **10:56:52** | backend/.venv/Scripts/python.exe, **3,3 MiB** working set |
| Intérprete hijo/listener FastAPI | **18164** / **17584** | **10:56:52** | C:/Python314/python.exe, **89,8 MiB** working set |

Los dos procesos corresponden al lanzamiento del entorno virtual, no a dos workers
Uvicorn. Configuración en disco fija **workers=1, reload=False**, proxy_headers y
access_log deshabilitados; listener final único de 8000: **127.0.0.1, PID 18164**.
Los tres flags de opt-in figuraban ausentes en los argumentos revalidados.

Logs comprobaron **Local server: LLM DISABLED**, **initial provisioning DISABLED**
y **Application startup complete**, sin ERROR/Traceback. La composición pasa
llm_observe=False, y el runtime deshabilitado no crea cliente Ollama.

### 8.4 Frontend iniciado

Comando de desarrollo equivalente del repositorio, desde frontend:

```powershell
npm.cmd run dev -- --config vite.development.config.ts
```

Se ejecutó directamente el mismo binario Vite existente, mediante Node oculto:

```powershell
& 'C:\Program Files\nodejs\node.exe' node_modules/vite/bin/vite.js --config vite.development.config.ts --host 127.0.0.1
```

No se usó npm install ni se modificaron scripts/dependencias/configuración.
**PID 25700**, padre 23116 del proceso de lanzamiento, creado **10:57:20 local**,
ejecutable Node instalado; argumento vite.development.config.ts revalidado.
Working set final aproximado **278,7 MiB**. Listener final único de 5173:
**127.0.0.1, PID 25700**. Los padres 31380/23116 son shells de lanzamiento, no
procesos que deban detenerse para cerrar los servicios.

El proxy explícito existente apunta /api a **127.0.0.1:8000**, sin modificar la
configuración aislada a 8001. stdout/stderr de Vite quedaron en la misma caché
ignorada; sin ERROR, Error:, Traceback o ECONNREFUSED detectados en stderr.

### 8.5 GET de comprobación y límites de evidencia

| Comprobación | Resultado |
| --- | --- |
| GET 8000/openapi.json | **200**, POST /api/v1/ia/consultas presente; solo se imprimió presencia de ruta |
| GET 8000/api/v1/auth/me sin Bearer | **401**, rechazo anónimo esperado |
| GET 5173/login | **200**, entrada HTML React con raíz |
| GET 5173/ia | **200**, entrada HTML SPA; no demuestra acceso autenticado a la pantalla |
| GET 5173/api/v1/auth/me vía proxy | **401 AUTENTICACION_REQUERIDA**, Cache-Control: **no-store** |
| GET Ollama /api/ps después del arranque | Sin modelos cargados |
| Errores críticos en logs de arranque | No detectados |

Los clientes de comprobación ignoraron proxies del entorno, usaron timeouts y
solo GET no autenticados. No se imprimieron cuerpos completos OpenAPI, perfiles,
JWT, claves o headers de autenticación. El GET me sin Bearer se rechaza antes de
consultar registros personales; no hubo login/logout ni creación de sesiones.

El 401 del proxy confirma comunicación con la API, no un error de conexión.
No se ejecutó navegador autenticado ni JavaScript de la SPA para certificar todas
las rutas, permisos, consola o casos de negocio. La presencia de IA en OpenAPI
**no significa proveedor habilitado**. No se envió POST a IA para probar su rechazo.

No hubo generación originada por esta intervención: no se llamó ningún endpoint
de inferencia y la instancia quedó con proveedor deshabilitado. /api/ps sin modelos
cargados es corroboración puntual, no auditoría universal de otros clientes Ollama.
No se alteraron usuarios, roles, credenciales, esquemas o archivos de aplicación,
y no se afirma una comparación exhaustiva de valores DB que no fue autorizada.

### 8.6 Estado entregado y detención segura futura

**COMPLETO para el arranque local y GET anónimos autorizados.** Se dejan FastAPI y
React funcionando porque ambos respondieron, los listeners son loopback y la RAM
final superó 0,75 GiB. No se detuvo ningún proceso ni se tocaron Docker,
PostgreSQL u Ollama. El observador y aprovisionamiento permanecen deshabilitados.

Para detenerlos posteriormente, **revalidar antes** PID, fecha de creación,
ejecutable, argumentos de lanzador/configuración Vite, parentesco y listener:

1. Detener únicamente Node **25700**, si sigue siendo esta instancia Vite.
2. Detener únicamente Python listener **18164**, si sigue siendo este lanzador
   propio; comprobar después si padre **17584** ya terminó. Solo detener ese
   padre si persiste y su identidad sigue coincidiendo.
3. Confirmar ausencia de esos procesos/listeners; no detener por número de puerto,
   no usar PIDs de este informe sin revalidar y no cerrar sus shells padres ni
   servicios de infraestructura. No editar .env o borrar cachés/volúmenes.

No se repitieron suites: no hubo cambios de código y los GET aportan la evidencia
operativa nueva; las pruebas históricas no se presentan como ejecución actual.
Únicos archivos nuevos auxiliares: logs de arranque en caché ignorada. Se actualiza
este informe; no se modificó código/configuración operativa o seguridad.

Recomendación: revisar el arranque y su margen de memoria antes de autorizar otra
etapa. La prueba manual autenticada y sus escrituras normales requieren alcance
expreso; el piloto Ollama necesita evaluación y autorización separadas. **No se
ejecutó Sprint 9.2.5H ni inferencia. Se finaliza y se espera revisión.**
