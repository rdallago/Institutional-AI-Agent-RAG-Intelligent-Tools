# Incremento 8.5A.5: contraseñas iniciales y cambio obligatorio en React

Fecha: 30 de octubre de 2026. Estado: **implementado y verificado con HTTP simulado
mediante MSW**. No se ejecutó integración con backend real ni se accedió a bases.
El aprovisionamiento operativo permanece deshabilitado. Se detiene el trabajo
en 8.5A.5, sin avanzar a 8.5A.6.

## Componentes y archivos

Creados:

- `frontend/src/router/PasswordRoute.tsx`.
- `frontend/src/features/auth/pages/ChangePasswordPage.tsx`.
- `frontend/src/shared/ui/NewPasswordFields.tsx`.
- `frontend/src/shared/validation/passwordPolicy.ts`.
- `frontend/src/features/usuarios/components/AsignarCredencialInicial.tsx`.
- `frontend/src/features/auth/model/passwordFlow.test.tsx`.
- `frontend/src/features/usuarios/initialCredentials.test.tsx`.
- `frontend/src/shared/validation/passwordPolicy.test.ts`.
- `docs/sprint-8-5a-5-implementacion.md` (este informe).

Actualizados:

- `frontend/src/api/contracts.ts` y `httpClient.ts`.
- `frontend/src/features/auth/api/authApi.ts`.
- `frontend/src/features/auth/model/AuthProvider.tsx`, `authContext.ts` y
  `authState.ts`.
- `frontend/src/router/routes.tsx`, `ProtectedRoute.tsx` y `AdminRoute.tsx`.
- `frontend/src/shared/ui/PasswordField.tsx`.
- `frontend/src/features/usuarios/api/usuariosApi.ts` y `mutationErrors.ts`.
- `frontend/src/features/usuarios/components/UsuarioForm.tsx`.
- `frontend/src/features/usuarios/pages/UsuarioDetailPage.tsx`.
- `frontend/src/test/mocks/handlers.ts` y las pruebas anteriores de LoginForm,
  session y mutations: adaptación a la bandera obligatoria y al alta con inicial.

Se mantienen React, TypeScript, MUI, React Hook Form, Vitest y MSW instalados.
No se agregaron dependencias ni se modificaron backend, contratos HTTP,
migraciones, Docker, configuración de integración, package.json o lockfile.

## Estado de autenticación y transporte

El proveedor distingue explícitamente anonymous, authenticated y
**passwordChangeRequired**, además de los estados transitorios existentes.
El estado restringido tiene user=null y solo contexto id/debe_cambiar_password;
no presupone nombre, email ni rol. No se infiere la obligación a partir de ADMIN.

Login exige el booleano debe_cambiar_password en TokenRespuesta y verifica después
el contrato discriminado de GET auth/me. No se interpreta una bandera ausente como
false. El me normal exige perfil activo válido y false; el pendiente exige solo
UUID válido y true. Una respuesta pendiente con campos adicionales no se acepta
como perfil normal.

Si login anuncia restricción pero me responde como normal, se rechaza la respuesta
contradictoria y se descarta el token. Si me indica una obligación que apareció
después del login, prevalece el contexto restringido. Nunca se muestra acceso
normal antes de comprobar me. Ambos endpoints exigen HTTP 200 y forma válida.

El JWT sigue únicamente en un ref privado del proveedor. No se persiste en
localStorage, sessionStorage, IndexedDB, cookies, URLs o estado del router, y no
se decodifica para extraer permisos. Recargar pierde la sesión local y exige login.

get/mutate continúan reservados a sesiones normales. changePassword utiliza un
camino separado, limitado al endpoint fijo auth/password, que admite ambos estados.
No se relaja el transporte general para permitir operaciones de perfiles desde
una sesión restringida. Logout y me conservan sus caminos específicos.

Los cambios de sesión mantienen generaciones y AbortController. Al pasar de normal
a pendiente se abortan solicitudes anteriores, se retiran datos y navegación
normales y se ignoran sus respuestas tardías. Una respuesta antigua de cambio no
puede cerrar ni restaurar otra sesión iniciada posteriormente.

## Guards, rutas y navegación

- El login restringido lleva a `/cambiar-password` con replace.
- ProtectedRoute y AdminRoute impiden rutas normales a una sesión pendiente,
  también mediante URL directa, navegación Atrás o rutas desconocidas.
- PasswordRoute admite el formulario para sesión normal y restringida. La normal
  conserva AppShell y menú; la restringida muestra solo el formulario y salir,
  sin dashboard, Mi perfil, rol o navegación administrativa.
- Los estados transitorios muestran carga; no crean ciclos login/password.
- La opción existente «Cambiar contraseña» del menú ahora abre el formulario real
  para cambios voluntarios. No hay una segunda implementación independiente.
- Un 403 CAMBIO_PASSWORD_REQUERIDO desde una operación normal retira el contenido
  privado y consulta me antes de mostrar el flujo restringido. Si ese contexto no
  puede verificarse, exige login. Un 403 PERMISO_DENEGADO no destruye una sesión válida.

El backend continúa siendo la autoridad real. Los guards no sustituyen sus
comprobaciones de sesión, credencial, rol y propiedad.

## Formulario único de cambio

ChangePasswordPage usa MUI y React Hook Form para contraseña actual, nueva y
confirmación. Solo actual y nueva viajan por PUT `/api/v1/auth/password`; la
confirmación es exclusivamente local. Se bloquean envíos simultáneos y no hay
reintentos automáticos.

Tras HTTP 204, el proveedor descarta token, identidad, contexto y peticiones
pendientes, y vuelve a login con «Contraseña cambiada. Ingresá nuevamente con tu
nueva contraseña.». No emite otro login, no retiene el secreto para autenticar y
no invoca logout con el token ya revocado. Los campos se vacían al enviar y el
formulario se desmonta tras limpiar la sesión.

| Resultado | Tratamiento |
| --- | --- |
| 401 CREDENCIALES_INVALIDAS | Error asociado a contraseña actual; conserva sesión normal o restringida válida |
| 401 de sesión inválida o código distinto | Limpia sesión y exige login |
| 422 PASSWORD_INVALIDA / validación | Mensaje comprensible de rechazo del servidor, sin inventar la regla incumplida |
| 422 PASSWORD_REUTILIZADA | Elegir una contraseña diferente de la actual e inicial |
| 429 LIMITE_INTENTOS | Retry-After, cuenta regresiva y bloqueo temporal; sin reenvío automático |
| Red, 500 o respuesta de éxito inesperada | Resultado ambiguo: limpia secretos y sesión, informa incertidumbre y exige login |

Un Retry-After ausente o inválido utiliza una espera local conservadora de 60 s,
igual que login; el servidor sigue siendo la autoridad. El cambio tiene timeout
de 15 s: abortarlo se trata como ambiguo, nunca como rollback confirmado.
Si la sesión termina durante el envío también se informa que puede haberse aplicado.

No se conservan contraseñas en el formulario tras un intento fallido. El usuario
debe volver a introducirlas para un reintento manual. Los mensajes de error se
seleccionan por códigos conocidos, sin reproducir cuerpos o mensajes arbitrarios
que pudieran incluir secretos.

## Política visual compartida

NewPasswordFields se reutiliza en cambio, alta y asignación. Muestra política antes
de escribir, cumplimiento textual y visual, y controles independientes para mostrar
u ocultar cada secreto. PasswordField conserva los slotProps y la asociación de
ayuda/errores, y sus controles de visibilidad tienen nombres accesibles por campo.

Las reglas locales conocidas son exactamente:

- 15–128 puntos de código Unicode, sin confundirlos con unidades UTF-16 o grafemas.
- Hasta 512 bytes UTF-8.
- Unicode válido; se detectan surrogates aislados antes de TextEncoder.
- Confirmación exacta, preservando espacios, mayúsculas y secuencias Unicode.
- Sin truncamiento, normalización ni combinación obligatoria de categorías.

No se usa maxlength HTML que recorte caracteres astrales válidos. No se bloquea
pegado ni gestores de contraseñas. Se informa que el servidor verifica contraseñas
comunes; no se copia su lista ni se asegura aceptación antes de su respuesta.
El login conserva su campo y validación previa, sin mostrar esta política de nueva.

## Alta administrativa

UsuarioForm agrega contraseña inicial y confirmación solo en creación. Mantiene
nombre, apellido, email, rol y validaciones anteriores. La edición continúa
enviando exclusivamente nombre, apellido y email, sin controles de contraseña.

Crear envía nombre, apellido, email, rol y password_inicial. No envía confirmación,
hashes, flags o estado. Sin inicial válida/coincidencia, el formulario no realiza
POST. Los secretos se vacían al enviar; los datos no secretos permanecen disponibles
ante errores. Tablas y detalles no muestran contraseñas.

Se reemplazó el aviso anterior de perfil sin acceso por la explicación de inicial
manual, acceso restringido y cambio obligatorio. También se informa que la emisión
operativa todavía no está habilitada.

403 APROVISIONAMIENTO_NO_HABILITADO presenta un mensaje explícito, conserva la
sesión válida y no muestra éxito ni navega a un perfil ficticiamente creado. No
hay fallback al alta sin contraseña ni parámetros para eludir la barrera.

## Asignación a perfiles existentes

El detalle administrativo ofrece «Asignar contraseña inicial» como acción explícita
para perfiles activos. El diálogo identifica el perfil y explica que solo sirve
si aún no tiene credencial, que el servidor comprobará esa condición y que no
reemplaza ni restablece contraseñas existentes. En inactivos la acción está
deshabilitada con explicación, sin reactivación implícita.

No se agrega un indicador de credencial ni se infiere su existencia de rol, email,
estado o bandera auth. El detalle no anuncia «sin credencial»: el POST decide la
precondición. Es la interacción prevista en el diseño y no requiere modificar GET.

POST `/api/v1/usuarios/{id}/credencial-inicial` envía solo password_inicial. La
confirmación es local. Un 204 simulado confirma la asignación sin mostrar secretos;
409 CREDENCIAL_EXISTENTE explica que esta operación no es reset. También maneja
inactivo, falta de permiso y barrera cerrada sin cerrar sesión válida.

Un resultado ambiguo vacía campos, bloquea reenvío y explica que el perfil no permite
consultar existencia de credencial; no promete resolverlo con un GET ni reintenta
automáticamente. Cancelar/desmontar el diálogo retira sus campos locales. No se
implementó recuperación de acceso.

## Pruebas y verificaciones

Todas las solicitudes de pruebas fueron interceptadas por MSW con rechazo de
tráfico no simulado. Se utilizaron únicamente datos y tokens ficticios. No se
inició Vite contra una API real ni se contactó usuarios_test o usuarios_dev.

Desde frontend:

```powershell
npm.cmd run typecheck
npm.cmd run lint
npm.cmd test
npm.cmd run build
```

| Verificación | Resultado |
| --- | --- |
| Typecheck | Aprobado |
| Lint | Aprobado sin errores ni advertencias |
| Suite frontend completa | **151 aprobadas en 8 archivos**, 132,54 s |
| Casos anteriores conservados/adaptados | **101 aprobados** |
| Casos nuevos | **50 aprobados** |
| Build de producción | Aprobado; 944 módulos, pantallas divididas por rutas |
| Backend, integración PostgreSQL o migraciones | No ejecutados en esta intervención |

Las pruebas nuevas cubren login restringido/me mínimo, rechazo de contratos
incompletos o contradictorios, URLs normales bloqueadas, ADMIN que pasa a pendiente,
transporte normal denegado, cambio obligatorio/voluntario, 204 y limpieza de token,
401 actual incorrecta en ambos estados, reutilización, confirmación, visibilidad,
429/Retry-After, expiración, timeout, red/500/contrato ambiguo, logout, recarga y
respuestas tardías entre sesiones. Se verificó ausencia de escrituras persistentes
de tokens/secretos.

La política tiene casos 14/15/128/129, emojis hasta 512 bytes, espacios, combinaciones
Unicode, surrogates inválidos, confirmación exacta y lista común delegada al servidor.
Los formularios administrativos prueban payloads exactos, secreto obligatorio,
barrera cerrada, asignación sin indicador inventado, conflictos y resultado ambiguo.
Las pruebas previas conservan listado, filtros, paginación, edición, baja,
reactivación, permisos y ciclo de sesión normal.

## Barrera, aislamiento y límites pendientes

**No se modificó la barrera del backend.** Su código fue inspeccionado por lectura:
require_initial_provisioning_enabled sigue lanzando AprovisionamientoNoHabilitado
de forma incondicional. No se añadió ningún flag de frontend, variable de entorno,
cabecera o configuración que la abra. Los 201/204 de aprovisionamiento de esta
intervención son exclusivamente respuestas simuladas de MSW, no emisión real.

**No se accedió a bases, usuarios, credenciales o sesiones reales.** No se
modificaron backend, migraciones, Docker o contratos HTTP. No se leyeron secretos
de desarrollo/pruebas ni se realizaron instalaciones. El proxy fijo y la separación
de configuración frontend/backend se mantienen sin cambios.

Quedan para una autorización posterior las pruebas integrales con backend aislado,
recorridos reales de navegador y revisión manual de accesibilidad/responsive.
La estructura MUI, breakpoints y controles accesibles existentes se conservan,
pero las pruebas de este incremento no equivalen a una auditoría WCAG completa.
No se afirma haber repetido las 556 pruebas backend del informe anterior.

Recargar sigue exigiendo login; no hay refresh ni sesión persistente. La asignación
no detecta previamente credenciales porque el contrato no las expone. El aviso de
aprovisionamiento cerrado es deliberado y deberá revisarse junto a una eventual
habilitación expresamente autorizada, nunca mediante una opción del usuario.

No se implementaron recuperación, reset administrativo, vencimiento de inicial,
nuevos endpoints ni historial de contraseñas. La emisión operativa permanece
**deshabilitada** hasta las verificaciones integrales y autorización explícita.

Se detiene el trabajo al completar **8.5A.5**. No se continúa con 8.5A.6.
