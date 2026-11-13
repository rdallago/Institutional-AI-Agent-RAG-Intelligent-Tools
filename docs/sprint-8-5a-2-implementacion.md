# Incremento 8.5A.2: sesiones restringidas y autorización en backend

Fecha: 30 de octubre de 2026. Estado: **implementado y verificado** en memoria y
usuarios_test. El alcance se detiene en 8.5A.2; no completa el cambio obligatorio
ni habilita el aprovisionamiento de credenciales pendientes.

## Archivos modificados y creados

Modificados:

- `backend/src/app/application/auth/service.py`: alcance de sesión en login,
  validación básica/normal separadas, contexto mínimo y control dentro de manage.
- `backend/src/app/application/auth/exceptions.py`: CambioPasswordRequerido.
- `backend/src/app/presentation/http/auth/dependencies.py`: dependencia explícita
  get_valid_session; get_current_user mantiene acceso normal como requisito.
- `backend/src/app/presentation/http/auth/router.py`: DTO de login y unión
  discriminada de me; dependencia de sesión válida para me/password.
- `backend/src/app/presentation/http/errors.py`: traducción pública del nuevo 403.
- `backend/tests/security/test_auth_models_persistence.py`: adaptación de
  expectativas de login/me y rehash al alcance implementado, conservando los casos.

Creados:

- `backend/tests/security/test_restricted_sessions.py`.
- `docs/sprint-8-5a-2-implementacion.md` (este informe).

No se modificaron modelos, persistencia, migraciones 0001/0002/0003, contratos de
perfiles, reglas ADMIN/USUARIO, frontend, Docker, configuración ni dependencias.

## Reglas incorporadas

Login decide `Sesion.restringida` desde `Credencial.debe_cambiar_password` dentro
de la UoW final, después de volver a comprobar usuario activo y hash. No usa una
marca antigua leída antes de verificar Argon2. El rehash conserva los campos de
credencial. El JWT mantiene firma, cabeceras, claims y duración de 900 segundos;
no contiene rol, alcance ni bandera nueva. PostgreSQL/memoria siguen siendo la
fuente de verdad para cada comprobación de sesión.

`authenticate_session` comprueba JWT y sesión persistida: identidad vinculada,
revocación, expiración, usuario activo y credencial existente. `_active` también
rechaza una sesión restringida cuya credencial ya no está pendiente: no la promueve.

`authenticate` exige además acceso normal mediante `_normal`: credencial sin
obligación y sesión no restringida. Es el camino predeterminado de los endpoints
de perfiles mediante get_current_user. `manage` repite esta comprobación dentro
de su propia UoW antes de aplicar rol, propiedad o ejecutar un caso de uso. Un
Principal construido directamente o una autorización anterior no permiten eludirla.

| Estado persistido | Resultado |
| --- | --- |
| Credencial normal + sesión normal | Permisos de rol y propiedad anteriores |
| Credencial pendiente + sesión restringida | Solo contexto mínimo, password actual y logout |
| Credencial pendiente + sesión normal antigua | Mismo bloqueo de operaciones normales; me mínimo |
| Credencial normal + sesión restringida | 401 AUTENTICACION_REQUERIDA, sin promoción |
| Sesión revocada/vencida, vínculo incorrecto, perfil inactivo o sin credencial | 401 antes del error de cambio pendiente |

**ADMIN pendiente tampoco puede administrar usuarios.** Listado, detalle propio,
detalle ajeno, creación, edición, baja y reactivación se rechazan con
`403 CAMBIO_PASSWORD_REQUERIDO`. No se revelan datos del destino ni se realizan
escrituras. La restricción precede a cualquier privilegio de rol.

No se agregó un middleware que bloquee rutas públicas. Login, documentación y
OpenAPI continúan disponibles. Logout conserva su camino previo de token firmado
y vigente, con revocación idempotente; no requiere acceso normal.

## Contratos HTTP

Los cambios se limitan a autenticación:

- POST `/api/v1/auth/login`: entrada sin cambios. Agrega el booleano obligatorio
  `debe_cambiar_password` a la respuesta, derivado de la sesión confirmada.
  Mantiene access_token, token_type y expires_in=900; ambos alcances responden 200.
- GET `/api/v1/auth/me`: respuesta discriminada por debe_cambiar_password.
  Para normales devuelve los siete campos del perfil más false. Para pendientes
  devuelve **únicamente id y debe_cambiar_password=true**, sin nombre, email o rol.
  Usa DTO específicos de auth; UsuarioResultado y UsuarioRespuesta de administración
  no fueron modificados.
- Operaciones normales prohibidas: nuevo error saneado 403 con código
  CAMBIO_PASSWORD_REQUERIDO y mensaje «Debe cambiar su contraseña antes de continuar.».
- PUT `/api/v1/auth/password`: entrada y éxito 204 sin cambios. Su dependencia
  acepta sesión válida restringida; mantiene comprobación de actual, política
  vigente, actualización y revocación total dentro del servicio.
- POST `/api/v1/auth/logout`: contrato anterior conservado.

Las respuestas auth mantienen Cache-Control no-store; login también Pragma
no-cache. Los 401 mantienen WWW-Authenticate Bearer. No se serializan hashes ni
se agregan secretos a errores o logs. Los usuarios normales conservan su acceso;
sus respuestas auth solo reciben el campo adicional false. Los validadores React
actuales admiten campos adicionales para respuestas normales, según lectura del
código; no se ejecutaron pruebas frontend ni se modificó su implementación.

## Pruebas y resultados

Las fixtures nuevas generan exclusivamente perfiles y secretos ficticios. La
misma matriz se ejecuta para ADMIN y USUARIO, sobre memoria y PostgreSQL. Incluye:

- Login normal/restringido, alcance persistido y claims JWT originales.
- HTTP directo sobre todas las rutas de usuarios; inventario de rutas contrastado
  con OpenAPI para detectar operaciones nuevas sin cobertura.
- Llamadas directas a manage con Principal, sin dependencias FastAPI.
- Contexto mínimo de me para token restringido y token normal antiguo.
- Rechazo defensivo de sesión restringida con credencial definitiva.
- Compatibilidad de perfil/rol normal, logout repetido y revocación.
- Disponibilidad de password, error de actual incorrecta sin perder la sesión
  válida y conservación del comportamiento anterior del cambio.
- Inactividad, credencial ausente, revocación, expiración y vínculo incorrecto.
- Login/documentación públicos y rechazo indistinguible de credenciales inválidas.
- Estado modificado después de la dependencia y durante la verificación de login.
- Ausencia de datos de terceros, contraseña y token en los errores probados/logs.

Comando final, desde backend:

```powershell
.\.venv\Scripts\python.exe -m pytest -q --run-postgres -p no:cacheprovider --basetemp=.pytest_cache/85a2-full-temp
```

| Verificación | Resultado |
| --- | --- |
| Suite backend completa | **404 aprobadas**, sin fallos, en 50,93 segundos |
| Casos anteriores conservados/adaptados | **340 aprobados** |
| Casos nuevos | **64 aprobados** |
| Casos PostgreSQL incluidos | **74 aprobados** |
| Casos sin PostgreSQL incluidos | **330 aprobados** |
| Revisión final de usuarios_test | **0003** |
| Alembic check final | **No new upgrade operations detected.** |

La ejecución inicial sin PostgreSQL obtuvo 328 aprobadas y 74 omitidas, con dos
errores de preparación de pruebas de configuración por permisos del directorio
temporal. La ejecución completa con permisos adecuados aprobó esas dos pruebas
y las restantes; no hubo que cambiar código ni validaciones para resolverlo.
Permanece un aviso existente de Starlette/TestClient sobre httpx; no se cambiaron
dependencias para suprimirlo.

## Aislamiento de bases

Antes de las integraciones se cargó solo la configuración de pruebas, se validó
`require_test_database()` y se comprobó por lectura el destino real mediante
`current_database()` y `current_user`: usuarios_test / usuarios_test_admin,
conexión configurada **127.0.0.1:5435**, revisión 0003. Solo después se habilitó
--run-postgres. La comprobación final repitió la validación de destino.

Las fixtures conservan sus guardas antes de limpiar datos. La suite completa
incluye las regresiones previas de migración, upgrade/downgrade y limpieza,
exclusivamente sobre usuarios_test. No se editó ninguna migración.

**No se accedió a usuarios_dev ni al puerto 5434; no se modificaron usuarios,
contraseñas o sesiones reales.** No se inició el backend de desarrollo ni se
leyeron sus secretos. No se modificó ningún contenedor.

## Limitaciones y punto de control

El cambio obligatorio completo sigue pendiente de 8.5A.3. El endpoint actual
password todavía no elimina debe_cambiar_password ni rechaza reutilización de la
inicial/actual; tampoco incorpora el limitador nuevo previsto para ese cambio.
Tras cambiar mediante ese endpoint, una credencial pendiente permanece pendiente
y sus siguientes logins continúan restringidos. Esto conserva deliberadamente
el alcance solicitado, sin conceder acceso normal antes de completar el flujo.

React aún no reconoce el estado restringido ni ofrece el formulario obligatorio.
No se deben emitir credenciales pendientes operativas: solo las fixtures aisladas
las crean para probar. No se agregó aprovisionamiento HTTP, se alteró bootstrap
ni se conectó la inserción estricta a una vía nueva de emisión.

El backend actualizado continúa requiriendo esquema 0003. Desarrollo permanece
fuera de esta intervención: no iniciar allí contra 0002 ni migrarlo sin una nueva
autorización. El despliegue coordinado y las barreras de habilitación del diseño
siguen vigentes.

Se detiene el trabajo en **8.5A.2** y se espera aprobación antes de continuar.
