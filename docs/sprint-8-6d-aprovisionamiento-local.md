# Sprint 8.6D: habilitación controlada de aprovisionamiento local

Fecha: **1 de noviembre de 2026**. Estado actualizado: **habilitación local
verificada y ocho comprobaciones manuales confirmadas por el responsable**.
La confirmación final se registra en la **sección 11**; no es una nueva ejecución
automatizada ni una nueva inspección del estado de los procesos.
La confirmación expresa posterior permitió completar el reinicio. Las secciones
6 y 9 conservan el rechazo anterior como historial; el resultado vigente está
en la **sección 10**. El arranque normal y la CLI siguen cerrados por defecto.

## 1. Autorización y antecedentes

El responsable autorizó expresamente una habilitación local, reversible y cerrada
por defecto. Esta decisión reemplaza, únicamente para la instancia local descrita
en este informe, la prohibición anterior de introducir un mecanismo de activación.
No autoriza exposición externa, modificación de JWT ni ampliación de permisos.

Se revisaron el diseño 8.5A, sus incrementos de modelos, restricción, cambio seguro,
aprovisionamiento y frontend, la integración 8.5A.6 y los antecedentes 8.6B/8.6C.
La migración 0003 ya fue aplicada; no se crea ni ejecuta otra migración en desarrollo.
Los informes anteriores conservan su carácter histórico.

El responsable informó haber completado personalmente login como ADMIN y acceso
al formulario, donde encontró el rechazo esperado de la barrera. Es una evidencia
manual comunicada, no observación automatizada de su sesión. No confirma todavía
listado/detalle, logout ni el ciclo de una credencial inicial.

## 2. Modificación mínima

La función `require_initial_provisioning_enabled()` **continúa cerrada**. AuthService
admite una política administrativa opcional, inyectada por instancia. Si no existe,
utiliza la función cerrada anterior. El control de sesión normal y ADMIN precede a
esa política y se repite antes de escribir, junto con todas las validaciones previas.

El nuevo lanzador `app.presentation.cli.local_server` crea y verifica un socket
real, valida configuración y base efectiva y entrega la misma configuración
inmutable al punto de composición. Solo esa instancia recibe la política abierta.
No hay cambio global, endpoint de activación, variable `.env` ni flags de React.
La CLI de bootstrap/asignación conserva su barrera original, incluso si una
instancia HTTP está habilitada.

Archivos de implementación:

- `backend/src/app/application/auth/service.py`: política administrativa opcional.
- `backend/src/app/application/auth/provisioning.py`: explicación del cierre por defecto.
- `backend/src/app/bootstrap.py`: composición de la política por instancia.
- `backend/src/app/infrastructure/configuration/local_provisioning.py`: controles.
- `backend/src/app/presentation/cli/local_server.py`: arranque local explícito.
- `backend/tests/security/test_local_provisioning.py`: casos nuevos.
- `frontend/src/features/usuarios/components/UsuarioForm.tsx` y
  `AsignarCredencialInicial.tsx`: aviso neutral sobre disponibilidad del servidor.
- `frontend/src/features/usuarios/mutations.test.tsx`: expectativa del texto ajustada.
- `README.md`, `backend/README.md`, `frontend/README.md`: instrucciones vigentes.

No se duplican casos de uso ni rutas de creación. No cambian contratos HTTP,
modelos, migraciones, persistencia, dependencias, claves o políticas de contraseña.

## 3. Condiciones exactas de habilitación

Todas son necesarias:

1. Ejecutar el lanzador especial con `--environment local-development` y
   `--enable-initial-provisioning`. Sin ese segundo argumento no se inyecta política.
2. Host HTTP exactamente `127.0.0.1`; socket IPv4 ya vinculado y escuchando allí.
   No basta declarar un host en una variable o cabecera. Se sirve con ese mismo
   socket, sin reload, workers adicionales ni confianza en cabeceras de proxy.
3. Configuración DB exactamente `usuarios_dev / 127.0.0.1:5434`.
4. Conexión efectiva con `current_database()` y `current_user()` iguales a la
   configuración y revisión única `0003`, comprobadas en transacción de lectura.
5. Socket aún válido y escuchando en loopback al autorizar cada operación.

`production` y `test` se rechazan antes de cargar secretos o conectar la base.
Una configuración de pruebas, otro puerto/base/host o una identidad efectiva
distinta también se rechazan. El control no depende únicamente de un booleano.
La política no interpreta HTTP Host, X-Forwarded-For ni parámetros de requests.

## 4. Seguridad preservada

ADMIN con cambio pendiente sigue bloqueado; USUARIO no puede aprovisionar.
La inicial manual sigue siendo obligatoria, validada y hasheada con Argon2id.
Creación de perfil/credencial y asignación/revocación conservan atomicidad e
inserción estricta. No se reemplazan credenciales existentes ni se ofrece reset.
Login inicial restringido, cambio obligatorio, antecedente de inicial, revocación
total y nuevo login definitivo conservan el flujo y límites ya implementados.

La habilitación incluye los dos endpoints administrativos existentes: alta y
asignación inicial a perfil activo sin credencial. No implica permiso para crear
datos automáticamente durante la activación. El responsable realizará las pruebas
manuales en la interfaz con sus propias credenciales de práctica.

## 5. Pruebas aisladas

Antes de ejecutar integración se verificaron por lectura configuración y destino
efectivos: **usuarios_test / usuarios_test_admin / 127.0.0.1:5435 / 0003**.
Las fixtures conservan sus guardas. No se dirige pytest a desarrollo.

Las pruebas nuevas usan sockets loopback efímeros y dobles de identidad para
validar el permiso de desarrollo **sin conectar a usuarios_dev**. Incluyen un
rechazo frente a PostgreSQL de pruebas real aunque se declare otra identidad.
El recorrido de negocio se ejecuta en memoria y en usuarios_test, no en desarrollo.

Comandos desde backend:

```powershell
.\.venv\Scripts\python.exe -B -m pytest -q --run-postgres -p no:cacheprovider --basetemp=.pytest_cache/86d-full --tb=short
.\.venv\Scripts\python.exe -B -m pytest -q tests/security/test_local_provisioning.py --run-postgres -p no:cacheprovider --basetemp=.pytest_cache/86d-policy-final --tb=short
```

Desde frontend: `npm.cmd run typecheck`, `npm.cmd run lint`, `npm.cmd test` y
`npm.cmd run build`, ejecutados secuencialmente con parada ante cualquier fallo.

| Comprobación | Resultado |
| --- | --- |
| Suite backend completa | **592 aprobadas**, 236,42 s; 568 anteriores y 24 nuevas |
| PostgreSQL / sin PostgreSQL dentro de esa ejecución | **162 / 430**, únicamente usuarios_test y memoria |
| Política/lanzador, ejecución final dirigida | **27 aprobadas**, 1,46 s |
| Frontend Vitest/MSW | **151 aprobadas en 8 archivos**, 167,96 s |
| Typecheck / lint | Aprobados |
| Build | Aprobado, 944 módulos |
| Barrera normal, proceso independiente | Cerrada, AprovisionamientoNoHabilitado esperado |

Después de la suite completa se precisó el código de salida del lanzador ante
fallo de inicio de Uvicorn y se añadieron tres casos de composición/arranque.
La ejecución dirigida final incluye esos tres y repite los 24 nuevos anteriores;
**no se suman como si hubiera una suite única de 619 pruebas**. Verifica opt-in,
cierre por defecto, socket cerrado, entorno/host/base/revisión inválidos, fallo de
arranque, creación ADMIN, rechazo de USUARIO/pendiente, no sobrescritura y ciclo
inicial → cambio → revocación → login definitivo, con antecedente conservado.
La regresión completa conservó los recorridos reales de navegador aislado de las
etapas anteriores; no representan una prueba autenticada sobre desarrollo.

La primera ejecución dirigida tuvo un error de preparación en una nueva prueba
por argumentos posicionales de un DTO nominal; se corrigió la prueba y las
ejecuciones posteriores aprobaron. Permanece el aviso previo Starlette/TestClient
sobre httpx; no se cambiaron paquetes para ocultarlo.

## 6. Primer intento de activación: historial

Tras aprobar las pruebas se revalidaron por lectura **usuarios_dev /
127.0.0.1:5434 / usuarios_dev_admin / 0003** y AuthConfig sin imprimir secretos.
Se confirmó en un proceso independiente que la función normal sigue cerrada.
No se ejecutaron pytest, fixtures, migraciones o escrituras contra desarrollo.

Se identificaron para reinicio el padre Python **34848** y su hijo/listener
**17636**, factoría `app.bootstrap:create_app` del workspace, creados a las
16:31:35 -03:00. El intento preparado exigía coincidencia de creación, padre,
workspace, entrada y listener antes de detenerlos.

**El sistema de revisión automática rechazó la ejecución del comando de reinicio
y activación antes de iniciarlo.** Motivo comunicado: la acción abre una capacidad
de seguridad para esa instancia y no había autorización explícita confiable visible
para ese cambio exacto. La solicitud adjunta del responsable sí describe esa
activación; se registra la discrepancia sin intentar eludir la revisión mediante
otro comando o mecanismo.

No se ejecutó Stop-Process ni se inició el nuevo lanzador. Una inspección posterior
de solo lectura confirmó:

| Recurso | Estado observado al finalizar el primer intento |
| --- | --- |
| Backend normal | Padre 34848 / hijo 17636, listener 127.0.0.1:8000; sin lanzador nuevo |
| React/Vite | PID 12376, listener 127.0.0.1:5173; no reiniciado |
| Habilitación local nueva | **No activada** |
| Función normal de barrera | **Cerrada** |

Comando preparado, **NO ejecutado**, desde backend tras resolver la autorización
operativa y revalidar los procesos actuales:

```powershell
.\.venv\Scripts\python.exe -B -m app.presentation.cli.local_server --environment local-development --enable-initial-provisioning --host 127.0.0.1 --port 8000
```

React conserva `http://127.0.0.1:5173`, con configuración explícita de desarrollo
y proxy `/api` hacia 8000; la configuración aislada sigue apuntando a 8001.
No se publican servicios fuera de loopback. No se imprimen respuestas de perfiles,
contraseñas, hashes, tokens o configuración sensible.

Los datos de desarrollo no fueron creados ni alterados por esta intervención.
No se realizaron login o solicitudes HTTP de aprovisionamiento en desarrollo.
PostgreSQL y React no se detuvieron. Las escrituras, fixtures y migraciones de
regresión se limitaron al destino de pruebas comprobado.

## 7. Recorrido manual: confirmado posteriormente en sección 11

Al entregar la activación de la sección 10 quedó pendiente efectuar personalmente:
login ADMIN, creación de una cuenta de
práctica con inicial, logout, login de la nueva cuenta, redirección al cambio
obligatorio, cambio por una definitiva y nuevo login normal. Comprobar también
que un ADMIN pendiente no tenga navegación administrativa. No enviar secretos,
respuestas completas o capturas con información personal al chat.

No se afirma que ese recorrido esté verificado operativamente por ejecutar tests.
La sesión personal del responsable no se comparte con el navegador automatizado.

## 8. Reversión y riesgos residuales

Para cerrar de nuevo, revalidar y detener exclusivamente los procesos propios del
lanzador y reiniciar sin `--enable-initial-provisioning`, o con la factoría normal:

```powershell
.\.venv\Scripts\python.exe -B -m uvicorn app.bootstrap:create_app --factory --host 127.0.0.1 --port 8000 --no-proxy-headers --no-access-log
```

No editar `.env`, borrar datos, hacer downgrade ni modificar la función global.
La retirada del permiso no deshace credenciales ya creadas ni elimina el cambio
obligatorio de las cuentas pendientes. Un reinicio interrumpe solicitudes activas;
coordinarlo y no reenviar automáticamente una creación de resultado incierto.

Se conserva el riesgo A02 aceptado temporalmente para práctica local, la decisión
previa de no respaldar y los límites conocidos: inicial sin TTL, sin recuperación
o reset, entrega manual segura, hash inicial adicional y JWT solo en memoria.
La etiqueta de entorno es una declaración del operador y se complementa con
destino efectivo y socket real; no es una certificación de infraestructura de
producción. No usar túneles, proxies externos ni exposición LAN para esta instancia.

No se inicia Sprint 9 ni se autoriza un despliegue externo.

## 9. Punto de control anterior, superado por la sección 10

La implementación está preparada y verificada en aislamiento. El bloqueo vigente
es operativo, de revisión automática; **no se declara habilitado el aprovisionamiento**.
Se solicita confirmación explícita en la conversación para detener únicamente el
backend propio revalidado en 8000 y arrancar el lanzador local con el opt-in indicado.
Hasta resolverlo no ejecutar las pruebas manuales de creación/asignación.
Se entrega este informe y se detiene el trabajo sin iniciar otro sprint.

## 10. Confirmación expresa y activación completada

Fecha: **1 de noviembre de 2026**, arranque a las **18:47:44 -03:00**.
El responsable confirmó expresamente en la conversación la detención del backend
propio y el inicio del lanzador con opt-in, limitado a local-development,
usuarios_dev:5434, revisión 0003 y HTTP 127.0.0.1:8000. La revisión automática
permitió esta operación tras esa confirmación. No se utilizó una vía alternativa
para eludir el rechazo histórico.

### Controles previos y procesos

Antes de modificar procesos se releyeron este informe, el lanzador, su política y
el proxy de desarrollo. Se verificaron por conexión forzada a solo lectura base y
usuario efectivos, destino **usuarios_dev / 127.0.0.1:5434**, revisión única
**0003** y modo de lectura. AuthConfig pasó sus validaciones sin revelar valores.
La función normal se comprobó cerrada en un proceso independiente.

Se revalidaron los procesos actuales **17636**, hijo de **34848**, con entrada
Uvicorn `app.bootstrap:create_app`, referencia exacta al workspace y creación
2026-11-01 19:31:35 UTC. El listener único de 8000 pertenecía a 17636 y estaba
en 127.0.0.1. No había otra instancia backend del proyecto en la inspección.

Se detuvo 17636 mediante Stop-Process. Se comprobó el padre 34848 y se aseguró su
cierre antes del nuevo arranque. No se detuvieron React, PostgreSQL, Docker o
procesos ajenos. Se exigió que 8000 quedara libre antes de iniciar el lanzador.

Se ejecutó desde backend con el entorno virtual existente:

```powershell
.\.venv\Scripts\python.exe -B -m app.presentation.cli.local_server --environment local-development --enable-initial-provisioning --host 127.0.0.1 --port 8000
```

El inicio se realizó con Start-Process oculto y logs bajo el directorio ignorado
`frontend/node_modules/.cache/86d-runtime/`, sin logging de accesos o cuerpos.
El lanzador validó identidad/revisión por lectura y reservó el socket real
loopback antes de componer la política administrativa de esta instancia.

### Resultado real verificado

| Control | Resultado observado |
| --- | --- |
| Proceso nuevo | Padre Python **31616**, hijo/listener **25604** |
| Identidad del listener | Lanzador local del workspace, opt-in explícito y padre 31616 |
| Socket HTTP | Único listener de 8000, **127.0.0.1** |
| Confirmación de habilitación | Marcador **Local server: initial provisioning ENABLED** |
| Inicio de aplicación | **Application startup complete**, sin ERROR/Traceback observado |
| GET OpenAPI directo | **200**, rutas existentes verificadas sin imprimir el documento |
| GET auth/me anónimo directo | **401** esperado |
| GET auth/me anónimo a través de Vite | **401** esperado |
| GET /login en Vite | **200**, HTML de entrada de React disponible |
| Frontend | **127.0.0.1:5173**, PID **12376** conservado; sin reinicio |
| Procesos backend anteriores | Ausentes tras el reinicio |
| Función normal en otro proceso, después de activar | **Cerrada**, AprovisionamientoNoHabilitado esperado |

La activación se confirma por el lanzador ejecutado, sus controles previos, el
marcador de política habilitada, el inicio completo y la identidad del socket
servido. **No se probó una creación o asignación autenticada en desarrollo**:
ese resultado funcional sigue pendiente del responsable y no se infiere de un
GET anónimo. Tampoco se extrajo ni reutilizó su sesión personal.

En esta reanudación solo se actualizó el informe: no se modificaron código,
configuración JWT, proxy o dependencias. No se ejecutaron migraciones, pytest,
fixtures, limpiezas, creación automática de cuentas o escrituras de datos de
aplicación. No se accedió a usuarios_test ni a su contenedor. Las pruebas de la
sección 5 son antecedentes aprobados; no se presentan como nuevas ejecuciones.

### Estado entregado y revisión manual

**FastAPI local habilitado y React disponibles** para que el responsable complete
el recorrido de la sección 7 en **http://127.0.0.1:5173**. Introducir personalmente
credenciales e iniciales en la interfaz; comunicar solo resultados/códigos sin
secretos o datos personales. El servicio mantiene permisos ADMIN, sesiones
restringidas, cambio obligatorio y las validaciones ya probadas.

La reversión descrita en la sección 8 sigue disponible: reiniciar sin el opt-in
vuelve a cerrar únicamente el aprovisionamiento, sin eliminar credenciales ni
quitar obligaciones de cambio. Los PIDs deben revalidarse antes de cualquier
intervención futura. No se inicia Sprint 9 ni se publica externamente.
Se finaliza la operación y se espera revisión y resultados manuales.

## 11. Cierre funcional confirmado por el responsable

El responsable comunicó expresamente que completó correctamente las siguientes
ocho verificaciones en el entorno local de práctica:

| Verificación | Resultado comunicado |
| --- | --- |
| Login ADMIN | OK |
| Creación de usuario con contraseña inicial | OK |
| Logout ADMIN | OK |
| Primer login restringido | OK |
| Cambio obligatorio de contraseña | OK |
| Nuevo login con contraseña definitiva | OK |
| Rechazo de acceso administrativo para USUARIO | OK |
| Logout y protección posterior de rutas | OK |

**Evidencia: confirmación manual del responsable**, recibida al autorizar el diseño
9.1. Codex no observó ni automatizó ese recorrido, no recibió credenciales y no
atribuye códigos HTTP concretos que no fueron comunicados. No se registran nombres,
emails, contraseñas, tokens ni datos de las cuentas de práctica.

Se considera completado el recorrido funcional local de 8.6D. La autorización
actual abre exclusivamente el **diseño e inspección de Sprint 9.1**; no inicia 9.2
ni convierte la habilitación local en una aprobación de despliegue externo.
No se reiniciaron servicios ni se cambió la barrera al registrar esta confirmación.
Los riesgos residuales y el procedimiento de cierre de la sección 8 se mantienen.
Ver [cierre de Sprint 8](sprint-8-cierre.md).
