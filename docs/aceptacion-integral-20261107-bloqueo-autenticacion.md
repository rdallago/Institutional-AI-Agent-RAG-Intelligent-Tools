# Aceptación integral: preparación y bloqueo de autenticación

Fecha: 7 de noviembre de 2026. Resultado: BLOQUEADA; no equivale a un fallo funcional del agente.

## Verificaciones reales

- RAM física disponible: 1,796 GiB en la lectura de preparación. No acredita margen futuro ni picos.
- FastAPI: PID 19020, GET directo `/openapi.json`: 200.
- React/Vite: PID 4576, GET `http://127.0.0.1:5173/ia`: 200.
- Ollama: PID 18208, GET `/api/ps`: 200, cero modelos cargados.
- PostgreSQL local 5434: conexión READ ONLY a `usuarios_dev` confirmada, con rollback.
- Documento académico: versión activa `7cb4e79c-747d-574a-8abb-0ebcb2e07636`, LISTA,
  432 fragmentos y 432 embeddings. Se comprobaron conteos, no se repitió una auditoría completa de integridad.
- Modelo configurado: `qwen2.5:1.5b`.
- Directorio privado existente: permisos restringidos comprobados, seis archivos de diagnóstico.
  No se inspeccionó contenido de ejecuciones ajenas a esta batería.
- GET `/api/v1/ia/conversaciones` sin autenticación: 401 tanto directo a FastAPI
  como por el proxy de Vite. Esto comprueba rechazo anónimo y comunicación del proxy;
  no demuestra aislamiento entre dos sesiones válidas.

## Bloqueo concreto

No hay sesiones autenticadas disponibles para el cliente HTTP de esta ejecución.
No se proporcionó un navegador controlable mediante las herramientas disponibles.
`frontend/src/features/auth/model/AuthProvider.tsx` mantiene el token en un `useRef`;
`frontend/src/api/httpClient.ts` construye Authorization Bearer y usa `credentials: omit`.
La sesión abierta por el usuario en Chrome no se transfiere a este cliente.
No se extrajeron tokens, no se leyeron contraseñas y no se fabricaron sesiones o Principals.
No se intentó un login con credenciales supuestas.

## Matriz de aceptación

| Prueba | Usuario | Conversación | Canal esperado | Canal real | Herramienta ejecutada | Resultado | Motivo | Estado |
|---|---|---|---|---|---|---|---|---|
| A1/A2: artículos 24 y 52 | ADMIN | No creada | RAG | No evaluado | Ninguna | Sin ejecución | Autenticación no disponible | BLOQUEADA |
| B1/B2: memoria del Rectorado | ADMIN | No creada | RAG / memoria extractiva | No evaluado | Ninguna | Sin ejecución | Autenticación no disponible | BLOQUEADA |
| C1/C2: clima y mañana | ADMIN | No creada | CLIMA | No evaluado | Ninguna | Sin ejecución | Autenticación no disponible | BLOQUEADA |
| D1/D2: API REST y ejemplo | ADMIN | No creada | GENERAL | No evaluado | Ninguna | Sin ejecución | Autenticación no disponible | BLOQUEADA |
| E: alternancia de canales | ADMIN | No creada | RAG → CLIMA → GENERAL → RAG | No evaluado | Ninguna | Sin ejecución | Autenticación no disponible | BLOQUEADA |
| Académica, general y memoria | Común | No creada | Según consulta y ACL | No evaluado | Ninguna | Sin ejecución | Autenticación no disponible | BLOQUEADA |
| Logout/login y accesos cruzados | Ambos | No creada | HTTP autenticado | No evaluado | Ninguna | Sin ejecución | Faltan dos sesiones válidas | BLOQUEADA |
| Persistencia tras reinicio | Ambos | No creada | Recuperación HTTP | No evaluado | Ninguna | Sin ejecución | Sin conversaciones de esta batería | BLOQUEADA |

No se midieron tiempos de inferencia ni RAM posterior a inferencias porque no se ejecutaron.
Llamadas a Qwen y embeddings realizadas por esta batería: cero.
Contratos JSON, abstenciones, cobertura, calidad, memoria e independencia entre propietarios:
NO EVALUADOS. No hay divergencia HTTP/servicio que pueda analizarse para estas pruebas.
No se reiniciaron servicios, crearon conversaciones ni modificaron configuraciones o datos.

## Intervención necesaria

Se necesita autenticar ambas cuentas mediante un navegador controlable o un cliente de
aceptación ejecutado localmente por el usuario, con contraseñas ingresadas de forma oculta
y tokens conservados únicamente en memoria. No enviar contraseñas, tokens ni exportaciones
de peticiones autenticadas al chat. Iniciar sesión solamente en Chrome no habilita el acceso
del cliente HTTP de Codex.

No es posible atribuir el problema funcional principal a React, el backend, el routing,
la memoria o Qwen sin ejecutar las solicitudes autenticadas. La dependencia bloqueante
demostrada en esta preparación es el acceso a sesiones válidas para la prueba.
