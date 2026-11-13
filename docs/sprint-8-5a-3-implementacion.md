# Incremento 8.5A.3: cambio obligatorio y seguro de contraseña

Fecha: 30 de octubre de 2026. Estado: **implementado y verificado exclusivamente
en memoria y usuarios_test**. El trabajo se detiene en 8.5A.3, sin habilitar
aprovisionamiento de credenciales pendientes ni modificar React.

## Archivos modificados

- `backend/src/app/application/auth/service.py`: cambio obligatorio/voluntario,
  rechazo de reutilización, límites, snapshot completo y confirmación atómica.
  Login conserva su contrato y utiliza el handle de su reserva al liberarla.
- `backend/src/app/application/auth/ports.py`: protocolo de reserva y devolución
  del handle desde check; success requiere la reserva concreta que debe liberar.
- `backend/src/app/application/auth/exceptions.py`: PasswordReutilizada.
- `backend/src/app/infrastructure/security/limiter.py`: reserva atómica de ambos
  cupos y liberación idempotente de la reserva propia de email+IP.
- `backend/src/app/presentation/http/auth/router.py`: IP real del Request para
  password, documentación de 429/Retry-After y reglas de cambio.
- `backend/src/app/presentation/http/errors.py`: traducción de PASSWORD_REUTILIZADA.
- `backend/tests/security/test_restricted_sessions.py`: adaptación del caso de
  password al flujo completo; conserva las pruebas de autorización anteriores.

## Archivos creados

- `backend/tests/security/test_password_changes.py`.
- `docs/sprint-8-5a-3-implementacion.md` (este informe).

No se modificaron entidades de perfiles, modelos/implementaciones de persistencia,
migraciones, configuración, Docker, dependencias, frontend ni CLI. No se instalaron
paquetes. No se agregaron endpoints.

## Flujo implementado

Se reutiliza PUT `/api/v1/auth/password`, con los mismos campos password_actual y
password_nueva y éxito **204 sin contenido**, sin JWT nuevo.

1. El servicio valida la sesión persistida, vínculo, vigencia, revocación, estado
   activo y credencial. Acepta sesiones normales o restringidas conforme a 8.5A.2.
2. Fuera de esa UoW reserva cupo compartido por IP y email normalizado+IP.
3. Verifica la contraseña actual con Argon2id. Si es incorrecta, conserva el cupo
   reservado y devuelve CREDENCIALES_INVALIDAS sin modificar credencial/sesiones.
4. Si es correcta, libera solo su reserva de pareja antes de la transacción final.
   Una liberación fallida detiene el cambio antes de escribir credenciales.
5. Aplica la política vigente a la nueva: 15–128 puntos de código, hasta 512 bytes
   UTF-8, Unicode válido y rechazo de las contraseñas comunes ya definidas. No
   recorta ni normaliza espacios, no exige composición y no cambia la lista actual.
6. Rechaza coincidencia con la contraseña actual y con password_inicial_hash si
   existe, mediante verify Argon2; nunca compara strings de hashes para decidir
   reutilización. Calcula el hash nuevo fuera de la transacción final.
7. Dentro de una única UoW vuelve a validar sesión/usuario y compara la credencial
   completa con el snapshot previo, incluidos marca, antecedente y fechas.
8. Guarda password_hash, actualizada_at y debe_cambiar_password=false, conserva
   creada_at/password_inicial_hash y revoca **todas** las sesiones del usuario.
9. Devuelve 204 únicamente después de confirmar esa transacción.

No hay promoción de sesiones: su alcance permanece inmutable y todas las sesiones
anteriores quedan revocadas, incluidas normales y restringidas. El usuario debe
iniciar sesión otra vez con la definitiva; ese login genera sesión normal y me
completo, sujeto a su rol vigente. El JWT mantiene estructura y duración de 900 s.

El mismo flujo atiende cambios voluntarios. Una credencial histórica con antecedente
null conserva ese null: no se inventa una contraseña inicial ni se impone cambio
obligatorio retroactivo. Si existe antecedente, continúa impidiendo volver a la
inicial en cambios posteriores. No se agrega historial general de contraseñas.

Argon2id conserva todos sus parámetros existentes. Los hashes continúan ocultos
en repr y fuera de DTO, errores, logs y métricas. Solo se almacena el hash nuevo,
nunca la contraseña original.

## Transacciones y concurrencia

Las UoW del limitador se abren y cierran antes de la UoW final de seguridad. No se
anidan conexiones esperando el mismo advisory lock. La actualización y la
revocación utilizan el mecanismo transaccional ya implementado, sin commits
intermedios ni acciones remotas posteriores que condicionen el éxito.

Dos cambios concurrentes pueden validar la misma credencial antes de hashear, pero
solo uno confirma: el otro encuentra sesión revocada o snapshot cambiado y no
sobrescribe el resultado. También se rechaza una revocación ocurrida mientras se
calcula el hash. Se mantiene la protección previa frente a login con hash antiguo
concurrente con cambio.

Se probaron fallos de escritura, revocación, liberación y commit. Los dos primeros
y el fallo de commit revierten el hash, la marca y las sesiones; el fallo de
liberación impide llegar a esa escritura. Los contadores de intentos usan sus
propias transacciones: no se promete revertirlos junto con la credencial.

Si se pierde la respuesta después del commit, el resultado sigue siendo ambiguo
para el cliente. No se agregan reintentos automáticos, tokens nuevos ni restauración
de sesiones. La futura interfaz deberá limpiar secretos y exigir nuevo login,
según el diseño aprobado. Este incremento no implementa esa interfaz.

## Límites de intentos e interacción con login

Ambas operaciones utilizan **los mismos cupos y claves** existentes:

- 30 reservas admitidas por IP en ventanas UTC fijas de 60 segundos.
- 5 reservas por email normalizado+IP en ventanas UTC fijas de 900 segundos.
- Las claves persistidas siguen siendo HMAC; no se agregan ámbitos, tablas,
  contraseñas, emails o IP en claro a auth_intentos.

check ahora devuelve un handle local de la reserva admitida. El puerto añade
LoginAttemptReservation.release; success recibe esa reserva explícitamente. El
adaptador serializa la liberación mediante un lock y solo la marca liberada tras
confirmar su UoW: repetirla sobre el mismo handle no descuenta el intento de otra
operación. No se guarda el handle en la base ni en un registro global creciente.

Se corrigió el consumo parcial anterior: si una clave rechaza la reserva, la
excepción sale de la UoW y revierte ambos consumos de esa solicitud. Una operación
rechazada no ejecuta Argon2 ni deja consumo de la otra clave.

Los fallos de login y de contraseña actual se acumulan en la misma pareja. Un
éxito libera únicamente su propia reserva de pareja, conservando los fallos previos;
no reinicia contadores. Si la actual es correcta pero la nueva incumple política
o reutiliza un secreto, tampoco queda consumida esa reserva de pareja. El cupo
global por IP **sí permanece consumido** para las solicitudes admitidas, incluso
exitosas o con nueva inválida: repetirlas sigue estando limitado.

El servicio recibe IP como argumento nominal; HTTP la obtiene de request.client,
sin confiar en X-Forwarded-For. Llamadas internas que no proporcionen IP comparten
el bucket conservador unknown. No se abre una vía para omitir el limitador.

Un 429 incluye Retry-After y no modifica hash, bandera o sesiones. No es bloqueo
permanente de la cuenta. Otra IP tiene su pareja independiente; personas detrás
de la misma IP comparten el límite global. Si la sesión expira mientras se espera,
es necesario login nuevamente, sin reinicio de contadores.

Las liberaciones de password ocurren antes de validar/hash de la nueva y del
commit final; no se intenta una liberación después de confirmar el cambio. No
se reintentan automáticamente fallos técnicos ni liberaciones de resultado incierto.

## Contratos y errores

Login, logout y me mantienen los contratos de 8.5A.2. La entrada de password sigue
rechazando campos adicionales y usando SecretStr. Las validaciones de transporte
pueden rechazar una solicitud mal formada antes de entrar al servicio; no se
verifica su contraseña actual en ese caso.

| Estado/código | Significado |
| --- | --- |
| 204 | Cambio confirmado y todas las sesiones revocadas; sin cuerpo |
| 401 CREDENCIALES_INVALIDAS | Actual incorrecta; la sesión válida permanece válida |
| 401 AUTENTICACION_REQUERIDA | Sesión/usuario inválido o carrera invalidada; nuevo login |
| 422 PASSWORD_INVALIDA | Política vigente incumplida |
| 422 PASSWORD_REUTILIZADA | Nueva coincide con actual o inicial conocida; elegir otra |
| 422 SOLICITUD_INVALIDA | Contrato HTTP incumplido |
| 429 LIMITE_INTENTOS | Cupo compartido agotado; Retry-After |
| 500 saneado | Fallo técnico; sin exponer valores, SQL ni hashes |

El nuevo 422 utiliza el envoltorio actual y body.password_nueva como campo. Se
documentó 429 en OpenAPI. Se conservan Cache-Control no-store y los encabezados
de autenticación existentes.

## Pruebas y resultados

Antes de integrar se cargó exclusivamente configuración de pruebas, se ejecutó
require_test_database y se confirmó mediante consultas de solo lectura:
**usuarios_test / usuarios_test_admin, 127.0.0.1:5435, revisión 0003**.
Solo después se habilitó --run-postgres. Se repitió la comprobación al finalizar.

Comandos principales desde backend:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/security -p no:cacheprovider --basetemp=.pytest_cache/85a3-unit-temp
.\.venv\Scripts\python.exe -m pytest -q --run-postgres -p no:cacheprovider --basetemp=.pytest_cache/85a3-full-temp
```

| Comprobación | Resultado |
| --- | --- |
| Seguridad en memoria, ejecución intermedia | 135 aprobadas, 87 omitidas; anterior a las últimas pruebas adicionales |
| Suite completa backend final | **493 aprobadas**, sin fallos, en 107,86 segundos |
| Casos anteriores conservados/adaptados | **404 aprobados** |
| Casos nuevos | **89 aprobados** |
| Casos PostgreSQL incluidos | **119 aprobados**, todos en usuarios_test |
| Casos sin PostgreSQL incluidos | **374 aprobados** |
| Revisión final de usuarios_test | **0003** |
| Alembic check final | **No new upgrade operations detected.** |

Los nuevos casos cubren cambio obligatorio y voluntario, marca false, antecedente
conservado, actual incorrecta, reutilización actual y futura de la inicial,
política, espacios/Unicode/límites, revocación de todas las sesiones, JWT anterior
inutilizable, login definitivo normal, rollback, fallo real simulado de commit
PostgreSQL, dos cambios concurrentes y revocación durante hash.

Las pruebas del limitador cubren 5 fallos y 429, Retry-After, recuperación sin
esperas reales usando reloj controlado, fallos cruzados login/password, éxito que
no borra errores anteriores, ausencia de consumo parcial, doble liberación,
presupuesto global exacto, independencia entre IP y operaciones legítimas repetidas.
El recorrido ADMIN pendiente también sigue cubierto por los casos adaptados de
8.5A.2, además de las nuevas matrices normal/pendiente sobre ambos adaptadores.

Se verificó que errores y repr no contienen secretos ficticios, hashes o JWT.
La suite previa conserva pruebas de autorización, sesiones, migraciones y rollback.
Permanece únicamente el aviso existente de Starlette/TestClient sobre httpx;
no se cambiaron dependencias para ocultarlo.

## Aislamiento, riesgos pendientes y detención

**No se accedió a usuarios_dev ni al puerto 5434.** No se modificaron credenciales,
usuarios o sesiones reales, ni se inició el backend de desarrollo. Las limpiezas
y migraciones de regresión de la suite ocurrieron exclusivamente en usuarios_test,
con los controles existentes. No se editó ni creó ninguna migración.

No se implementó aprovisionamiento administrativo, reset, vencimiento de inicial,
formularios ni navegación React. Las credenciales pendientes solo se crearon como
fixtures ficticias. No se habilita emisión operativa de iniciales hasta completar
los incrementos autorizados y controles de frontend del diseño.

El hash inicial conservado tiene el coste y exposición adicional ya aceptados en
8.5A; su protección y la entrega manual de la inicial siguen siendo requisitos.
El sistema no reconstruye antecedentes desconocidos de usuarios históricos y no
incorpora historial general ni vencimiento específico de la inicial.

El backend sigue requiriendo esquema 0003. No iniciar desarrollo sobre un esquema
anterior ni aplicar allí migraciones sin autorización separada. Se mantiene el
requisito de despliegue coordinado antes de habilitar el flujo completo en uso real.

El trabajo se detiene al finalizar **8.5A.3**. No se continúa con 8.5A.4.
