# Sprint 8: diseño técnico del frontend React

Estado: propuesta para aprobación, sin implementación. Fecha: 30 de octubre de
2026. No se creó el proyecto frontend, no se instalaron dependencias y no se
modificaron backend, bases de datos ni Docker.

## 1. Diagnóstico y fuentes del contrato

El Sprint 7 cerró con 319 pruebas aprobadas, incluidos 31 casos PostgreSQL.
El usuario confirmó manualmente migración 0002, administrador inicial, login y
`GET /api/v1/auth/me` en desarrollo. Este diseño no repite operaciones sobre
desarrollo. Algunos apartados históricos de arquitectura y Sprint 7 todavía
describen 0002 como pendiente: no representan el estado posterior confirmado.

La fuente de verdad inspeccionada es:

- `backend/src/app/presentation/http/auth/router.py`: esquemas y rutas auth.
- `backend/src/app/presentation/http/usuarios/{router,schemas}.py`: usuarios.
- `backend/src/app/presentation/http/errors.py`: errores reales y cabeceras.
- `backend/src/app/application/auth/{service,policies}.py`: reglas y permisos.
- `backend/src/app/infrastructure/security/{crypto,limiter}.py`: JWT y límites.
- `backend/src/app/bootstrap.py`: composición y ausencia de middleware CORS.
- `backend/src/app/domain/usuarios/{email,usuario}.py`: validación de perfiles.
- `docs/sprint-7-autenticacion.md`: requisito visual de contraseñas.

### Tipos compartidos del contrato HTTP

Los nombres en español se conservan en transporte; no se inventa una API inglesa.
UUID y fechas ISO 8601 se representan como strings TypeScript. Las fechas se
formatean para presentación sin alterar el instante recibido.

| Tipo propuesto | Campos reales |
| --- | --- |
| `UsuarioRespuesta` | `id`, `nombre`, `apellido`, `email`, `activo: boolean`, `rol: ADMIN o USUARIO`, `fecha_creacion` |
| `CrearUsuarioSolicitud` | `nombre`, `apellido`, `email`, `rol` opcional, predeterminado USUARIO |
| `ModificarUsuarioSolicitud` | `nombre`, `apellido`, `email`, todos obligatorios |
| `LoginSolicitud` | `email`, `password` |
| `TokenRespuesta` | `access_token`, `token_type: bearer`, `expires_in: 900` |
| `PasswordSolicitud` | `password_actual`, `password_nueva`; sin confirmación en la API |
| `ErrorRespuesta` | `error: { codigo, mensaje, usuario_id?, detalles?: [{ campo, codigo, mensaje }] }` |

Los esquemas de entrada rechazan campos adicionales. El dominio exige nombre y
apellido de 1 a 100 caracteres después de eliminar espacios externos. El email
es ASCII, hasta 254 caracteres, parte local hasta 64 y dominio con al menos dos
etiquetas; normaliza a minúsculas y quita espacios ASCII externos. No admite
partes locales entre comillas ni puntos iniciales, finales o consecutivos.
La unicidad del email incluye perfiles inactivos. No usar un validador de email
de biblioteca o el navegador como autoridad que bloquee formatos admitidos por
este dominio: validación conservadora local y respuesta definitiva del servidor.

### Endpoints implementados

Todas las rutas siguientes incluyen el prefijo `/api/v1`. Salvo login, requieren
`Authorization: Bearer <token>`. Los errores 500 son posibles en todas ellas.

| Método y ruta | Entrada | Éxito | Otros estados relevantes |
| --- | --- | --- | --- |
| POST `/auth/login` | LoginSolicitud JSON | 200 TokenRespuesta; `Cache-Control: no-store`, `Pragma: no-cache` | 401, 422, 429 |
| GET `/auth/me` | Sin cuerpo | 200 UsuarioRespuesta propio | 401 |
| POST `/auth/logout` | Sin cuerpo | 204 sin cuerpo | 401 |
| PUT `/auth/password` | PasswordSolicitud JSON | 204 sin cuerpo; revoca todas las sesiones | 401, 422 |
| POST `/usuarios` | CrearUsuarioSolicitud JSON | 201 UsuarioRespuesta; cabecera Location | 401, 403, 409, 422 |
| GET `/usuarios` | Query estado, limite, desplazamiento | 200 array de UsuarioRespuesta | 401, 403, 422 |
| GET `/usuarios/{id}` | UUID en path | 200 UsuarioRespuesta | 401, 403 documentado, 404, 422 |
| PUT `/usuarios/{id}` | ModificarUsuarioSolicitud JSON | 200 UsuarioRespuesta | 401, 403, 404, 409, 422 |
| DELETE `/usuarios/{id}` | Sin cuerpo o `{}` | 204, baja lógica idempotente | 401, 403, 404, 422 |
| PATCH `/usuarios/{id}/reactivar` | Sin cuerpo o `{}` | 200 UsuarioRespuesta, idempotente | 401, 403, 404, 422 |

`PUT /usuarios/{id}` conserva rol, estado, identidad y fecha; permite editar
inactivos. No existe modificación de rol vía HTTP. Reactivación conserva UUID
y no restaura sesiones anteriores. ADMIN no puede darse de baja a sí mismo.

Listado: `estado=activos|inactivos|todos` (activos por defecto), `limite=1..100`
(20 por defecto), `desplazamiento>=0` (0 por defecto). Filtra antes de paginar,
ordena ascendente por fecha de creación y UUID. No hay total, búsqueda por texto,
filtro por rol ni orden configurable. No ofrecer controles que sugieran esos
contratos. La paginación por offset puede desplazarse con cambios concurrentes.

### Errores y diferencias importantes

| Estado / código | Tratamiento diseñado |
| --- | --- |
| 401 `CREDENCIALES_INVALIDAS` en login | Mensaje común; no distinguir inexistente, inactivo o sin credencial |
| 401 `AUTENTICACION_REQUERIDA` en operación protegida | Invalidar estado de autenticación, cancelar peticiones y volver a login |
| 401 `CREDENCIALES_INVALIDAS` en cambio de contraseña | Contraseña actual incorrecta; mostrar error del formulario sin destruir una sesión válida |
| 403 `PERMISO_DENEGADO` | Mostrar falta de permiso; no cerrar sesión; refrescar perfil si procede |
| 404 `USUARIO_NO_ENCONTRADO` | Mostrar recurso no disponible, sin inferir que pertenece a otra persona |
| 409 `USUARIO_ACTIVO_EXISTENTE` | Conflicto de alta; no crear ni sobrescribir |
| 409 `USUARIO_INACTIVO_REACTIVABLE` | Ofrecer revisar perfil indicado en usuario_id y confirmar reactivación explícita |
| 409 `EMAIL_EN_USO` | Error en email de edición; mantener formulario |
| 422 `PASSWORD_INVALIDA` | Política incumplida; error general en nueva contraseña |
| 422 `SOLICITUD_INVALIDA` y códigos de dominio | Mostrar detalles conocidos y resumen si campo no mapeable |
| 429 `LIMITE_INTENTOS` | Respetar Retry-After en segundos; deshabilitar reenvío con cuenta regresiva; sin reintentos automáticos |
| 500 / red / respuesta inesperada | Mensaje técnico genérico; distinguir de cierre de sesión; reintento manual seguro |

Los detalles de validación Pydantic saneados pueden denominar los campos de
contraseña `body.campo`, no su nombre original. No siempre se pueden asociar
automáticamente a un input. `PASSWORD_INVALIDA` sí indica `body.password_nueva`,
pero no distingue contraseña común de las otras reglas: no inventar ese motivo.
Los 401 incluyen WWW-Authenticate Bearer. Auth agrega Cache-Control no-store.

### Límites que condicionan el alcance

1. Alta de usuario crea solo un perfil: no contraseña, credencial ni invitación.
   El formulario se llamará «Crear perfil» y explicará que no habilita login.
   No hay indicador HTTP de si un perfil tiene credencial. No mostrar estados
   inventados de acceso. El aprovisionamiento inicial sigue siendo una CLI local.
2. No existen refresh, cookies de sesión, recuperación de contraseña, registro
   público, consulta de política, administración de sesiones ni cambio de rol.
   No se diseñan botones funcionales para esas operaciones.
3. CORS no está configurado. Acceso directo desde otro origen necesita cambios
   aprobados o un proxy de mismo origen. El diseño recomendado usa el proxy.
4. El frontend no podrá recuperar la sesión después de una recarga con el
   contrato actual y la prohibición de persistir JWT. Se acepta nuevo login.
5. La lista no tiene total ni estadísticas: el dashboard no mostrará métricas
   globales ficticias. Tampoco simular filtros globales sobre una sola página.

## 2. Arquitectura propuesta

SPA React + TypeScript estricto + Vite, organizada por funcionalidad. Componentes
presentan; hooks coordinan estado y peticiones; módulos API conocen HTTP; el
backend mantiene las decisiones de negocio y autorización. No reproducir las
capas Python ni crear interfaces y repositorios frontend sin necesidad.

```text
frontend/                         # futuro; no creado en esta intervención
  package.json
  package-lock.json
  vite.config.ts
  tsconfig.json
  index.html
  .env.example                    # solo configuración pública
  src/
    main.tsx
    app/
      App.tsx
      providers.tsx
      config.ts
      theme.ts
    router/
      routes.tsx
      ProtectedRoute.tsx
      AdminRoute.tsx
    api/
      httpClient.ts
      contracts.ts
      errors.ts
    features/
      auth/
        api/authApi.ts
        model/AuthProvider.tsx
        model/authState.ts
        pages/LoginPage.tsx
        pages/ChangePasswordPage.tsx
        components/LoginForm.tsx
        components/ChangePasswordForm.tsx
      usuarios/
        api/usuariosApi.ts
        hooks/useUsuarios.ts
        pages/UsuariosPage.tsx
        pages/UsuarioDetailPage.tsx
        pages/UsuarioCreatePage.tsx
        pages/UsuarioEditPage.tsx
        components/UsuarioForm.tsx
        components/UsuariosTable.tsx
        components/EstadoFilter.tsx
      perfil/pages/MiPerfilPage.tsx
      dashboard/pages/DashboardPage.tsx
    shared/
      layout/AppShell.tsx
      ui/ConfirmDialog.tsx
      ui/AsyncState.tsx
      ui/PasswordField.tsx
      ui/NewPasswordFields.tsx
      validation/passwordPolicy.ts
      validation/profileFields.ts
    test/
      setup.ts
      renderWithProviders.tsx
      mocks/handlers.ts
      mocks/server.ts
  e2e/
    auth.spec.ts
    usuarios.spec.ts
    permissions.spec.ts
```

Pruebas unitarias junto al módulo (`*.test.tsx`). `api/contracts.ts` centraliza
DTO del transporte; cada feature expone una API pequeña y no importa páginas de
otra feature. `perfil` usa el usuario de auth, no crea un segundo estado de
identidad. `dashboard` solo compone información real. `shared` no contiene
políticas ADMIN/USUARIO ni estado global de negocio. `app/providers.tsx` compone
dependencias e inyecta el lector de token al cliente para evitar imports cíclicos.

## 3. Tecnologías y decisiones de mantenimiento

| Elección propuesta | Justificación y límite |
| --- | --- |
| React, TypeScript estricto, Vite | Stack solicitado; contratos explícitos y SPA sin SSR innecesario |
| React Router en modo declarativo | Rutas anidadas, layouts y guards simples; sin framework SSR |
| Context + reducer para auth | Estado pequeño y explícito; no Redux ni persistencia automática |
| Fetch nativo + AbortController | Cliente HTTP pequeño; no Axios por ahora |
| React Hook Form | Registro de campos, errores y envíos; validadores propios ajustados al contrato |
| Material UI Core + Emotion | Componentes base, formularios, diálogos, layout y tema comunes; usar componentes gratuitos |
| CSS propio acotado | Ajustes responsive y layout; evitar construir desde cero focos, diálogos y estados de inputs |
| Vitest + jsdom + Testing Library + user-event | Pruebas de comportamiento de componentes y formularios |
| MSW | Simulación de API al nivel de red, compartida entre pruebas |
| Playwright | Recorridos reales de navegador contra backend exclusivamente de pruebas |

Elegir tabla MUI estándar, no Data Grid con paginación que presuponga un total.
MUI reduce trabajo repetitivo y permite concentrar el aprendizaje en React y
los contratos. Su coste es aprender tematización y adaptar estilos; no garantiza
por sí solo accesibilidad. CSS propio completo daría más práctica visual, pero
aumentaría componentes y pruebas de interacción para este sprint.

No añadir aún TanStack Query, Zustand, Zod, Axios ni un framework de IA. Si el
estado remoto crece, los hooks de feature permiten incorporar caché después sin
reescribir páginas. En este sprint habrá refetch explícito e invalidación simple.

Las versiones concretas quedan pendientes de implementación: comprobar Node
disponible, requisitos de Vite, peer dependencies y versiones estables compatibles;
fijarlas en lockfile y ejecutar build/typecheck. No asumir compatibilidad por las
versiones del backend ni instalar herramientas globales en esta intervención.

Referencias oficiales consultadas para estas recomendaciones:
[Vite](https://vite.dev/config/),
[React Router](https://reactrouter.com/start/modes),
[Material UI](https://mui.com/material-ui/getting-started/accessibility/),
[React Hook Form](https://react-hook-form.com/guides).

## 4. Autenticación: estrategia compatible con Sprint 7

### Token y estado

JWT únicamente en memoria dentro del proveedor de autenticación: nunca en
localStorage, sessionStorage, IndexedDB, URLs, cookies escritas por JavaScript,
logs, analítica ni persistencia de caché. No guardar contraseñas en estado global.
No decodificar roles desde el JWT: no los contiene y no son una autoridad.
El usuario y rol para presentación provienen de `/auth/me`.

Estados: anónimo, autenticando, validando perfil, autenticado y cerrando sesión.
Una transición de sesión incrementa un identificador de generación: respuestas
tardías de un login o petición anterior no pueden restaurar identidad o datos.
En logout o 401 terminal, cancelar solicitudes e invalidar datos de features.
No hacer llamadas de red dentro de un reducer.

Flujo de login: validar campos mínimos, enviar JSON, guardar JWT provisionalmente
en memoria, consultar `/auth/me` y solo después habilitar rutas privadas. Si me
devuelve 401, descartar token. Si falla por red/500, ofrecer reintentar la
validación mientras el token siga vigente; nunca declarar autenticado sin perfil.
Al abandonar este estado, intentar revocar el token si se dispone de conexión.

La duración publicada es 900 segundos. Programar un aviso/cierre conservador a
partir del inicio de la solicitud de login más expires_in, y revisar reloj al
recuperar foco: los temporizadores de pestañas en segundo plano no son exactos.
La sesión de backend expira estrictamente; la tolerancia del verificador JWT no
extiende la sesión. Un 401 protegido prevalece sobre cualquier temporizador.
No extender plazo con actividad ni repetir login en segundo plano.

Antes de mostrar el layout privado se requiere estado autenticado. Guards
ocultan navegación y evitan pantallas improcedentes; no reemplazan autorización
servidora. Refrescar `/auth/me` al recuperar foco cuando sea razonable para reflejar
rol/estado actual; ante cambio limpiar datos administrativos. Una petición ya
autorizada siempre queda sujeta a las comprobaciones de backend.

### Recarga, pestañas y alternativas futuras

En Sprint 8 una recarga completa, pestaña nueva o reinicio pierde el token y lleva
a login. La navegación interna SPA conserva la sesión en memoria. No intentar
restaurarla invocando me sin token ni usar un token de Swagger. La sesión anterior
del servidor puede seguir vigente hasta expirar: perder memoria no la revoca.
Documentar esta limitación en la ayuda, sin recuperar tokens de otros almacenes.

| Alternativa | Implicancias; fuera del alcance actual |
| --- | --- |
| Cookie HttpOnly con sesión de backend | Requiere modificar contratos y transporte, Secure/SameSite, CSRF y política de origen; puede permitir restauración con me |
| BFF con cookie HttpOnly y token en servidor | Añade servicio y ciclo de sesiones; evita token en JavaScript; requiere diseño operativo y CSRF |
| Refresh con rotación y revocación | Requiere endpoints, almacenamiento seguro, protección de reutilización y pruebas nuevas; hoy no existe |

No se recomienda una cookie accesible a JavaScript para esconder persistencia
del token. La memoria reduce persistencia, pero un XSS activo sigue pudiendo
actuar como usuario: evitar HTML no confiable, no usar dangerouslySetInnerHTML,
no introducir secretos en el bundle y planificar CSP/HTTPS al desplegar.

### Logout y cambio de contraseña

Logout: capturar el token en memoria, bloquear nuevos envíos, cancelar solicitudes
de negocio e invocar POST logout con ese token. Tras 204 limpiar todo y navegar
a login con replace. Si devuelve 401, limpiar igualmente. Si hay red/500, limpiar
localmente y avisar que no se pudo confirmar revocación remota y que la sesión
puede seguir vigente hasta expirar. No anunciar «revocada» sin confirmación ni
conservar el token en disco para reintentar. El cierre de pestaña no garantiza
logout; no depender de beforeunload.

Cambio de contraseña: enviar solo actual y nueva, nunca confirmación. Tras 204,
vaciar los tres campos, descartar token y usuario, limpiar datos y volver a login
con mensaje de éxito: todas las sesiones fueron revocadas. No intentar logout
ni otro me usando la sesión ya invalidada. Un 401 CREDENCIALES_INVALIDAS de esta
operación se presenta como error de contraseña actual, sin confundirlo con
AUTENTICACION_REQUERIDA. Ante resultado ambiguo por red, no reenviar
automáticamente: explicar que puede haberse aplicado y pedir nuevo login.

## 5. Navegación por roles

| Ruta frontend propuesta | Anónimo | ADMIN | USUARIO |
| --- | --- | --- | --- |
| `/login` | Disponible | Redirigir a dashboard si autenticado | Igual |
| `/dashboard` | Login | Perfil y accesos administrativos | Perfil y accesos propios |
| `/mi-perfil` | Login | Consulta propia | Consulta propia |
| `/cambiar-password` | Login | Permitido | Permitido |
| `/usuarios` | Login | Listado y operaciones | Pantalla sin permiso |
| `/usuarios/nuevo` | Login | Crear perfil | Sin permiso |
| `/usuarios/:id` | Login | Consultar cualquier perfil | Sin acceso a esta sección; usar mi-perfil |
| `/usuarios/:id/editar` | Login | Editar datos | Sin permiso |
| Ruta desconocida | 404 de interfaz | 404 de interfaz | 404 de interfaz |

Redirección posterior a login solo a rutas internas permitidas; validar returnTo
para evitar redirecciones externas y no colocar tokens o datos personales allí.
ADMIN tiene todas las acciones salvo baja propia; deshabilitar esa acción con
explicación. USUARIO no puede editar ni siquiera sus datos propios por el contrato
actual, aunque sí cambiar su contraseña en su ruta específica. El backend devuelve
404 al consultar perfiles ajenos como USUARIO para no revelar existencia.

## 6. Pantallas y componentes

### Login

Tarjeta centrada responsive, título claro, email y contraseña, control mostrar/
ocultar, botón con estado de carga y error accesible. autocomplete username y
current-password. No mostrar política de contraseña nueva ni imponer 15 caracteres
a la contraseña de login: el esquema acepta de 1 a 128. Sin recortar contraseña.
Validar email requerido de forma compatible y bloquear doble envío. Mensaje
común para credenciales inválidas y contador con Retry-After ante 429. Sin
«Registrarse» o «Olvidé mi contraseña» funcionales: esos flujos no existen.

### Dashboard y shell

Encabezado con nombre, rol recibido y menú de cuenta; navegación lateral en
escritorio y panel desplegable en móvil. Mostrar saludo, datos propios y accesos
reales. No tarjetas de métricas deducidas de una página de usuarios. Acciones
comunes: mi perfil, cambiar contraseña y salir; administración solo para ADMIN.

### Administración

Tabla semántica con nombre, apellido, email, rol y estado; vista de tarjetas en
móvil conservando etiquetas y acciones. Skeleton o indicador de carga, vacío
informativo y error con reintento manual. Filtro de estado y tamaño de página
(opciones hasta 100); cambiar filtro reinicia offset. Mostrar «Anterior» y
«Siguiente», sin total inventado. Si la página tiene menos que el límite, no hay
siguiente; si está completa se permite avanzar y puede aparecer una página vacía.
En ese caso ofrecer volver. Al cambiar filtro, cancelar la petición anterior y
evitar que una respuesta tardía reemplace la consulta actual.

Alta: nombre, apellido, email y selección de rol, USUARIO por defecto. Avisar
«Crea un perfil; no asigna contraseña ni habilita acceso». No agregar contraseña.
Éxito lleva a detalle del UUID devuelto. Edición solo nombre, apellido y email;
rol y estado son informativos. No enviar campos de solo lectura.

Baja: diálogo que identifica el perfil, explica baja lógica y revocación de
sesiones, confirma o cancela. Reactivación: confirmación explícita, sin prometer
recuperar sesiones. No hay borrado físico. Tras mutación recargar consulta/detalle
afectados; si queda página vacía, volver a offset anterior de forma controlada.
Conflicto por email inactivo ofrece revisar y confirmar reactivación por separado;
no reactivar al confirmar un formulario de alta ni copiar sus datos sobre el perfil.

### Mi perfil

Lectura de nombre, apellido, email, rol, estado y fecha; fuente `/auth/me`.
Sin edición propia para USUARIO. ADMIN puede acceder a edición administrativa
propia, sin exponer una acción de baja propia. Estados de carga y fallos coherentes.

### Cambio de contraseña y componentes compartidos

Contraseña actual (current-password), nueva y confirmación (new-password).
Política visible antes de escribir solo para la nueva. Mostrar/ocultar cada campo
con botón type button y nombre accesible dinámico. No bloquear pegado ni gestores
de contraseñas. Error de actual incorrecta se asocia al campo; la confirmación
es validación local y nunca viaja por HTTP.

`PasswordField` resuelve input y visibilidad. `NewPasswordFields` compone nueva,
confirmación, explicación, lista de cumplimiento y errores del servidor; no sabe
de login, HTTP ni roles. `passwordPolicy.ts` contiene solo reglas locales conocidas.
El formulario decide envío, limpieza y transición tras éxito.

### Política visual exacta

- Longitud por puntos de código Unicode: 15 a 128, no String.length UTF-16 ni
  grafemas. No usar maxlength HTML que impida valores válidos con caracteres astrales.
- Hasta 512 bytes UTF-8; detectar surrogates aislados antes de TextEncoder para
  no convertir Unicode inválido silenciosamente en caracteres de reemplazo.
- Preservar espacios, mayúsculas y secuencias Unicode; no normalizar ni truncar.
- No exigir categorías de caracteres ni usar un medidor de fuerza como bloqueo.
- Lista visual con texto y estado accesible para longitud, bytes, Unicode válido
  y coincidencia. Actualizar sin anuncios excesivos de lector de pantalla.
- Informar «El servidor también verifica contraseñas comunes». No copiar la lista
  interna ni mostrarla como aprobada por el navegador.
- El servidor hoy solo expone PASSWORD_INVALIDA general: mostrar su mensaje
  público sin afirmar que la causa fue una contraseña común. Un código específico
  futuro requeriría contrato aprobado antes de adaptar ese mensaje.

Reutilizable en futuros formularios de establecimiento de contraseña; no crear
pantallas de restablecimiento o registro que hoy no tienen backend.

### Accesibilidad y consistencia

Objetivo WCAG 2.2 AA: labels visibles, navegación completa por teclado, foco
visible, contraste, regiones de estado, errores asociados mediante aria-describedby
y aria-invalid. ConfirmDialog restaura foco al cerrar y enfoca una acción segura.
En cambios de ruta actualizar título y foco principal; respetar movimiento reducido.
No depender solo de color para activo/inactivo o validación. Mostrar éxito de
mutaciones en región accesible y conservar errores hasta que puedan comprenderse.

## 7. Cliente HTTP e integración con FastAPI

`httpClient.ts` recibe baseURL y callbacks para leer token y notificar sesión
inválida. Construye JSON, agrega Bearer solo para el backend configurado y recibe
AbortSignal. No enviar Authorization a terceros o URLs arbitrarias. Reconocer
204 sin intentar parsear JSON. Errores tipados distinguen HTTP, red, cancelación
y contrato inesperado; validar estructura mínima de respuestas críticas, porque
TypeScript no valida JSON en ejecución. No registrar cuerpos auth, tokens ni
cabeceras Authorization. Mensajes desconocidos se reemplazan por texto seguro.

AuthApi conoce rutas auth; usuariosApi conoce rutas y queries de usuarios.
No concatenar paths en componentes. Centralizar códigos del contrato y mapeo de
campos conocidos. Señalar 401 por código y contexto, no un interceptor que cierre
sesión ante cualquier 401. Respuestas de una sesión anterior se ignoran usando
la generación de sesión. No reintentar automáticamente operaciones mutantes,
login ni 429. Cancelar fetch no garantiza rollback de una mutación ya recibida:
si su resultado es ambiguo, consultar estado antes de repetir cuando sea posible.

`VITE_API_BASE_URL=/api/v1` será configuración pública; sin claves JWT/HMAC ni
contraseñas PostgreSQL en frontend. Variables VITE se incorporan al cliente, no
son un almacén de secretos. El frontend usará su propio directorio/env, nunca
leerá `.env` de backend/raíz. [Configuración de Vite](https://vite.dev/config/).

### Origen y CORS

Recomendación: navegador -> Vite en loopback -> proxy `/api` -> FastAPI, conservando
el path completo `/api/v1`. El frontend pide rutas relativas al mismo origen,
sin cambios CORS de backend. Configurar solo cuando se autorice implementar.
La capacidad está documentada en [server.proxy de Vite](https://vite.dev/config/server-options).

Desarrollo manual futuro podrá usar backend de desarrollo solo mediante acciones
expresamente autorizadas. Pruebas automatizadas usarán backend de pruebas en otro
puerto (propuesta 8001) y usuarios_test en 5435. El frontend de prueba debe rechazar
un destino distinto y no tener fallback al servidor de desarrollo. No consultar
directamente PostgreSQL desde React.

En despliegue, preferir proxy inverso de mismo origen y HTTPS, con fallback SPA
solo para rutas de interfaz, nunca para `/api`. Vite dev proxy no se aplica al
build estático. No modificar Docker para resolverlo en este diseño.

Alternativa pendiente: si frontend y API deben tener orígenes diferentes, aprobar
CORS explícito con origen exacto (incluidos host/puerto), métodos GET/POST/PUT/
PATCH/DELETE/OPTIONS y cabeceras Authorization/Content-Type; exponer Retry-After
y Location si se consumen. Bearer en memoria no requiere cookies ni credentials
include. No wildcard como solución general ni confundir CORS con autorización.

Un proxy puede agrupar IPs para el limitador actual: backend usa request.client.host
y no confía en X-Forwarded-For de la aplicación. Planificar límites y proxies de
confianza al desplegar, sin habilitar confianza arbitraria en cabeceras.
Límites actuales: 30 reservas por IP/minuto y 5 por email+IP/ventana de 15 minutos;
un login exitoso libera su reserva del segundo cupo. La UI respeta Retry-After,
no promete desbloqueo por un temporizador local si el servidor sigue rechazando.

## 8. Extensión futura para IA

Reservar la convención de una futura `features/chat` con páginas/componentes,
API propia y estado local de conversación, enchufable al AppShell y router.
No crear carpetas vacías, endpoints, proveedores ni dependencias de IA ahora.
Reutilizar cliente autenticado, tratamiento 401 y cancelación. Si luego se adopta
streaming, definir transporte y contrato por separado: no asumir que EventSource
permite enviar el Bearer actual ni que hay una ruta de chat implementada.

Identidad y permisos efectivos se validarán en backend en cada consulta y
herramienta. El frontend no filtrará datos para convertirlos en «autorizados» ni
guardará claves de proveedores. Al cambiar usuario o cerrar sesión, limpiar
conversación y cancelar solicitudes; no persistir historial sensible por defecto.
LLM, RAG, embeddings y agentes están fuera de este sprint.

## 9. Estrategia de pruebas

Vitest ejecutará funciones y componentes con jsdom; Testing Library y user-event
verificarán comportamiento por etiquetas/roles, no estructura interna. MSW
interceptará HTTP y fallará ante solicitudes no simuladas. Playwright comprobará
recorridos reales. Referencias: [Vitest](https://main.vitest.dev/guide/),
[Testing Library](https://testing-library.com/docs/), [MSW](https://mswjs.io/docs/),
[Playwright](https://playwright.dev/docs/best-practices).

| Área | Casos mínimos |
| --- | --- |
| Política | 14/15/128/129 puntos de código, emojis, combinaciones, espacios, bytes y Unicode inválido; sin truncamiento ni restricciones extra |
| Formularios | Confirmación, visibilidad, doble envío, errores 422 sin campo preciso, PASSWORD_INVALIDA genérico, limpieza tras éxito |
| Login | Éxito seguido de me, rechazo común, inactivo simulado sin revelar causa, red/500, 429 y Retry-After |
| Estado auth | Expiración con reloj simulado, foco tras suspensión, 401 terminal, 401 de contraseña actual sin logout, respuestas tardías |
| Navegación | Guards anónimo/ADMIN/USUARIO, URL directa, returnTo seguro, recarga obliga login, menú basado en me |
| Usuarios | Alta de perfil sin contraseña, PUT sin rol, filtro/offset sin total, conflictos 409, baja propia bloqueada visualmente |
| Sesiones | Logout confirmado y fallo remoto diferenciados, cambio de contraseña elimina estado, baja y reactivación no restauran token |
| Seguridad de salida | Tokens/contraseñas fuera de almacenamiento, URLs y logs; errores no reproducen payloads sensibles |
| Accesibilidad | Labels, teclado, foco de diálogo, errores anunciados y mobile; comprobaciones automáticas más revisión manual |

E2E solo contra instancia dedicada con `create_test_database_app` y usuarios_test.
El setup comprueba configuración y destino real con los guardas existentes antes
de aprovisionar datos ficticios por fixtures. Nunca usa administrador real ni
variables/secretos de desarrollo. Serializar pruebas que compartan limpieza de
tablas; evitar interferencia entre workers. No guardar tokens mediante storageState
ni capturas, vídeos o trazas auth que expongan credenciales; usar datos ficticios
y política de artefactos segura. Validar también 401/403 reales, no solo esconder
botones en la interfaz. La suite backend de 319 pruebas debe seguir aprobando.

## 10. Plan incremental propuesto

Todos los archivos y dependencias de esta sección son futuros. Cada incremento
termina en typecheck, pruebas pertinentes y aceptación antes de continuar.

| Incremento | Objetivo y funcionalidades | Archivos previstos | Dependencias | Pruebas y aceptación |
| --- | --- | --- | --- | --- |
| 8.1 Base y primer login funcional | SPA mínima, tema, cliente, login + me, token en memoria, dashboard mínimo, proxy | package/lock, vite/tsconfig, main, app, api, AuthProvider, LoginPage/Form, routes, DashboardPage mínimo | React/DOM, TS, Vite/plugin React, Router, MUI/Emotion, RHF; Vitest/jsdom, RTL/user-event, MSW, tipos y lint compatibles | Login contra API simulada y luego usuarios_test; sin persistencia; 401/429/500 comprensibles; build y typecheck correctos |
| 8.2 Ciclo completo de sesión | Shell, guards, menús, perfil, logout, expiración, pérdida tras recarga | shared/layout, router guards, authState, authApi, MiPerfilPage, DashboardPage | Reutilizar 8.1 | Rutas por rol, me obligatorio, logout y errores de red, reloj simulado, recarga y respuestas tardías; ninguna fuga entre usuarios |
| 8.3 Administración de consulta | Listado, detalle, filtro real de estado y paginación offset | usuariosApi, useUsuarios, UsuariosPage, UsuarioDetailPage, UsuariosTable, EstadoFilter | Sin nuevas librerías | ADMIN accede; USUARIO bloqueado; sin total ficticio; cancelación y páginas vacías; contrato GET comprobado |
| 8.4 Administración de mutaciones | Crear perfil, editar, baja y reactivar con confirmación | UsuarioForm/CreatePage/EditPage, ConfirmDialog, profileFields | Sin nuevas librerías | 201/200/204; payloads exactos; 409 activo/inactivo/email; no auto-reactivación; no contraseña en alta; baja propia impedida |
| 8.5 Contraseña explicada | Componente reutilizable, cambio con actual y confirmación, revocación y nuevo login | PasswordField, NewPasswordFields, passwordPolicy, ChangePasswordPage/Form | Sin nuevas librerías | Equivalencia Unicode y espacios; 422; actual incorrecta no cierra sesión; éxito 204 limpia y exige login; política ausente en login |
| 8.6 Cierre e integración | Responsive, accesibilidad, E2E aislados y documentación | e2e, configuración Playwright, pruebas adicionales y guía Sprint 8 | Playwright y navegadores locales; herramienta de accesibilidad solo si se justifica | Recorridos ADMIN/USUARIO, expiración/revocación, errores, no escrituras en desarrollo; regresión backend, build/typecheck/lint y pruebas frontend aprobadas |

8.1 prioriza una pantalla usable con arquitectura mínima, sin esperar a terminar
administración ni toda la biblioteca visual. No adelantar una infraestructura
genérica de caché o IA. Cada dependencia se instala solo al autorizar implementación
y confirmar compatibilidad local.

## 11. Riesgos y decisiones para aprobación

| Decisión propuesta | Riesgo o condición |
| --- | --- |
| JWT solo en memoria y nuevo login tras recarga | Menor comodidad; sesión remota puede seguir vigente al cerrar pestaña. Si se exige persistencia, necesita otro diseño aprobado |
| Proxy de mismo origen | Sin cambios CORS ahora; despliegue necesita routing SPA/API y política de IP confiable |
| MUI Core, Fetch y RHF, sin gestor de estado adicional | Menor superficie inicial; revisar caché solo con complejidad real |
| Alta de perfiles sin credenciales | La gestión de accesos iniciales no estará disponible desde React; no prometerla |
| Paginación sin total, búsqueda ni orden nuevo | UI debe explicar navegación simple; cualquier ampliación requiere backend futuro |
| Errores de contraseña genéricos | No se puede identificar la regla de contraseñas comunes ni siempre el campo; presentar resumen honesto |
| Token y permisos pueden quedar obsoletos en pantalla | Me al recuperar foco y servidor como autoridad; nunca asumir permiso por esconder botones |
| Backend sin control de concurrencia optimista de edición | Dos ediciones pueden sobrescribirse; mostrar datos frescos, no prometer detección de conflictos por versión |
| Documentación histórica de estado desactualizada | Este documento registra el cierre posterior confirmado; actualización global no incluida en el diseño |

La propuesta permite implementar Sprint 8 sin cambiar los contratos actuales si
se aceptan la sesión no persistente, el proxy y el alcance de perfiles sin
aprovisionamiento web. Persistencia entre recargas, reset de contraseña, refresh,
invitaciones, cambio de rol y chatbot requieren decisiones posteriores separadas.

Punto de control: entregar este diseño y esperar autorización antes de crear
React, instalar dependencias o tocar configuración de integración. No avanzar
al Sprint 9.
