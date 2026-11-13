# Incremento 8.5A.1: modelos, persistencia y migración 0003

Fecha: 30 de octubre de 2026. Estado: **implementado y verificado exclusivamente
en memoria y usuarios_test**. No se implementó 8.5A.2 ni se modificó React.

## Archivos creados

- `backend/migrations/versions/0003_password_inicial.py`.
- `backend/tests/security/test_auth_models_persistence.py`.
- `backend/tests/integration/postgresql/test_password_state_migration.py`.
- `docs/sprint-8-5a-1-implementacion.md` (este informe).

## Archivos modificados

- `backend/src/app/domain/auth/models.py`: campos explícitos de credencial y sesión.
- `backend/src/app/application/auth/ports.py`: inserción estricta en el puerto UoW.
- `backend/src/app/application/auth/service.py`: únicamente construcción explícita
  de credenciales normales y sesiones normales, conservando el comportamiento actual.
- `backend/src/app/infrastructure/persistence/models/auth.py`: columnas y CHECK.
- `backend/src/app/infrastructure/security/postgres.py`: mapeos e inserción estricta.
- `backend/src/app/infrastructure/security/memory.py`: inserción estricta equivalente.
- `backend/tests/security/test_authentication.py`: construcción explícita de sesión.
- `backend/tests/integration/postgresql/test_migrations.py` y
  `test_auth_migration.py`: expectativa de la revisión head actualizada a 0003;
  conservan sus escenarios previos.

No se modificaron 0001/0002, contratos HTTP, autorización, configuración, Docker,
frontend ni dependencias. No se instalaron paquetes.

## Modelos y compatibilidad

Credencial incorpora `debe_cambiar_password: bool` y
`password_inicial_hash: str | None`. Ambos se exigen como argumentos nominales,
sin valores predeterminados implícitos. Los dos hashes tienen `repr=False`.
Se rechaza una marca no booleana o una credencial pendiente sin hash inicial.

Sesion incorpora `restringida: bool`, también nominal y explícito, validado como
booleano. Las dataclasses siguen siendo inmutables. `replace`, las copias de
snapshot de memoria, el rehash y las actualizaciones conservan los campos nuevos.

Las fábricas actuales de bootstrap/asignación continúan escribiendo false/null y
login crea sesiones con restringida=false: solo se adaptaron al modelo. No se
conectó la nueva inserción al servicio, HTTP ni CLI. No se cambió la política de
contraseñas ni se activó el flujo obligatorio.

## Persistencia y transacciones

Los mapeos explícitos de PostgreSQL leen y escriben todos los campos nuevos;
los modelos ORM no tienen defaults de Python ni de servidor para las banderas.
Memoria almacena las dataclasses completas y su snapshot incluye los nuevos datos.

`SecurityUnitOfWork.insert_initial_credential` permite insertar sin upsert ni
sobrescritura. En memoria comprueba existencia dentro del lock de la UoW. En
PostgreSQL utiliza INSERT ORM, PK y savepoint bajo el advisory lock existente.
Un conflicto único se traduce a `AprovisionamientoRechazado`, sin incluir hashes
en el mensaje. El savepoint permite continuar la UoW si el llamador maneja el
conflicto. Otros errores de integridad se traducen a persistencia saneada.
La actualización previa `put_credential` se conserva separada.

Se verificó una sola inserción ganadora ante solicitudes concurrentes, conservación
de la credencial original, rollback de inserciones y rollback conjunto de cambios
de perfil, credencial y sesión. No hay commits internos en esta operación nueva.

## Migración 0003

Depende de 0002 y afecta únicamente a dos tablas de public:

| Tabla | Cambio | Filas históricas |
| --- | --- | --- |
| usuario_credenciales | debe_cambiar_password BOOLEAN NOT NULL | false |
| usuario_credenciales | password_inicial_hash TEXT NULL | null |
| auth_sesiones | restringida BOOLEAN NOT NULL | false |

Agrega `ck_credenciales_password_inicial`:
`NOT debe_cambiar_password OR password_inicial_hash IS NOT NULL`.

Las banderas se agregan con default temporal false para completar filas históricas;
ambos defaults se eliminan antes de terminar upgrade. Downgrade elimina únicamente
el CHECK y las tres columnas nuevas. No modifica usuarios, hashes existentes,
roles, estados, fechas, relaciones ni las columnas previas de sesiones.
No se utiliza `Base.metadata.create_all()`.

La prueba histórica cubre ADMIN/USUARIO, activos/inactivos, con/sin credenciales,
y sesiones vigentes/revocadas. Compara todos los valores previos antes y después
de upgrade y downgrade; verifica inventario de tablas, nulabilidad, CHECK y ausencia
de defaults finales. No se crean credenciales para perfiles históricos sin ellas.

## Aislamiento y verificaciones ejecutadas

Antes de habilitar PostgreSQL se cargó únicamente configuración de pruebas, se
ejecutó `require_test_database()` y se comprobó por lectura `current_database()` y
`current_user()`: **usuarios_test / usuarios_test_admin**, destino configurado
**127.0.0.1:5435**. La revisión inicial era 0002. Las fixtures y Alembic conservan
sus protecciones existentes de destino de pruebas.

La primera conexión dentro del aislamiento de ejecución agotó su timeout. La
comprobación de solo lectura fuera de ese aislamiento confirmó el destino; solo
después se ejecutaron las integraciones. No se recurrió a desarrollo como fallback.

Comandos principales, desde backend:

```powershell
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider --basetemp=.pytest-tmp-85a-unit
.\.venv\Scripts\python.exe -m pytest -q --run-postgres -p no:cacheprovider --basetemp=.pytest_cache/85a-final-temp
```

| Verificación | Resultado |
| --- | --- |
| Ejecución intermedia sin PostgreSQL | 296 aprobadas, 42 omitidas; anterior a las últimas dos pruebas de memoria/HTTP |
| Suite final completa | **340 aprobadas**, sin fallos, en 26,44 segundos |
| Cobertura anterior | **319 pruebas conservadas y aprobadas** |
| Pruebas nuevas | **21 aprobadas** |
| Casos PostgreSQL incluidos en el total | **42 aprobados**, todos en usuarios_test |
| Ciclo específico de 0003 | 0002 → 0003 → 0002 → 0003 aprobado con datos históricos ficticios |
| Comprobación Alembic final | **0003 (head)**; `No new upgrade operations detected.` |
| Compilación de archivos principales modificados | Correcta |

Además se verificaron roundtrips entre UoW independientes, conservación de campos
en rehash/cambio actual y revocación, rechazo de datos inválidos por PostgreSQL,
hashes ocultos en repr y ausencia de secretos/campos nuevos en respuestas HTTP.
Los contratos de login y me mantienen sus campos anteriores.

La ejecución inicial tuvo dos errores de preparación por permisos del directorio
temporal global de pytest; se resolvió usando un basetemp dentro del proyecto.
Una prueba nueva comparaba el inventario por orden de reflexión: se corrigió a
comparación de conjuntos, pues el orden no forma parte del contrato. La suite
completa se repitió satisfactoriamente después de corregirla.

Queda un aviso existente de Starlette sobre la futura sustitución de httpx por
httpx2 en TestClient. No se alteraron dependencias para ocultarlo.

## Límites y decisiones pendientes

**No se accedió ni se modificó usuarios_dev, ni se utilizó el puerto 5434.** No se
leyeron credenciales reales ni se ejecutaron operaciones contra usuarios de
desarrollo. No se ejecutaron migraciones de desarrollo ni pruebas de frontend.

Los campos son infraestructura preparada, no una garantía funcional de restricción:
la comprobación de acceso pendiente y la derivación de alcance en login pertenecen
a 8.5A.2. Las marcas true de las pruebas son ficticias y no deben aprovisionarse
operativamente hasta completar servidor, cambio obligatorio y controles de React.
No se ha habilitado una vía HTTP/CLI nueva para emitirlas.

La migración en desarrollo necesita autorización separada. Antes de usar el backend
modificado contra cualquier base, esa base debe tener 0003: su modelo ORM espera
las columnas nuevas. No ejecutar el backend actualizado contra desarrollo 0002.
El despliegue coordinado y la prohibición de downgrade funcional tras emitir
credenciales pendientes siguen el diseño aprobado. No se modificó ni arrancó el
servicio de desarrollo durante esta intervención.

El hash inicial adicional tendrá el coste y exposición documentados en 8.5A; no
se implementó un historial general. No se implementaron bloqueo funcional,
vencimiento de inicial, restablecimiento, nuevos DTO ni formularios.

El trabajo se detiene al completar **8.5A.1**. No se continúa con 8.5A.2.
