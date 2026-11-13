# Sprint 9.2.4: interfaz React para consultas IA

Fecha: **2 de noviembre de 2026**. Estado: **implementado y verificado en aislamiento**.
Alcance: interfaz y verificación aislada con
MSW. **Sin inferencia real ni activación operativa de IA**. No se inicia 9.2.5.

## 1. Arquitectura y archivos

Se revisaron rutas, AppShell, AuthProvider, JWT en memoria, transporte HTTP,
componentes MUI, proxy Vite, pruebas existentes y el contrato aprobado de 9.2.3.
La nueva funcionalidad conserva esos mecanismos y no añade dependencias.

Nuevos:

- `frontend/src/features/ia/model/promptPolicy.ts`: métricas y validación textual.
- `frontend/src/features/ia/api/iaApi.ts`: operación autenticada y validación de salida.
- `frontend/src/features/ia/pages/ConsultaIAPage.tsx`: formulario y respuesta actual.
- `frontend/src/features/ia/ia.test.tsx`: pruebas unitarias e integración React/MSW.
- `docs/sprint-9-2-4-interfaz-react-ia.md`: este informe.

Modificados:

- `frontend/src/router/routes.tsx`: ruta lazy `/ia` dentro de ProtectedRoute.
- `frontend/src/shared/layout/AppShell.tsx`: enlace Consultar IA y título de página.
- `frontend/src/api/httpClient.ts`: `body.prompt` en la allowlist de campos de
  validación saneados; sin cambios en autenticación o tratamiento de sesiones.

## 2. Pantalla y transporte

ADMIN y USUARIO normales comparten la pantalla. ProtectedRoute conserva el bloqueo
de sesiones anónimas o pendientes; no se amplía AdminRoute ni se cambian permisos.
El formulario usa React Hook Form y Material UI: texto multilínea, contador,
Enviar consulta, indicador de carga, Cancelar consulta y Limpiar. Espaciado y
botones adaptan su disposición a pantallas pequeñas; textos largos pueden partirse.
No se declara una auditoría visual en dispositivos ni certificación de accesibilidad.

La API reutiliza `useAuth().mutate('/ia/consultas', 'POST', {prompt}, signal, 200)`.
El transporte existente añade Bearer y el prefijo `/api/v1`. No se crea otro cliente,
se lee el JWT desde la pantalla ni se envía identidad/modelo/URL/opciones adicionales.
No se cambian los proxies: configuración aislada 8001 y desarrollo explícito 8000.

Se valida la respuesta como objeto de exactamente dos campos: respuesta y
finalizacion (`completa|limite`). Texto válido, no vacío, sin NUL, hasta 4096 puntos
y 16384 bytes. Un contrato inesperado se rechaza sin mostrar su contenido.
La respuesta se renderiza como texto escapado, preservando saltos de línea; no hay
HTML interpretado, Markdown, enlaces automáticos, herramientas ni ejecución.

El prompt se limpia al admitir el envío en la interfaz; la respuesta previa se
retira al enviar otra consulta. Limpiar elimina texto y resultado, pero no acorta
un Retry-After vigente. No hay historial, persistencia, analítica o logs de contenido.

## 3. Validación y sesión

Prompt obligatorio, distinto de espacios, máximo 1000 puntos Unicode y 3000 bytes
UTF-8, sin NUL ni surrogates aislados. Se cuentan puntos, no unidades UTF-16.
El reconocimiento de espacios coincide con Python str.strip, incluidos NEL y
separadores de control; BOM por sí solo no se considera espacio en esa regla.
El texto válido se transmite exactamente: sin trim, normalización ni truncamiento.
Los mensajes y contadores explican el exceso. Backend sigue siendo la autoridad;
el límite HTTP de 16 KiB no se expone como un control del formulario.

401 utiliza la expiración existente. 403 CAMBIO_PASSWORD_REQUERIDO conserva la
revalidación y redirección del AuthProvider; otro 403 se muestra como falta de acceso.
Un 503 y los demás fallos de IA no invalidan una sesión normal.

## 4. Errores, cancelación y carreras

| Estado | Tratamiento visible |
| --- | --- |
| 413 / 422 | Solicitud demasiado grande o consulta rechazada; revisar contenido |
| 429 IA_OCUPADA | Servicio ocupado; sin reenvío automático |
| 429 IA_LIMITE_INTENTOS | Cuota agotada; sin reenvío automático |
| 502 | Respuesta inválida del servicio |
| 503 | Servicio no disponible; sesión conservada |
| 504 | Tiempo agotado; advertencia de que el cálculo puede continuar |
| Red / contrato | Comunicación fallida o respuesta inesperada saneada |

Solo se muestran mensajes fijos de interfaz, nunca mensajes arbitrarios del
proveedor, cuerpos completos o tracebacks. Retry-After usa el entero validado por
el transporte existente, muestra cuenta regresiva y bloquea envíos hasta su plazo.
Si falta o es inválido, no se inventa tiempo. Limpiar no reinicia ese plazo.

Un lock inmediato en ref evita doble envío antes del siguiente render; el botón
también se deshabilita durante la solicitud. Cada operación tiene AbortController,
identidad de secuencia y comprobación de montaje. Cancelar o desmontar aborta;
una respuesta tardía no restaura contenido. AuthProvider conserva además su control
de generación de sesión y aborto por logout/expiración. Al abandonar `/ia` se
descartan formulario y resultado, también al volver a entrar.

Un deadline local fijo de **70 segundos** aborta la espera. No se confunde con el
deadline backend de 60 s, no es una opción del usuario y no reenvía solicitudes.
Abortar transporte no garantiza detener el cálculo de Ollama; la interfaz informa
esa limitación. No se promete cancelación dura del proveedor ni borrado seguro de RAM.

## 5. Verificaciones

Las pruebas usan MSW con rechazo de solicitudes no manejadas y datos exclusivamente
ficticios. Atraviesan rutas, AppShell, AuthProvider y transporte reales del frontend;
no llaman al backend operativo, Ollama o PostgreSQL.

Cubren límites Unicode/bytes, tipos de respuesta, acceso normal de ambos roles,
enlace de navegación, anonimato, restricción por 403, payload/Bearer, carga, texto
HTML escapado, completa/límite, errores HTTP y de red, Retry-After real/ausente,
doble envío, cancelación, desmontaje pendiente, deadline y respuestas tardías.
Se comprueba limpieza tras navegación/logout y ausencia de escrituras en Storage.
El deadline se dispara con un temporizador controlado, sin esperar 70 s reales.

Comandos desde frontend:

```powershell
npm.cmd run typecheck
npm.cmd run lint
npm.cmd exec vitest run src/features/ia/ia.test.tsx
npm.cmd test
npm.cmd run build
```

| Verificación | Resultado |
| --- | --- |
| Typecheck independiente | Aprobado |
| Lint corregido | Aprobado, sin errores |
| Dirigida intermedia final | **37 aprobadas**, 18,62 s totales; antes del caso 403 de permiso y de comprobar el enlace de navegación |
| Regresión frontend final | **189 aprobadas en 9 archivos**, sin fallos, **83,20 s** totales |
| Casos conservados / nuevos en regresión | **151 / 38**; las repeticiones no se suman |
| Build y TypeScript final | Aprobados; **947 módulos**, chunk IA **6,06 kB / 2,72 kB gzip** |
| Backend, bases e inferencia real | No ejecutados en este incremento |

La primera dirigida obtuvo 33 aprobadas y un fallo por leer el estado del botón
antes del render. Se precisó la espera al indicador de cancelación manteniendo
las comprobaciones de bloqueo y una sola solicitud. Una segunda dirigida mantuvo
ese fallo porque la espera se había añadido a otra prueba; al ubicarla en la prueba
correcta aprobaron los 37 casos. El primer lint señaló
caracteres de control en una expresión regular; se sustituyó por comprobaciones
explícitas de códigos Unicode. Las ejecuciones intermedias no son el resultado final.

## 6. Límites y preparación del piloto

No se modificaron backend, configuración operativa, JWT, roles, barrera,
dependencias o esquemas. No hubo conexiones a bases, fixtures de desarrollo,
migraciones, descargas, inferencias ni reinicios de servicios. Build genera solo
artefactos locales ignorados; no publica el sistema ni habilita IA.

No se efectuó una prueba manual autenticada sobre desarrollo ni se certifica la
respuesta del modelo real. IA sigue deshabilitada por defecto; ver la página en
el frontend no acredita disponibilidad operativa del proveedor. Los resultados
backend de 9.2.3 son antecedentes y no se reejecutaron aquí.

Para 9.2.5 deberán revisarse recursos locales, socket/worker, habilitación explícita,
modelo disponible, tokenización, rendimiento y cancelación real, bajo autorización
separada. No se descarga ni activa nada como efecto secundario de esta interfaz.
Se entrega 9.2.4 para revisión y se detiene antes del piloto.
