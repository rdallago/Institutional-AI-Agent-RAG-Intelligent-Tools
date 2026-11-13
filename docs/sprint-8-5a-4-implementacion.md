# Incremento 8.5A.4: aprovisionamiento administrativo preparado

Fecha: 30 de octubre de 2026. Estado: **implementado y verificado**, con
**aprovisionamiento operativo deshabilitado**. Solo las pruebas aisladas pueden
ejercitar la emisión preparada. No se modifica React ni se avanza a 8.5A.5.

## Archivos creados

- `backend/src/app/application/auth/provisioning.py`: barrera de código cerrada.
- `backend/tests/security/test_initial_provisioning.py`: pruebas del flujo y barrera.
- `docs/sprint-8-5a-4-implementacion.md` (este informe).

## Archivos modificados

Código:

- `backend/src/app/application/auth/service.py`: creación compuesta, asignación
  administrativa, controles transaccionales y adaptación de bootstrap/asignación CLI.
- `backend/src/app/application/auth/exceptions.py`: errores de barrera, credencial
  existente y perfil inactivo no aprovisionable.
- `backend/src/app/presentation/http/usuarios/schemas.py`: inicial obligatoria en
  alta y esquema estricto de asignación, con SecretStr.
- `backend/src/app/presentation/http/usuarios/router.py`: alta compuesta y endpoint
  de asignación inicial, ambos sujetos a la barrera.
- `backend/src/app/presentation/http/errors.py`: errores públicos saneados y campo
  password_inicial en errores de política de estas operaciones.
- `backend/src/app/presentation/cli/security.py`: barrera antes de cargar servicios
  o pedir contraseñas para los comandos de aprovisionamiento.

Pruebas y fixtures:

- `backend/tests/auth_support.py` y `backend/tests/conftest.py`.
- `backend/tests/http/conftest.py`, `test_usuarios.py`, `test_validacion.py` y
  `test_openapi.py`.
- `backend/tests/integration/postgresql/test_http_usuarios.py`.
- `backend/tests/security/test_authorization.py`, `test_cli.py`,
  `test_transactions.py` y `test_restricted_sessions.py`.

No se modificaron Domain, los seis casos de uso de perfiles, UserRepository,
SecurityUnitOfWork, sus adaptadores, modelos, migraciones, configuración, Docker,
dependencias ni frontend. No se instalaron paquetes.

## Operaciones de aplicación

### Creación de perfil y credencial inicial

`AuthService.create_with_initial` compone el caso de uso original CrearUsuario con
la inserción estricta de credencial en una única SecurityUnitOfWork. `manage` deriva
su acción crear a esa operación: no deja un camino alternativo de alta HTTP sin
credencial. La operación interna original de perfil puro sigue disponible para
composición y fixtures históricas; su contrato no cambia.

El servicio comprueba sesión normal y rol ADMIN antes de la barrera y del trabajo
criptográfico. Valida la contraseña manual mediante la política vigente y calcula
Argon2id fuera de la transacción final. Dentro de esa UoW vuelve a comprobar actor,
rol, sesión, obligación y barrera, crea el perfil y hace INSERT estricto de la
credencial con:

- debe_cambiar_password=true.
- password_hash y password_inicial_hash con el mismo hash Argon2id inicial.
- Fechas de credencial UTC; sin contraseña original almacenada.

Solo se calcula un hash para esos dos campos. No se emite sesión, JWT ni contraseña
en la respuesta. Los conflictos globales de email conservan el comportamiento
previo: activo existente e inactivo reactivable; nunca se adopta ni sobrescribe
otra identidad. Un fallo en credencial o commit revierte también el perfil.

### Asignación administrativa a perfiles históricos

`AuthService.assign_initial_admin` exige ADMIN con sesión normal, barrera abierta
solo bajo el mecanismo de pruebas, destino existente, activo y sin credencial.
Comprueba las condiciones antes de hashear y nuevamente dentro de la UoW final.
Autoriza al actor antes de revelar estado del destino.

La inserción es estricta, sin merge/upsert; la PK y los locks existentes protegen
frente a carreras. Una credencial ya existente se rechaza aunque siga pendiente.
Se revocan preventivamente las sesiones anómalas del destinatario dentro de esa
misma transacción. No se modifica el perfil ni se reactiva implícitamente.

ADMIN autenticado puede asignar inicial a otro perfil ADMIN sin credencial. Esta
autoridad HTTP es distinta del bootstrap local y no elimina sus restricciones.
No hay reset ni reemplazo de contraseñas.

### CLI

Bootstrap y assign_initial locales también quedan detrás de la barrera. Su
implementación preparada escribe credenciales pendientes mediante inserción
estricta. assign_initial rechaza inactivos; se mantienen la prohibición de adoptar
emails y el cierre de bootstrap ante cualquier ADMIN con credencial, incluso
inactivo o pendiente. No se permite otro ADMIN por assign_initial local tras el cierre.

La CLI rechaza aprovisionamiento antes de configurar conexión o pedir contraseña;
--allow-development no abre esta barrera. El comando limpiar-intentos conserva su
comportamiento previo y no fue ejecutado operativamente durante esta intervención.

## Barrera de habilitación

`require_initial_provisioning_enabled()` en Application **siempre lanza
AprovisionamientoNoHabilitado**. No existe booleano configurable, variable de
entorno, argumento CLI, cabecera HTTP o implementación productiva que la abra.
No se cambia el constructor de AuthService ni la arquitectura de composición.

La barrera se comprueba en servicios, no solo en HTTP. Cubre creación, asignación
administrativa, bootstrap y asignación local; se repite antes de las escrituras.
La CLI la comprueba además antes de getpass. Un ADMIN normal recibe 403
APROVISIONAMIENTO_NO_HABILITADO; USUARIO, anónimo o ADMIN pendiente conservan primero
sus errores de autorización correspondientes. Una solicitud mal formada puede
ser rechazada con 422 por el esquema antes de entrar al servicio.

Las pruebas optan explícitamente por `initial_provisioning_test_gate`, que sustituye
esa función mediante monkeypatch solo durante el caso de prueba y la restaura al
terminar. Las fixtures históricas no abren la barrera: preparan directamente datos
ficticios normales con false/null. El helper histórico bootstrap_login se adaptó
para representar ese estado previo; las pruebas específicas de bootstrap siguen
ejercitando el comando real bajo la excepción aislada.

Se verificó que variables de entorno que intentan habilitarla no tienen efecto.
Una comprobación posterior en **otro proceso Python** confirmó que la función
productiva continúa denegando. Su futura habilitación requerirá un cambio de código
revisado y autorización explícita, después de verificar frontend e integración.
Este incremento no incluye ese cambio ni un procedimiento para eludir la barrera.

## Contratos HTTP e incompatibilidad

### POST /api/v1/usuarios

Entrada: nombre, apellido, email, rol opcional USUARIO y **password_inicial
obligatoria**. La inicial usa SecretStr, longitud de transporte 15–128, política
completa en Application y campos adicionales prohibidos. No se admiten hash,
confirmación, estado ni bandera de cambio elegida por el cliente.

La respuesta preparada conserva 201, Location y los siete campos de UsuarioRespuesta,
sin contraseña, hash o estado de credencial. En uso operativo actual la barrera
impide ese éxito; no se crea un perfil parcial como alternativa.

**Incompatibilidad explícita:** el frontend 8.4 y scripts anteriores no envían
password_inicial, por lo que su alta ahora obtiene 422 sin crear perfil. Incluso
una solicitud válida manualmente obtiene el 403 de barrera hasta la autorización
futura. No hay fallback al contrato anterior.

### POST /api/v1/usuarios/{id}/credencial-inicial

Entrada exclusiva password_inicial. Éxito preparado 204 sin cuerpo, sujeto a ADMIN
normal y barrera. Errores:

| Estado / código | Causa |
| --- | --- |
| 401 AUTENTICACION_REQUERIDA | Sesión ausente, inválida, revocada, vencida o actor inactivo |
| 403 PERMISO_DENEGADO | Actor normal sin rol ADMIN |
| 403 CAMBIO_PASSWORD_REQUERIDO | Actor con obligación pendiente, incluso ADMIN |
| 403 APROVISIONAMIENTO_NO_HABILITADO | Barrera productiva cerrada |
| 404 USUARIO_NO_ENCONTRADO | Destino ausente, tras autorización y barrera |
| 409 CREDENCIAL_EXISTENTE | Ya tiene credencial o colisión de inserción; nunca reemplazar |
| 409 USUARIO_INACTIVO_NO_APROVISIONABLE | Perfil inactivo sin credencial |
| 422 PASSWORD_INVALIDA / SOLICITUD_INVALIDA | Política o contrato incumplido |
| 500 saneado | Fallo técnico, sin SQL ni secretos |

Si un perfil inactivo ya tiene credencial, prevalece CREDENCIAL_EXISTENTE: no se
ofrece esta operación como reset. Los errores de política de estas operaciones
señalan body.password_inicial. Los errores de cambio voluntario/obligatorio siguen
señalando body.password_nueva. No cambian los contratos de login, logout o me.

No se agregan indicadores de existencia de credencial a los GET ni endpoints de
inventario/reset. OpenAPI muestra siete operaciones de usuarios; los seis casos
de uso originales de perfiles mantienen sus contratos.

## Transacciones, concurrencia y secretos

La autorización se revalida bajo los locks existentes de la UoW. Argon2 se calcula
fuera de una transacción larga. La alta confirma perfil y credencial juntos; la
asignación confirma inserción y revocación juntas. No se agregan commits internos.
Las dos solicitudes concurrentes de creación de un mismo email dejan un único
perfil con la credencial ganadora. Las asignaciones concurrentes dejan una única
credencial sin sobrescritura. Se verificaron rollback ante hash, inserción,
revocación y fallo de commit PostgreSQL.

SecretStr oculta el secreto de entrada; UsuarioResultado/UsuarioRespuesta no lo
contienen. Los hashes permanecen ocultos en repr y fuera de errores y logs. No
se incluyen secretos reales en archivos versionados ni contraseñas de ejemplo en
OpenAPI; las contraseñas de las pruebas son exclusivamente ficticias.

El primer login preparado genera una sesión restringida. La matriz HTTP y los
servicios impiden administración incluso a ADMIN pendiente. El cambio de 8.5A.3
conserva el antecedente, elimina la obligación y revoca sesiones; solo un nuevo
login obtiene sesión normal. El flujo se verificó para ADMIN y USUARIO.

## Pruebas y resultados

Antes de integrar se cargó exclusivamente la configuración de pruebas y se ejecutó
require_test_database. Una consulta de solo lectura confirmó base y cuenta reales:
**usuarios_test / usuarios_test_admin, 127.0.0.1:5435, revisión 0003**. No se
habilitó --run-postgres hasta confirmar ese destino.

Comandos principales, desde backend:

```powershell
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider --basetemp=.pytest_cache/85a4-unit-temp
.\.venv\Scripts\python.exe -m pytest -q tests/security/test_initial_provisioning.py -p no:cacheprovider --basetemp=.pytest_cache/85a4-new-unit-temp
.\.venv\Scripts\python.exe -m pytest -q --run-postgres -p no:cacheprovider --basetemp=.pytest_cache/85a4-full-temp
```

| Verificación | Resultado |
| --- | --- |
| Regresión previa en memoria | 374 aprobadas, 119 PostgreSQL omitidas |
| Pruebas nuevas en memoria, ejecución intermedia | 29 aprobadas, 29 omitidas; anterior a las últimas ampliaciones |
| Suite completa final | **556 aprobadas**, sin fallos, en 99,57 segundos |
| Casos anteriores conservados/adaptados | **493 aprobados** |
| Casos nuevos | **63 aprobados** |
| Casos PostgreSQL incluidos | **151 aprobados**, todos en usuarios_test |
| Casos sin PostgreSQL incluidos | **405 aprobados** |
| Revisión final de usuarios_test | **0003** |
| Alembic check final | **No new upgrade operations detected.** |
| Barrera en proceso Python nuevo | **Aprovisionamiento operativo DESHABILITADO** |

Se cubrieron alta atómica, hash, política, errores y campos extra, asignación a
ambos roles, inactivos/ausentes/con credencial, anónimo/USUARIO/ADMIN pendiente,
concurrencia, rollback, no exposición de secretos, revalidación de actor y barrera
durante hash, cierre CLI, primer login restringido y cambio a sesión normal.

Las pruebas antiguas de transporte conservan sus sustituciones explícitas de casos
de perfiles puros; las nuevas y las integraciones verifican AuthService real, sin
esas sustituciones. Los payloads de creación se adaptaron al secreto obligatorio;
PUT no lo acepta. La enumeración de rutas restringidas incluye el nuevo endpoint.
Se conserva la cobertura de usuarios históricos con credenciales normales.

Permanece el aviso previo de Starlette/TestClient sobre httpx; no se cambiaron
dependencias para ocultarlo. No hubo fallos en la ejecución completa final.

## Aislamiento, impacto pendiente y detención

**No se accedió a usuarios_dev ni al puerto 5434.** No se modificaron usuarios,
contraseñas o sesiones reales. No se inició el backend de desarrollo. Las limpiezas
y migraciones de regresión ocurrieron exclusivamente en usuarios_test, con sus
guardas existentes; no se creó ni modificó ninguna migración o contenedor.

React queda pendiente de 8.5A.5: campos inicial/confirmación, política explicada,
estado restringido, guards y manejo de errores. Las consultas/edición de perfiles
históricos y su autenticación no cambian; el alta del frontend anterior es
incompatible y permanece inutilizable con el nuevo contrato. No se simuló éxito
ni se agregó una forma de habilitar emisión real desde configuración.

No se implementó reset, recuperación, vencimiento de inicial ni historial general.
La exposición adicional del hash inicial y su entrega manual segura mantienen
los riesgos ya documentados en el diseño. El backend sigue requiriendo esquema
0003; no iniciar desarrollo sobre 0002 ni aplicar allí migraciones sin autorización.

El aprovisionamiento operativo continúa **deshabilitado en HTTP y CLI**, aunque
el comportamiento preparado esté probado. Se detiene el trabajo en **8.5A.4** y
se espera aprobación antes de continuar.
