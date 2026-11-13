# Sprint 8.6A: auditoría final y preparación del cierre Full Stack

Fecha: **31 de octubre de 2026**. Auditoría realizada sobre esta copia local.
No se implementaron funcionalidades ni correcciones productivas. No se inició
8.6B. **Usuarios_dev no fue consultada ni modificada; la barrera sigue cerrada.**

## 1. Dictamen y alcance

No se encontraron defectos críticos ni una vía de elusión de autorización en el
alcance revisado. Hay hallazgos medios de accesibilidad, dependencias, documentación
y tolerancia a fallos. Existe además un riesgo alto de despliegue si se mezclan
versiones anteriores con las nuevas; no se afirma que esa mezcla esté ocurriendo.

**Recomendación: aprobación condicionada de 8.6B**, con alcance acordado para
resolver o aceptar expresamente los hallazgos de este informe. No equivale a
aprobar el cierre final, desplegar ni habilitar aprovisionamiento. El foco visible,
la documentación operativa y la decisión sobre dependencias deben quedar resueltos
antes de considerar completo el cierre de calidad. No hay un defecto crítico que
exija suspender esta auditoría o hacer cambios estructurales inmediatos.

Se revisaron el diseño aprobado `sprint-8-5a-diseno.md`, los informes 8.5A.1–6,
código real, migraciones y pruebas. Las descripciones de cada incremento son
históricas: por ejemplo, las limitaciones de 8.5A.2 fueron superadas por 8.5A.3.
Esta auditoría no convierte una descripción histórica de desarrollo en una
comprobación actual de su base: su revisión real deberá verificarse con otra
autorización antes del despliegue.

## 2. Arquitectura y controles revisados

| Área | Resultado y evidencia de código |
| --- | --- |
| Clean Architecture | Domain/Application no importan FastAPI ni SQLAlchemy. Los seis casos de perfiles mantienen puertos; los adaptadores y la composición están fuera del dominio |
| Seguridad de aplicación | AuthService coordina políticas y UoW; no se confía únicamente en dependencias HTTP o guards React |
| Persistencia | Mapeos explícitos, sesiones independientes, savepoints y commit/rollback. Restricción única de email global, PK de credencial e inserción inicial sin upsert |
| Transacciones | Alta+credencial y cambio+revocación son atómicos. Revalidación de actor/credencial después de Argon2; pruebas de concurrencia y rollback conservadas |
| Migraciones | Cadena 0001 → 0002 → 0003. Backfill false/null/false, CHECK de inicial y eliminación de defaults temporales. Sin create_all ni cambios a migraciones anteriores |
| Frontend | TypeScript estricto, cliente HTTP acotado, DTO comprobados en ejecución, estado restringido separado y JWT privado en memoria |
| Pruebas | Memoria, PostgreSQL, HTTP, MSW y navegador real se distinguen; fixtures aisladas y sin credenciales reales |

El advisory lock global de seguridad es conservador y favorece la corrección;
serializa operaciones de seguridad y exige revisar capacidad antes de ampliar
carga. La clase AuthService concentra varias operaciones relacionadas: no se
propone una refactorización estructural durante esta auditoría.

## 3. Auditoría de autenticación y autorización

- JWT: algoritmo HS256 fijado, kid conocido, typ=at+jwt, issuer/audience,
  sub/jti UUID y claims requeridos. Fechas enteras y duración máxima 900 segundos.
  La tolerancia criptográfica de 30 s no extiende la sesión persistida: `_active`
  rechaza una sesión cuya expiración ya llegó.
- Cada operación protegida verifica vínculo usuario/sesión, revocación, vigencia,
  perfil activo y credencial existente. Los endpoints normales también requieren
  credencial sin obligación y sesión no restringida, antes de evaluar ADMIN/USUARIO.
- ADMIN pendiente no puede listar, consultar ni administrar perfiles; USUARIO
  normal solo consulta el suyo. La consulta ajena devuelve 404 y baja propia de
  ADMIN está prohibida. No se encontró escalamiento por campos extra del cuerpo.
- Cambio obligatorio y voluntario verifican contraseña actual, política y no
  reutilización mediante Argon2. Guardan hash y revocación total en una UoW, sin
  promover tokens viejos. La sesión restringida con credencial definitiva se rechaza.
- Argon2id productivo: 65536 KiB, tiempo 3, paralelismo 1, salt 16 bytes, hash
  32 bytes. El hasher reducido de fixtures no permite inferir rendimiento real.
  Se contrastó el uso de hashing dedicado con la [guía OWASP](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html).
- Login y cambio comparten límites por IP y email+IP; reservas atómicas, liberación
  de la propia reserva, ventanas UTC y Retry-After. La IP se obtiene del Request,
  sin confiar en X-Forwarded-For enviado arbitrariamente. No se alteró esta política.
- SecretStr, repr ocultos, errores saneados, parámetros SQL ocultos y ausencia de
  logs de cuerpos/token reducen exposición. Los errores no serializan input/ctx.
  No se encontró almacenamiento persistente de JWT o dangerouslySetInnerHTML en
  código productivo revisado. Se conservaron las pruebas de no exposición.
- Las claves de JWT y limitador deben ser independientes y de al menos 32 bytes;
  AuthConfig valida ambas condiciones y no incorpora claves predeterminadas.
  No se leyeron secretos de desarrollo para comprobarlo.

La contraseña inicial sigue sin vencimiento propio, es conocida por ADMIN y se
entrega fuera del sistema. El hash inicial aumenta almacenamiento y exposición en
backups, sin historial general. Son decisiones ya aprobadas, no garantías nuevas
de recuperación o verificación de identidad. No se cambió ninguna política.

## 4. Hallazgos clasificados

| ID / severidad | Hallazgo, evidencia y efecto | Acción propuesta, no ejecutada |
| --- | --- | --- |
| A01 · Medio | “Ingresar” alcanza `:focus-visible` con Tab, pero presenta outline 0, sombra none y mismo fondo/borde antes y después de blur en Chrome/Edge/Firefox. La captura tampoco muestra un foco distinguible | Acordar corrección del estilo de foco y revisar botones equivalentes; repetir teclado. Relacionado con [WCAG 2.4.7](https://www.w3.org/WAI/WCAG22/Understanding/focus-visible.html), sin declarar certificación |
| A02 · Medio | npm audit informa 12 entradas moderadas propagadas por un aviso de minimatch; versión instalada 10.2.6, transitiva de ESLint/typescript-eslint | Evaluar actualización compatible con aprobación y lockfile revisado. No ejecutar audit fix --force ni aceptar el downgrade sugerido automáticamente |
| A03 · Medio | README raíz indica desarrollo 0001/pruebas 0002 y aprovisionamiento local disponible; frontend/README afirma que cambio de contraseña no está implementado | Actualizar guías e índice de estado en una intervención autorizada. Seguir hoy informes 8.5A y esta auditoría; no iniciar backend actual contra 0002 |
| A04 · Medio | AuthService.login confirma la sesión y luego llama limiter.success. Se reprodujo en memoria que un fallo de liberación lanza error dejando una sesión vigente que no se entrega al cliente | Diseñar tratamiento del fallo sin debilitar límites. No hay bypass ni token entregado, pero sí resultado ambiguo, consumo de recursos y posible dificultad de reintento. No se corrigió |
| A05 · Alto, riesgo condicional de despliegue | Un backend antiguo no aplica las marcas nuevas; una mezcla de procesos/versiones puede interpretar incorrectamente credenciales/sesiones nuevas. La eliminación de defaults también impide escrituras de binarios antiguos | Mantenimiento, detener todos los workers antiguos, publicación coordinada y verificación de versiones. Prohibir despliegue mixto o rolling sin un diseño de compatibilidad aprobado |
| A06 · Medio, riesgo residual aceptado | La lista interna de contraseñas comunes contiene cuatro entradas; no es una comprobación extensa de contraseñas comprometidas. La inicial no tiene TTL y el antecedente se conserva | Documentar límite; cualquier ampliación de política, TTL o recuperación requiere decisión separada, no forma parte de este sprint |
| A07 · Bajo | Aviso Starlette/TestClient por httpx y ausencia de pip-audit instalado | Planificar revisión de compatibilidad y auditoría de vulnerabilidades Python autorizada. pip check solo valida coherencia de requisitos |
| A08 · Bajo | Lock global, sesiones históricas sin un proceso de purga observado y ausencia de control optimista en edición | Medir capacidad/retención y concurrencia antes de escalar. No prometer detección de ediciones simultáneas ni borrar sesiones fuera de política |

**Críticos: ninguno encontrado.** A05 es una condición que bloquea un despliegue
inseguro, no un incidente observado. A01–A04 son hallazgos reproducidos o directamente
verificados. A06/A08 explicitan límites; no justifican cambiar seguridad sin permiso.

No se verificaron permisos efectivos del usuario de desarrollo, ACL de secretos,
cifrado/retención de backups, historial Git ni infraestructura HTTPS/CSP. Esta copia
no contiene `.git`: `.gitignore` excluye `.env` y `.env.*`, pero eso no demuestra que
nunca hayan sido versionados en otro lugar. No se encontró ni se afirma una fuga
real; estas comprobaciones operativas siguen pendientes.

### Dependencias

La primera consulta npm falló por conectividad del entorno de ejecución. El
reintento al registro oficial con TLS activo y caché dentro del proyecto devolvió:

- Auditoría completa: **12 moderadas, 0 altas, 0 críticas**. Son entradas de un
  árbol afectado, no doce vulnerabilidades independientes.
- Auditoría `--omit=dev`: **0 avisos** en las dependencias de producción consultadas.
- `npm ls minimatch`: 10.2.6 bajo ESLint y typescript-eslint.
- Aviso [GHSA-g3hv-75wg-m249 / CVE-2026-118764](https://github.com/advisories/GHSA-g3hv-75wg-m249):
  amplificación de patrones, con consumo excesivo de CPU/memoria en determinados
  usos de optimización. El mantenedor publicó [11.0.1](https://github.com/isaacs/minimatch/releases/tag/v11.0.1).
  No se demostró una ruta explotable desde la API o el bundle; el riesgo observado
  está en herramientas/CI y entradas de patrones no confiables.
- Python: `pip check` aprobó; pip-audit no está instalado. No se instaló y **no se
  declara ausencia de CVE en Python**. Tampoco una auditoría npm limpia garantiza
  ausencia de todas las vulnerabilidades.

No se modificaron package.json, lockfile, dependencias ni configuración TLS/global.

## 5. Pruebas ejecutadas

| Verificación | Resultado de esta intervención |
| --- | --- |
| Regresión completa backend anterior | **558 aprobadas**, 116,45 s; incluye 153 PostgreSQL y 405 sin PostgreSQL |
| Auditoría adicional de navegadores | **3 aprobadas**, 64,72 s, una por navegador; todas con PostgreSQL real |
| Total de casos únicos verificados entre ambas ejecuciones | **561**; no se presenta como una única ejecución de 561 |
| Frontend Vitest/MSW | **151 aprobadas**, 8 archivos, 101,36 s |
| Typecheck / lint / build | Aprobados; build 944 módulos, sin modificación productiva |
| Alembic check final | **No new upgrade operations detected.**; usuarios_test en **0003** |
| pip check | No broken requirements found |
| Barrera en proceso independiente | Rechazo esperado AprovisionamientoNoHabilitado |
| Inyección adicional en memoria | Reprodujo A04; diagnóstico manual, no se cuenta como caso pytest nuevo |

Comandos ejecutados desde backend:

```powershell
.\.venv\Scripts\python.exe -m pytest -q --run-postgres -p no:cacheprovider --basetemp=.pytest_cache/86a-full-temp --tb=short
.\.venv\Scripts\python.exe -m pytest -q tests/integration/postgresql/test_browser_quality_audit.py --run-postgres -p no:cacheprovider --basetemp=.pytest_cache/86a-browser-final-temp --tb=short
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m pip show pip-audit
```

Desde frontend:

```powershell
npm.cmd run typecheck
npm.cmd run lint
npm.cmd test
npm.cmd run build
npm.cmd audit --json --cache node_modules/.cache/npm-audit-86a
npm.cmd audit --omit=dev --json --cache node_modules/.cache/npm-audit-86a
npm.cmd ls minimatch
```

El exit code 1 de audit completo refleja los avisos, no un fallo de build o tests.
Alembic check se ejecutó programáticamente con `database_config` de pruebas,
después de require_test_database y consultas del destino/revisión. La regresión
de migraciones usa exclusivamente pruebas, incluidas sus reversiones históricas.

Los intentos iniciales del arnés de calidad tuvieron errores de disponibilidad y
timeout de protocolos. Se ampliaron esperas locales y se corrigió la medición del
foco al activar diálogos. No se atribuyeron a fallos del producto. La ejecución
final de los tres navegadores aprobó; no se ocultaron fallos productivos con skips.

## 6. Revisión visual, teclado y navegadores

| Navegador instalado | Protocolo existente utilizado | Resultado |
| --- | --- | --- |
| Chrome 156.0.8078.48 | CDP + WebSocket nativo de Node | Recorrido completo de auditoría aprobado |
| Edge 156.0.4314.50 | CDP + WebSocket nativo de Node | Recorrido completo de auditoría aprobado |
| Firefox 159.0 | WebDriver BiDi + WebSocket nativo de Node | Recorrido completo de auditoría aprobado |

No se instalaron drivers, paquetes ni navegadores. Perfiles nuevos temporales,
servidores de aplicación solo en loopback 18002/15174 y sin cambios globales.
La barrera no se sustituyó en estos tres casos: las credenciales pendientes son
fixtures ficticias insertadas directamente en el entorno aislado.

Cada navegador generó 22 capturas: login, validación de login, dashboard, listado,
detalle, asignación, edición, alta, error de barrera, cambio voluntario y obligatorio,
en **1280×900 y 390×844**. Son viewports emulados, no dispositivos físicos.
Se inspeccionaron visualmente las nueve pantallas solicitadas en Chrome y muestras
de Edge/Firefox; las comprobaciones DOM y recorridos sí abarcaron los tres.

- Sin desbordamiento horizontal en las 66 observaciones de viewport.
- Inputs interactivos con etiqueta y botones con nombre en la muestra. Los inputs
  internos aria-hidden de los selects MUI se excluyeron del conteo; se revisaron
  sus comboboxes etiquetados, evitando reportar falsos positivos.
- Tab real desde email: contraseña → mostrar/ocultar → Ingresar en los tres.
  El botón final tiene el defecto A01. El formulario muestra errores comprensibles
  y asociados a campos al enviarse vacío.
- Ocho pulsaciones Tab conservaron el foco dentro del diálogo; Cancelar lo devolvió
  al botón de asignación. Esto es una muestra, no una prueba exhaustiva de teclado.
- Tras logout y navegación Atrás no reaparecieron navegación ni datos de perfiles.
  Un ADMIN pendiente que intentó `/usuarios` permaneció en cambio obligatorio, sin
  menú normal. Al terminar, localStorage y sessionStorage tenían cero entradas.
- Contraste calculado sobre colores sólidos del tema: texto principal/blanco
  **14,17:1**, secundario/blanco **6,05:1**, texto de botón/fondo primario **7,62:1**,
  secundario/fondo general **5,47:1**. No cubre cada estado, borde, transparencia,
  gráfico o modo de alto contraste.
- Estados de carga, 401/403/422/429/500, timeout y respuestas tardías cuentan además
  con regresión frontend MSW. El rechazo de aprovisionamiento se observó con HTTP
  real; no se inyectaron fallos de red para todas las pantallas del navegador.

No se realizó una certificación WCAG, auditoría con lector de pantalla, pruebas
en dispositivos físicos, Safari, zoom extremo o todas las combinaciones de teclado.
Los formularios se rellenaron mediante automatización; no se afirma que el
recorrido entero se haya realizado exclusivamente por teclado.

## 7. Aislamiento y barrera

Preflight y comprobación final: **usuarios_test / usuarios_test_admin /
127.0.0.1:5435 / revisión 0003**. Se cargó exclusivamente configuración de pruebas,
se validó require_test_database y se consultaron current_database/current_user.
Las fixtures validan destino antes de migrar/limpiar; las nuevas de auditoría
comprueban además revisión antes de invocar esas fixtures.

**No se accedió a usuarios_dev, 5434 ni sus secretos.** No se arrancó un servicio
contra esquema 0002, no se modificaron contenedores y no se cambió ninguna
migración. La comprobación final encontró tablas de aplicación de pruebas vacías
tras limpiar fixtures y ningún listener temporal de la auditoría.

require_initial_provisioning_enabled conserva su rechazo incondicional. Las
pruebas positivas anteriores de la regresión usan únicamente su fixture aislada
ya existente; no habilitan la función productiva. Los tres casos nuevos no abren
la barrera ni siquiera por monkeypatch. La comprobación independiente final la
confirmó cerrada. No se añadió flag, variable, cabecera ni alternativa de activación.

## 8. Preparación del despliegue: propuesta NO ejecutada

**Todos los comandos de esta sección son futuros. No autorizan ni describen
operaciones realizadas sobre desarrollo en esta auditoría.** Requieren nueva
autorización operativa, ventana de mantenimiento y responsable identificado.

### 8.1 Requisitos y puntos de control previos

1. Aprobar resolución/aceptación de A01–A04 y revisión de dependencias Python.
   Publicar un inventario exacto de artefactos y sus checksums, lockfile y paquetes.
2. Confirmar por configuración segura y lectura destino real **usuarios_dev /
   127.0.0.1:5434**, cuenta esperada y revisión **0002**. Si ya es 0003, no repetir
   este procedimiento sin revisar su estado; cualquier otro valor obliga a parar.
3. Confirmar que 0003 depende únicamente de 0002, sin otras revisiones pendientes,
   y revisar su DDL. No usar head para avanzar accidentalmente a una revisión futura.
4. Definir mantenimiento en proxy/origen; impedir peticiones y escrituras. Detener
   todos los workers FastAPI antiguos y procesos de tareas que puedan escribir.
   No compartir tráfico entre versiones ni arrancar el binario nuevo sobre 0002.
5. Definir respaldo verificable y ruta protegida fuera del repositorio. Verificar
   herramientas PostgreSQL compatibles con el servidor; no asumir que pg_dump.exe
   está instalado. Aprobar por separado una restauración de ensayo aislada.
6. Asegurar claves actuales disponibles mediante el almacén autorizado, sin
   imprimirlas. Respaldo de configuración/roles por separado cuando corresponda:
   pg_dump de una base no incluye los roles globales ni el archivo de secretos.
7. Definir proxy de mismo origen para `/api`, HTTPS si sale de loopback, política
   de cabeceras/CSP, permisos DB mínimos y tratamiento de IPs del limitador. El
   proxy de Vite no forma parte del build estático ni reemplaza ese trabajo.

### 8.2 Resguardo propuesto

Ejemplo desde una terminal local segura, solo tras aprobar lo anterior:

```powershell
$operadorDb = Read-Host 'Usuario autorizado de PostgreSQL'
$archivoRespaldo = Read-Host 'Ruta absoluta protegida del respaldo fuera del repositorio'
pg_dump.exe --host=127.0.0.1 --port=5434 --username=$operadorDb --dbname=usuarios_dev --format=custom --file=$archivoRespaldo --password
if ($LASTEXITCODE -ne 0) { throw 'Respaldo fallido; detener despliegue' }
pg_restore.exe --list $archivoRespaldo | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Archivo no verificable; detener despliegue' }
Get-FileHash -Algorithm SHA256 -LiteralPath $archivoRespaldo
```

La contraseña se introduce en el prompt de PostgreSQL, nunca en argumentos,
PGPASSWORD, chat o un archivo versionado. Proteger el archivo y sus copias mediante
permisos, cifrado y retención acordados: contiene hashes y datos personales.
Listar el archivo prueba su legibilidad, **no una restauración completa**. La
restauración de ensayo requiere otra base aislada autorizada, nunca usuarios_dev
ni una limpieza sobre otros proyectos. [Referencia oficial de pg_dump](https://www.postgresql.org/docs/current/app-pgdump.html).

### 8.3 Línea base y migración propuestas

Antes de migrar, mantener un snapshot solo en memoria de un control local autorizado:

- Filas ordenadas de usuarios: UUID, nombres, email, rol, activo, fecha.
- Credenciales: usuario_id, password_hash, creada_at y actualizada_at.
- Sesiones: id, usuario_id, fechas de creación/expiración/revocación.
- Intentos: campos actuales y conteos; inventario de tablas, relaciones e índices.
- Definiciones de objetos ajenos a las dos tablas que cambia 0003.

No imprimir ni exportar hashes individuales en informes. Comparar valores completos
en memoria antes/después y reportar únicamente igualdad/conteos; proteger el backup
si se necesita una evidencia persistente. Mantenimiento evita cambios concurrentes
que invalidarían la comparación. El respaldo es necesario aunque la migración sea
transaccional.

Consultas de control propuestas en el cliente local autorizado:

```sql
SELECT current_database(), current_user;
SELECT version_num FROM public.alembic_version;
SELECT count(*) FROM public.usuarios;
SELECT count(*) FROM public.usuario_credenciales;
SELECT count(*) FROM public.auth_sesiones;
SELECT table_schema, table_name FROM information_schema.tables
WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
ORDER BY table_schema, table_name;
```

El host/puerto deben comprobarse también en la configuración de conexión; el
puerto publicado 5434 no es el puerto interno que PostgreSQL ve dentro de Docker.
No mostrar la URL con credenciales ni copiar `.env` a los artefactos de revisión.

Desde backend, **solo con la autorización futura y verificaciones satisfactorias**:

```powershell
.\.venv\Scripts\python.exe -m alembic -x allow-development=true current
.\.venv\Scripts\python.exe -m alembic -x allow-development=true upgrade 0003
if ($LASTEXITCODE -ne 0) { throw 'Migracion fallida; mantener mantenimiento' }
.\.venv\Scripts\python.exe -m alembic -x allow-development=true current
.\.venv\Scripts\python.exe -m alembic -x allow-development=true check
```

Se conserva el mecanismo explícito existente; no debilitar migrations/env.py.
El permiso de Alembic no habilita aprovisionamiento. **No ejecutar downgrade.**

### 8.4 Integridad posterior propuesta

Exigir revisión 0003 y Alembic check sin diferencias. Comparar snapshots de perfiles,
hashes, fechas, sesiones e intentos; ninguno de los campos previos debe cambiar.
Inventario de tablas igual, objetos ajenos intactos y ninguna credencial nueva.
Comprobar columnas, CHECK, FK y ausencia de defaults finales:

```sql
SELECT count(*) FROM public.usuario_credenciales
WHERE debe_cambiar_password IS DISTINCT FROM false OR password_inicial_hash IS NOT NULL;
SELECT count(*) FROM public.auth_sesiones
WHERE restringida IS DISTINCT FROM false;
SELECT table_name, column_name, data_type, is_nullable, column_default
FROM information_schema.columns
WHERE table_schema='public' AND
 ((table_name='usuario_credenciales' AND column_name IN ('debe_cambiar_password','password_inicial_hash'))
 OR (table_name='auth_sesiones' AND column_name='restringida'))
ORDER BY table_name, column_name;
```

Los dos primeros conteos deben ser cero inmediatamente después del backfill,
antes de cualquier actividad nueva. No aceptar solo igualdad de cantidades como
prueba de conservación de UUID, emails o hashes: se requieren comparaciones de
valores. Cualquier diferencia inesperada mantiene bloqueada la reapertura.

### 8.5 Publicación coordinada propuesta

Preparar backend y frontend reproducibles en staging; no instalar paquetes sobre
el servicio activo. `npm.cmd ci`, typecheck/lint/tests/build corresponden al árbol
frontend sin secretos; evitar copiar el `.env` raíz o instalar herramientas globales.
El backend preparado debe tener sus dependencias bloqueadas y pruebas aprobadas.

Después de 0003, iniciar únicamente el backend compatible mediante el gestor de
servicios acordado. Ejemplo local, no ejecutado aquí:

```powershell
# Desde backend; requiere esquema 0003 ya verificado y configuración local válida.
.\.venv\Scripts\python.exe -m uvicorn app.bootstrap:create_app --factory --host 127.0.0.1 --port 8000 --no-proxy-headers
```

Publicar atómicamente frontend/dist y su configuración de proxy del mismo origen.
No usar Vite dev/preview como servidor de producción. Servir HTML con revalidación
obligatoria o no-store, purgar caché del HTML/CDN y conservar temporalmente assets
anteriores con hash para pestañas abiertas. Pedir cierre/recarga de pestañas viejas;
comprobar que reciben HTML/JS nuevos y contrastar contratos OpenAPI/login/me.
No existe un protocolo de versión del cliente que permita garantizar la expulsión
de toda pestaña antigua: la autorización del backend debe seguir denegando siempre
acceso normal restringido. No añadir ese protocolo sin diseño/aprobación.

Mantener mantenimiento hasta comprobar el conjunto completo, no solo que el
servidor está escuchando. Si se requieren orígenes distintos, detener y aprobar
CORS específico; este plan supone proxy de mismo origen. Cualquier confianza en
cabeceras de proxy debe diseñarse y probarse con el limitador antes de modificarla.

### 8.6 Verificación manual y eventual habilitación

Con otra autorización para pruebas manuales en desarrollo: usar personalmente una
cuenta existente, sin revelar su contraseña en chat ni comandos, comprobar login,
me, roles, consultas, logout y rechazo de su sesión revocada. No ejecutar pytest,
fixtures o limpieza automatizada contra desarrollo. No editar perfiles reales
para un smoke test sin permiso específico; validar mutaciones con fixtures aisladas.

El alta y la asignación deben seguir rechazadas por la barrera; esto es el resultado
esperado de esta publicación. No crear administradores, asignar contraseñas o
generar credenciales reales como efecto secundario del despliegue.

Evaluar habilitación en una decisión posterior: cierre de hallazgos, entrega segura
de iniciales, aceptación de falta de TTL/reset, pruebas actualizadas y un cambio de
código revisado expresamente. No existe ni se propone un flag para abrir la barrera.

### 8.7 Contingencia y condiciones de parada

Detener si falla respaldo/restauración de ensayo, destino, revisión, DDL esperado,
integridad, Alembic check, configuración segura, compatibilidad de artefactos o
comprobaciones de permisos. También si queda un worker antiguo, HTML obsoleto sin
tratamiento o una forma de abrir aprovisionamiento no aprobada.

Si la migración falla, mantener mantenimiento y comprobar el rollback transaccional
antes de decidir. No presuponer que todos los pasos externos se revirtieron.
Preferir corrección hacia adelante si 0003 está confirmada. Nunca ejecutar un
backend viejo sobre credenciales pendientes ni eliminar flags para recuperar acceso.

Si fuera imprescindible restaurar, exigir autorización específica y restauración
coordinada de base completa/configuración/artefactos desde respaldo verificado,
con servicios detenidos y pérdida de datos posterior al respaldo explícitamente
aceptada. No improvisar pg_restore --clean sobre desarrollo ni borrar volúmenes.
Un downgrade no deshace cambios de contraseña ni sustituye este plan.

## 9. Archivos y evidencias de esta auditoría

Creados únicamente para pruebas e informe:

- `backend/tests/integration/postgresql/test_browser_quality_audit.py`.
- `backend/tests/integration/postgresql/browser_quality_audit.mjs`.
- `docs/sprint-8-6a-auditoria.md`.

Los screenshots y report.json sanitizados quedaron bajo el directorio ignorado
`frontend/node_modules/.cache/`, con perfiles locales de navegador separados:

- `audit-86a-chrome-1793462380981`.
- `audit-86a-edge-1793462398469`.
- `audit-86a-firefox-1793462419115`.

Contienen únicamente vistas de fixtures ficticias; los campos de contraseña están
vacíos en las capturas. No se generaron vídeos ni trazas HTTP, no se guardaron JWT
en el informe y no se modificó código productivo, Docker, migraciones o secretos.

## 10. Limitaciones y punto de control

No es una prueba de penetración exhaustiva ni certificación de accesibilidad.
No se midió carga con Argon2id productivo, distribución de límites detrás de un
proxy real, dispositivos físicos, HTTPS/CSP desplegados o restauración de respaldo.
La auditoría Python de CVE y controles operativos de secretos/roles quedan pendientes.
No se afirma ausencia universal de vulnerabilidades ni éxito de despliegue real.

8.6A queda entregado para revisión. **No se ejecutó ninguno de los pasos propuestos
sobre usuarios_dev. La barrera continúa cerrada. No se inicia 8.6B ni se corrigen
hallazgos productivos sin la siguiente autorización.**
