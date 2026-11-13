# Sprint 7: autenticación y autorización

> Documento histórico: sus revisiones y comandos describen esa etapa, no el inicio actual.
> El backend vigente requiere **0003**, pruebas solo en usuarios_test:5435, cambio
> obligatorio implementado y aprovisionamiento cerrado. Seguir [la guía backend](../backend/README.md)
> y [preparación 8.6B](sprint-8-6b-preparacion.md). No ejecutar operaciones de desarrollo
> ni iniciar este código con 0001/0002 a partir de instrucciones históricas.

Implementado el 29 de octubre de 2026. **Punto de control obligatorio:** 0002 se
aplicó y verificó solo en usuarios_test. No se migró usuarios_dev, no se crearon
administradores ni credenciales allí y no se avanzó al Sprint 8.

## Arquitectura

Domain/usuarios, Application/usuarios, sus DTO y UserRepository permanecen
intactos. Credencial y Sesion viven en Domain/auth; puertos, políticas y AuthService
en Application/auth. No importan FastAPI, SQLAlchemy, Argon2 ni PyJWT.
Infrastructure implementa hashing, JWT, limitador y SecurityUnitOfWork. Presentation
conecta HTTP Bearer y comandos locales, sin consultas ni transacciones en routers.

Cada solicitud protegida valida firma/claims, sesión, vigencia, revocación,
credencial y perfil activo. Las políticas consultan el rol vigente en el backend.
El JWT no contiene rol, email, contraseña ni hash. La falta de persistencia nunca
habilita autenticación basada únicamente en JWT.

Los casos existentes siguen realizando las operaciones del perfil. Los endpoints
los invocan mediante AuthorizedCase y AuthService.manage, que aplica las políticas
dentro de la UoW y revoca sesiones al dar de baja. El repositorio tradicional sigue
disponible, pero sus commits independientes no se utilizan para componer seguridad.
Los futuros puntos de entrada deben usar la misma unidad de aplicación, no llamar
a baja/reactivación directamente para eludir la coordinación de sesiones.

### Atomicidad y concurrencia

PostgresSecurityUnitOfWork abre una sesión y transacción. El repositorio de usuarios
usa savepoints, conserva las excepciones existentes y detecta conflictos al escribir.
Solo la UoW confirma toda la operación. Un fallo revierte perfiles, credenciales
y sesiones juntos. Los errores SQLAlchemy se convierten en ErrorPersistencia saneado.

Para este backend local se utiliza un advisory lock transaccional común a todas
las operaciones de seguridad. Serializa bootstrap, cambios, comprobaciones y
contadores; simplifica la consistencia y evita intercalados inseguros. Es una
decisión conservadora con coste de rendimiento: antes de escalar se deberá diseñar
bloqueo más granular. Argon2 se ejecuta fuera de la transacción cuando es posible.
Login verifica de nuevo la credencial y el estado dentro de la transacción final,
evitando emitir sesiones con una contraseña reemplazada concurrentemente.

MemorySecurityUnitOfWork toma bloqueos de memoria, captura el estado y lo restaura
ante fallos. Usa el repositorio de memoria existente; no conecta a PostgreSQL.
Los casos de rollback y concurrencia se ejecutan contra ambos adaptadores.

## Contraseñas

Argon2id, memoria 65536 KiB, tres iteraciones, paralelismo uno, hash de 32 bytes y
salt aleatorio de 16 bytes. Son parámetros explícitos del adaptador, no valores
elegidos implícitamente por la versión de la biblioteca. Se almacenan en el hash
codificado y se verifica check_needs_rehash en un login válido.

La asignación/cambio exige 15 a 128 caracteres y hasta 512 bytes UTF-8, sin recortar,
normalizar ni truncar. Una lista mínima de contraseñas largas triviales se rechaza;
no se presenta como una base completa de contraseñas comprometidas. No hay reglas
arbitrarias de composición ni cambios periódicos forzados. El login conserva el
valor exacto. Hashes, passwords y JWT no se registran en logs.

Una cuenta inexistente o sin credencial verifica un hash ficticio para reducir
diferencias de trabajo. Inexistente, contraseña incorrecta, sin credencial e
inactivo reciben el mismo 401. No se promete igualdad perfecta de tiempos.
Un hash almacenado inválido se trata como fallo técnico, no como error de entrada.

## JWT y configuración

HS256, duración 900 segundos. Claims obligatorios: sub (UUID), jti (UUID de sesión),
iat, exp, iss, aud y token_use=access. Se comprueban tipos, duración máxima, firma,
algoritmo y fechas; tolerancia criptográfica de reloj de 30 segundos. La sesión
persistida tiene además su vencimiento estricto. Header typ=at+jwt y kid de una
lista local; algoritmos alternativos, kid desconocido y headers de claves remotas
son rechazados. Los tokens no se aceptan por query string.

Configuración externa, sin claves predeterminadas:

| Variable | Contenido |
| --- | --- |
| AUTH_JWT_KEYS_JSON | JSON kid -> clave aleatoria base64, al menos 32 bytes por clave |
| AUTH_JWT_CURRENT_KID | Identificador de clave activa presente en el JSON |
| AUTH_LIMITER_KEY | Clave HMAC independiente, al menos 32 bytes, base64 |
| AUTH_JWT_ISSUER | Emisor; predeterminado api-usuarios-clean |
| AUTH_JWT_AUDIENCE | Audiencia; predeterminada api-usuarios-clean-api |

Para pruebas se usan exclusivamente TEST_AUTH_* y .env.test. Durante esta
implementación se generaron claves aleatorias independientes solo en ese archivo,
sin mostrarlas. .env de desarrollo no fue modificado. La configuración oculta
secretos en repr y errores. No hay acceso a archivos ni conexión al importar main;
lifespan carga y compone, y dispone el Engine al finalizar.

Rotación: agregar nueva clave/kid, seleccionarla para firmar y mantener la anterior
solo durante la vida restante de tokens más tolerancia. Retirar una clave hace
inválidos sus tokens. No reutilizar claves de base de datos para JWT o HMAC.

## Endpoints y permisos

| Endpoint nuevo | Resultado |
| --- | --- |
| POST /api/v1/auth/login | 200: access_token, token_type=bearer, expires_in=900 |
| GET /api/v1/auth/me | 200: perfil propio |
| POST /api/v1/auth/logout | 204: revoca sesión; repetición idempotente con token firmado vigente |
| PUT /api/v1/auth/password | 204: exige password_actual y password_nueva; revoca todas las sesiones |

Login recibe email y password como JSON. Passwords HTTP usan SecretStr y no se
devuelven. Los endpoints auth llevan Cache-Control: no-store. Logout no exige que
la sesión siga activa para repetir la revocación; sí exige JWT firmado y vigente.
Después del cambio de contraseña se requiere nuevo login.

| Operación de perfiles | ADMIN activo | USUARIO activo |
| --- | --- | --- |
| POST /api/v1/usuarios | Sí, crea perfil sin credencial | No |
| GET /api/v1/usuarios | Sí | No |
| GET /api/v1/usuarios/{id} | Cualquier perfil | Solo propio; ajeno devuelve 404 |
| PUT /api/v1/usuarios/{id} | Sí | No |
| DELETE /api/v1/usuarios/{id} | Sí, excepto a sí mismo | No |
| PATCH /api/v1/usuarios/{id}/reactivar | Sí | No |

Sin autenticación: 401 y WWW-Authenticate: Bearer. Permiso insuficiente: 403.
Consulta de perfil ajeno por usuario común: 404, sin revelar si existe.
Validación: 422. Límite temporal: 429 y Retry-After. Fallo técnico: 500 saneado.
Se conserva el formato {"error":{"codigo":...,"mensaje":...}}.

La baja revoca todas las sesiones en la misma transacción. Reactivar no restaura
ninguna; los JWT previos siguen rechazados. No existe endpoint para elevar roles.
POST con rol ADMIN queda reservado a un administrador autenticado. PUT sigue
rechazando rol, identidad, fecha y activo. No hay registro público.

## Usuarios existentes y aprovisionamiento

0002 no cambia perfiles ni asigna passwords. Un perfil sin credencial no tiene
acceso, aunque activo sea true. Asignar credencial no reactiva una cuenta.

Comandos locales (desde backend), predeterminados a usuarios_test:

```powershell
.\.venv\Scripts\python.exe -m app.presentation.cli.security --target test bootstrap-admin --nombre Operador --apellido Pruebas --email operador.local@example.com
.\.venv\Scripts\python.exe -m app.presentation.cli.security --target test asignar-credencial-inicial --usuario-id <UUID>
.\.venv\Scripts\python.exe -m app.presentation.cli.security --target test limpiar-intentos
```

Los dos primeros solicitan password oculta y confirmación en una terminal
interactiva. No admiten argumentos de contraseña ni entrada redirigida. El operador
debe comprobar la identidad antes de asignar acceso a un UUID existente.

Bootstrap crea perfil ADMIN y credencial juntos. Si hay perfiles ADMIN antiguos
sin credenciales, se conservan; bootstrap solo puede crear un perfil de email
nuevo. Un email ya registrado se rechaza: no se adopta ni promociona la cuenta.
Alternativamente el operador puede aprovisionar por UUID un ADMIN existente sin
credencial, tras verificar su identidad. En ambos caminos, la primera credencial
ADMIN cierra bootstrap. También cuenta un administrador inactivo.

Después de ese cierre, asignar-credencial-inicial no permite aprovisionar otros
ADMIN: evita una segunda vía permanente de creación administrativa. El alta de
perfiles ADMIN sigue disponible al administrador, pero la habilitación de accesos
administrativos adicionales requerirá un flujo posterior explícitamente aprobado.
La asignación inicial de usuarios comunes sigue siendo de una sola vez. No
sobrescribe passwords y no permite reclamar cuentas conociendo su email.

No hay recuperación pública, invitaciones, refresh tokens, cookies, React ni IA.
Si se pierde el primer administrador se requiere un procedimiento local de
recuperación separado y revisado, no volver a abrir bootstrap.

## Limitación de intentos

PostgreSQL comparte contadores entre procesos. Dos ámbitos: 30 intentos/IP/minuto
y cinco fallos/reservas pendientes por email/IP en ventanas de 15 minutos. Cada
intento reserva cupo antes de Argon2; un éxito libera el cupo de la pareja, pero
no el contador global por IP. Un fallo conserva la reserva. Bajo concurrencia
pueden rechazarse temporalmente solicitudes mientras se verifican otras cinco;
no se omiten verificaciones ni se acepta un número ilimitado de trabajos costosos.

No se almacenan emails ni IP en claro: claves HMAC SHA-256 con secreto separado.
Los incrementos son atómicos y se serializan con la UoW; una reserva rechazada no
incrementa el contador de la pareja. Retry-After indica segundos de espera.
Ventanas vencidas se limpian acotadamente al recibir peticiones (100 registros)
y mediante limpiar-intentos (hasta 1000 por ejecución).

Se usa request.client, nunca se interpreta X-Forwarded-For desde la aplicación.
Ejecutar Uvicorn con --no-proxy-headers, como en los comandos siguientes, para no
aceptar reescrituras de IP por un proxy no configurado. Este control es una base
local; no constituye protección completa frente a ataques distribuidos.

## Migración y pruebas

0001 permanece idéntica. 0002 agrega public.usuario_credenciales, auth_sesiones y
auth_intentos, con FK RESTRICT a usuarios, restricciones temporales/contadores,
PK e índices para revocación y vencimientos. No guarda JWT completos.
Downgrade a 0001 conserva perfiles, pero destruye credenciales y sesiones; solo
se probó en la base descartable. No ejecutar downgrade en desarrollo.

Alembic normaliza una copia de metadata para comparar el esquema predeterminado
de PostgreSQL (None) con public en las FK. Los modelos y las migraciones conservan
el esquema explícito public; no se ocultaron diferencias de estructura.

```powershell
# Backend; solo pruebas aisladas
.\.venv\Scripts\python.exe -m alembic -x target=test upgrade head
.\.venv\Scripts\python.exe -m alembic -x target=test current
.\.venv\Scripts\python.exe -m alembic -x target=test check
.\.venv\Scripts\python.exe -m pytest -m "not postgres"
.\.venv\Scripts\python.exe -m pytest --run-postgres
.\.venv\Scripts\python.exe -m pip check
```

La suite original conserva sus escenarios. Las pruebas HTTP anteriores ahora
usan un actor ADMIN real en memoria y sustituyen los casos de negocio para
conservar sus datos originales. Las nuevas pruebas de seguridad y la integración
ejercitan la composición real sin esos overrides. No hay flag de desactivación
de seguridad en producción. Los tests de importación/lifespan usan dobles de
autenticación cuando su objetivo es verificar recursos, no permisos.

Las fixtures PostgreSQL comprueban base, usuario y puerto antes de migrar/limpiar;
limpian tablas conocidas junto con sus FK, sin CASCADE ni acceso a usuarios_dev.
Las pruebas no están diseñadas para correr en procesos paralelos sobre la misma
base; los escenarios concurrentes usan hilos dentro de una ejecución controlada.

## Verificación manual en pruebas

Desde la raíz, iniciar solo el servicio aislado si hace falta:

```powershell
docker compose --env-file .env.test -f compose.test.yaml up -d --wait postgres
Set-Location backend
.\.venv\Scripts\python.exe -m alembic -x target=test upgrade head
.\.venv\Scripts\python.exe -m app.presentation.cli.security --target test bootstrap-admin --nombre Operador --apellido Local --email operador.local@example.com
.\.venv\Scripts\python.exe -m uvicorn app.bootstrap:create_test_database_app --factory --host 127.0.0.1 --port 8001 --no-proxy-headers
```

Si ya hay administrador con credencial, bootstrap debe fallar; usar su cuenta
existente o un entorno descartable separado, no sobrescribir credenciales.
Las pruebas automatizadas limpian usuarios_test y pueden retirar perfiles manuales.

Swagger: http://127.0.0.1:8001/docs. Ejecutar login con la contraseña introducida
localmente; copiar access_token a Authorize. Probar me, perfiles, baja/reactivación,
logout y cambio de contraseña. No compartir capturas o exportaciones con tokens.
En Postman importar docs/postman/usuarios.postman_collection.json e ingresar un
token ADMIN en una variable local/no compartida accessToken; el archivo versionado
deja esa variable vacía y no contiene passwords.

## Desarrollo: segunda autorización pendiente

No se ejecutaron estos pasos. Solo después de autorizar la migración y el
aprovisionamiento en desarrollo:

1. Generar claves criptográficamente aleatorias independientes (JWT >=32 bytes;
   se recomienda 64; HMAC >=32) y configurar AUTH_* en .env sin mostrarlas.
2. Comprobar usuarios_dev en 127.0.0.1:5434 y los perfiles existentes.
3. Revisar 0002 y aplicar con la autorización operativa:

```powershell
.\.venv\Scripts\python.exe -m alembic -x allow-development=true upgrade head
.\.venv\Scripts\python.exe -m alembic -x allow-development=true current
.\.venv\Scripts\python.exe -m alembic -x allow-development=true check
```

4. Elegir explícitamente crear un ADMIN nuevo de email no usado, o asignar la
   primera credencial por UUID a un ADMIN existente cuya identidad se verificó.
   Los comandos requieren --target development --allow-development; no ejecutarlos
   ahora ni pasar passwords en argumentos.
5. Iniciar solo en loopback:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-proxy-headers
```

Sin claves externas la aplicación falla al iniciar en lugar de inventar una
clave. Con 0001 solamente, las operaciones de seguridad no están habilitadas: no
se intenta migrar automáticamente. El flag de CLI no sustituye la autorización
del usuario para modificar desarrollo.

## Dependencias, resultados e inventario

Python 3.14.3 sin cambios. Dependencias nuevas: argon2-cffi 25.1.0, PyJWT 2.15.1.
Transitivas: argon2-cffi-bindings 26.1.0, cffi 2.1.1, pycparser 3.12. Instaladas
en .venv mediante wheels compatibles y TLS activo, sin cambios globales de CA.
Se conserva la advertencia previa de Starlette/TestClient sobre httpx.

Verificados: hashing y rehash, JWT alterados/vencidos y rotación, fallos de login
indistinguibles, permisos actuales, inactivos, revocación, cambios de contraseña,
rollback después de escribir perfil/credencial, fallo al firmar tokens, carreras
de contraseña/login, bootstrap concurrente, contadores concurrentes y limpieza,
migraciones con perfiles existentes y ausencia de plaintext en limitadores.
Resultado final: **319 pruebas aprobadas en 17,17 segundos**: las 248 anteriores
con cobertura conservada y 71 nuevas. Hay una advertencia ya conocida de
Starlette/TestClient sobre httpx. Alembic: `0002 (head)` y
`No new upgrade operations detected.`. `pip check`: sin conflictos.
Ejecución separada sin PostgreSQL: **288 aprobadas**, 31 casos PostgreSQL
excluidos. Los 31 casos PostgreSQL también aprobaron dentro de la suite completa.
Las pruebas de bootstrap cubren perfiles ADMIN previos sin credencial, rechazo
de apropiación por email, cierre tras la primera credencial y dos creaciones
concurrentes con un único ganador, tanto en memoria como en PostgreSQL.

Una consulta final estrictamente de solo lectura confirmó usuarios_dev en 0001
y ausencia de las tres tablas nuevas. Los contenedores mantienen sus identidades
y estados anteriores. Se comprobaron por hashes los archivos originales de
Domain/usuarios, Application/usuarios y la revisión 0001.

Nuevos archivos principales:

- domain/auth/__init__.py y models.py.
- application/auth/__init__.py, exceptions.py, ports.py, policies.py y service.py.
- infrastructure/configuration/auth.py.
- infrastructure/security/__init__.py, crypto.py, memory.py, postgres.py y limiter.py.
- infrastructure/persistence/models/auth.py.
- presentation/http/auth/__init__.py, dependencies.py y router.py.
- presentation/cli/__init__.py y security.py.
- migrations/versions/0002_auth.py.
- tests/auth_support.py, tests/security (conftest y seis módulos de pruebas),
  tests/integration/postgresql/test_auth_migration.py y esta guía.

Modificados: bootstrap.py, dependencias/router/errores HTTP, migrations/env.py,
pyproject.toml, fixtures y pruebas HTTP/migraciones existentes (sin eliminarlas),
.env.example y .env.test local (solo claves de pruebas), README, arquitectura y
colección Postman. Los archivos existentes de Domain/usuarios, Application/usuarios,
UserRepository y 0001 conservan sus hashes. .env y Compose permanecen intactos.

## Requisito futuro de React: validación visual y explicativa de contraseñas

Estado: documentado, pendiente de implementación del frontend. Este requisito
no habilita nuevos flujos, endpoints ni el avance al siguiente sprint.

Aplica a todos los formularios donde se establezca una contraseña nueva:
creación, cambio o restablecimiento, cuando dichos flujos estén disponibles.
La política y su lista de requisitos no deben mostrarse en el formulario de login.

Antes de escribir, el formulario debe explicar la política actual del backend:

- Entre 15 y 128 caracteres, ambos límites incluidos.
- Tamaño máximo de 512 bytes UTF-8.
- Rechazo de determinadas contraseñas comunes por el backend.
- Se admiten espacios y caracteres Unicode válidos.
- No se exige combinar mayúsculas, números ni símbolos.

Durante la escritura, debe validar las reglas comprobables localmente y mostrar
qué condiciones se cumplen y cuáles faltan. Debe incluir controles para mostrar
u ocultar la contraseña y su confirmación, verificar que ambas coincidan y
presentar errores comprensibles asociados al campo correspondiente. Los estados
deben expresarse con texto o indicadores accesibles, sin depender solo del color.
Debe impedir el envío cuando incumpla alguna regla conocida o la confirmación
no coincida. No debe imponer restricciones adicionales.

La validación debe conservar exactamente el valor introducido: no recortar
espacios, normalizar Unicode ni truncar la contraseña. Para equivalencia con
Python, contar puntos de código Unicode, no unidades UTF-16 de `String.length`
ni caracteres visuales; calcular por separado los bytes UTF-8 y rechazar Unicode
inválido, sin sustituirlo silenciosamente durante la codificación.

El backend sigue siendo la autoridad definitiva. No duplicar en React su lista
interna de contraseñas comunes ni marcar esa condición como aprobada por una
comprobación local. Explicar que el servidor la verificará al enviar. Si el
servidor identifica ese rechazo mediante su contrato de errores, mostrar junto
al campo: «Esta contraseña es demasiado común. Elegí otra». Si la respuesta
solo indica incumplimiento general de la política, mostrar un mensaje general
comprensible sin atribuirle una causa específica. No inferir códigos ni motivos
que el contrato del backend no exponga. Los errores del servidor deben permitir
corregir la contraseña y volver a enviar sin revelar ni registrar su contenido.

Criterios de aceptación para la futura implementación:

- Política visible antes de escribir en los formularios aplicables y ausente en login.
- Indicadores actualizados en tiempo real para longitud, bytes UTF-8, Unicode
  válido y coincidencia de confirmación.
- Controles de visibilidad disponibles para ambos campos.
- Envío bloqueado ante incumplimientos locales; sin reglas de composición añadidas.
- Rechazos del backend presentados de forma comprensible, sin duplicar la lista
  de contraseñas comunes y sin prometer aceptación antes de la respuesta del servidor.
- Equivalencia con el backend en límites, espacios y Unicode, incluyendo caracteres
  fuera del plano básico y secuencias combinadas.
