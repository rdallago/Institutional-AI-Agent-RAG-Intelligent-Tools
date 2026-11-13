# Sprint 8.6C: arranque local controlado

Fecha: **1 de noviembre de 2026**. Estado: **FastAPI y React iniciados localmente;
verificación anónima aprobada, recorrido autenticado pendiente del responsable**.
No se declara todavía cerrado Sprint 8.6 ni se inicia otro sprint.

## 1. Configuración efectiva y controles previos

Se revisó la sección 9 de `sprint-8-6b-migracion.md`. Su migración es un antecedente
completado; en esta intervención **no se ejecutó Alembic ni otra migración**.

Antes del inicio se verificó la configuración cargada por
`load_database_config()` sin argumentos de pruebas, exigiendo coincidencia exacta
con **usuarios_dev / 127.0.0.1:5434**. Una conexión Psycopg forzada a solo lectura
confirmó base efectiva, usuario **usuarios_dev_admin**, `transaction_read_only=on`
y única revisión **0003**. La conexión terminó con rollback y cierre.
`load_auth_config()` superó sus validaciones sin imprimir secretos.

No había listeners en 8000, 8001 o 5173 ni procesos Uvicorn/Vite anteriores del
workspace. PostgreSQL permaneció funcionando en 5434. No se detuvieron procesos.

| Componente | Destino efectivo | Proceso observado |
| --- | --- | --- |
| PostgreSQL existente | 127.0.0.1:5434, usuarios_dev, 0003 | Listener Windows 25552, conservado |
| FastAPI, factoría de desarrollo | 127.0.0.1:8000 | Python padre 34848; hijo/listener 17636 |
| React/Vite, configuración explícita de desarrollo | 127.0.0.1:5173 | Node/listener 12376 |

FastAPI se inició a las **16:31:35 -03:00** y Vite a las **16:32:00 -03:00**.
Los PIDs son evidencia del momento: deben revalidarse antes de cualquier acción
posterior. No se abrió escucha en LAN/Internet ni se inició una instancia en 8001.

## 2. Proxy separado y archivos ajustados

Se diagnosticó por lectura que `frontend/vite.config.ts` mantiene el destino
aislado **8001**. Para evitar cambiarlo se creó
`frontend/vite.development.config.ts`, que compone la configuración existente y
sobrescribe únicamente el proxy `/api` hacia **http://127.0.0.1:8000**.

Se resolvieron ambas configuraciones mediante la API de Vite y se comprobaron
sus destinos efectivos: configuración original **8001**, desarrollo **8000**;
ambas conservan host 127.0.0.1 y puerto estricto 5173. No ejecutarlas simultáneamente
en ese puerto. La selección explícita no depende de una variable que cambie los tests.

Se agregó el archivo al alcance de `frontend/tsconfig.json` y se documentó el
comando separado en `frontend/README.md`. No se modificaron `package.json`, lockfile,
dependencias, configuración JWT, contratos HTTP ni código funcional de la aplicación.

## 3. Arranque realizado

Desde backend, con el entorno virtual existente:

```powershell
.\.venv\Scripts\python.exe -B -m uvicorn app.bootstrap:create_app --factory --host 127.0.0.1 --port 8000 --no-proxy-headers --no-access-log
```

Desde frontend, el proceso iniciado equivale al siguiente comando reproducible:

```powershell
npm.cmd run dev -- --config vite.development.config.ts
```

Se lanzó directamente Node con `node_modules/vite/bin/vite.js --config
vite.development.config.ts --host 127.0.0.1`. Los procesos se iniciaron ocultos,
sin reload de Uvicorn, y **se dejan funcionando** para la revisión manual autorizada.
No repetir los comandos mientras estén activos. Los logs de arranque están bajo
el directorio ignorado `frontend/node_modules/.cache/86c-runtime/`; no se habilitó
logging de cuerpos, contraseñas, tokens ni accesos Uvicorn.

## 4. Comprobaciones realizadas

| Verificación | Resultado de esta intervención |
| --- | --- |
| Identidad y revisión PostgreSQL | usuarios_dev / 5434 / 0003, consulta de solo lectura |
| Inicio FastAPI | Application startup complete; sin ERROR/Traceback observado |
| OpenAPI directo en 8000 | Respuesta válida; ruta auth/me presente |
| GET auth/me directo, sin token | 401 esperado |
| Login React en Chrome real | Formulario email/contraseña cargado |
| Acceso anónimo a /dashboard, /usuarios y /cambiar-password | Redirección a /login en los tres casos |
| GET /api/v1/auth/me desde el navegador, a través de Vite | 401 AUTENTICACION_REQUERIDA y Cache-Control: no-store |
| Excepciones JavaScript / llamadas console.error | Cero en el recorrido anónimo |
| localStorage / sessionStorage del navegador aislado | Vacíos |
| Typecheck y lint | Aprobados tras el ajuste de configuración |
| Barrera productiva, llamada directa independiente | AprovisionamientoNoHabilitado esperado |

El recorrido Chrome utilizó CDP y herramientas ya instaladas, sin MSW,
interceptación de respuestas ni credenciales. Solo hizo navegación y GET de lectura;
no invocó login ni operaciones administrativas. El 401 es un rechazo esperado,
no un fallo de comunicación. Se comprobó el proxy y la API, pero un GET anónimo
no demuestra por sí mismo el recorrido autenticado de persistencia.

No se ejecutaron pytest, fixtures, Vitest, build ni auditorías de dependencias en
esta intervención. Los resultados de suites de informes previos son históricos.
El script auxiliar anónimo y el perfil temporal de Chrome están en la caché
ignorada; Chrome se cerró al concluir, los servidores de aplicación permanecen activos.

## 5. Comprobaciones pendientes del responsable

Se solicitó interacción manual en **http://127.0.0.1:5173**. Introducir las
credenciales personalmente allí; no enviarlas por chat, comandos ni informes.
No se inventaron credenciales ni se consultaron hashes para intentar acceder.

- Login de la cuenta de práctica existente y respuesta autenticada de auth/me.
- Dashboard y navegación correspondientes al rol efectivo.
- Listado y detalle de usuarios si la cuenta es ADMIN, sin editar datos.
- Logout y comprobación de que Atrás o una ruta protegida no recuperan contenido privado.
- Ausencia de errores relevantes durante ese recorrido autenticado.

El estado de estos puntos es **pendiente**, no aprobado por inferencia de las
pruebas anteriores. Comunicar solo éxito o código de error sin información personal.
No probar alta, asignación inicial ni cambio de contraseña como efecto secundario.
No se ofrece un puerto de inspección del navegador personal ni se extraen sus tokens.

## 6. Barrera, incidencias y límites

`require_initial_provisioning_enabled()` sigue rechazando incondicionalmente.
Se comprobó mediante llamada directa y captura del error esperado, sin monkeypatch,
conexión adicional o solicitud HTTP de aprovisionamiento. No se modificó ni abrió.

Durante la validación de Vite apareció un aviso por importación de configuración
sin extensión. Se precisó `.ts` en el nuevo archivo; no se ocultó el aviso mediante
variables ni se actualizaron paquetes. No se observaron fallos funcionales en el
alcance anónimo. Esta comprobación no certifica accesibilidad ni compatibilidad
completa de navegadores; no repite la auditoría visual anterior.

No se consultó ni modificó usuarios_test o su contenedor. No hubo migraciones,
respaldos, exportaciones, limpiezas, creación de usuarios, modificaciones de datos,
login automatizado ni emisión de credenciales por esta intervención. Los SELECT
de preflight y los GET anónimos no alteraron registros de práctica. El login/logout
manual posterior sí utilizará las escrituras normales de sesiones e intentos.

Se mantienen la omisión de respaldo y aceptación temporal A02 decididas para el
entorno local de práctica, con revisión antes de despliegue externo. Vite es un
servidor local de desarrollo, no una publicación productiva.

## 7. Recomendación y punto de control

**Arranque local satisfactorio; cierre funcional de Sprint 8.6 pendiente de la
verificación autenticada del responsable.** Mantener el sistema en localhost y
la barrera cerrada. No iniciar otros sprints, publicar externamente ni habilitar
aprovisionamiento a partir de este informe.

Para una futura detención, revalidar primero PIDs, fecha de creación, entrada y
workspace; detener solo estos procesos propios. No detener PostgreSQL ni procesos
por un número de puerto sin comprobar identidad.

Se entrega el informe y se espera el resultado de la interacción manual antes de
afirmar cierre completo. No se requieren ni solicitan contraseñas en la conversación.

## 8. Revisión funcional solicitada en navegador local

Fecha: **1 de noviembre de 2026**. Se repitió el recorrido anónimo en Chrome local
contra la aplicación existente en 5173, mediante el auxiliar CDP ya disponible.
No se modificaron código ni configuración. No hubo simulación HTTP.

| Prueba solicitada | Resultado | Código HTTP / evidencia limitada |
| --- | --- | --- |
| Carga de pantalla de login | **OK** | Formulario renderizado en Chrome |
| Introducción personal de credenciales por el responsable | **NO VERIFICADO** | El navegador automatizado usa un perfil aislado; requiere intervención manual |
| Login correcto | **NO VERIFICADO** | No se envió POST login ni se observó una sesión manual |
| auth/me autenticado | **NO VERIFICADO** | Solo se comprobó GET anónimo: **401 AUTENTICACION_REQUERIDA**, no-store |
| Navegación según rol autenticado | **NO VERIFICADO** | Sin acceso a sesión autenticada manualmente |
| Listado y detalle ADMIN | **NO VERIFICADO** | No se consultaron datos de usuarios |
| Cierre de sesión autenticada | **NO VERIFICADO** | No se envió POST logout |
| Rutas protegidas después de logout | **NO VERIFICADO** | No se ejecutó el ciclo login/logout |
| Rutas protegidas sin autenticación | **OK** | /dashboard, /usuarios y /cambiar-password redirigen a /login |
| Errores JavaScript en el recorrido anónimo | **OK** | Cero excepciones y cero llamadas console.error |

El responsable confirmó disponer de credenciales ADMIN; esto **no confirma** haber
completado el login ni las pruebas. El perfil temporal de automatización no comparte
su sesión personal y no se intentó extraerla, copiar cookies o capturar tokens.
Se detuvieron las comprobaciones que requieren autenticación. Chrome auxiliar se
cerró; no se detuvieron ni reiniciaron FastAPI o Vite.

Se solicita al responsable realizar personalmente login, comprobar en la pestaña
Red de su navegador únicamente los estados HTTP de login y auth/me, navegar a
listado/detalle si corresponde, cerrar sesión y probar Atrás/rutas protegidas.
Comunicar exclusivamente **OK, ERROR o NO VERIFICADO** y códigos HTTP/de error;
no compartir cuerpos de respuestas, capturas con información personal, cabeceras
Authorization, credenciales ni archivos HAR. No recargar durante las pruebas de
sesión: el JWT solo en memoria se pierde por diseño.

No se invocaron operaciones de aprovisionamiento, cambios de usuarios, fixtures,
migraciones o conexiones PostgreSQL en esta revisión. No se accedió a usuarios_test
ni se modificó la barrera. Su comprobación independiente anterior sigue siendo
antecedente; no se presenta como una nueva prueba HTTP autenticada.
**El cierre funcional continúa pendiente de los resultados manuales.**
