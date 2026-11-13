# Incremento 8.2: ciclo completo de sesión

Fecha: 30 de octubre de 2026. Estado: implementado y verificado. Alcance exclusivo
8.2; no se implementaron administración, edición de perfiles, cambio de contraseña
ni funcionalidades de IA. No se modificaron backend, PostgreSQL, migraciones,
Docker, credenciales ni archivos de secretos.

## Archivos creados

- `frontend/src/shared/layout/AppShell.tsx`: encabezado, identidad, rol, menú
  de escritorio/móvil, foco y título de página, avisos y cierre de sesión.
- `frontend/src/router/ProtectedRoute.tsx`: límite de acceso autenticado y estado
  de cierre sin información privada.
- `frontend/src/router/AdminRoute.tsx`: restricción visual basada en el rol de me.
- `frontend/src/router/ReservedPage.tsx`: aviso explícito sin operaciones futuras.
- `frontend/src/features/perfil/pages/MiPerfilPage.tsx`: consulta de datos propios.
- `frontend/src/features/auth/model/session.test.tsx`: 30 pruebas nuevas.
- Este informe.

## Archivos modificados

- `frontend/src/features/auth/model/AuthProvider.tsx`: ciclo de sesión, cancelación,
  generación de sesión, refresco del perfil, reloj, expiración y logout.
- `frontend/src/features/auth/model/authState.ts`: estado closing sin identidad.
- `frontend/src/features/auth/model/authContext.ts`: logout, refreshProfile y avisos.
- `frontend/src/features/auth/api/authApi.ts`: POST logout con respuesta 204 exigida.
- `frontend/src/api/httpClient.ts`: validación opcional de estado HTTP esperado.
- `frontend/src/features/auth/pages/LoginPage.tsx`: avisos de cierre/expiración.
- `frontend/src/features/dashboard/pages/DashboardPage.tsx`: integración con layout
  compartido, sin duplicar main ni el indicador de rol del encabezado.
- `frontend/src/router/routes.tsx`: rutas anidadas, guards y carga diferida.
- `frontend/src/test/mocks/handlers.ts`: simulación segura de logout 204.
- `frontend/vite.config.ts`: chunk separado de React sin cambiar proxy ni umbral.
- `frontend/README.md`: instrucciones de uso y comprobación manual actualizadas.
- `docs/sprint-8-1-implementacion.md`: restauración de tildes y eñes dañadas al
  escribir el informe anterior; guardado y comprobado como UTF-8.

No se instalaron nuevas dependencias ni se alteró el lockfile para este incremento.
Las 20 pruebas anteriores se conservaron sin modificar sus archivos.

## Navegación y permisos

| Ruta | Disponibilidad en 8.2 |
| --- | --- |
| `/login` | Anónimo; autenticado redirige a dashboard |
| `/dashboard` | Autenticado; bienvenida e identidad real |
| `/mi-perfil` | Autenticado; nombre, apellido, email, rol, estado y fecha local de creación |
| `/usuarios` | ADMIN; aviso de sección reservada, sin listado ni operaciones |
| `/usuarios/nuevo` | ADMIN; reservada, sin alta |
| `/usuarios/:id` | ADMIN; reservada, sin consulta de terceros |
| `/usuarios/:id/editar` | ADMIN; reservada, sin edición |
| `/cambiar-password` | Autenticado; reservada, sin formulario |
| Ruta desconocida con sesión | Página no encontrada |

Anónimos vuelven al login al visitar una ruta privada. USUARIO no ve navegación
administrativa y recibe una pantalla de acceso restringido al escribir sus URLs.
ADMIN ve su acceso administrativo, marcado al entrar como no operativo todavía.
El backend sigue siendo la única autoridad de autorización; ocultar enlaces no
confiere permisos. El token no contiene ni determina el rol de interfaz.

La pantalla de perfil consume la misma identidad de AuthContext procedente de
GET me; no mantiene otra copia. Actualizar perfil y recuperar foco vuelven a
consultar ese endpoint. Si el rol cambia, menú y guard se actualizan juntos,
incluso si el usuario está visitando una sección reservada administrativa.

## Logout, expiración y carreras

Logout captura el token antes de limpiar, bloquea nuevos intentos/operaciones,
invalida la generación y cancela solicitudes pendientes. Elimina inmediatamente
la identidad y muestra un estado de cierre; POST logout usa el token capturado.
Solo una respuesta 204 anuncia revocación confirmada. Un 401 informa que el
servidor ya no acepta ese token. Ante error de red, 500, respuesta inesperada o
timeout de 5 segundos, se vuelve igualmente a login y se advierte que la sesión
remota puede seguir vigente hasta expirar. No se persiste el token para reintentar.

El temporizador conservador se calcula desde el inicio de POST login, más los
900 segundos publicados por el backend. Incluye el tiempo de red y no se renueva
por actividad, refresco de perfil o navegación. Si me llega después del vencimiento,
no se autentica. Se verifica el reloj al recuperar foco y visibilidad, sin depender
solo del timer de una pestaña suspendida.

Un 401 de GET me es terminal: borra sesión y cancela solicitudes. Un 403 muestra
falta de permiso sin cerrar sesión. Errores de red/servidor conservan los últimos
datos verificados con aviso de que no se actualizaron; cada operación real sigue
sujeta a autorización del servidor. No se generaliza este tratamiento de 401 al
formulario futuro de cambio de contraseña, que tendrá otro contexto y contrato.

El identificador de generación y AbortController impiden que respuestas de un
perfil anterior, logout o login desmontado restauren datos tras cerrar o abrir
otra sesión. Se bloquea doble logout y reautenticación durante el cierre. Al
desmontar se cancelan peticiones, timer y listeners. Si me falla tras login, se
intenta revocación del token provisional con timeout, sin exponer identidad.

No hay refresh, cookies ni almacenamiento persistente. Una recarga completa,
pestaña nueva o cierre pierde el token y exige login. Cerrar la pestaña no garantiza
revocación remota; esa sesión puede continuar hasta expirar. No se intenta logout
automático mediante beforeunload.

## Verificaciones y evidencias

| Verificación | Resultado |
| --- | --- |
| Typecheck | Aprobado, también dentro de build |
| Lint | Aprobado, sin deshabilitar reglas |
| Vitest + MSW | **50 aprobadas**: 20 conservadas y 30 nuevas; ejecución final 19,85 s |
| Build de producción | Aprobado sin advertencia de chunks mayores a 500 kB |
| Chrome headless, build de producción | Perfil, menú móvil, logout 204, USUARIO sin menú administrativo y recarga aprobados |
| Almacenamiento en Chrome | localStorage/sessionStorage vacíos; cero excepciones JavaScript |
| PostgreSQL / integración real | No utilizada; HTTP simulado y datos ficticios exclusivamente |

Las pruebas nuevas cubren rutas anónimas, navegación ADMIN/USUARIO, todas las
rutas administrativas reservadas, perfil, democión de rol, logout 204/401/500/red,
respuesta inesperada, timeout, cierre en curso, respuestas tardías entre sesiones,
recarga, ausencia de escritura en almacenamiento/cookies, timer conservador,
foco/visibilidad vencidos y respuestas 401/403/red al refrescar.

Se ajustó la espera de la primera importación diferida del perfil a cinco segundos
en una prueba nueva: el límite original de un segundo podía agotarse durante la
transformación inicial del módulo. Se conservaron las comprobaciones funcionales.
La comprobación en Chrome del mismo build confirmó navegación efectiva al perfil.

MSW falla ante solicitudes no simuladas. Chrome interceptó las rutas auth antes
del servidor, con datos ficticios. No se usó el administrador real, no se ejecutó
login real ni se consultó o escribió usuarios_dev/usuarios_test. No se repitió la
suite backend: su código no cambió y se mantiene el antecedente de 319 aprobadas.

## Bundle

Dashboard, perfil y layout privado usan React.lazy/Suspense. Se separó React/DOM/
scheduler en un chunk estable, sin dependencias nuevas ni aumentar el umbral:

| Archivo | Tamaño / gzip |
| --- | --- |
| Principal | 308,93 kB / 99,28 kB |
| Runtime React | 218,71 kB / 68,26 kB |
| Layout privado | 18,23 kB / 5,91 kB |
| Dashboard | 5,41 kB / 1,90 kB |
| Mi perfil | 1,29 kB / 0,71 kB |
| Runtime del bundler | 0,59 kB / 0,36 kB |

La división no elimina el coste de React y UI en la primera carga; mejora la
separación y caché, y difiere las pantallas privadas. No se declara una reducción
del total de bytes por el mero hecho de separarlos. Se probó el resultado de
producción en Chrome para detectar errores de carga o dependencias entre chunks.

## Comprobación manual en Chrome

Con PostgreSQL de pruebas y credenciales ficticias ya disponibles, desde backend:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.bootstrap:create_test_database_app --factory --host 127.0.0.1 --port 8001 --no-proxy-headers
```

Desde frontend:

```powershell
npm.cmd run dev
```

Abrir `http://127.0.0.1:5173`. No cambiar el proxy al backend de desarrollo.

1. Visitar `/mi-perfil` sin sesión: comprobar redirección a login.
2. Ingresar con cuenta ficticia ADMIN: comprobar nombre, rol y menú.
3. Abrir Mi perfil: comprobar datos de me, estado y fecha. No hay edición.
4. Abrir Administración o Cambiar contraseña: solo aviso de sección reservada.
5. Cerrar sesión: confirmar aviso; volver a una URL privada o usar Atrás no
   debe recuperar datos.
6. Ingresar con cuenta ficticia USUARIO: no aparece administración. Escribir una
   URL administrativa dentro de la sesión muestra acceso restringido.
7. Recargar: debe solicitar login. No copiar JWT de Swagger ni guardarlo para evitarlo.
8. Dejar pasar 15 minutos, incluso con la pestaña en segundo plano: al vencer o
   recuperar foco se solicita login nuevamente.
9. Desconectar red en DevTools después de ingresar y cerrar sesión: comprobar
   limpieza local y aviso de revocación no confirmada. Restablecer conexión.

Las pruebas backend pueden limpiar cuentas ficticias: comprobar su existencia
por los mecanismos autorizados antes de probar manualmente. Esta intervención
no las crea ni aprovisiona.

## Limitaciones y punto de control

Quedan pendientes listado/filtros/paginación (8.3), mutaciones de perfiles (8.4),
cambio de contraseña (8.5) y cierre integral posterior (8.6). Sin refresh ni
persistencia entre recargas por decisión aprobada. Fuera de alcance IA y Sprint 9.
Los errores de red no pueden garantizar revocación remota ni perfil actualizado;
se informa expresamente. La autorización final continúa en backend.

Trabajo detenido al completar 8.2, pendiente de autorización para el siguiente
incremento.
