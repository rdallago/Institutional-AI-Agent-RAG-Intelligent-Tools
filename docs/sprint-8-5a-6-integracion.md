# Incremento 8.5A.6: integración y validación

Fecha: 31 de octubre de 2026. Estado: verificación integral en entorno aislado.
El aprovisionamiento operativo sigue **deshabilitado**. No se inicia Sprint 8.6.

## 1. Arquitectura integrada

Se contrastaron el diseño 8.5A, sus informes 1–5 y los contratos reales.
El recorrido de navegador conecta **Chrome → React/Vite → FastAPI → PostgreSQL**,
sin MSW, interceptación de respuestas ni repositorios en memoria en ese recorrido.
FastAPI utiliza AuthService, SecurityUnitOfWork y los adaptadores PostgreSQL reales.
Las claves JWT/limitador se generan en memoria con los helpers de pruebas; los
perfiles y contraseñas son ficticios. Se utiliza el Argon2id de pruebas, con coste
reducido; no constituye una medición de rendimiento del hasher productivo.

Los servidores del arnés escuchan únicamente en `127.0.0.1:18001` (FastAPI) y
`127.0.0.1:15173` (Vite). Se verifica disponibilidad antes de iniciarlos y se
detienen al terminar. Los puertos habituales 8001/5173 estaban ocupados: no se
consultaron ni detuvieron sus servicios. La sustitución de puertos y proxy ocurre
solo en el proceso de pruebas; no cambia vite.config.ts ni habilita credenciales.

## 2. Contratos verificados

| Operación | Contrato contrastado entre servidor y cliente |
| --- | --- |
| POST auth/login | email/password; 200 con access_token, token_type=bearer, expires_in=900 y booleano debe_cambiar_password obligatorio |
| GET auth/me normal | Perfil completo activo más debe_cambiar_password=false |
| GET auth/me restringido | Exclusivamente id y debe_cambiar_password=true |
| PUT auth/password | password_actual/password_nueva; confirmación solo local; 204 sin cuerpo, revocación total y nuevo login |
| POST auth/logout | 204 sin cuerpo; token revocado no habilita operaciones protegidas |
| POST usuarios | nombre/apellido/email/rol/password_inicial; 201 y perfil sin secretos, únicamente bajo fixture positiva; barrera cerrada devuelve 403 |
| POST usuarios/{id}/credencial-inicial | Solo password_inicial; 204 sin cuerpo; no reemplaza una credencial existente |
| Consultas y edición | DTO de perfil sin secretos; PUT conserva únicamente nombre/apellido/email |
| Errores | Envoltorio error con codigo/mensaje y detalles saneados; 401, 403, 409, 422 y 429 según contexto |

Se comprobó la distinción entre CREDENCIALES_INVALIDAS por contraseña actual
incorrecta y AUTENTICACION_REQUERIDA por sesión inválida. Los primeros no destruyen
una sesión válida. CAMBIO_PASSWORD_REQUERIDO impide acceso normal incluso a ADMIN;
PERMISO_DENEGADO no equivale a logout. Se conservan PASSWORD_REUTILIZADA,
PASSWORD_INVALIDA y APROVISIONAMIENTO_NO_HABILITADO.

Las pruebas backend comprueban Retry-After real y el presupuesto compartido
login/password. Las pruebas frontend con MSW comprueban la cuenta regresiva y
ausencia de reintentos. No se presenta esa simulación como una respuesta real del
limitador atravesando Chrome. Los 204 de ambos recorridos completos sí son reales.

## 3. Escenarios ejecutados

| Escenario | Evidencia |
| --- | --- |
| A: creación administrativa | Chrome autentica ADMIN histórico, crea perfil con inicial, cierra sesión, autentica destinatario restringido, verifica redirección obligatoria y bloqueo de /usuarios, cambia contraseña y vuelve a ingresar normalmente |
| B: perfil histórico sin credencial | Chrome autentica ADMIN, abre detalle del perfil ficticio, asigna inicial mediante diálogo, autentica destinatario, completa cambio obligatorio y realiza nuevo login normal |
| C: seguridad | Suite HTTP/aplicación real sobre memoria y PostgreSQL: ADMIN pendiente sin administración, USUARIO sin aprovisionamiento, no sobrescritura, inactivos rechazados, revocación, no reutilización y llamadas directas sin bypass |
| D: barrera cerrada | Caso Chrome independiente sin fixture especial: rechazo real mostrado por React, sin navegación de éxito ni perfil parcial; lectura PostgreSQL confirma ausencia de perfil nuevo y de credencial del histórico |

El caso positivo lee después desde otra UoW las credenciales de ambos destinatarios:
hash definitivo válido, marca pendiente=false y antecedente inicial conservado.
Tras los logout finales no quedan sesiones sin revocar en las fixtures de ese caso.
Las pruebas específicas existentes verifican además que el cambio revoca todas las
sesiones anteriores y que sus JWT reciben 401, no solo una redirección visual.

Chrome comprueba ausencia de excepciones JavaScript y almacenamiento web vacío.
La limpieza del token privado se verifica mediante comportamiento de navegación y
pruebas del proveedor; el arnés no extrae ni imprime ese ref privado.

## 4. Backend y resultados

Desde backend:

```powershell
.\.venv\Scripts\python.exe -m pytest -q --run-postgres -p no:cacheprovider --basetemp=.pytest_cache/85a6-full-temp --tb=short
.\.venv\Scripts\python.exe -m pytest -q tests/integration/postgresql/test_browser_password_flow.py --run-postgres -p no:cacheprovider --basetemp=.pytest_cache/85a6-browser-final-temp --tb=short
```

La suite completa aprobó **558 pruebas** en **134,40 s**: las 556 anteriores y
dos recorridos reales nuevos. Incluye **153 casos PostgreSQL** y **405 sin
PostgreSQL**. No se suman repeticiones del mismo caso como pruebas diferentes.
El segundo comando verifica las últimas aserciones adicionales del arnés.
Su ejecución final aprobó **2 de 2 casos en 27,73 s**, después de los ajustes
de sincronización, preparación y comprobaciones de persistencia.

La comprobación final de Alembic, con database_config de pruebas explícita,
devolvió **No new upgrade operations detected.** Se reconfirmó revisión **0003**
y ausencia de filas de fixtures en usuarios, usuario_credenciales, auth_sesiones
y auth_intentos tras la limpieza de pruebas. Los puertos propios 18001/15173
quedaron sin listeners. La consulta final fue de solo lectura.

La regresión cubre autorización, cambio voluntario/obligatorio, errores y secretos,
concurrencia, rollback, sesiones, límites cruzados y migraciones históricas.
Los upgrade/downgrade de regresión ocurrieron solo en usuarios_test. No se creó
ni editó ninguna migración. Permanece el aviso previo de Starlette sobre httpx en
TestClient; no se instalaron dependencias para ocultarlo.

## 5. Frontend y resultados

Desde frontend:

```powershell
npm.cmd run typecheck
npm.cmd run lint
npm.cmd test
npm.cmd run build
```

Typecheck y lint aprobaron sin errores ni advertencias. Vitest aprobó **151
pruebas en 8 archivos**, en **196,86 s**. Build aprobado, 944 módulos, separación
por rutas y mayor chunk de 218,75 kB antes de gzip. No se cambiaron dependencias.

Se conserva cobertura de listado, filtro de estado, paginación sin total, detalle,
edición, baja lógica, reactivación y permisos. Creación y asignación se ejercitan
positivamente solo en pruebas habilitadas. **No existe búsqueda por texto en el
contrato actual**; no se añadió ni se afirma haber verificado una funcionalidad
de búsqueda inexistente. Los filtros actuales permanecen cubiertos.

## 6. Integración real y archivos nuevos

- `backend/tests/integration/postgresql/test_browser_password_flow.py`: preflight
  de base/revisión antes de fixtures que escriben, servidores loopback, uso de
  fixture autorizada, comprobaciones PostgreSQL y cierre de recursos propios.
- `backend/tests/integration/postgresql/browser_password_flow.mjs`: Chrome CDP
  mediante Node ya instalado, formularios reales y navegación SPA. No intercepta
  tráfico ni genera capturas, vídeos o trazas de autenticación.
- `docs/sprint-8-5a-6-integracion.md`: este informe.

No se modificó código productivo de backend o frontend, configuración, contratos,
modelos, migraciones, Docker ni archivos de secretos. No se instalaron herramientas.
Los perfiles temporales de Chrome quedan en node_modules/.cache, ignorado por Git;
el arnés no escribe explícitamente valores de inputs, JWT ni hashes en artefactos.

## 7. Pruebas simuladas

Las 151 pruebas de frontend utilizan MSW, incluyendo errores de red, timeout,
respuestas tardías, 401/403/422/429/500, contratos inválidos y resultados ambiguos.
Son pruebas de comportamiento de React con HTTP simulado. Se distinguen de los
dos casos Chrome con FastAPI/PostgreSQL reales y de las integraciones HTTP backend.
Las pruebas unitarias en memoria tampoco se presentan como persistencia real.

## 8. Incidencias y correcciones

No se identificó una incompatibilidad que requiriera cambiar contratos o código
productivo. Durante preparación del arnés se detectaron puertos ocupados y se
usaron otros puertos loopback libres, conservando intactos los servicios ajenos.
Se corrigieron en el arnés una espera de formulario entre logout/login y el orden
de argumentos de verify(encoded, password) en una aserción nueva. También se
revoca explícitamente la sesión auxiliar de preparación, que el navegador no
reutiliza, antes de comprobar que no queda ninguna sesión vigente. Los fallos
intermedios no se contabilizan como aprobaciones.

## 9. Aislamiento de las bases

Antes de integrar se cargó exclusivamente load_database_config(testing=True), se
ejecutó require_test_database y se confirmó por consultas de solo lectura:
**usuarios_test / usuarios_test_admin / 127.0.0.1:5435 / revisión 0003**.
El arnés repite esas comprobaciones antes de invocar las fixtures de migración o
limpieza. Las fixtures existentes mantienen además su guarda de destino real.
No hay fallback a desarrollo ni uso de create_all.

**No se accedió a usuarios_dev ni al puerto 5434**, no se leyeron secretos de
desarrollo y no se modificaron usuarios, credenciales o sesiones reales.
Las limpiezas de regresión afectan únicamente datos ficticios de usuarios_test.

## 10. Barrera cerrada

require_initial_provisioning_enabled conserva su rechazo incondicional productivo.
El recorrido positivo obtiene la fixture existente initial_provisioning_test_gate
solo dentro del caso pytest; no se creó un interruptor de entorno, HTTP o CLI.
El caso cerrado no usa esa fixture y demuestra el rechazo real desde React.
Los servidores se detienen antes de restaurar la fixture. La emisión operativa
continúa prohibida y requiere autorización y cambio revisado separados.
Una comprobación en otro proceso Python confirmó además el rechazo productivo,
sin monkeypatch ni acceso a una base.

## 11. Limitaciones

La verificación de navegador usa Chrome headless de escritorio, servidor Vite y
datos ficticios. No es una auditoría completa de accesibilidad, responsive,
compatibilidad entre navegadores, despliegue estático/HTTPS ni rendimiento de
Argon2id productivo. Cambio voluntario, agotamiento de límites y fallos de red se
cubren por suites backend/frontend, no todos mediante un recorrido Chrome real.
No se probaron cuentas reales ni el despliegue de desarrollo.

La recarga pierde el JWT por diseño. No hay refresh, reset administrativo,
recuperación, historial general ni vencimiento propio de contraseña inicial.
La entrega de la inicial sigue siendo manual y requiere un canal seguro.

## 12. Recomendaciones para Sprint 8.6

Con otra autorización: revisar visualmente móvil/escritorio, teclado, foco,
mensajes accesibles y navegación Atrás; completar pruebas entre navegadores y
de cambio voluntario/429 en navegador si se amplía esa cobertura. Usar únicamente
cuentas ficticias y usuarios_test. No abrir operativamente la barrera para esas
comprobaciones: reutilizar el proceso pytest aislado.

Antes de desplegar, aprobar un procedimiento coordinado que detenga escrituras,
verifique esquema 0003, publique backend/React compatibles y evite clientes viejos
en caché. La migración de desarrollo y la habilitación de aprovisionamiento siguen
requiriendo autorizaciones separadas. Este incremento no ejecuta esos pasos.

Se detiene el trabajo en **8.5A.6**, sin iniciar Sprint 8.6.
