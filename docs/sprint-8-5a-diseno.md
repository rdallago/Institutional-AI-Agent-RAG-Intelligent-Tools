# Sprint 8.5A: diseño de contraseña inicial y cambio obligatorio

Fecha: 30 de octubre de 2026. **Estado: arquitectura general aprobada; precisiones
documentadas para revisión antes de autorizar la implementación.**
Esta intervención crea exclusivamente este documento. No implementa código, no
ejecuta pruebas ni migraciones, no accede a bases de datos y no modifica backend,
frontend, configuración, Docker o credenciales.

La decisión funcional aprobada reemplaza, para las altas nuevas, el comportamiento
de 8.4 de crear perfiles sin acceso: ADMIN establece manualmente una contraseña
inicial; su destinatario debe reemplazarla antes de usar funcionalidades normales.
La autorización de este documento no implica autorización operativa para desplegar
o migrar desarrollo.

## 1. Diagnóstico de la arquitectura actual

### Código inspeccionado y responsabilidades

| Componente real | Estado actual verificado |
| --- | --- |
| `backend/src/app/domain/usuarios/usuario.py` | Perfil con UUID, nombre, apellido, Email, activo, Rol y fecha UTC. No contiene secretos ni estado de credencial |
| `domain/auth/models.py` | Credencial con hash y fechas; Sesion con UUID, usuario, creación, expiración y revocación. No existe debe_cambiar_password ni alcance restringido |
| `infrastructure/persistence/models/auth.py` | Tablas public.usuario_credenciales, auth_sesiones, auth_intentos; FK a usuarios y restricciones de fechas |
| `infrastructure/security/crypto.py` | Argon2id: memoria 65536 KiB, tiempo 3, paralelismo 1, salt 16 bytes, hash 32 bytes; verify y needs_rehash |
| `application/auth/service.py` | Login, authenticate, me, change_password, logout, manage, bootstrap y assign_initial |
| `infrastructure/security/postgres.py` | UoW con transacción, rollback, repositorio de perfiles mediante savepoints y advisory lock transaccional compartido. Credenciales se escriben actualmente mediante merge |
| `infrastructure/security/memory.py` | UoW con RLock, snapshots y rollback de perfiles, credenciales, sesiones e intentos |
| `presentation/http/auth/dependencies.py` | Bearer obligatorio y get_current_user que llama authenticate |
| `presentation/http/dependencies.py` | AuthorizedCase delega operaciones de perfiles en AuthService.manage |
| `application/auth/policies.py` | ADMIN puede administrar, salvo baja propia; USUARIO solo consulta su propio perfil y obtiene 404 ante perfiles ajenos |
| `presentation/cli/security.py` | Bootstrap y asignación inicial por UUID; getpass con confirmación y terminal interactiva, sin argumentos de contraseña; autorización explícita de desarrollo |
| `migrations/versions` | Revisiones 0001 y 0002. No existe 0003 en los archivos inspeccionados |

El JWT es HS256 con kid, tipado at+jwt y claims sub, jti, iat, exp, iss, aud,
token_use=access. No contiene rol ni contraseña. El servicio verifica también la
sesión persistida, revocación, expiración, perfil activo y existencia de credencial.
Su duración publicada es de 900 segundos. El estado real del usuario se consulta
en backend, no se deriva exclusivamente del JWT.

El login verifica hash o hash ficticio, rechaza inactivos y perfiles sin credencial
con la misma respuesta pública, admite rehash y revalida estado/hash antes de crear
la sesión. Hay límites por IP y email+IP. El cambio de contraseña exige la actual,
valida la nueva, revalida la credencial en otra UoW y revoca todas las sesiones
en la misma transacción que actualiza el hash. **Hoy no rechaza elegir la misma
contraseña ni aplica cambio obligatorio.** El limitador existente se usa en login,
no en change_password.

### Contratos HTTP actuales

- POST `/api/v1/usuarios`: nombre, apellido, email y rol opcional USUARIO. Crea solo
  perfil; responde 201 UsuarioRespuesta. No acepta contraseña.
- PUT `/api/v1/usuarios/{id}`: exclusivamente nombre, apellido, email. No es un
  mecanismo de cambio de contraseña ni de rol.
- POST `/api/v1/auth/login`: email/password; responde access_token, token_type,
  expires_in. No distingue sesiones restringidas.
- GET `/api/v1/auth/me`: UsuarioRespuesta completo del propio usuario.
- PUT `/api/v1/auth/password`: password_actual/password_nueva; 204, sin nuevo token,
  todas las sesiones revocadas. No recibe UUID ni confirmación.
- POST `/api/v1/auth/logout`: revoca la sesión del token; 204, con repetición
  idempotente mientras el token firmado continúe vigente.
- No existe endpoint administrativo HTTP para asignar credenciales iniciales.

UsuarioRespuesta contiene id, nombre, apellido, email, activo, rol y fecha_creacion.
Los esquemas de entrada prohíben campos adicionales. Los errores tienen envoltorio
error con codigo, mensaje y opcionalmente detalles/usuario_id, sin reproducir los
valores sensibles. La configuración real se llama **AuthConfig**, no AuthSettings;
carga AUTH_* de .env para desarrollo y TEST_AUTH_* de .env.test para pruebas.
No se leyeron secretos para elaborar este diseño.

### CLI y React

Bootstrap rechaza emails existentes y se cierra cuando existe cualquier ADMIN con
credencial, incluso inactivo. assign_initial exige un perfil sin credencial y
también impide aprovisionar otro ADMIN local tras ese cierre. Actualmente ambos
generan credenciales sin una marca de cambio obligatorio; assign_initial puede
encontrar un perfil inactivo porque no contiene una comprobación explícita de activo.

React guarda JWT únicamente en memoria. AuthProvider establece autenticado solo
después de me y maneja reloj, revocación, generaciones y AbortController. Su estado
no contempla cambio pendiente. isToken exige expires_in=900; isUsuario exige un
perfil completo activo. ProtectedRoute/AdminRoute habilitan vistas normales con
ese estado. UsuarioForm de 8.4 no tiene contraseña y advierte que el alta no asigna
acceso. `/cambiar-password` sigue siendo una pantalla reservada, sin formulario.
El cliente elimina sesión ante cualquier 401 protegido; habrá que distinguir el
401 de contraseña actual incorrecta cuando se implemente ese formulario.

Antecedentes de verificación: 319 pruebas backend y 101 frontend aprobadas en los
cierres anteriores. Son antecedentes, no ejecuciones de esta intervención.

## 2. Decisiones técnicas propuestas

### 2.1 Estado de la credencial, no del perfil

Guardar debe_cambiar_password en **Credencial/public.usuario_credenciales**. Describe
el ciclo de un secreto y no el rol o estado del perfil. No agregarlo a Usuario ni
a los contratos originales UserRepository y los seis casos de uso de perfiles.

Crear una operación de aplicación de seguridad, por ejemplo
CrearUsuarioConCredencialInicial, que componga CrearUsuario y la inserción de
credencial dentro de la misma SecurityUnitOfWork. No introducir SQLAlchemy en
Domain/Application ni volver a implementar unicidad, baja o reactivación.

Toda credencial inicial nueva se escribe con debe_cambiar_password=true y un
hash Argon2id. El cliente no puede elegir false. PUT de perfil y reactivación
no modifican esta marca. El login con rehash conserva su valor.

### 2.2 Alcance inmutable de la sesión

Agregar **restringida: bool** a Sesion/public.auth_sesiones. En cada login se decide
su valor desde la credencial leída y revalidada en la transacción final. No se
puede promover una sesión restringida cambiando una bandera en React ni simplemente
actualizando la credencial. Para acceso normal siempre hacen falta una sesión
normal y una credencial sin cambio pendiente.

Conservar en esta propuesta HS256, kid, claves, claims y TokenService.issue/verify:
el JWT sigue identificando la sesión revocable. **token_use=access no significa
acceso pleno por sí mismo**; el alcance efectivo se comprueba en PostgreSQL. No
agregar roles ni flags autorizativos al JWT. Todas las sesiones mantienen 900
segundos para minimizar incompatibilidades; no se implementa refresh.

Alternativa evaluada: token_use=password_change o un scope firmado especial.
Da una señal adicional a consumidores externos, pero exige cambiar emisión,
verificación y puertos, y aun así no sustituye revocación/estado persistido.
No se recomienda para este backend único en esta fase. Un futuro servicio que
acepte estos JWT deberá hacer la comprobación equivalente de sesión/alcance o
acordar otro contrato; no podrá tratar la firma como autorización plena.

### 2.3 Prohibición de reutilizar la inicial

Agregar password_inicial_hash nullable, oculto en repr y nunca serializado. Para
credenciales iniciales nuevas conserva el hash Argon2id del secreto inicial, incluso
después del cambio. Antes de guardar cualquier nueva contraseña, verificar con
Argon2 que no coincide con la actual ni con ese antecedente si existe.

Esto garantiza que no se elija la inicial durante el cambio obligatorio **ni se
vuelva a ella en un cambio voluntario posterior**. Comparar strings de hashes no
sirve: cada hash tiene salt aleatorio. Al rehashear la credencial actual no borrar
el antecedente ni cambiarlo por el hash de la contraseña definitiva.

Es un único antecedente, no un historial general de contraseñas. Su coste es
almacenamiento sensible adicional y una verificación Argon2 extra por cambio,
no por login. Se protege igual que password_hash y no se conserva plaintext ni
un digest rápido. Para credenciales históricas el valor será null: la contraseña
inicial antigua no puede reconstruirse y no se hará una promesa de control
retroactivo que los datos actuales no permiten.

El coste de almacenamiento es un string Argon2id codificado adicional por
credencial nueva, más la sobrecarga de columna/fila y sus copias en respaldos y
replicación; no son los 64 MiB de memoria de trabajo de Argon2 por fila. Mientras
ambos hashes coincidan no hace falta calcular dos veces el mismo hash al crear
la credencial. Después del cambio se conservan dos verificadores distintos.
Una filtración de la base expone también el verificador de un secreto antiguo
conocido por ADMIN, que puede ser objeto de ataques offline aunque ya no permita
login. Limitar lectura y exportación, proteger respaldos y excluir ambos hashes
de DTO, logs y telemetría. Se acepta esta exposición adicional exclusivamente
para impedir volver a la inicial; no se amplía a un historial general.

### 2.4 Flujos separados por autoridad

- ADMIN con sesión normal crea perfiles con contraseña inicial, incluidos nuevos
  ADMIN: estos últimos también quedan restringidos hasta cambiarla.
- USUARIO, anónimo o ADMIN con cambio pendiente no pueden aprovisionar a terceros.
- Una operación HTTP específica permite asignar una inicial a perfiles existentes
  activos **sin credencial**. Nunca reemplaza una credencial ni sirve de reset.
- Nuevas credenciales emitidas por CLI también quedan pendientes, incluido un
  futuro primer bootstrap. Ese primer ADMIN puede completar su cambio restringido
  sin necesitar otro administrador. Se conservan las barreras de cierre de bootstrap
  y la prohibición de otro ADMIN mediante assign_initial local tras el cierre.
- La administración autenticada de nuevos ADMIN es distinta del bootstrap local:
  no se debe llamar directamente a assign_initial como si representase autorización
  HTTP ni eliminar sus protecciones para reutilizarlo.

## 3. Cambios necesarios en PostgreSQL y modelos

Proponer revisión **0003**, dependiente de 0002, con nombre a fijar al implementar.
No editar 0001/0002. No crear tablas ajenas, claves nuevas, credenciales ficticias
ni contraseñas predeterminadas.

| Tabla | Columna / restricción propuesta | Tratamiento de filas actuales |
| --- | --- | --- |
| public.usuario_credenciales | debe_cambiar_password BOOLEAN NOT NULL | false, para no forzar a todos |
| public.usuario_credenciales | password_inicial_hash TEXT NULL | null, sin inventar antecedentes |
| public.usuario_credenciales | CHECK (NOT debe_cambiar_password OR password_inicial_hash IS NOT NULL) | Cumplida con false/null |
| public.auth_sesiones | restringida BOOLEAN NOT NULL | false, conserva sesiones normales actuales |

Agregar columnas booleanas inicialmente con default false para el backfill y
quitar ese default al terminar la misma migración. Los nuevos modelos/fábricas
deben exigir valores explícitos: evita que un alta futura olvide marcar una
credencial o sesión inicial. Esta elección requiere despliegue coordinado con
el backend detenido; un binario antiguo que omita columnas obligatorias fallará
al insertar en vez de abrir acceso accidentalmente.

No hacen falta índices en los booleanos: las comprobaciones leen por PK de
credencial/sesión. No modificar usuarios, UUID, emails, roles, activo, hashes
actuales, fechas o relaciones existentes. No copiar secretos a tablas de perfil.
La restricción no compara hashes ni verifica criptografía en SQL.

Actualizar dataclasses de auth, ORM, mapeos manuales de PostgresSecurityUnitOfWork,
snapshots de memoria y todas las fábricas/fixtures. replace usado en rehash/revocación
debe conservar los campos nuevos. Las fechas siguen siendo UTC con zona horaria.

Agregar al puerto UoW una inserción estricta de credencial inicial, separada del
merge actual usado para actualizaciones. Debe fallar si ya existe usuario_id.
El chequeo en aplicación y advisory lock se mantienen, pero la PK y la inserción
sin upsert son defensa ante carreras: no convertir un conflicto en sobrescritura.
Mapear esa colisión a un conflicto público saneado. Memoria debe ser equivalente.

## 4. Cambios necesarios en FastAPI y Application

### 4.1 Autenticación básica y acceso normal

Separar dos comprobaciones de servicio con nombres definitivos a fijar al codificar:

1. **Sesión válida:** JWT válido, sesión vinculada a sub/jti, no revocada ni vencida,
   perfil activo y credencial existente. Se usa en el flujo de cambio y contexto.
2. **Acceso normal:** además exige debe_cambiar_password=false y restringida=false.
   Se exige en todos los casos de uso normales antes de aplicar rol/propiedad.

Mantener Principal con identidad de usuario/sesión, sin aceptar un flag de permiso
en requests. Los campos leídos en la dependencia no se consideran una autorización
duradera: revalidar dentro de la UoW que realiza la operación, igual que hoy manage
revalida estado. Un cambio de rol/estado durante Argon2 o entre dependencia y
operación no debe eludir el control.

get_current_user debe conservar el significado seguro de acceso normal para los
endpoints de perfiles. Crear dependencias explícitas de sesión válida para me y
password; no aflojar una dependencia compartida para hacer funcionar el formulario.
logout conserva su camino de token firmado/vigente e idempotencia actual.

### Matriz efectiva de autorización

| Operación | Sesión normal ADMIN | Sesión normal USUARIO | Sesión pendiente/restringida de cualquier rol |
| --- | --- | --- | --- |
| GET auth/me | Perfil propio + indicador false | Igual | Solo contexto mínimo de cambio pendiente |
| PUT auth/password | Cambio voluntario propio | Cambio voluntario propio | Cambio obligatorio propio |
| POST auth/logout | Permitido según contrato actual | Igual | Permitido según contrato actual |
| GET usuarios / detalle propio / detalle ajeno | Política actual | Solo detalle propio según política actual | 403 CAMBIO_PASSWORD_REQUERIDO, incluso para el perfil propio |
| POST/PUT/DELETE/PATCH usuarios | Política actual y prohibición de baja propia | 403 PERMISO_DENEGADO | 403 CAMBIO_PASSWORD_REQUERIDO |
| Asignación inicial a otro perfil | Solo si cumple precondiciones | 403 PERMISO_DENEGADO | 403 CAMBIO_PASSWORD_REQUERIDO |
| Futuras operaciones normales | Requieren comprobación explícita | Según permiso | Denegadas por defecto |

Si una sesión marcada restringida apareciera activa con credencial ya definitiva,
rechazarla con 401 AUTENTICACION_REQUERIDA: exige nuevo login, no se promueve ni
obliga a cambiar dos veces. Si una sesión vieja normal encuentra una credencial
pendiente, tampoco puede usar endpoints normales: el estado de credencial prevalece.
JWT inválido, perfil inactivo, credencial ausente o sesión revocada/vencida siguen
produciendo 401, antes de tratarlo como un caso de cambio pendiente.

### 4.2 Creación atómica con contraseña inicial

Validar actor normal ADMIN y datos, aplicar política de password y generar Argon2id
fuera de una transacción larga cuando sea posible. Después, en una única UoW,
revalidar actor/rol/restricción, ejecutar CrearUsuario y agregar credencial con
hash actual=hash inicial y debe_cambiar_password=true. Si falla cualquier escritura,
rollback de perfil y credencial. El hash nunca entra en Usuario ni en UsuarioResultado.

Conservar los conflictos globales de email y nunca adoptar una cuenta existente.
No crear una sesión para el destinatario ni enviar su contraseña en la respuesta.

### 4.3 Login y cambio obligatorio

1. Login valida contraseña como hoy, con rechazo indistinguible para inactivo,
   ausente, sin credencial o secreto incorrecto.
2. Revalida bajo UoW hash, marca y estado. Si se necesita rehash, conserva la marca
   y el antecedente. Crea Sesion.restringida según el estado de la credencial.
3. Emite JWT sin permisos normales implícitos. React consulta me para validar
   el contexto antes de mostrar la pantalla obligatoria.
4. Todos los endpoints normales comprueban las dos condiciones de acceso, también
   si el usuario ignora React y hace llamadas HTTP directas.
5. Password exige contraseña actual correcta, valida la nueva y rechaza coincidencia
   con actual/inicial usando verify Argon2. La confirmación es solo del frontend.
6. Calcula el nuevo hash; vuelve a verificar sesión, activo y snapshot de la
   credencial/marca en la transacción final. No acepta otro usuario_id del cuerpo.
7. Actualiza password_hash, actualizada_at y debe_cambiar_password=false, conserva
   password_inicial_hash y revoca **todas** las sesiones del usuario dentro de la
   misma transacción, incluidas normales/restringidas. Rollback revierte todo.
8. Devuelve 204 solo tras commit. No emite token nuevo. React borra estado y exige
   login con la definitiva; ese login crea una nueva sesión normal.

Dos cambios concurrentes no pueden sobrescribirse: gana el primero que confirma;
el segundo encuentra sesión revocada o snapshot cambiado y no guarda otro hash.
La combinación de cambio de hash y revocación ya existente debe extenderse, no
reemplazarse por varias confirmaciones independientes.

### 4.4 Cambio voluntario y límite de intentos

Reutilizar exactamente el mismo servicio/endpoints para el cambio voluntario de
una sesión normal. También exige la actual, política, no reutilización y revocación
total. No recibe ni acepta debe_cambiar_password o restringida desde el cliente.

Aplicar el limitador existente a la verificación de contraseña actual en password:
resolver primero identidad válida, reservar cupo email normalizado+IP e IP antes
de Argon2, conservar reserva si es incorrecta y liberar el cupo de pareja si la
actual es válida. Se propone compartir explícitamente los cupos vigentes de login
(30/IP/minuto y 5/email+IP/15 minutos), sin nuevos ámbitos de auth_intentos.
La reserva/liberación se hace fuera de la UoW final para no anidar conexiones que
esperen el mismo advisory lock. No condicionar la respuesta de un cambio ya
confirmado a una liberación posterior que pueda fallar. Una contraseña actual
correcta puede liberar su reserva antes del commit final; las comprobaciones de
estado se repiten igual en ese commit.

Interacción explícita entre ambas operaciones:

- Comparten las ventanas por IP y por email+IP: los errores de contraseña actual
  reducen también el cupo disponible para login desde esa pareja, y viceversa.
  No existe bloqueo permanente de cuenta ni un contador por usuario independiente
  de IP. Un 429 no revoca sesiones ni cambia hashes o la obligación pendiente.
- Un login inicial correcto libera únicamente su propia reserva de pareja; no
  borra fallos anteriores. El cambio obligatorio inmediato dispone de cupo salvo
  que esos fallos o el límite agregado por IP ya hayan agotado la ventana. No se
  reserva un cupo especial ni se promete que login exitoso garantice otro envío.
- Password con actual correcta libera únicamente su reserva de pareja, incluso
  si después la nueva resulta inválida o reutilizada. No liberar todas las
  reservas: permitiría borrar intentos fallidos anteriores. Las solicitudes
  admitidas siguen consumiendo el cupo global por IP, aunque tengan éxito.
- Cada operación reserva una sola vez; comprobar ambas claves de forma atómica
  para que una reserva rechazada no deje consumo parcial de la otra. No reservar
  en la dependencia y otra vez en el servicio. La liberación debe ser idempotente.
- React respeta Retry-After también en el cambio obligatorio, conserva el estado
  restringido mientras la sesión siga vigente y no reintenta automáticamente.
  Si esta expira durante la espera, exige login; ese login no reinicia contadores.

Compartir IP puede afectar a varias personas detrás de NAT/proxy; es un efecto
documentado del límite global, no una causa para confiar en cabeceras arbitrarias.
La aceptación exige probar el recorrido login -> cambio -> nuevo login y los
límites cruzados con reloj controlado. Si esas pruebas muestran bloqueos distintos
de los definidos aquí, no habilitar aprovisionamiento: revisar la estrategia antes
de desplegar, sin eliminar la protección ni cambiar cupos silenciosamente.

El endpoint incorporará 429/Retry-After como contrato nuevo. No usar contraseñas
como claves del limitador ni almacenar email/IP en claro. La IP debe obtenerse
por el mecanismo actual de Request, sin habilitar confianza en cabeceras arbitrarias.

## 5. Contratos HTTP propuestos y compatibilidad

Todo lo siguiente es **propuesto, no implementado**. Mantener envoltorio de errores
actual y extra=forbid. Campos de secretos con SecretStr en transporte y repr=False
en comandos internos. No incluir ejemplos con contraseñas utilizables en OpenAPI.

### POST /api/v1/usuarios

Extender entrada con **password_inicial obligatorio**, además de nombre, apellido,
email y rol opcional USUARIO. No aceptar confirmación, hash, flags de credencial
ni estado de sesión. Política completa en Application; longitud del esquema debe
ser coherente. Respuesta 201 y Location/UsuarioRespuesta se mantienen sin secretos.

Es un cambio incompatible de entrada para clientes 8.4 y scripts antiguos: omitirlo
producirá 422, sin crear perfil. Se prefiere obligatorio a un opcional que dejaría
altas nuevas sin contraseña y contradiría la decisión aprobada. No mantener un
camino HTTP alternativo de alta sin credenciales. Las operaciones internas de
perfil puro siguen existiendo para composición, pruebas y datos históricos.

### POST /api/v1/usuarios/{id}/credencial-inicial

Nueva operación recomendada para perfiles históricos sin credencial. Entrada:
password_inicial, y ningún otro campo. Solo ADMIN con sesión normal. Respuesta
204 sin contraseña ni hash. Inserción estricta y revocación preventiva de cualquier
sesión anómala del destinatario dentro de la misma UoW.

Precondiciones y errores propuestos:

- 404 USUARIO_NO_ENCONTRADO si no existe el perfil.
- 409 CREDENCIAL_EXISTENTE si ya tiene credencial, incluso pendiente: nunca resetear,
  reemplazar ni dar un segundo secreto por este endpoint.
- 409 USUARIO_INACTIVO_NO_APROVISIONABLE si está inactivo; reactivar por la operación
  existente y luego asignar, en decisiones separadas.
- 401/403 conforme a sesión, restricción y rol; 422 política/entrada; 500 saneado.

Autorizar al actor antes de revelar estado del destino y revalidar dentro de UoW.
ADMIN puede asignar inicial a otro perfil ADMIN sin credencial por esta autoridad
autenticada; no es un segundo bootstrap local. La marca siempre es true.

Los GET actuales no informan existencia de credencial. No inferirla desde rol,
estado, email o debe_cambiar_password. Para mantener contratos mínimos, la primera
UI de asignación puede ser una acción explícita con texto «solo perfiles sin
credencial», dejando la precondición al POST y mostrando 409 sin sobrescribir.
No se propone añadir un inventario público de credenciales en esta fase.

### POST /api/v1/auth/login

Mantener entrada, códigos de rechazo, JWT y expires_in=900. Agregar booleano
obligatorio **debe_cambiar_password** a TokenRespuesta, obtenido de la transacción
que creó la sesión. Ambos tipos de sesión responden 200. No convertir login en
403, porque debe entregar el medio restringido para completar el cambio.
La bandera orienta UX; no autoriza operaciones sin comprobación de backend.

### GET /api/v1/auth/me

Separar su DTO de UsuarioRespuesta de administración. Proponer una unión discriminada:

| Situación | Respuesta 200 |
| --- | --- |
| Normal | Campos actuales de UsuarioRespuesta + debe_cambiar_password=false |
| Pendiente | Solo id propio + debe_cambiar_password=true |

La respuesta pendiente es contexto de autenticación mínimo, **no una consulta
normal de perfil**. No devuelve email, nombre, rol u otros perfiles; tampoco habilita
Mi perfil. Mantiene el handshake de React sin permitir acceso normal anticipado.
La respuesta normal es aditiva; la pendiente requiere adaptar validadores y estado
de React. No extender los DTO originales de Domain/usuarios por comodidad HTTP.

### PUT /api/v1/auth/password

Reutilizar entrada password_actual/password_nueva y éxito 204, sin devolver JWT ni
contraseña. Admitir sesión válida restringida para cambio obligatorio y normal
para voluntario. No aceptar objetivo, roles ni bandera para desactivar obligación.

Errores:

- 401 AUTENTICACION_REQUERIDA: JWT/sesión/perfil inválido, o carrera invalidada;
  requiere nuevo login.
- 401 CREDENCIALES_INVALIDAS: contraseña actual incorrecta; conservar la sesión
  restringida/normal válida y mostrar el error en el formulario.
- 422 PASSWORD_INVALIDA: política actual incumplida, sin divulgar lista interna.
- 422 PASSWORD_REUTILIZADA: nueva coincide con actual o inicial conocida; mensaje
  público de elegir otra, sin devolver hashes o valores.
- 429 LIMITE_INTENTOS con Retry-After por límite propuesto de verificación actual.
- 500 saneado: resultado potencialmente ambiguo, sin reenvío automático.

POST logout permanece igual y disponible también en sesión restringida. Los
endpoints normales agregan 403 CAMBIO_PASSWORD_REQUERIDO con mensaje público que
indica completar cambio; no lo confundir con PERMISO_DENEGADO.

## 6. Impacto sobre React

Incorporar estado **passwordChangeRequired** separado de authenticated; contiene
únicamente el contexto mínimo de me y token privado en memoria. Guardar rol y
perfil completos solo en estado normal. No tratar ausencia de bandera como false
en los nuevos contratos: una respuesta no conforme falla de forma segura.

El login conserva JWT provisional, valida me y transita a cambio obligatorio o
a autenticado. Me es la confirmación efectiva; cualquier contradicción entre
login y me se resuelve sin mostrar pantallas normales prematuramente. La ruta
obligatoria solo permite cambiar contraseña o cerrar sesión, sin AppShell normal,
dashboard, Mi perfil ni navegación ADMIN, incluso si el nuevo usuario es ADMIN.
Escribir URLs manualmente también queda bloqueado por guards; FastAPI mantiene
la barrera definitiva.

Reutilizar `/cambiar-password` con un modo obligatorio y otro voluntario, no un
endpoint distinto. El control de acceso al modo obligatorio acepta el estado
restringido; las rutas normales siguen exigiendo authenticated. Al recibir
CAMBIO_PASSWORD_REQUERIDO desde una operación normal, descartar datos privados,
cancelar peticiones, consultar contexto me y pasar al flujo obligatorio; si falla
la validación del contexto, volver a login, sin asumir permisos a partir del error.

En AuthProvider separar transporte para las operaciones permitidas al estado
restringido del transporte de perfiles normales. No relajar protectedRequest
para que ese estado pueda hacer cualquier GET/mutación. También adaptar el manejo
de 401 por código y contexto: un error de contraseña actual no debe disparar el
expire general de hoy. Un 403 de permisos no cierra por sí solo una sesión válida.

El alta de 8.4 agregará nueva contraseña inicial y confirmación, con campos ocultos,
visibilidad y política visual antes de escribir. Reemplazará el aviso actual de
«no habilita acceso» por una explicación de acceso inicial restringido y cambio
obligatorio. Nunca agregar contraseña a edición de perfil ni devolverla en detalle.
La asignación histórica usará un formulario/diálogo administrativo separado, sin
guardar secretos ni ofrecer reset de cuentas ya aprovisionadas.

Componente reutilizable de contraseña nueva: 15–128 puntos de código, máximo 512
bytes UTF-8, Unicode válido y espacios preservados; no truncar ni normalizar y no
exigir mayúsculas/números/símbolos. Confirmación exacta, mostrar/ocultar, estados
accesibles y bloqueo de reglas locales incumplidas. No duplicar la lista backend
de contraseñas comunes ni asegurar aceptación antes de la respuesta. Esta política
no se muestra en login ni se aplica a su campo de contraseña como si fuera un alta.

### Éxito y errores de red

Tras 204, borrar token, contexto, datos y todos los campos de contraseña; mostrar
éxito y exigir nuevo login. No llamar logout con el token ya revocado ni emitir
automáticamente otro login con un secreto retenido.

Si la respuesta se pierde o llega 500/contrato inesperado tras enviar el cambio,
no se sabe si hubo commit: borrar secretos y sesión local, informar incertidumbre
y volver a login. No reenviar PUT automáticamente ni probar contraseñas en segundo
plano. El usuario puede intentar manualmente la nueva; si el cambio no se confirmó,
la inicial puede seguir siendo válida y llevará de nuevo al flujo restringido.
Aplicar el limitador y no prometer que alguna de ellas funcionará si otro operador
dio de baja el perfil o modificó el estado simultáneamente.

En creación/asignación con error ambiguo, conservar solo datos no secretos y
consultar resultado antes de repetir. No usar el endpoint inicial para sobrescribir
una credencial potencialmente creada. Cualquier recuperación de acceso perdido
requiere un proceso futuro aprobado, no SQL manual ni una excepción de seguridad.

Recargar sigue perdiendo el JWT y exige login. Si no cambió la contraseña, el
backend vuelve a emitir sesión restringida; la recarga nunca elimina obligación.

## 7. Riesgos y controles de seguridad

| Riesgo | Control propuesto |
| --- | --- |
| Eludir React con llamadas directas | Comprobación de credencial y alcance dentro de cada operación/UoW; denegar normal por defecto |
| ADMIN pendiente intenta administrar | Restricción previa a cualquier regla de rol; el rol ADMIN no exceptúa el cambio |
| Token restringido «promovido» al terminar | Alcance inmutable, revocación total y nuevo login; rechazo defensivo de sesión restringida con credencial definitiva |
| Asignación inicial sobrescribe una cuenta | Endpoint solo sin credencial, inserción estricta, PK, lock y conflicto 409; no reset |
| Error entre alta y credencial o entre hash y revocación | Transacción única y pruebas de rollback, sin commits parciales |
| Reutilización del secreto que conoce ADMIN | Comparación Argon2 con actual e inicial histórica conocida en todo cambio |
| Filtración por DTO, logs o herramientas | SecretStr/repr=False, no cuerpos auth ni valores en logs/trazas/analítica; respuestas sin secretos; TLS al transmitir fuera de loopback |
| Adivinar contraseña actual con token restringido robado | Verificación de actual y limitador compartido, sesiones de 15 minutos, 429 sin revelar secretos |
| Campos de escalamiento en requests | extra=forbid, no objetivo en password, flags solo en servidor y permisos revalidados |
| Peticiones concurrentes o respuestas tardías | Revalidación transaccional, revocación, generación de sesión y cancelación en frontend |
| Hash inicial adicional comprometido | Tratarlo como dato sensible en backup/DB/permisos; no índices, exposición ni historial plaintext |
| Cliente viejo presupone acceso normal | Coordinar despliegue; backend deniega igualmente, aunque el cliente viejo no pueda completar el flujo |

La contraseña inicial es conocida por ADMIN hasta que el destinatario la cambie:
quien la posea puede iniciar el flujo restringido y escoger una definitiva. No
equivale a verificar identidad mediante MFA. Entregarla por un canal seguro fuera
del sistema, sin tickets, URLs o mensajes de esta conversación. El endpoint no la
devuelve ni envía correos. No se añade generación automática ni un canal de entrega.

La propuesta mínima no incorpora vencimiento específico de la credencial inicial:
la sesión vence en 15 minutos, pero se puede volver a iniciar el flujo con la
inicial mientras siga pendiente y el perfil activo. Un TTL de inicial y un proceso
de reemisión son decisiones adicionales, no funcionalidades existentes ni garantías
de este diseño. Tampoco se establece rotación periódica de contraseñas definitivas.
El vencimiento propio de la inicial y el restablecimiento administrativo quedan
expresamente como funcionalidades futuras. El endpoint de asignación inicial no
es un restablecimiento: no reemplaza credenciales, aunque sigan pendientes.

Referencias oficiales usadas para contrastar controles generales, no para atribuir
la decisión funcional de cambio inicial a un estándar:
[OWASP Password Storage](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html)
para hashing dedicado con salt;
[OWASP Authentication](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html)
para verificar la contraseña actual en cambios sensibles;
[OWASP Session Management](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html)
para invalidación efectiva del lado servidor. No se propone reducir los parámetros
Argon2id actuales.

## 8. Estrategia de migración y datos existentes

| Situación previa | Resultado propuesto tras migrar |
| --- | --- |
| ADMIN con credencial | Hash intacto, pendiente=false, antecedente=null; no pierde acceso ni cambia por esta migración |
| USUARIO con credencial | Mismo tratamiento; no se fuerza cambio indiscriminado |
| Perfil React sin credencial | Sigue sin credencial/login; ADMIN puede usar la nueva asignación inicial explícita |
| Perfil inactivo con credencial | Continúa inactivo, no puede autenticarse; no se altera su hash ni se reactiva |
| Perfil inactivo sin credencial | No se aprovisiona durante migración; operación futura exige reactivación separada antes de asignar |
| Sesión actual normal | restringida=false; fechas/revocación intactas; sigue hasta su expiración normal si el perfil sigue válido |
| Credencial inicial emitida después del despliegue | pendiente=true, antecedente Argon2id presente; nuevos logins restringidos |

No inferir obligación desde rol, fecha, email o el hecho de haber usado CLI en el
pasado: los datos actuales no describen quién escogió cada contraseña. Una campaña
selectiva de cambio para personas concretas sería otra operación autorizada,
con revocación y trazabilidad; no un backfill arbitrario.

Orden operativo futuro:

1. Implementar y probar migración 0003 en usuarios_test: upgrade, esquema/modelos,
   datos históricos representativos y escenarios de autenticación.
2. Comprobar downgrade/upgrade solo en pruebas aisladas, antes de usar datos nuevos
   como evidencia. El downgrade elimina marca, antecedente y alcance; no revierte
   contraseñas cambiadas. No es una reversión funcional segura tras aprovisionar
   usuarios pendientes: un backend viejo podría darles acceso normal.
3. Preparar despliegue coordinado de backend y React, impedir escrituras durante
   la transición y no mezclar binarios viejos con el nuevo esquema sin defaults.
4. Solo con autorización operativa separada: verificar revisión/destino, inventario,
   conteos y huellas de perfiles/hashes/sesiones sin mostrarlos; realizar respaldo
   por el procedimiento autorizado y aplicar 0003 en desarrollo.
5. Verificar por lectura revisiones, diferencias de esquema e integridad de datos
   existentes. No aprovisionar personas reales ni probar login de desarrollo como
   efecto secundario de esa autorización.

### Despliegue coordinado y clientes antiguos

Antes de la ventana, preparar juntos artefactos identificables de FastAPI y React,
con contratos nuevos y pruebas completas en usuarios_test. No publicar primero
un frontend que exija campos que el servidor antiguo no conoce, ni mantener
réplicas FastAPI antiguas detrás del mismo destino tras aplicar 0003.

Durante la ventana, bloquear el acceso normal en el punto de entrada y detener
todas las instancias antiguas de FastAPI, incluidos procesos CLI que puedan
escribir. Drenar solicitudes en curso antes de migrar. Con autorización operativa
separada, aplicar 0003, iniciar solo el backend compatible y publicar React como
un único despliegue coordinado. La pausa afecta al servicio; no implica revocar
en masa las sesiones históricas ni cambiar sus contraseñas.

Servir el HTML de entrada con revalidación y assets versionados por contenido;
invalidar cachés del HTML/proxy y verificar que no exista un service worker antiguo
sirviendo la aplicación. Una pestaña ya abierta puede seguir ejecutando JavaScript
viejo: exigir recarga como parte de la reapertura y comprobar ese caso en pruebas.
La caché no es una barrera de seguridad: aunque el cliente viejo no se recargue,
FastAPI debe rechazar altas sin password_inicial con 422 y todo acceso normal de
sesión pendiente con 403, sin crear perfiles parciales ni conceder permisos.
Un cliente antiguo puede quedar inutilizable hasta recargar; no se promete
compatibilidad de UX ni se agrega un fallback que omita la obligación.

Antes de reabrir, verificar artefactos servidos, contrato OpenAPI, revisión 0003,
Alembic check e integridad histórica por lectura. Los recorridos con escrituras
y clientes antiguos deben haberse verificado exclusivamente en pruebas, no
improvisarse contra desarrollo. Solo reabrir cuando estén desplegados juntos la
restricción del servidor, el cambio obligatorio y los controles de React. Si
falla la verificación, mantener la pausa; no activar aprovisionamiento ni volver
a un backend antiguo sobre datos nuevos. La reapertura no autoriza por sí sola
a crear credenciales reales.

No se ejecuta ninguno de estos pasos operativos en esta intervención. Ante fallo
de despliegue después de emitir credenciales restringidas, mantener bloqueo y
corregir hacia adelante o restaurar de forma coordinada; no quitar la restricción
mediante downgrade en desarrollo.

## 9. Plan de pruebas

Usar memoria y usuarios_test exclusivamente, con MSW y cuentas ficticias en React.
No ejecutar pruebas de limpieza, escrituras o contraseñas reales en usuarios_dev.
Mantener la cobertura previa: algunos payloads/fixtures deberán adaptarse al nuevo
contrato obligatorio; no congelar aserciones antiguas que exigían alta sin secreto.
No eliminar casos de unicidad, permisos, sesiones, rollback ni los seis casos de uso.

### Unitarias y contratos de aplicación

- Factorías de credencial pendiente/normal y sesión restringida/normal; mapeo de
  todos los campos en memoria y PostgreSQL, repr sin hashes ni plaintext.
- Alta compuesta crea perfil y credencial inicial con Argon2id; rollback si falla
  inserción, hash, autorización revalidada o commit. Conflictos de email sin adopción.
- Credencial existente rechazada por asignación incluso bajo dos solicitudes
  concurrentes; una sola ganadora, hash original intacto.
- Login inicial correcto crea sesión restringida; contraseña inicial incorrecta,
  inactivo o sin credencial producen rechazo indistinguible y límites correctos.
- Rehash conserva pendiente/antecedente y no promueve sesión.
- Cambio obligatorio verifica actual, nueva política y no reutilización; confirmar
  que dos hashes distintos del mismo secreto se detectan mediante verify.
- Rechazar volver a la inicial en un cambio voluntario posterior, sin exigir
  historial imposible a usuarios históricos.
- Cambio guarda hash definitivo, false y revocaciones atómicamente. Una excepción
  en revocación no deja una credencial parcialmente definitiva.
- Dos cambios concurrentes o login/cambio/baja concurrentes no dejan un token
  utilizable de la credencial previa ni permiten sobrescribir el resultado ganador.

### Integración HTTP y seguridad directa

Criterio de aceptación específico para ADMIN pendiente: probar un ADMIN real de
fixture con JWT y sesión restringida, no solo un rol simulado en React. Debe recibir
403 CAMBIO_PASSWORD_REQUERIDO al listar, consultar cualquier perfil (incluido el
propio), crear, editar, dar de baja, reactivar o asignar credenciales. Verificar
ausencia de datos y escrituras en cada caso y repetir la prohibición llamando
directamente a los servicios. En React no debe aparecer navegación administrativa
ni ser accesible por URL, Atrás o respuestas tardías. Solo puede consultar el
contexto mínimo, cambiar su contraseña y salir. Tras cambiar, el JWT anterior
debe fallar con 401; solo un nuevo login normal habilita la administración según
las políticas existentes. No hay excepción para el primer ADMIN de bootstrap.

| Prueba | Resultado esperado |
| --- | --- |
| ADMIN normal crea ADMIN o USUARIO con inicial | 201, sin devolver secretos, estado pendiente persistido |
| Falta inicial, se envía hash, flag false, usuario_id o confirmación extra | 422, sin escrituras |
| USUARIO/anónimo/ADMIN restringido intenta aprovisionar | 403/401/403 según contexto; nada creado |
| Token restringido llama cada GET/POST/PUT/DELETE/PATCH normal directamente | 403 CAMBIO_PASSWORD_REQUERIDO; ningún dato normal ni mutación |
| Token restringido consulta GET usuarios/{propio} | También bloqueado; no excepción de propiedad |
| Token restringido consulta me | Solo id y pendiente=true; sin perfil/rol |
| Token restringido usa logout | Revocación según contrato actual |
| Actual incorrecta en password | 401 CREDENCIALES_INVALIDAS; no cambia hash ni flag; sesión válida no se cierra por esa causa |
| Nueva incumple política o reutiliza inicial/actual | 422 con código propuesto; transacción sin cambios |
| Límite de verificaciones actuales | 429/Retry-After, sin datos sensibles |
| Cambio correcto | 204; todas las sesiones previas rechazadas con 401 |
| Login definitivo posterior | Sesión nueva normal, me completo y permisos según rol real |
| Sesión restringida artificialmente no revocada con flag ya false | 401; nunca se convierte en normal |
| Sesión normal con credencial marcada pendiente en prueba | Endpoints normales bloqueados por el estado persistido |
| Perfil dado de baja antes/durante el cambio | No autentica/no confirma fuera de las comprobaciones transaccionales |
| Asignación a existente/inactivo/ausente | Conflictos/404 documentados; no reemplazo ni reactivación implícita |

Enumerar rutas desde el router/OpenAPI para que ninguna operación normal quede
sin probar. Además de las dependencias, llamar a servicios de aplicación con un
Principal restringido para demostrar que no basta con saltarse el transporte.
Comprobar respuestas, capturas de logs y validación Pydantic con secretos ficticios:
ni contraseñas, hashes, JWT ni valores originales deben aparecer en errores.

### Límites cruzados y ausencia de bloqueos inesperados

- Con ventanas vacías, login inicial -> cambio obligatorio -> login definitivo
  funciona sin 429; repetir para ADMIN y USUARIO, y para cambio voluntario.
- Con reloj controlado, comprobar exactamente los umbrales vigentes de pareja e
  IP, Retry-After y recuperación al vencer cada ventana, sin esperas reales.
- Alternar login incorrecto y password_actual incorrecta: el consumo se acumula
  en la misma pareja y no permite duplicar el presupuesto cambiando de endpoint.
- Un éxito libera su reserva propia y conserva fallos previos; una nueva inválida
  o reutilizada con actual correcta no deja una reserva de pareja por error.
- Un rechazo de reserva no consume parcialmente otro cupo; probar concurrencia,
  liberación repetida y errores antes/después de Argon2 y de la UoW final.
- Otra pareja no hereda fallos por email+IP, aunque comparte el límite agregado
  si usa la misma IP. Una IP distinta no borra reservas anteriores. Probar NAT
  para distinguir límites esperados de un bloqueo accidental de toda la cuenta.
- Un 429 durante cambio deja hash, marca y sesión intactos; esperar o volver a
  login tras expirar la sesión no reinicia contadores. No hay reintentos de UI.
- Fallo de liberación previo al commit no produce cambio parcial; una liberación
  posterior no puede convertir un cambio confirmado en un error ambiguo evitable.

### Migración y compatibilidad

Crear fixtures de cada fila de la matriz histórica, incluir sesiones vigentes y
revocadas. Upgrade no modifica hashes, usuarios ni timestamps y asigna false/null
correctamente. Probar PK, CHECK, no defaults finales e integridad. Verificar
upgrade/downgrade/upgrade y Alembic check en usuarios_test, nunca desarrollo.
Los usuarios actuales siguen entrando normalmente; perfiles sin credencial siguen
sin entrar; reactivar un pendiente no elimina su obligación.

### React y fallos de red

- Login normal y restringido, validación de ambos me, respuesta incompleta o
  contradictoria sin renderizar menú/perfil normal.
- URLs directas y navegación Atrás no eluden la pantalla obligatoria, tampoco
  para ADMIN. Recarga exige login y conserva la obligación en servidor.
- Política visual, Unicode, espacios, bytes UTF-8, confirmación, mostrar/ocultar
  y rechazo backend sin duplicar lista de contraseñas comunes.
- Cambio obligatorio y voluntario, 401 por contraseña actual distinguido de
  sesión inválida, 403 pendiente, 422 política/reuso y 429/Retry-After.
- 204 y pérdida de respuesta antes/después del commit: limpiar secretos y tokens,
  nunca reenviar automáticamente ni iniciar sesión usando una contraseña retenida.
- Error de creación/asignación: no conservar secreto en estado global, logs o
  almacenamiento; conflicto no sobrescribe, duplicado no hace reset.
- Respuestas tardías, logout, expiración, cambio de rol, doble envío y ausencia de
  persistencia del JWT en todos los estados.

## 10. Orden propuesto de implementación por incrementos

| Incremento futuro | Trabajo | Criterio de aceptación |
| --- | --- | --- |
| 8.5A.1 Modelo y migración | Campos de credencial/sesión, puertos, inserción estricta, memoria/ORM, 0003 versionada | Datos históricos conservados, rollback y migración verificados solo en pruebas |
| 8.5A.2 Restricción del servidor | Estado de login, me mínimo, dependencias separadas y comprobación en servicios | Matriz HTTP directa y servicios sin bypass, incluidos ADMIN pendientes |
| 8.5A.3 Cambio seguro | Reuso de password, actual obligatoria, comparación inicial, límite de intentos, transacción y revocación | Cambio concurrente seguro, 204 seguido de nuevo login, reuso rechazado |
| 8.5A.4 Aprovisionamiento administrativo | POST usuarios obligatorio con inicial, asignación histórica separada y adaptación CLI | Creación atómica, solo ADMIN normal, no sobrescritura y cierre de bootstrap conservado |
| 8.5A.5 React | Estado restringido, guards, formularios inicial/obligatorio/voluntario, errores y política visual | No acceso normal anticipado, sin secretos persistidos, fallos ambiguos controlados |
| 8.5A.6 Regresión y preparación operativa | Suites existentes adaptadas y ampliadas, MSW, integración aislada, build/documentación | Evidencias completas y plan de migración/despliegue listo para otra autorización |

Estos incrementos son trabajo propuesto **dentro del diseño 8.5A**, no autorización
para comenzar ni para adelantar el cierre 8.6. La creación de nuevas credenciales
no debe habilitarse en ningún entorno antes de que restricción y cambio estén
implementados y probados de extremo a extremo.

Esta condición abarca todas las vías de aprovisionamiento: alta HTTP, asignación
a perfiles históricos y CLI, incluido bootstrap. Completar 8.5A.4 no habilita su
uso por separado. El punto de habilitación exige evidencias aprobadas de 8.5A.2,
8.5A.3 y 8.5A.5, la matriz de ADMIN pendiente, límites cruzados y despliegue
coordinado. Hasta entonces solo se permite aprovisionamiento ficticio dentro de
pruebas aisladas para verificar el flujo; nunca nuevas credenciales operativas.

Decisiones que se someten a aprobación: inicial obligatoria en alta, campo histórico
Argon2 para impedir reutilización posterior, alcance persistido de sesión, me mínimo
para pendientes, endpoint inicial solo para perfiles activos sin credencial,
limitador compartido en cambio y compatibilidad false/null de datos actuales.
No se ejecutan cambios operativos, aprovisionamientos o implementación hasta recibir
aprobación del diseño y la autorización correspondiente.
