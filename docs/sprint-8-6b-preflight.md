# Sprint 8.6B: preflight de puesta en funcionamiento

Fecha: **1 de noviembre de 2026**. Alcance: inspección autorizada de solo lectura
de desarrollo y preparación del siguiente punto de control. No se ejecutaron
respaldo, migración, despliegue, login ni cambios de datos o configuración.

## 1. Dictamen

**Bloquear la ejecución inmediata de la migración.** El destino y el esquema
coinciden con el punto de partida previsto, y no se detectó una incompatibilidad
estructural evidente que impida preparar 0003. Sin embargo, quedan procesos
activos, respaldo sin realizar/verificar y ubicación protegida sin acordar.
La aceptación temporal de A02 aún necesita confirmación del responsable.

Se puede solicitar la siguiente autorización operativa para preparar/verificar
el respaldo y establecer mantenimiento. La migración solo debe ejecutarse tras
satisfacer esos controles y recibir autorización expresa. Este informe no la
concede ni recomienda omitirlos por tratarse de un entorno local.

Documentación revisada: auditoría 8.6A, preparación 8.6B, backend/README.md y README
principal. Sus resultados de pruebas son antecedentes: no se volvió a ejecutar
pytest, Vitest, build ni auditoría de dependencias durante este preflight.

## 2. Identificación verificada del entorno

Antes de abrir la conexión se cargó la configuración operativa mediante
load_database_config y se exigió coincidencia exacta de base, host y puerto.
No se imprimieron el archivo .env, la contraseña ni una cadena de conexión.

| Comprobación | Resultado observado |
| --- | --- |
| Base configurada y efectiva | usuarios_dev |
| Host y puerto configurados | 127.0.0.1:5434 |
| Usuario efectivo, igual al configurado | usuarios_dev_admin |
| Servidor | PostgreSQL 18.6, Debian |
| Revisión en public.alembic_version | **0002**, una sola fila |
| Modo efectivo de la transacción de inspección | **transaction_read_only = on** |
| Contenedor propio | api-usuarios-clean-postgres-1, imagen postgres:18 |
| Publicación Docker observada | 127.0.0.1:5434 → 5432 interno |

Se utilizó Psycopg con default_transaction_read_only=on desde la conexión,
conn.read_only=True, connect_timeout=5, statement_timeout=10000 y lock_timeout=2000.
Se verificaron current_database/current_user y modo de solo lectura antes de
inspeccionar estructura y conteos; al finalizar se hizo rollback y se cerró la
conexión. No se modificaron valores predeterminados persistentes de PostgreSQL.

La configuración de autenticación de desarrollo superó los validadores existentes
de AuthConfig sin mostrar valores, claves ni contenidos de JWT_KEYS_JSON. Esto
valida configuración, no constituye una prueba de login o de servicios activos.

## 3. Estado estructural de la base

Inventario observado de tablas de usuario: exclusivamente las siguientes en public.

| Tabla | Filas observadas |
| --- | ---: |
| usuarios | **3** |
| usuario_credenciales | **1** |
| auth_sesiones | **10** |
| auth_intentos | **2** |
| alembic_version | **1**, revisión 0002 |

Son conteos del momento de inspección, no una línea base congelada para migrar.
Había otras **4 conexiones idle** a esta base. No se consultó el texto de sus
sentencias ni se concluye que nunca puedan escribir. Deben repetirse los controles
en mantenimiento antes del respaldo/migración que se autoricen posteriormente.

### Columnas y restricciones

- usuarios presenta los campos de perfil esperados, UUID, booleano activo y fecha
  timestamp with time zone. No se consultaron valores de sus filas.
- usuario_credenciales presenta usuario_id, password_hash, creada_at y actualizada_at;
  el nombre/tipo de password_hash se inspeccionó como metadato, **no su contenido**.
- auth_sesiones presenta id, usuario_id y fechas creada_at, expira_at, revocada_at.
- auth_intentos presenta ámbito, clave binaria, fechas y contador; no se leyeron
  claves ni filas, únicamente metadatos y cantidad.
- Se observaron PK/FK de credenciales y sesiones y los CHECK de fechas existentes.

| Objeto nuevo de 0003 | Estado actual |
| --- | --- |
| usuario_credenciales.debe_cambiar_password | **Ausente** |
| usuario_credenciales.password_inicial_hash | **Ausente** |
| auth_sesiones.restringida | **Ausente** |
| ck_credenciales_password_inicial | **Ausente** |

Las tablas sobre las que opera 0003 existen y las columnas nuevas todavía no:
es la situación estructural esperada para migrar desde 0002. No hay evidencia de
una aplicación parcial de esas adiciones en los objetos inspeccionados. No se
ejecutó Alembic check contra el modelo 0003 sobre desarrollo 0002, ni se presentó
esa diferencia prevista como un error inesperado.

La revisión local de archivos, sin conectar Alembic a desarrollo, confirmó un
único head **0003**, dependiente de **0002**. Se revisó el contenido real: solo
añade tres columnas y un CHECK en las dos tablas de autenticación, usa defaults
temporales false y los elimina. No cambia perfiles ni asigna contraseñas.

## 4. Procesos, puertos y compatibilidad

Se inspeccionaron procesos mediante identificadores y clasificación de argumentos;
no se publicaron líneas de comando completas ni variables de entorno.

| Recurso | Observación |
| --- | --- |
| 8001 loopback | Ocupado por PID **27496**, Uvicorn; padre Python **16432** |
| Entrada ASGI de esos procesos | **app.main:app**, referencia al workspace; no aparece create_test_database_app |
| Fecha de creación de ambos | 30 de octubre de 2026 |
| Reload | No se observó --reload |
| 5173 loopback | Ocupado por PID **6168**, Vite del workspace |
| Otro Node observado | PID **29268**; finalidad no determinada, no se intervino |
| 8000 / 4173 | Sin listener observado |
| PostgreSQL de pruebas | Contenedor propio separado, loopback 5435; no se consultó su base en esta intervención |

**Atención operativa:** en el código actual, app.main:app llama create_app() sin
inyectar la configuración de pruebas. Esa entrada carga configuración de desarrollo
por defecto; el puerto 8001 no la convierte en una instancia de pruebas. El proxy
Vite actual dirige /api a 127.0.0.1:8001. No asumir que el frontend que ya está
abierto está aislado de desarrollo por usar los puertos habituales de las guías.

No se hicieron peticiones HTTP, introspección de memoria de procesos, login ni
consultas de datos personales para averiguar la versión cargada. Por ello no se
certifica el código efectivo en memoria ni el destino histórico de esa instancia.
Los procesos fueron creados antes de las últimas correcciones y no muestran
reload: deben tratarse como candidatos a obsoletos y detenerse/reemplazarse solo
con autorización durante mantenimiento. No se reiniciaron en este preflight.

### Requisitos de inicio

- Python observado: **3.14.3**, entorno backend/.venv disponible.
- Node observado: **24.14.1**; npm **11.11.0**; node_modules y dist/index.html existen.
  Su existencia no demuestra que el bundle activo sea el último verificado.
- El backend en disco usa campos de 0003. **No iniciarlo contra el desarrollo 0002
  observado**, ni arrancar una segunda instancia para probarlo antes de migrar.
- El frontend espera los contratos de login/me normal o restringido y cambio
  obligatorio actuales; el backend sigue siendo autoridad. Evitar versiones mixtas.
- Vite está configurado para un destino de pruebas fijo en 8001. Su uso operativo
  con desarrollo no se configura cambiando ese proxy en esta intervención: falta
  definir y aprobar el proxy de mismo origen para la publicación compatible.
- Vite dev/preview no sustituyen servidor estático, configuración de rutas API/SPA,
  caché de HTML y, si corresponde, HTTPS/CSP. No se publicó ningún artefacto.

## 5. Herramientas y ubicación de respaldo

| Comprobación | Resultado |
| --- | --- |
| pg_dump/pg_restore/psql nativos en PATH | No encontrados |
| Ubicaciones convencionales revisadas | Sin ejecutables encontrados en C:/Program Files/PostgreSQL o C:/Program Files/pgAdmin 4/runtime; no es una búsqueda exhaustiva de discos |
| Herramientas del contenedor propio | **pg_dump 18.6 y pg_restore 18.6**, compatibles en versión con servidor 18.6 |
| Comprobación realizada | docker exec del contenedor propio con cada herramienta y **--version**, sin exportar ni restaurar |
| Espacio libre observado en D: | Aproximadamente **111,67 GiB**, variable; sin estimar tamaño final del respaldo |
| Ubicación propuesta | **D:/Backups/api-usuarios-clean**, fuera del workspace |
| Estado de la ubicación propuesta | No existen D:/Backups ni su subcarpeta; **no se crearon** |

La ruta es una propuesta a confirmar, no un almacén protegido ya habilitado.
Quedan pendientes permisos/ACL, cifrado, responsable, retención, copia independiente
y espacio suficiente. No se validó capacidad de escribir allí, porque no se
autorizaron creaciones ni respaldos. Tampoco se comprobó una exportación completa
o una restauración de ensayo; --version solo demuestra disponibilidad de binarios.

Se puede preparar el respaldo futuro con las herramientas ya presentes dentro
del contenedor, sin instalar programas. Tras autorización, el plan será generar
un archivo custom en una ruta temporal acordada del contenedor y copiarlo con
**docker cp** a la ubicación protegida. Evitar una redirección binaria a través
de una tubería PowerShell que pueda alterar el archivo. La autenticación del
operador deberá resolverse con entrada interactiva local segura, sin contraseñas
en argumentos, logs o variables impresas.

No se consultó Docker inspect con variables de entorno ni se cambiaron servicios,
volúmenes o configuración. No se inició el servicio de ningún contenedor: exec
--version ejecutó únicamente herramientas de inspección en uno ya existente.

## 6. A02: aceptación temporal propuesta

Se registra la propuesta del usuario de **aceptar temporalmente el riesgo residual
de dependencias de desarrollo**, pendiente de confirmación del responsable.
No se interpreta como aceptación definitiva ni como autorización de despliegue.

Evidencia anterior, no reejecutada aquí: 12 entradas moderadas propagadas por
minimatch en herramientas, 0 altas/críticas y 0 avisos con --omit=dev. La corrección
publicada está fuera de los rangos declarados revisados. No se modificaron
package.json o lockfile y no se instalaron/actualizaron paquetes.

Antes de cerrar la aceptación, registrar responsable, alcance solo herramientas,
justificación, fecha de revisión/caducidad y condiciones de reapertura (aviso de
mayor severidad, exposición en runtime o actualización compatible disponible).
Mantener controladas las entradas no confiables de patrones/CI. No se inventó una
fecha de caducidad ni se atribuyó una aceptación a una persona no confirmada.

## 7. Plan concreto para 0003 — NO ejecutado

1. Obtener autorización expresa para respaldo/mantenimiento/migración y confirmar
   aceptación temporal de A02. Acordar directorio y protección del archivo.
2. Acordar ventana; identificar y detener únicamente los procesos propios antiguos
   con permiso del responsable. No matar por número de puerto ni afectar proyectos
   ajenos. Impedir nuevas peticiones/escrituras; comprobar conexiones restantes.
3. Revalidar destino efectivo usuarios_dev / 127.0.0.1:5434, cuenta y revisión 0002.
   Repetir inventario y conteos: **3/1/10/2 son solo antecedentes de este preflight**.
   Si el estado cambió, revisarlo antes de continuar; si ya es 0003, no repetir upgrade.
4. Generar respaldo custom con pg_dump 18.6 del contenedor propio, autenticación
   segura y destino acordado. Copiar binariamente, verificar checksum y catálogo
   con pg_restore --list. Proteger también configuración/roles por separado.
5. Probar restauración en una base aislada específicamente autorizada; no asumir
   que leer el catálogo equivale a restaurar. No usar automáticamente usuarios_test
   para este fin: podría contener datos reales restaurados, debe acordarse otro
   destino protegido y su eliminación posterior.
6. Capturar una línea base consistente en mantenimiento, inventario y fechas.
   Este preflight **no leyó hashes ni datos personales**. Una comparación futura
   exacta de esos valores necesitará alcance explícito; no dar por autorizada su
   lectura/exportación a partir de esta inspección. No basta contar filas.
7. Revalidar archivos de migración y único head 0003. Ejecutar solo la revisión
   aprobada, con las protecciones existentes. Estos comandos son una propuesta:

```powershell
# FUTURO: desde backend, solo con autorización y controles previos completos.
.\.venv\Scripts\python.exe -m alembic -x allow-development=true current
.\.venv\Scripts\python.exe -m alembic -x allow-development=true upgrade 0003
if ($LASTEXITCODE -ne 0) { throw 'Detener; mantener mantenimiento' }
.\.venv\Scripts\python.exe -m alembic -x allow-development=true current
.\.venv\Scripts\python.exe -m alembic -x allow-development=true check
```

8. Hacer las comprobaciones posteriores antes de arrancar backend compatible y
   publicar frontend. Esos arranques/publicación tampoco se autorizan aquí.
9. Mantener el aprovisionamiento bloqueado; su habilitación es otra decisión y
   otro cambio revisado. El permiso de migración no abre la barrera.

La migración prevista preserva hashes/fechas existentes y agrega false/null/false
para datos históricos. No crea credenciales ni fuerza cambio a usuarios actuales.
Los defaults de las banderas son temporales y deben quedar eliminados al terminar.

## 8. Plan de verificación posterior

Tras una futura ejecución autorizada, exigir:

- Alembic 0003 y check sin diferencias; mismas tablas y ausencia de cambios ajenos.
- Nuevas columnas boolean/text/boolean con nulabilidad esperada, CHECK
  ck_credenciales_password_inicial y sin defaults finales en banderas.
- Conteos iguales a la línea base de mantenimiento, sin credenciales nuevas.
  Backfill pendiente=false, antecedente=null y restringida=false en filas previas.
- Integridad exacta de perfiles, credenciales y sesiones mediante el procedimiento
  expresamente aprobado, sin imprimir valores sensibles. Ninguna contraseña nueva,
  reactivación o revocación causada por la migración.
- Todos los workers antiguos detenidos y artefactos compatibles identificados.
  Reapertura/arranque únicamente con el permiso correspondiente, esquema 0003 y
  proxy que no confunda instancias de pruebas/desarrollo.
- Pruebas manuales de login/me/roles/logout solo si se autorizan aparte, con entrada
  personal segura. **Nunca pytest, fixtures o limpieza automatizada en desarrollo.**
- Barrera productiva aún cerrada. Los formularios de alta/asignación no deben
  aparentar éxito mientras siga cerrada.

## 9. Riesgos y condiciones de parada

| Condición | Tratamiento |
| --- | --- |
| Backend actual frente a esquema 0002 | Bloquea inicio del nuevo código hasta migrar con permiso |
| app.main:app en 8001 y proxy Vite a 8001 | Aclarar/detener instancia antigua con autorización; no asumir aislamiento de pruebas ni efectuar solicitudes a modo de diagnóstico |
| Procesos o conexiones capaces de escribir | Establecer mantenimiento antes de fijar línea base o migrar |
| Carpeta/ACL/cifrado no definidos; backup sin ensayo | Bloquea ejecución de migración hasta resolver y verificar |
| A02 sin confirmación responsable | Pendiente de aceptación documentada o resolución |
| Destino/revisión/DDL inesperados | Parar sin escribir; no usar fallback ni upgrade head |
| Fallo de backup, migración o integridad | Mantener mantenimiento; investigar antes de siguientes pasos |
| Versiones mixtas o barrera abierta sin permiso | No arrancar/reabrir servicio |

Si falla la migración, comprobar el estado real y el rollback; no asumir éxito
o reversión solo por el código de salida. Si 0003 quedó aplicada, preferir corrección
hacia adelante. No hacer downgrade de desarrollo: puede quitar restricciones y
no revierte cambios de contraseña. Una restauración exige autorización específica,
respaldo ensayado, servicios detenidos, artefactos/configuración coherentes y
aceptación explícita de pérdida de datos posteriores. No borrar volúmenes ni usar
pg_restore --clean contra desarrollo como respuesta improvisada.

## 10. Ausencia de escrituras y detención

Solo se creó **docs/sprint-8-6b-preflight.md** como entregable. Se ejecutaron SELECT
de identidad, conteos, catálogo y estado agregado de conexiones en transacción
forzada a solo lectura. No se consultaron por SQL perfiles individuales,
contraseñas, hashes, JWT, claves o texto de consultas de otras sesiones. La
validación de configuración procesó sus secretos únicamente en memoria, sin
imprimirlos ni incorporarlos a archivos o resultados.

No se ejecutaron DML/DDL, Alembic upgrade/downgrade/check contra desarrollo,
pytest, backup, restauración, login ni peticiones HTTP. No se detuvieron/reiniciaron
procesos, no se arrancaron servicios ni se modificaron paquetes, configuración,
código productivo o barrera. Se verificó que la función de barrera sigue rechazando
en un proceso independiente, sin conexión a la base.

**Preflight finalizado. Respaldo, migración, despliegue y habilitación siguen sin
ejecutar. Se espera autorización expresa para la siguiente operación.**
