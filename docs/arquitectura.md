# Arquitectura y decisiones aprobadas

> Documento histórico: sus revisiones y comandos describen esa etapa, no el inicio actual.
> El backend vigente requiere **0003**, pruebas solo en usuarios_test:5435, cambio
> obligatorio implementado y aprovisionamiento cerrado. Seguir [la guía backend](../backend/README.md)
> y [preparación 8.6B](sprint-8-6b-preparacion.md). No ejecutar operaciones de desarrollo
> ni iniciar este código con 0001/0002 a partir de instrucciones históricas.

## Alcance actual

Etapa 1 completada: paquete Python instalable, FastAPI mínimo y punto de composición.
Etapa 2: entidad Usuario, Email, Rol y pruebas unitarias, sin persistencia ni autenticación.
Etapa 3: seis casos de uso, DTO inmutables, contrato UserRepository y adaptador en memoria.
Etapas 4 y 5: PostgreSQL, adaptador SQLAlchemy y migración Alembic 0001 aplicada.
Etapa 6: API REST, lifespan, errores saneados y pruebas HTTP. Sprint 7: autenticación
y autorización verificadas solo en pruebas; 0002 pendiente en desarrollo. El dominio original
y Application se conservan sin modificaciones.
Python 3.14.3 en `backend/.venv`. No modificar instalaciones globales ni variables del sistema.
Antes de agregar bibliotecas futuras, verificar compatibilidad con Python 3.14.3.
Una incompatibilidad requiere explicar alternativas; no cambiar automáticamente de Python.

## Capas

- **Domain:** entidades y reglas de negocio con Python estándar.
- **Application:** casos de uso y contratos de persistencia y servicios.
- **Infrastructure:** adaptadores concretos de los contratos (posteriormente SQLAlchemy y proveedores externos).
- **Presentation:** transporte HTTP, esquemas y traducción de errores.

Presentation depende de Application; Application puede depender de Domain.
Infrastructure implementa contratos internos. Domain no depende de frameworks.
`bootstrap.py` es el punto de composición externo a las capas: conectará las implementaciones.
Actualmente compone FastAPI, router, handlers y persistencia durante lifespan.
`main.py` expone la instancia a Uvicorn sin conectar a PostgreSQL al importar.

Aplicaremos Repository Pattern e inyección de dependencias por constructor.
FastAPI `Depends` quedará en el límite HTTP, sin entrar en dominio o casos de uso.
Como en Spring, la configuración conectará componentes, pero aquí será explícita.

SOLID: responsabilidades separadas; adaptadores sustituibles que respeten contratos;
interfaces acotadas; casos de uso dependientes de abstracciones.

## Dominio implementado en etapa 2

Usuario encapsula UUID, nombre, apellido, Email, activo, Rol y fecha de creación UTC.
`crear` genera identidad y fecha nuevas; `reconstruir` valida y conserva datos existentes.
`modificar_datos` valida todos los valores antes de modificar el objeto, sin alterar rol ni estado.
`dar_de_baja` y `reactivar` son idempotentes y conservan los demás atributos.
Los datos personales tienen entre 1 y 100 caracteres una vez recortados los espacios externos.
Email es un objeto de valor inmutable con normalización a minúsculas; su política ASCII
y límites están documentados en README y cubiertos por pruebas.
Rol es una enumeración ADMIN/USUARIO. No representa por sí misma autorización.
El dominio no importa FastAPI, Pydantic, SQLAlchemy ni clientes de bases de datos.
pytest es una dependencia opcional de desarrollo. Cada cambio de dominio ejecutará toda la suite de regresión.

Responsabilidad única: Usuario controla transiciones, Email su formato y Rol sus valores.
Las excepciones expresan invariantes sin códigos HTTP. Los contratos y sus implementaciones
se incorporarán posteriormente, sin agregar interfaces innecesarias al dominio.

## Reglas definitivas de usuarios (incluyen comportamiento futuro de aplicación/API)

- UUID, nombre, apellido, email normalizado único, activo y fecha de creación con zona horaria.
- Alta nueva: activo=true, HTTP 201.
- Email de usuario activo: HTTP 409, USUARIO_ACTIVO_EXISTENTE.
- Email de usuario inactivo: HTTP 409, USUARIO_INACTIVO_REACTIVABLE e identificador del usuario.
- Nunca reactivar automáticamente ni insertar otro registro con el mismo email.
- DELETE /api/v1/usuarios/{id}: baja lógica mediante activo=false, sin eliminación física.
- PATCH /api/v1/usuarios/{id}/reactivar: activo=true, conservando todos los demás datos.
- Baja repetida: 204; reactivación repetida: 200 con el usuario actual. Ambas idempotentes.
- UUID inexistente: 404. No se modifica UUID ni fecha de creación.
- Alta y edición ordinaria no admiten activo; los campos adicionales se rechazarán.
- Listado: estado=activos por defecto; estado=inactivos o estado=todos explícitos.
- Consulta individual accesible para activos e inactivos.
- Restricción UNIQUE global sobre email normalizado, transacciones y control de concurrencia.
- React mostrará confirmación antes de reactivar; cancelar no modifica datos.
- Reactivación administrativa: incorporar autorización cuando exista autenticación.
- Roles ADMIN y USUARIO; operaciones administrativas reservadas a ADMIN.
- Credenciales separadas de Usuario: sin contraseñas ni hashes en la etapa 2.
- PostgreSQL en etapa 4; SQLAlchemy y Alembic en etapa 5.
- Esquema administrado exclusivamente por migraciones versionadas. Prohibida la sincronización automática
  y el uso de `Base.metadata.create_all()`.

## Plan histórico y reorganización

2. Dominio y pruebas unitarias.
3. Contratos, casos de uso y repositorio en memoria.
4. PostgreSQL en Docker Compose.
5. SQLAlchemy, Alembic, unicidad y transacciones.
6. API de usuarios, filtros y reactivación.
7. Validación integral del backend, incluyendo concurrencia.
8. Hash de contraseñas, credenciales y creación segura del primer ADMIN.
9. Login, JWT, renovación y cierre de sesión.
10. Autorización por roles.
11. Pruebas de autenticación, permisos y revocación.
12. React, TypeScript, Vite y cliente HTTP.
13. Login y sesión en React.
14. Listado con filtros y consulta.
15. Alta, edición, baja lógica y confirmación de reactivación.
16. Integración del ABMC autenticado y pruebas.
17. Chat flotante y multichat con servicio simulado.
18. LangChain y proveedores LLM local/remoto.
19. Tool Calling real sobre instituto.csv.
20. Conversaciones y mensajes persistentes en PostgreSQL, ventana y presupuesto de tokens.
21. Integración multichat con propiedad y acceso por usuario autenticado.
22. Memoria larga con ChromaDB, Ollama y bge-m3.
23. Integración de memorias y carga explícita de asistente_institucional/SKILL.md.
24. RAG sobre PDF normativos: ingesta, OCR cuando corresponda, fuentes y evaluación.
25. Evaluación integral del agente, memorias, RAG y aislamiento.
26. Integración final, Docker y documentación.

Las etapas HTTP incluirán Swagger y ejemplos Postman, complementarios a pytest.
El Sprint 7 autorizado posteriormente reúne seguridad prevista en etapas 8 a 11.
No supone autorización para Sprint 8 ni para migrar desarrollo a 0002.
Las conversaciones pertenecerán al usuario autenticado; el servidor impone user_id.
PostgreSQL conservará historial completo y registros canónicos; ChromaDB será una proyección
reconstruible con tareas idempotentes y sin transacción compartida con PostgreSQL.
Se separarán memoria_usuarios y documentos_instituto. El CSV y los PDF serán fuentes oficiales,
sin dar prioridad a recuerdos personales. Se contemplará funcionamiento sin ChromaDB.
El rol y las sesiones vigentes se verificarán en el servidor; baja revocará sesiones y
reactivación no las recuperará. El primer ADMIN se creará por comando local seguro.

## Aplicación implementada en etapa 3

Los seis casos de uso reciben UserRepository por constructor y no importan Infrastructure ni FastAPI.
El contrato ABC pertenece a Application; Infrastructure implementa agregar/actualizar y consultas
sin exponer referencias vivas. Cada lectura y escritura del adaptador en memoria usa un bloqueo local,
con copias reconstruidas y comprobación global de email único al escribir.
La ordenación es por fecha_creacion e id; el filtro se aplica antes de paginar.
Los DTO congelados separan las entradas/salidas de la entidad mutable.
Email duplicado durante alta se traduce según el estado del propietario; durante modificación,
un email ajeno produce EmailEnUso. UsuarioInactivoReactivable conserva usuario_id y un código estable.
Baja y reactivación actualizan sin insertar y mantienen la idempotencia.
El ejemplo realiza composición manual; no se conecta todavía este adaptador a FastAPI.

El bloqueo garantiza unicidad por escritura, no una transacción de todo el caso de uso.
Las ediciones concurrentes de la misma identidad no tienen control de versiones todavía.
No hay Unit of Work ni transacciones de base de datos en esta etapa; cada caso realiza una sola escritura.
Las pruebas de integración son entre componentes Python, no de PostgreSQL ni HTTP.

Cada etapa requiere autorización. La etapa 4 fue autorizada explícitamente.
Etapa 5 verificada en pruebas y posteriormente migrada a desarrollo con la segunda
autorización explícita. Etapa 6 autorizada e implementada. No avanzar a etapa 7.

## Infraestructura de etapa 4

Etapa completada y verificada: PostgreSQL 18.6 healthy, persistencia tras reinicio
y recreación, cero tablas de aplicación, 161 pruebas aprobadas y ejemplo correcto.

PostgreSQL 18 mediante Compose en la raíz, separado del backend. Publicación
local `127.0.0.1:5434`, puerto interno 5432, volumen nombrado en
`/var/lib/postgresql`, red bridge propia, healthcheck pg_isready y reinicio
unless-stopped. Las credenciales locales están en `.env`, excluido de Git;
`.env.example` no contiene contraseña.

No cambia el dominio, Application, bootstrap ni el repositorio en memoria.
No se instalan SQLAlchemy/Alembic ni se crean tablas de aplicación. La futura
conexión y las migraciones corresponden a etapa 5. Toda operación Docker se
limita a este proyecto; los recursos ajenos no se modifican.

Procedimientos y evidencias: [etapa-4-postgresql.md](etapa-4-postgresql.md).

## Persistencia de etapa 5

Implementados configuración externa, Engine/fábrica de sesiones, modelo ORM,
mapeo explícito, SQLAlchemyUserRepository y revisión Alembic 0001. Domain,
Application y contratos no se modifican. Cada escritura confirma o revierte
dentro del adaptador; los casos de uso pueden capturar conflictos al escribir.
No hay transacción global del caso de uso ni control de versiones: se mantiene
la política existente de última escritura válida sobre una misma identidad.

Pruebas en un PostgreSQL independiente con tmpfs, usuarios_test y puerto 5435.
Las fixtures rechazan desarrollo y validan base/usuario antes de limpiar datos.
Upgrade/downgrade verificados solo en pruebas. Suite: 196 pruebas aprobadas.
La revisión 0001 se aplicó después a usuarios_dev con autorización explícita;
se verificaron sus dos tablas, restricciones e índices, sin insertar usuarios.

Detalle y punto de control: [etapa-5-persistencia.md](etapa-5-persistencia.md).
No aplicar nuevas migraciones a desarrollo sin autorización.

## API REST de etapa 6

Presentation/http contiene esquemas Pydantic, conversiones explícitas, router y
dependencias FastAPI. Los seis endpoints delegan en los casos de uso existentes.
Domain, Application y sus contratos permanecen intactos (20 archivos verificados
por hashes). Las rutas usan /api/v1/usuarios; DELETE es baja lógica y PATCH
/{id}/reactivar es reactivación explícita. No hay eliminación física.

create_app acepta un repositorio inyectado para pruebas, sin leer configuración
PostgreSQL. En ejecución normal lifespan construye la persistencia y dispone el
Engine al cerrar; importar main no configura ni conecta a PostgreSQL. Las sesiones
y transacciones siguen perteneciendo al adaptador. Los endpoints son síncronos.

Errores públicos consistentes: 422, 404, 409 y 500. Las lecturas de filas inválidas
se clasifican como ErrorPersistencia. El registro técnico usa solo código, clase,
plantilla de ruta y ubicaciones de código, sin mensajes, SQL ni valores originales.
Una frontera HTTP evita que excepciones inesperadas lleguen al log ASGI con datos.

La fábrica create_test_database_app y la colección Postman usan usuarios_test;
las pruebas automatizadas conservan las guardas de base/usuario/puerto existentes.
Suite completa: 248 aprobadas (196 anteriores y 52 nuevas). No se aplicaron
nuevas migraciones ni se escribieron usuarios de prueba en desarrollo durante etapa 6.
No se incorporó autenticación, autorización ni funcionalidades de etapa 7.

Operación y resultados: [etapa-6-api-rest.md](etapa-6-api-rest.md).

## Sprint 7: autenticación y autorización

Credenciales separadas, Argon2id, JWT HS256 de 15 minutos y sesiones revocables.
Cada petición consulta sesión, credencial, perfil activo y permisos actuales.
ADMIN administra; USUARIO solo consulta su perfil y cambia su propia contraseña.
La baja revoca sesiones y reactivar no las recupera. No hay registro público.

SecurityUnitOfWork en memoria y PostgreSQL coordina las operaciones atómicas.
El adaptador PostgreSQL usa savepoints del repositorio y una sola confirmación
externa, con advisory lock conservador para serializar la seguridad. La política
de última escritura del repositorio tradicional permanece en sus usos originales;
los endpoints protegidos usan ahora la unidad de seguridad.

0002 agrega credenciales, sesiones e intentos con claves HMAC; solo usuarios_test
se migró. Usuarios_dev permanece en 0001. El bootstrap local no adopta perfiles
existentes por email y se cierra al existir una credencial ADMIN, aun inactiva.
No hay claves predeterminadas ni secretos en respuestas de perfiles o logs.

Guía e inventario: [sprint-7-autenticacion.md](sprint-7-autenticacion.md).
Detenerse antes de modificar estructura/datos de desarrollo o avanzar al Sprint 8.
