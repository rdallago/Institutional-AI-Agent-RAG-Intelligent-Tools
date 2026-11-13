# Incremento 8.4: administración de mutaciones de usuarios

Fecha: 30 de octubre de 2026. Alcance: crear, editar, dar de baja lógicamente y
reactivar perfiles con los contratos existentes. Sin implementación de 8.5, 8.6
o Sprint 9. No se modificaron backend, PostgreSQL, Docker, migraciones, secretos
ni credenciales. No se instalaron dependencias ni se cambió el lockfile.

## Archivos creados

- `frontend/src/shared/validation/profileFields.ts`: validación local de nombres
  y email alineada con las reglas reales de dominio.
- `frontend/src/shared/ui/ConfirmDialog.tsx`: confirmación accesible, cancelación,
  foco inicial seguro y bloqueo durante la operación.
- `frontend/src/features/usuarios/api/mutationErrors.ts`: mensajes locales y
  clasificación de resultados ambiguos.
- `frontend/src/features/usuarios/hooks/useMutation.ts`: envío único, estados de
  carga/error, cancelación al desmontar y protección de respuestas tardías.
- `frontend/src/features/usuarios/components/UsuarioForm.tsx`: formulario compartido
  de alta/edición con React Hook Form.
- `frontend/src/features/usuarios/components/MutationError.tsx`: errores de escritura
  y enlaces de revisión de conflictos o resultados inciertos.
- `frontend/src/features/usuarios/components/UsuarioActions.tsx`: edición, baja y
  reactivación en el detalle, con confirmación y bloqueo de baja propia.
- `frontend/src/features/usuarios/pages/UsuarioCreatePage.tsx`: alta y navegación
  al detalle creado.
- `frontend/src/features/usuarios/pages/UsuarioEditPage.tsx`: carga del perfil,
  edición y refresco de identidad al editar datos propios.
- `frontend/src/features/usuarios/mutations.test.tsx`: 27 pruebas nuevas con MSW.
- Este informe.

## Archivos modificados

- `frontend/src/api/httpClient.ts`: métodos PUT/DELETE/PATCH y lectura restringida
  de nombres de campos y UUID de conflicto; no se reproducen mensajes arbitrarios.
- `frontend/src/api/errors.ts`: metadatos seguros de validación/conflicto.
- `frontend/src/features/auth/model/authContext.ts` y `AuthProvider.tsx`: transporte
  autenticado de mutaciones usando la misma generación y cancelación de sesión.
  No se altera JWT, almacenamiento, login ni duración de sesión.
- `frontend/src/features/usuarios/api/usuariosApi.ts`: cuatro mutaciones, JSON
  explícito, estados HTTP esperados y comprobación de respuestas.
- `frontend/src/features/usuarios/pages/UsuariosPage.tsx`: enlace Crear perfil,
  conservando la consulta del listado.
- `frontend/src/features/usuarios/pages/UsuarioDetailPage.tsx`: acciones, mensajes
  de éxito, recarga del detalle y aislamiento al cambiar UUID.
- `frontend/src/router/routes.tsx`: alta/edición reales con carga diferida dentro
  de AdminRoute y ProtectedRoute.
- `frontend/src/features/auth/model/session.test.tsx`: actualización de un caso
  de navegación que antes esperaba pantallas reservadas de alta/edición. Se
  mantienen todos los casos anteriores y el cambio de contraseña sigue reservado.
- `frontend/vite.config.ts` y `frontend/src/test/setup.ts`: dos workers, presupuesto
  de 15 segundos por caso y espera asíncrona de cinco segundos para renderizado
  inicial/importaciones. Se conservan todas las aserciones y el bloqueo MSW de
  tráfico no simulado. El proxy y la configuración de entornos no cambiaron.
- `frontend/README.md`: alcance e instrucciones actualizados.

## Formularios y contratos

| Operación | Endpoint | JSON | Éxito esperado |
| --- | --- | --- | --- |
| Crear | POST `/api/v1/usuarios` | nombre, apellido, email, rol | 201 UsuarioRespuesta |
| Editar | PUT `/api/v1/usuarios/{id}` | exclusivamente nombre, apellido, email | 200 UsuarioRespuesta |
| Baja lógica | DELETE `/api/v1/usuarios/{id}` | Sin cuerpo | 204 sin contenido |
| Reactivar | PATCH `/api/v1/usuarios/{id}/reactivar` | Sin cuerpo | 200 UsuarioRespuesta activo |

Las consultas GET de listado/detalle y GET me siguen usando el contrato existente.
No se inventaron endpoints ni campos para contraseñas o aprovisionamiento.

El alta pide nombre, apellido, email y rol ADMIN/USUARIO; predetermina USUARIO.
Explica antes de enviar: «Crear un perfil no asigna una contraseña ni habilita el
inicio de sesión». Tras 201 navega al UUID devuelto y consulta su detalle.

La edición admite perfiles activos e inactivos. Presenta rol y estado informativos,
sin controles para modificarlos. El serializador de PUT selecciona explícitamente
los tres campos permitidos, aunque el formulario compartido conozca el rol.
No envía UUID, activo, fecha ni rol. Tras guardar consulta el detalle; si es el
perfil propio, actualiza me sin emitir otro JWT.

Nombre y apellido: entre 1 y 100 puntos de código después de quitar espacios
externos conforme a Python str.strip. No se usa maxlength UTF-16 que recorte
valores Unicode válidos. Email: ASCII sin controles, longitud total hasta 254,
parte local hasta 64, etiquetas válidas de dominio y al menos dos etiquetas.
Se admiten los símbolos y normalizaciones del dominio, sin requisitos adicionales.
Los valores se envían al backend, que normaliza y mantiene la autoridad definitiva.

## Confirmación y actualización

El detalle muestra Editar. Si está activo ofrece Dar de baja; si está inactivo,
Reactivar. La baja propia se deshabilita y se explica en texto visible. Comparación
de UUID sin distinguir mayúsculas. FastAPI conserva la decisión final.

Ambas operaciones de estado identifican al perfil por nombre y email en un diálogo
con confirmación explícita. La baja explica que es lógica, no borra físicamente
y revoca sesiones existentes. La reactivación explica que no restaura sesiones
anteriores ni asigna credenciales nuevas. Cancelar antes del envío no hace petición.

Durante la petición se bloquea doble confirmación y cierre del diálogo. Tras un
error se cierra la confirmación para que el mensaje quede accesible en el detalle.
Tras éxito se informa la operación confirmada y se vuelve a consultar el detalle.
Volver al listado lo carga nuevamente respetando filtro, tamaño y desplazamiento;
un perfil puede dejar de aparecer por el filtro de estado. Si la página queda
vacía, Anterior permite volver sin inventar un total.

## Conflictos, fallos y seguridad

- 409 USUARIO_ACTIVO_EXISTENTE: informa conflicto de alta y conserva campos.
- 409 USUARIO_INACTIVO_REACTIVABLE: conserva campos y ofrece Revisar perfil inactivo
  únicamente con un UUID válido proporcionado por el backend. Esa navegación no
  muta nada. La reactivación se realiza en su detalle con un PATCH separado y
  confirmación; no se envían los datos del formulario ni se adopta la cuenta.
- 409 EMAIL_EN_USO: error de email en edición, conservando los valores ingresados.
- 422: resumen y marcación de campos conocidos; no se refleja texto arbitrario
  ni nombres de campos desconocidos del servidor.
- 401 protegido: invalida sesión y cancela las solicitudes, incluidas escrituras.
- 403: error de permisos sin cerrar automáticamente la sesión válida.
- 404: perfil no disponible, sin inferir ni revelar datos adicionales.
- Red, 500 o respuesta inesperada: resultado ambiguo, sin reintento automático.
  Se conservan datos y se bloquea reenvío directo; se ofrece consultar el listado
  antes de volver a intentar por navegación explícita.

Los formularios están dentro de AdminRoute; USUARIO no puede montarlos. Un envío
único se bloquea sincrónicamente para cubrir eventos anteriores al siguiente render.
Las escrituras usan el token privado en memoria y el mismo conjunto de solicitudes
cancelables de la sesión. No hay persistencia de JWT ni contraseñas.

Desmontar, cambiar UUID, cerrar sesión o expirar invalida respuestas pendientes:
no pueden actualizar ni navegar en otra sesión. Cancelar HTTP no garantiza rollback
en el servidor; una escritura ya recibida puede completarse. No se afirma lo contrario.

## Verificaciones

- Typecheck: aprobado.
- Lint: aprobado sin deshabilitar reglas.
- Build: aprobado con carga diferida, sin advertencias de tamaño de chunks.
- Suite final: **101 pruebas aprobadas**, 74 casos anteriores conservados y 27
  nuevos, en cinco archivos y 94,52 segundos. Las 27 nuevas también aprobaron
  en ejecución aislada.
- Chrome headless sobre build de producción, HTTP interceptado: alta, edición,
  baja, reactivación y retorno a listado verificados, exactamente un POST, PUT,
  DELETE y PATCH. PUT con claves apellido/email/nombre exclusivamente. Vista móvil
  sin desborde, cero excepciones JavaScript y almacenamiento web vacío.
- Capturas de formularios de escritorio/móvil revisadas. El helper y capturas
  temporales están dentro de node_modules/.cache, excluidos de Git.

Pruebas nuevas: alta y rol predeterminado/ADMIN, campos y reglas locales, edición
inactiva, payload PUT exacto, conflicto EMAIL_EN_USO, conflictos de alta, revisión y
reactivación separada sin sobrescritura, baja con cancelación, reactivación, baja
propia bloqueada, HTTP 401/403/404/422, errores visibles tras diálogo, red/500/formato
ambiguos, doble POST y doble confirmación, actualización de detalle/listado/identidad,
respuestas tardías tras logout, aislamiento de sesión y acceso denegado a USUARIO.

Hubo timeouts por contención de jsdom en Windows durante los primeros casos con
varios formularios/importaciones; se limitó paralelismo y se ajustaron esperas,
sin eliminar casos ni aserciones. Dos pruebas nuevas se corrigieron para esperar
la transición de cierre del diálogo antes de comprobar que desapareció.

No se hicieron escrituras reales ni logins reales. Todo HTTP de pruebas usó MSW
o interceptación de Chrome, con datos ficticios. No se accedió a usuarios_dev ni
usuarios_test; no se repitió la suite backend porque no se modificó ese código.

## Comprobación manual de cada operación en Chrome

Usar exclusivamente el entorno de pruebas con cuentas ficticias ya disponibles.
Desde backend:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.bootstrap:create_test_database_app --factory --host 127.0.0.1 --port 8001 --no-proxy-headers
```

Desde frontend:

```powershell
npm.cmd run dev
```

Abrir `http://127.0.0.1:5173`. El proxy sigue apuntando únicamente a 8001 y la
fábrica usa usuarios_test en 5435. Esta implementación no crea datos de prueba
ni credenciales automáticamente.

1. Ingresar como ADMIN ficticio. En Administración de usuarios pulsar Crear perfil.
2. Introducir datos ficticios y un email nuevo de example.com, comprobar rol USUARIO
   predeterminado y aviso de que no se asigna acceso. Crear: ver éxito y detalle.
3. Pulsar Editar, cambiar nombre/apellido/email y guardar. Comprobar detalle nuevo;
   no hay controles para rol, estado, UUID o fecha. También probar un perfil inactivo.
4. Intentar crear con un email activo ya existente: ver conflicto y valores intactos.
5. En el detalle de un perfil ficticio distinto del propio pulsar Dar de baja.
   Cancelar primero: comprobar que sigue activo. Repetir y confirmar: ver inactivo.
6. Intentar crear con ese email ahora inactivo: ver conflicto. Revisar perfil inactivo
   sin que se reactive; pulsar Reactivar y confirmar separadamente. Comprobar que
   mantiene sus datos previos, sin recibir los del alta fallida.
7. Volver al listado con estado Todos o el filtro pertinente: comprobar estado actual.
8. Consultar el propio perfil administrativo: Dar de baja debe estar deshabilitado
   con explicación. No probar baja propia con SQL ni modificar protecciones.
9. Cambiar email de un perfil al de otro: ver EMAIL_EN_USO y conservar los datos.
10. Ingresar como USUARIO ficticio: no debe acceder a alta/edición/acciones ADMIN.

Para un resultado ambiguo no repetir escrituras sin comprobar primero el estado
mediante consulta. No usar datos ni administrador reales de desarrollo en pruebas
automatizadas, no cambiar el proxy y no ejecutar estos recorridos sobre usuarios_dev.

## Limitaciones y punto de control

No se cambian roles existentes ni se asignan contraseñas. Crear perfiles no habilita
login. Cambio de contraseña sigue reservado para 8.5; 8.6 y Sprint 9 no se avanzaron.
No hay bloqueo/versionado optimista en la API: dos ediciones concurrentes pueden
sobrescribirse según el orden del servidor. Sin total en listados ni restauración
de sesiones anteriores al reactivar. La cancelación no equivale a deshacer una
escritura; ante incertidumbre se requiere revisión manual del resultado.

Trabajo detenido al completar 8.4, pendiente de autorización para continuar.
