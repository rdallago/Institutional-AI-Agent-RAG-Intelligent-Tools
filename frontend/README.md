# Frontend React y TypeScript

Incrementos 8.1–8.5A.6 implementados; correcciones de calidad en preparación 8.6B.
React, TypeScript estricto, Vite, React Router, MUI/Emotion, React Hook Form y Fetch.
No se ha publicado el sistema ni habilitado el aprovisionamiento.

## Inicio local de desarrollo (8.6C)

Con `usuarios_dev` en `127.0.0.1:5434` y esquema **0003** verificados, iniciar
desde backend (sin ejecutar migraciones):

```powershell
.\.venv\Scripts\python.exe -B -m uvicorn app.bootstrap:create_app --factory --host 127.0.0.1 --port 8000 --no-proxy-headers --no-access-log
```

Desde frontend, con las dependencias existentes:

```powershell
npm.cmd run dev -- --config vite.development.config.ts
```

Abrir **http://127.0.0.1:5173**. Esta configuración explícita dirige `/api` a
**8000**. No usarla para los tests ni iniciar ambos entornos simultáneamente
en 5173. La configuración aislada siguiente conserva su destino **8001**.
Introducir credenciales personalmente en la interfaz, nunca en comandos o chat.
El arranque habitual conserva el aprovisionamiento bloqueado. La instancia local
autorizada puede usar el [lanzador explícito 8.6D](../backend/README.md#habilitación-local-explícita-86d);
React no dispone de un interruptor ni decide su habilitación.

## Inicio aislado

Node 24.14.1 compatible con rama 24, npm 11. Desde frontend:

```powershell
npm.cmd ci
npm.cmd run dev
```

Abrir **http://127.0.0.1:5173**. `npm.cmd` evita cambiar políticas PowerShell.
Puerto estricto: no detener procesos ajenos. El proxy `/api` apunta solo a
**127.0.0.1:8001**, conservando el path. La configuración pública solo admite
`VITE_API_BASE_URL=/api/v1`; no lee `.env` raíz ni contiene secretos backend.

Preparar y verificar primero [el backend](../backend/README.md), con
**usuarios_test en 5435 y esquema 0003**. Desde backend, en otra terminal:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.bootstrap:create_test_database_app --factory --host 127.0.0.1 --port 8001 --no-proxy-headers
```

Solo cuentas ficticias existentes y autorizadas. Las suites limpian sus fixtures,
no dejan un administrador permanente. La barrera bloquea aprovisionamiento por
HTTP/CLI. Para recorrer el flujo completo usar los arneses aislados, sin cambiar
la barrera ni recurrir a desarrollo.

## Funcionalidades y límites reales

- Login seguido de me, dashboard, Mi perfil, expiración y logout.
- ADMIN: listado/detalle, filtro `activos|inactivos|todos`, límite 1–100 y offset,
  edición, baja lógica y reactivación explícitas. Sin total ni búsqueda por texto.
- USUARIO: consulta propia y cambio de contraseña, sin edición administrativa.
- Alta preparada con inicial manual obligatoria y asignación a históricos activos
  sin credencial; **ambas bloqueadas operativamente**, sin éxito ficticio.
- Estado restringido: solo cambio obligatorio y salir, sin menú ni perfil completo;
  también ADMIN pendiente está bloqueado por React y FastAPI.
- Cambio obligatorio y voluntario funcionales: actual/nueva, confirmación local,
  política visible, 15–128 puntos Unicode, hasta 512 bytes, sin normalizar/recortar
  ni exigir categorías. Lista común delegada al servidor. No aplicar mínimo de
  contraseña nueva o mostrar su política en login.
- Tras 204 de cambio se limpian token/datos/campos y se exige nuevo login.
  Actual incorrecta conserva sesión válida; revocación/vencimiento la termina.
- Baja revoca sesiones; reactivar no las restaura. Sin cambio de rol, reset,
  recuperación, refresh ni vencimiento propio de la inicial.

JWT solo en memoria, nunca en almacenamiento persistente/cookies/URLs/logs.
Recargar exige login. Generaciones y cancelación descartan respuestas de otra
sesión. Los guards no sustituyen al backend; 403 de permisos no equivale a logout.

Mensajes saneados y Retry-After para 429; no hay reintentos automáticos de login o
mutaciones. Un cambio ambiguo limpia secretos/sesión y exige login. Asignación
ambigua no se repite ni ofrece reset; GET no informa existencia de credencial.

## Comprobaciones

```powershell
npm.cmd run typecheck
npm.cmd run lint
npm.cmd test
npm.cmd run build
npm.cmd audit --json
npm.cmd audit --omit=dev --json
```

Vitest/jsdom/MSW rechazan tráfico no simulado. Los arneses pytest usan navegadores
instalados y PostgreSQL real de pruebas. No instalar herramientas sin autorización.
El tema compartido incorpora foco de teclado para botones, iconos, enlaces MUI,
inputs y selects. Las verificaciones no son una certificación WCAG.
Resultados en [8.6B](../docs/sprint-8-6b-preparacion.md), antecedentes en
[8.6A](../docs/sprint-8-6a-auditoria.md).

## Publicación futura

El build necesita proxy del mismo origen para `/api` y fallback SPA exclusivo de
interfaz; Vite dev/preview no son un despliegue productivo. No mezclar versiones
antiguas React/FastAPI con el esquema nuevo. Respaldo, mantenimiento, caché e
integridad siguen el plan 8.6A/8.6B, **no ejecutado por esta preparación**.
Ninguna variable de frontend abre la barrera.
