# Incremento 8.1: implementación y verificaciones

Fecha: 30 de octubre de 2026. Estado: **implementado y verificado con HTTP
simulado, incluida comprobación en Chrome**. Integración PostgreSQL real no
ejecutada; no se modificó ninguna base de datos.

## Estructura y archivos

```text
frontend/
  package.json, package-lock.json, tsconfig.json, vite.config.ts, eslint.config.js
  index.html, .gitignore, .npmrc, .env.example, README.md
  src/
    main.tsx
    app/                 App, providers, config, theme
    api/                 contracts, errors, httpClient y pruebas
    router/              routes
    features/auth/       API, contexto/reducer/proveedor, LoginForm/Page y pruebas
    features/dashboard/  DashboardPage
    shared/ui/           PasswordField
    test/                setup, renderWithProviders, mocks MSW
```

Se creó únicamente la base necesaria para 8.1. El inventario completo de archivos
fuente está en frontend; no se generaron módulos de administración o IA.

## Funcionalidades disponibles

Login responsive con email y contraseña obligatorios, mostrar/ocultar contraseña,
prevención de doble envío, estados de carga, errores accesibles 401/422/429/500,
red y contrato inesperado. Retry-After bloquea el reenvío durante el plazo indicado;
sin cabecera válida se aplica una espera local conservadora de 60 segundos.
El login no impone la política de contraseña nueva.

Flujo real implementado: POST login, token privado en memoria, GET me con Bearer,
validación del perfil activo y dashboard con nombre, apellido, email y rol del
perfil. No se interpreta el JWT para obtener permisos. No hay almacenamiento
persistente, logs de credenciales ni tokens en URLs. Recargar exige otro login.
La cancelación y generación de intentos impiden restaurar identidad con respuestas
tardías. El formulario también bloquea envíos simultáneos antes del siguiente render.

Proxy Vite /api fijo a 127.0.0.1:8001, sin reescritura de path ni fallback a
desarrollo. La configuración pública solo acepta /api/v1. MSW falla ante peticiones
no simuladas. No se lee el archivo de secretos raíz desde frontend.

## Entorno y dependencias instaladas

Node 24.14.1 y npm 11.11.0. Se usa npm.cmd porque PowerShell bloquea npm.ps1,
sin cambiar la política del sistema. Versiones resueltas en package-lock.json:

| Dependencia | Versión |
| --- | --- |
| React / React DOM | 19.3.1 |
| React Router DOM | 7.18.5 |
| Material UI Core | 7.3.11 |
| Emotion React / Styled | 11.14.0 / 11.14.1 |
| React Hook Form | 7.91.0 |
| Vite / plugin React | 8.3.5 / 6.1.2 |
| TypeScript | 5.9.3 |
| Vitest | 4.1.12 |
| Testing Library React / user-event / jest-dom | 16.3.3 / 14.6.8 / 6.9.1 |
| MSW / jsdom | 2.15.0 / 27.4.0 |
| ESLint / @eslint/js | 10.13.0 / 10.0.1 |
| typescript-eslint | 8.72.1 |
| eslint-plugin-react-hooks / react-refresh | 7.1.1 / 0.4.26 |
| globals | 16.5.0 |
| @types/node / react / react-dom | 24.19.2 / 19.3.0 / 19.3.0 |

Node satisface los requisitos de Vite 8 y plugin React 6. Los plugins de lint
aceptan ESLint 10. npm ls final no mostró dependencias faltantes, inválidas ni
extraneous. No se instalaron herramientas globales.

## Verificaciones ejecutadas

| Comprobación | Resultado |
| --- | --- |
| npm run typecheck | Aprobado; también ejecutado en build |
| npm run lint | Aprobado sin errores ni advertencias |
| npm test | 20 pruebas aprobadas en 2 archivos; ejecución final 22,96 s |
| npm run build | Aprobado; 919 módulos; JS 526,45 kB / gzip 166,20 kB |
| npm ls --depth=0 | Correcto |
| npm audit --json | Cero vulnerabilidades en todas las severidades |
| Chrome headless | Login, dashboard, responsive y recarga aprobados con HTTP simulado |
| Integración real con usuarios_test | No ejecutada; no se modificó PostgreSQL |

Las 20 pruebas cubren renderizado, campos, visibilidad, JSON/Bearer, login seguido
de me, perfil pendiente, doble envío, 401/422/429/500, red, respuestas inesperadas,
no persistencia, nuevo montaje sin sesión, respuestas tardías, cancelación, 204 y
rechazo de destinos externos. MSW rechaza tráfico no previsto.

La comprobación independiente en Chrome interceptó ambas rutas HTTP con datos
ficticios y confirmó orden login -> me, identidad y rol, almacenamiento web vacío,
recarga que exige login, viewport móvil de 390 px sin desborde y cero excepciones
JavaScript. Se inspeccionaron visualmente capturas de escritorio y móvil.
El helper y capturas temporales quedaron en node_modules/.cache, excluidos del
control de versiones. No se usó el administrador real ni se contactó al backend.

No se repitió la suite backend porque no se modificó backend y las pruebas
PostgreSQL escriben/limpian la base de pruebas. Se conserva el resultado previo
de 319 aprobadas como antecedente, sin presentarlo como una nueva ejecución.

## Problemas resueltos y limitaciones

La primera conexión a npm devolvió HTTP 403 y la consulta HTTPS directa detectó
SELF_SIGNED_CERT_IN_CHAIN. La caché offline era insuficiente. El usuario liberó
la conexión y el siguiente intento completó la instalación.

Se detectó strict-ssl=false en la configuración npm heredada. No fue establecido
por esta intervención ni se modificó globalmente: frontend/.npmrc fija
strict-ssl=true y el registro oficial, antes de la instalación efectiva. No se
usaron certificados inventados, registros alternativos ni desactivación TLS.

ESLint 9 inicialmente resuelto estaba fuera de soporte: se actualizó a ESLint 10
con plugins compatibles. Los avisos del linter sobre refs durante render se
corrigieron moviendo la composición del cliente al evento y usando un callback
para el envío, sin deshabilitar reglas.

El build advierte un chunk mayor a 500 kB (526,45 kB sin gzip). No impide el build;
optimizar división por rutas antes de ampliar significativamente las pantallas.
No se alteró el umbral para ocultar la advertencia.

Logout, temporizador de expiración y ciclo completo de sesión son alcance de 8.2.
Si login crea una sesión y luego falla me, se descarta el token local y la sesión
remota puede durar hasta expirar. No hay refresh ni recuperación tras recarga.
El dashboard es mínimo; no hay administración, cambio de contraseña, IA ni
operaciones de incrementos posteriores. El build estático necesita proxy de mismo
origen al desplegar; vite preview no sustituye esa configuración de producción.

## Comandos de uso en PowerShell

Desde backend, con el entorno de pruebas ya disponible y migrado:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.bootstrap:create_test_database_app --factory --host 127.0.0.1 --port 8001 --no-proxy-headers
```

Desde frontend, en otra terminal:

```powershell
npm.cmd ci
npm.cmd run dev
```

Abrir Chrome en **http://127.0.0.1:5173**. El servidor usa puerto estricto. La
fábrica FastAPI carga únicamente configuración de pruebas y exige usuarios_test
en 5435. Se necesitan credenciales ficticias existentes; no se crean automáticamente.
No cambiar al administrador de desarrollo para probar. Las pruebas backend pueden
limpiar los perfiles de pruebas previamente creados.

Los comandos adicionales de typecheck, lint, pruebas, build y auditoría están en
frontend/README.md. No se accedió a PostgreSQL, no se ejecutaron migraciones/login
reales y no se alteraron backend, Docker, secretos ni usuarios. Se detiene el
trabajo al completar 8.1; 8.2 a 8.6 y Sprint 9 requieren otra autorización.
