# Incremento 8.3: administración de consulta

Fecha: 30 de octubre de 2026. Alcance exclusivo de consulta. Implementado el
listado y el detalle usando los endpoints existentes, sin cambios de contratos,
backend, PostgreSQL, Docker, migraciones o secretos. No se instalaron dependencias
ni se modificó package-lock.json.

## Archivos creados

- `frontend/src/features/usuarios/api/usuariosApi.ts`: acceso GET, validación de
  respuestas, UUID, parámetros y serialización de consulta.
- `frontend/src/features/usuarios/hooks/useConsulta.ts`: carga, error, reintento y
  cancelación; evita presentar resultados de una consulta anterior.
- `frontend/src/features/usuarios/components/UsuariosTable.tsx`: tabla de escritorio,
  tarjetas móviles y enlace de consulta de cada perfil.
- `frontend/src/features/usuarios/components/ConsultaError.tsx`: errores públicos
  locales sin reflejar mensajes o identificadores del servidor.
- `frontend/src/features/usuarios/pages/UsuariosPage.tsx`: listado, filtro y paginación.
- `frontend/src/features/usuarios/pages/UsuarioDetailPage.tsx`: detalle y retorno.
- `frontend/src/features/usuarios/usuarios.test.tsx`: 24 casos nuevos con MSW.
- Este informe.

## Archivos modificados

- `frontend/src/api/httpClient.ts`: query params mediante URLSearchParams y rutas
  seguras que permiten UUID, conservando el destino relativo permitido.
- `frontend/src/api/contracts.ts`: validación de perfiles activos o inactivos para
  consulta. La identidad autenticada sigue exigiendo un perfil activo.
- `frontend/src/features/auth/model/authContext.ts` y `AuthProvider.tsx`: acceso GET
  autenticado con cancelación, generación de sesión y tratamiento de 401.
  No se expone el JWT a componentes ni se agrega almacenamiento persistente.
- `frontend/src/router/routes.tsx`: listado y detalle reales con carga diferida,
  conservando ProtectedRoute y AdminRoute.
- `frontend/src/test/mocks/handlers.ts`: listado vacío predeterminado para pruebas.
- `frontend/src/features/auth/model/session.test.tsx`: adaptación de dos casos de
  navegación que antes esperaban secciones reservadas en listado/detalle. Se
  conservaron los 50 casos anteriores, sus comprobaciones de sesión, permisos y
  las secciones que continúan reservadas.
- `frontend/README.md`: alcance actual e instrucciones de consulta.

## Funcionalidades y contratos utilizados

| Operación | Contrato existente |
| --- | --- |
| Listado | GET `/api/v1/usuarios?estado=activos&limite=20&desplazamiento=0` |
| Estados permitidos | `activos`, `inactivos`, `todos` |
| Paginación | limite entre 1 y 100, desplazamiento entero no negativo |
| Detalle | GET `/api/v1/usuarios/{id}` con UUID válido |
| Autenticación | Authorization Bearer, token privado en memoria |
| Éxito | 200 array de UsuarioRespuesta o 200 UsuarioRespuesta individual |

Se muestran nombre, apellido, email, rol y estado. El detalle agrega UUID y fecha
de creación, presentada en la zona horaria del navegador. Se admiten perfiles
inactivos sin habilitarlos como identidad de sesión.

Se respeta el orden recibido: fecha de creación y UUID ascendentes. No se aplica
ordenamiento o filtrado parcial en el navegador. La pantalla ofrece filtro de
estado y tamaño de página; cambiar cualquiera reinicia offset. Los tamaños
habituales son 10, 20, 50 y 100, y se admite cualquier límite válido de la URL.
Parámetros inválidos se normalizan a valores predeterminados antes del envío;
valores fuera del rango seguro de enteros JavaScript también se descartan.

No hay total de registros. Se muestran las posiciones de los perfiles de la página,
Anterior y Siguiente. Siguiente se habilita cuando la respuesta llena el límite;
puede llevar a una página vacía. Desde ella se puede volver, sin inventar un total
ni efectuar consultas extra para simularlo. Anterior permanece disponible para
offsets mayores a cero, incluso si una página falla o queda vacía.

Filtro, límite y desplazamiento viven en la URL. El enlace de detalle lleva los
parámetros normalizados y Volver al listado los conserva. Los detalles abiertos
sin contexto vuelven a la consulta predeterminada. No se almacena información
privada ni JWT en esos parámetros.

Hay indicadores de carga, vacío explícito y reintento manual. No hay reintentos
automáticos. La vista de escritorio usa tabla semántica y la móvil tarjetas con
etiquetas y enlaces accesibles.

## Seguridad y cancelación

AdminRoute impide montar estas pantallas para USUARIO, por lo que no se envían
consultas desde ellas. El rol proviene exclusivamente de me; la autorización
efectiva sigue en FastAPI. Las rutas de alta y edición continúan reservadas y no
se agregaron acciones de escritura, reactivación, roles ni contraseñas.

El proveedor de sesión registra cada GET protegido. Logout, expiración o un 401
invalidan la generación, abortan solicitudes y eliminan identidad. Un 403 se
presenta como permiso denegado sin cerrar la sesión válida. Errores 404, 422, 500,
de red y respuestas inesperadas tienen mensajes locales sin reflejar email, UUID,
SQL, secretos ni el cuerpo arbitrario de error del servidor.

Al cambiar filtro, página, UUID o abandonar pantalla, se aborta su consulta. El
hook también verifica su vigencia antes de actualizar. Mientras carga una consulta
nueva, no presenta datos de la anterior. Las comprobaciones de generación en el
proveedor impiden que una respuesta de otra sesión repueble datos privados.

## Verificaciones

- Typecheck, lint y build de producción: aprobados.
- Pruebas frontend: **74 aprobadas**, 50 casos anteriores conservados y 24 nuevos;
  ejecución final en 32,31 segundos, cuatro archivos de pruebas.
- Build con carga diferida de listado (14,04 kB; gzip 4,60 kB) y detalle
  (1,59 kB; gzip 0,88 kB), sin advertencias de tamaño. Sin nuevas dependencias.
- Se mantienen MSW y el rechazo de solicitudes no simuladas.
- Chrome headless sobre el build, con HTTP interceptado: listado, detalle, retorno,
  tarjetas móviles sin desborde, perfil propio, logout, rol USUARIO sin menú ADMIN
  y recarga sin sesión verificados. Cero excepciones JavaScript y almacenamiento
  web vacío. Capturas revisadas visualmente.
- No se ejecutaron consultas reales ni logins reales contra FastAPI o PostgreSQL.
  No se usaron credenciales de desarrollo ni se modificaron usuarios_test/usuarios_dev.
- El proxy no cambió: solo backend de pruebas en 127.0.0.1:8001, sin fallback.
- No se repitieron pruebas backend: no hay cambios en su código ni contratos.

Los casos nuevos cubren listado y cabecera Bearer, parámetros exactos, filtro,
reinicio de offset, paginación sin total, páginas vacías, perfil inactivo, retorno
con contexto, HTTP 401/403/404/422/500, red, formato inesperado, reintentos, rechazo
visual de USUARIO, solicitudes abortadas, respuestas tardías de filtro/UUID y
aislamiento tras logout y nuevo login. También cubren parámetros inválidos y límites.

## Comprobación manual en Chrome

Con el entorno de pruebas y cuentas ficticias ya disponibles, desde backend:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.bootstrap:create_test_database_app --factory --host 127.0.0.1 --port 8001 --no-proxy-headers
```

Desde frontend:

```powershell
npm.cmd run dev
```

Abrir `http://127.0.0.1:5173`:

1. Ingresar como ADMIN ficticio y abrir Administración de usuarios.
2. Comprobar columnas y alternar Activos, Inactivos y Todos.
3. Cambiar tamaño: comprobar que vuelve al inicio; probar Anterior y Siguiente.
   También puede usarse `/usuarios?estado=todos&limite=1&desplazamiento=0` para
   recorrer páginas pequeñas sin modificar datos. No debe mostrarse un total.
4. Abrir Ver perfil; comprobar sus datos y Volver al listado, conservando consulta.
5. Reducir el ancho de Chrome: comprobar tarjetas, campos y navegación sin desborde.
6. Para comprobar el error de red, activar Offline en DevTools y cambiar filtro;
   restablecer conexión y pulsar Reintentar consulta.
7. Cerrar sesión e ingresar con USUARIO ficticio: no aparece administración;
   escribir `/usuarios` debe mostrar acceso restringido, sin petición de listado.
8. Recargar o volver a URL privada tras logout: debe exigir login.

Si no hay perfiles para un estado, se muestra vacío; esta intervención no crea
datos para llenar el listado. Las credenciales ficticias deben existir previamente.
No apuntar el proxy a desarrollo ni usar el administrador real para automatizaciones.

## Limitaciones pendientes y cierre

Sin total, búsqueda, filtro por rol ni orden configurable porque no existen en
el contrato. La paginación por offset puede desplazarse si otros operadores
cambian perfiles durante la navegación. Volver al listado vuelve a consultar, no
restaura una copia antigua. Los cambios de estado, edición, creación, eliminación,
reactivación, roles y contraseñas continúan fuera de alcance. El cierre de pestaña
no garantiza revocación remota y no hay persistencia ni refresh, según diseño.

Trabajo detenido al finalizar 8.3. El incremento 8.4 y los posteriores requieren
otra autorización.
