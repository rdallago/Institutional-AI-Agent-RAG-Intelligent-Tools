# Sprint 8.6B: migración controlada 0002 → 0003

Fecha: **1 de noviembre de 2026**.
**Estado final: APLICADA y verificada. usuarios_dev en 0003 (head).
FastAPI/React detenidos; aprovisionamiento cerrado.**

En la operación anterior se inició el mantenimiento autorizado, pero aparecieron nuevos procesos de la
aplicación durante los controles. No se pudo asegurar una ventana sin escritores;
se cumplió la condición de parada indicada por el responsable. No se ejecutaron
Alembic current/upgrade/check, ni escrituras sobre la base.

Las secciones **2–8 conservan los intentos anteriores como historial**; sus
bloqueos y estados 0002 no describen el resultado final. La autorización específica
de terminación, migración e integridad completadas se documentan en la **sección 9**.

## 1. Autorizaciones y riesgos aceptados

El responsable confirmó expresamente que usuarios_dev contiene exclusivamente
datos de prueba y autorizó continuar **sin respaldo**, aceptando la posibilidad
de pérdida o reconstrucción. Se registra como decisión del responsable, no como
una propiedad de los datos verificada mediante lectura de información personal.
No se creó respaldo ni exportación; no se condiciona la reanudación a repetir
una solicitud de respaldo ya dispensada.

Se acepta temporalmente **A02** para este **entorno local de práctica**, sin
actualizar o forzar dependencias. La revisión es obligatoria **antes de cualquier
despliegue externo**; no se extiende esta aceptación a producción externa.
No se inventó una fecha de caducidad adicional. No se repitió npm audit; los
resultados previos siguen siendo antecedentes, no una auditoría nueva.

La autorización para migrar sigue sujeta a los controles previos, especialmente
ausencia de escritores y mantenimiento. No autoriza iniciar la aplicación después
de la migración, abrir aprovisionamiento ni intervenir sobre servicios ajenos.

## 2. Procesos identificados y acciones realizadas

Antes de detener cada proceso se comprobó PID, fecha de creación y referencia
exacta al workspace `D:/Downloads/proyectos/api-usuarios-clean`, además de su
entrada Uvicorn o Vite. No se actuó únicamente por número de puerto.

| PID / recurso | Identificación | Resultado |
| --- | --- | --- |
| 6168 / 5173 | Vite del workspace, creado el 30 de octubre | Detenido con Stop-Process tras revalidar identidad |
| 27496 / 8001 | Uvicorn app.main:app del workspace, hijo de 16432, creado el 30 de octubre | Detenido con Stop-Process tras revalidar identidad |
| 16432 | Padre Python/Uvicorn del mismo workspace y entorno virtual | Terminó durante la secuencia; Stop-Process informó que el PID ya no existía. La comprobación posterior confirmó su ausencia |
| 29268 | Node previamente no identificado inequívocamente por sus argumentos | No se detuvo explícitamente; ya no figuraba en la inspección posterior |
| PostgreSQL / 5434 | Listener existente, PID 25552 | Conservado, sin detener servicio o contenedor |

Después aparecieron otros dos procesos:

| PID | Identificación observada | Acción |
| --- | --- | --- |
| **26988** | Python/Uvicorn, app.main:app del workspace, --port 8000, padre 8804 | No detenido |
| **33588** | Hijo de 26988, mismo app.main:app del workspace; listener efectivo **127.0.0.1:8000** | No detenido |
| 8804 | Terminal PowerShell existente, padre del proceso nuevo | No intervenida |

Los nuevos procesos se crearon durante la operación (1 de noviembre). No se
determinó si fueron iniciados manualmente o por algún mecanismo externo. No se
afirma que exista un reinicio automático. No se cerró la terminal para intentar
suprimirlos, ni se supuso autorización para interrumpir una ejecución recién
iniciada sin aclarar la situación.

Los procesos antiguos 16432/27496/6168 ya no estaban presentes en el control final.
8001 y 5173 quedaron sin listener; **8000 quedó ocupado por el nuevo Uvicorn**.
Por ello no se declaró establecido el mantenimiento ni se inició la migración.
No se inició ningún proceso FastAPI/React durante esta intervención.

## 3. Estado de la base confirmado por lectura

La configuración se verificó antes de abrir conexión y coincidió exactamente con
usuarios_dev / 127.0.0.1:5434. Se usó Psycopg con solo lectura forzada desde el
inicio, timeout de conexión y de sentencias; se verificó transaction_read_only=on.

| Control | Resultado |
| --- | --- |
| Base efectiva | usuarios_dev |
| Usuario efectivo, igual al configurado | usuarios_dev_admin |
| Revisión de base | **0002**, una fila |
| Único head local | **0003** |
| Predecesor de 0003 | **0002** |
| Perfiles | **3** |
| Credenciales | **1** |
| Sesiones | **10** |
| Registros de intentos | **2** |
| Otras conexiones cliente | **5 idle** al consultar |

Estos conteos coinciden con los antecedentes del preflight, pero no se consideran
una línea base congelada: el nuevo servidor puede recibir solicitudes y las
conexiones idle pueden empezar a escribir después de la observación.

No se capturaron datos personales, hashes, tokens o secretos para comparar
integridad: esa comparación exacta en memoria quedó pendiente porque no se llegó
al punto seguro de migración. La igualdad de conteos no se presenta como prueba
de conservación completa de valores frente a actividad de otros procesos.

## 4. Revisión de migración y comandos

Se leyó el archivo real `backend/migrations/versions/0003_password_inicial.py` y
se contrastó con el preflight: tres columnas nuevas, CHECK de contraseña inicial,
defaults false temporales eliminados al terminar; sin cambios a perfiles ni
credenciales nuevas. ScriptDirectory confirmó head/predecesor localmente, sin
ejecutar el entorno Alembic contra la base.

Operaciones efectivamente realizadas:

- Inspección de procesos y listeners, mostrando solo clasificación y metadatos
  seguros, nunca líneas completas con posibles secretos.
- Stop-Process para los dos procesos antiguos identificados. En el tercero hubo
  la carrera de salida descrita arriba; se verificó el estado antes de continuar
  con cualquier decisión.
- SELECT de identidad, revisión, conteos y estados agregados de otras conexiones,
  en conexión de solo lectura, cerrada con rollback.
- Comprobación de la barrera productiva en un proceso independiente.

| Comando previsto de migración | Resultado |
| --- | --- |
| python -m alembic -x allow-development=true current | **No ejecutado** |
| python -m alembic -x allow-development=true upgrade 0003 | **No ejecutado** |
| python -m alembic -x allow-development=true current posterior | **No ejecutado** |
| python -m alembic -x allow-development=true check | **No ejecutado** |

No hay códigos de salida de Alembic que informar: la condición de mantenimiento
falló antes de esos comandos. No se utilizó upgrade head, downgrade, SQL manual
de modificación, terminación de sesiones PostgreSQL, pytest, fixtures o limpiezas.

## 5. Revisión final e integridad

La lectura final confirmó revisión **0002** y conteos **3/1/10/2**. No se aplicó
0003, por lo que no se verificó backfill ni columnas nuevas como resultado de una
migración. Esos controles siguen pendientes junto con Alembic check.

La intervención no creó perfiles, credenciales o sesiones, no cambió contraseñas
y no emitió JWT. No se afirma que no pueda haber actividad independiente del
servidor nuevo: precisamente por ello se detuvo el procedimiento. No se exportaron
datos ni se leyó contenido sensible para generar un informe de integridad ficticio.

## 6. Barrera y aislamiento

`require_initial_provisioning_enabled()` sigue lanzando
AprovisionamientoNoHabilitado de forma incondicional. Se comprobó sin monkeypatch
y no se modificó su archivo ni se agregó un mecanismo de activación.

No se accedió ni modificó usuarios_test ni su contenedor. No se detuvo PostgreSQL,
ningún contenedor o volumen, ni se cambiaron dependencias, código productivo,
configuración de conexión o proxy. El único entregable creado es este informe.

## 7. Recomendación de la operación anterior

**No iniciar la aplicación actualizada y no migrar todavía.** Se necesita aclarar
la ejecución nueva en 8000 y establecer de nuevo la ventana de mantenimiento.

Solicitar al responsable que cierre esa instancia o confirme expresamente que
pueden detenerse sus PIDs actuales, y que no iniciará/relanzará escritores durante
la operación. Después se deberán revalidar identidades de procesos —los PIDs pueden
cambiar— y comprobar ausencia de conexiones cliente capaces de escribir antes
de capturar línea base y ejecutar los comandos autorizados.

Una vez aclarado el bloqueo se conserva la decisión expresa de omitir respaldo y
la aceptación local de A02; no se requieren nuevas dependencias ni una excepción
de seguridad para reanudar. Si aparecen conexiones no atribuibles al proyecto,
no terminarlas indiscriminadamente: detenerse y consultar.

Tras completar una futura migración satisfactoria: comparar en memoria valores
preexistentes, verificar 0003/check/columnas/CHECK/defaults y backfill, conservar la
barrera cerrada y entregar resultados **antes de iniciar FastAPI o React**.
No improvisar restauraciones, borrados o downgrades ante anomalías.

Se detiene esta operación en el punto de control de escritores. No se avanzó a
despliegue, habilitación de aprovisionamiento ni Sprint 9.

## 8. Reanudación autorizada: Uvicorn detenido, conexiones pendientes

El responsable autorizó expresamente cerrar la nueva instancia en 8000 tras
revalidar workspace y padres. Mantiene la omisión del respaldo para datos de
práctica y la aceptación temporal de A02 local, con revisión antes de despliegue
externo. No se modificaron esas decisiones ni se pidieron de nuevo.

### Procesos revalidados y detenidos

- PID 26988: Python/Uvicorn app.main:app, padre 8804, referencia exacta al workspace,
  creado el 1 de noviembre de 2026 a las 14:44:27 -03:00, puerto 8000.
- PID 33588: hijo de 26988, misma entrada y workspace, mismo momento de creación,
  listener efectivo 127.0.0.1:8000.
- Se revalidaron creación, padre, workspace y entrada antes de intervenir. Se
  detuvo **33588** con Stop-Process (resultado satisfactorio). Al comprobar 26988
  ya había finalizado; no se intentó detener la terminal 8804.
- La inspección posterior no encontró procesos Python/Node/Uvicorn de aplicación
  restantes ni listeners en **8000, 8001 o 5173**. PostgreSQL en 5434 se mantuvo
  funcionando. No se detuvo Docker, un contenedor o volumen.

### Bloqueo nuevo: clientes PostgreSQL externos al control del servicio

Después de cerrar Uvicorn quedaron **cinco conexiones cliente**, excluida la propia
conexión transitoria de inspección:

| PID del backend PostgreSQL | Cliente clasificado | Estado | Origen observado |
| --- | --- | --- | --- |
| 382 | psql | idle | Socket Unix local del servidor |
| 1914 | psql | idle | Socket Unix local del servidor |
| 156348 | DBeaver | idle | Conexión TCP a través de la red Docker |
| 156349 | DBeaver | idle | Conexión TCP a través de la red Docker |
| 156350 | DBeaver | idle | Conexión TCP a través de la red Docker |

Los cinco son PIDs de PostgreSQL, **no PIDs de Windows que deban pasarse a
Stop-Process**. La clasificación proviene del identificador de aplicación, sin
imprimir cadenas completas ni el texto de sus consultas. En Windows se observaron
tres conexiones TCP a 5434 del proceso **dbeaver.exe PID 24372**; su comando no
acredita pertenencia exclusiva a este workspace. No se cerró DBeaver, porque
podría utilizar otras conexiones/proyectos.

Ninguna sesión tenía transacción abierta al observarse, pero idle no garantiza
ausencia de futuras escrituras. Las dos sesiones psql son anteriores al intento
de mantenimiento y no se atribuyeron a una terminal específica. No se ejecutó
pg_terminate_backend ni se cancelaron conexiones, de acuerdo con la restricción
de no terminar sesiones desconocidas indiscriminadamente.

**Se detuvo la operación antes de capturar la línea base de valores y migrar.**
Se requiere cierre de estas conexiones por su responsable, o autorización
específica para cerrarlas tras revalidar su identidad. No basta cerrar Uvicorn.

### Controles de base y resultado efectivo

Se verificó nuevamente configuración exacta usuarios_dev / 127.0.0.1:5434, identidad
efectiva usuarios_dev_admin y modo de solo lectura. Los controles se realizaron
con conexiones forzadas a lectura y cerradas con rollback.

| Control final | Resultado |
| --- | --- |
| Revisión de desarrollo | **0002** |
| Único head local / predecesor | **0003 / 0002**, comprobados sin conectar Alembic |
| Usuarios / credenciales / sesiones / intentos | **3 / 1 / 10 / 2** |
| Línea base exacta de valores para migración | **No capturada**: mantenimiento no garantizado |
| Alembic current / upgrade 0003 / current posterior / check | **No ejecutados**, sin códigos de salida |
| Backfill y columnas de 0003 como resultado de migración | **No aplicados** |
| Barrera productiva | **Cerrada**, rechazo comprobado sin monkeypatch |

Se leyeron únicamente identidad, revisión, conteos y metadatos de conexiones.
No se leyeron hashes, datos personales de perfiles o tokens, ni se exportaron
datos. No se ejecutaron pruebas, fixtures, limpiezas, respaldo, downgrade, DML o
DDL; no se accedió ni modificó usuarios_test o su contenedor.

### Recomendación vigente

**Mantener bloqueada la migración y no iniciar FastAPI ni React** hasta cerrar o
controlar las cinco conexiones y confirmar que no se reabrirán durante la ventana.
No hay una anomalía nueva de esquema que justifique modificar tablas o migraciones.
El obstáculo es operativo: no se puede garantizar ausencia de escritores.

Tras resolverlo, revalidar procesos, conexiones, destino y revisión; conservar la
línea base solo en memoria, ejecutar exclusivamente los comandos autorizados y
comparar integridad/backfill/estructura, sin valores sensibles en el informe.
Si los PIDs cambian, no usar ciegamente los de esta tabla. Ante anomalías conservar
estado y diagnosticar, sin borrar, restaurar o hacer downgrade.

Se mantiene el punto de control: **migración no ejecutada, aplicación detenida y
barrera cerrada; esperando instrucciones para las conexiones restantes**.

## 9. Reanudación final: sesiones autorizadas cerradas y migración completada

Fecha: **1 de noviembre de 2026**. Se recibió autorización expresa para terminar
solo las cinco sesiones previamente identificadas, previa revalidación. Se
mantienen la decisión del responsable de omitir respaldo para datos de práctica
y la aceptación temporal local de A02, con revisión antes de despliegue externo.

### 9.1 Identificación y cierre de conexiones

Se verificó nuevamente el destino configurado y efectivo usuarios_dev /
127.0.0.1:5434 y usuario usuarios_dev_admin. No se usaron PIDs antiguos sin
comparar su identidad actual. Las cinco sesiones conservaban los mismos valores
de backend_start, aplicación, origen y puerto observados anteriormente:

| PID PostgreSQL | Cliente | Inicio del backend, UTC | Origen / puerto | Estado al autorizar la terminación |
| --- | --- | --- | --- | --- |
| 382 | psql | 2026-10-28 20:44:36.553233 | Socket Unix / -1 | idle, sin transacción |
| 1914 | psql | 2026-10-28 21:01:09.556532 | Socket Unix / -1 | idle, sin transacción |
| 156348 | DBeaver | 2026-11-01 17:40:17.261199 | 172.20.0.1 / 48442 | idle, sin transacción |
| 156349 | DBeaver | 2026-11-01 17:40:17.384883 | 172.20.0.1 / 48448 | idle, sin transacción |
| 156350 | DBeaver | 2026-11-01 17:40:17.538429 | 172.20.0.1 / 48460 | idle, sin transacción |

Se usó SELECT pg_terminate_backend exclusivamente para esos cinco PIDs. Cada
sentencia filtró además base, nombre de aplicación revalidado, backend_start,
origen, puerto, state=idle, xact_start IS NULL y backend_type=client backend,
excluyendo la propia conexión. **Las cinco terminaciones devolvieron true**.
No se terminó ninguna sesión adicional, base ajena o proceso de sistema.

Durante **10 segundos** de observación no hubo reconexiones. Se repitió el control
de clientes antes y después de cada comando Alembic y al cerrar la verificación:
no aparecieron otros clientes. No se cerró la aplicación DBeaver completa ni sus
otras bases; solo las cinco sesiones autorizadas de usuarios_dev.

La inspección de procesos confirmó que no había Uvicorn/FastAPI/Vite del workspace
ni listeners en 8000, 8001 o 5173. PostgreSQL siguió activo en 5434. Los procesos
de aplicación habían sido detenidos en los pasos históricos; en esta reanudación
final no hubo que detener nuevos procesos Windows ni iniciar servicios.

### 9.2 Línea base de integridad

Con mantenimiento establecido se confirmó revisión **0002**, único head local
**0003**, predecesor **0002** y ausencia de las columnas nuevas. Se volvió a leer
el archivo de migración y se comprobó que no cambiara durante la operación.

La línea base se mantuvo **solo en memoria** dentro de un único proceso de control,
sin respaldo, archivos de datos ni exportaciones. Se leyeron ordenadamente todos
los campos preexistentes de las cuatro tablas para comparar valores exactos
después: perfiles, hashes/fechas de credenciales, sesiones y registros de intentos.
**No se imprimieron valores personales, hashes, claves, contraseñas o tokens.**

También se conservó en memoria inventario de tablas, metadatos de columnas,
definiciones de PK/FK/CHECK e índices de los esquemas de usuario. Las conexiones
de inspección estaban forzadas a solo lectura; Alembic utilizó su conexión de
migración autorizada separada, con la protección de desarrollo existente.

| Tabla | Antes | Después |
| --- | ---: | ---: |
| usuarios | **3** | **3** |
| usuario_credenciales | **1** | **1** |
| auth_sesiones | **10** | **10** |
| auth_intentos | **2** | **2** |

Estos son los conteos de la línea base efectiva de esta operación, no únicamente
una repetición de los antecedentes del preflight.

### 9.3 Comandos ejecutados y resultados

Desde backend, mediante el ejecutable del entorno existente; `-B` evita generar
bytecode y no altera las protecciones o revisiones de Alembic:

```powershell
.\.venv\Scripts\python.exe -B -m alembic -x allow-development=true current
.\.venv\Scripts\python.exe -B -m alembic -x allow-development=true upgrade 0003
.\.venv\Scripts\python.exe -B -m alembic -x allow-development=true current
.\.venv\Scripts\python.exe -B -m alembic -x allow-development=true check
```

| Comando | Código de salida | Resultado efectivo |
| --- | ---: | --- |
| current previo | **0** | **0002** |
| upgrade 0003 | **0** | Migración terminada |
| current posterior | **0** | **0003 (head)** |
| check | **0** | **No new upgrade operations detected.** |

Se verificó cada código antes de seguir. No se ejecutó upgrade head, downgrade,
pytest, fixtures o SQL manual de modificación. La inspección de procesos y de
conexiones se repitió entre comandos. No se debilitaron migrations/env.py ni las
guardas del proyecto.

### 9.4 Verificaciones finales de estructura y datos

La comparación exacta en memoria de los valores preexistentes resultó **igual**
para las cuatro tablas. Por lo tanto:

- UUID, nombres, apellidos, emails, roles, estados y fechas previos conservados,
  sin mostrar su contenido en el informe.
- Hash y fechas de la credencial existente conservados; ninguna credencial nueva
  ni cambio de contraseña.
- Sesiones, expiraciones y revocaciones previas conservadas; no se crearon o
  revocaron sesiones de autenticación por la migración. Terminar conexiones de
  PostgreSQL no equivale a revocar filas de auth_sesiones.
- Registros de intentos, sus claves opacas, contadores y fechas conservados.
- Inventario de tablas e índices igual al previo. Columnas previas, nulabilidad,
  defaults y restricciones PK/FK/CHECK previas conservados. Sin diferencias
  inesperadas en los objetos inspeccionados.

Las únicas adiciones de columnas fueron:

| Columna | Tipo / nulabilidad | Default final | Valor histórico observado |
| --- | --- | --- | --- |
| usuario_credenciales.debe_cambiar_password | boolean / NOT NULL | Ninguno | false en la credencial existente |
| usuario_credenciales.password_inicial_hash | text / NULL permitido | Ninguno | null |
| auth_sesiones.restringida | boolean / NOT NULL | Ninguno | false en las diez sesiones |

La única adición PK/FK/CHECK fue **ck_credenciales_password_inicial**, con expresión
equivalente a `NOT debe_cambiar_password OR password_inicial_hash IS NOT NULL`.
La nulabilidad de las banderas también quedó verificada en metadatos; los defaults
temporales false se retiraron. No se forzó cambio a usuarios históricos ni se
asignaron contraseñas automáticamente.

La comprobación independiente de require_initial_provisioning_enabled volvió a
producir **AprovisionamientoNoHabilitado**. La barrera no se modificó ni se abrió.

### 9.5 Incidencias, límites y estado final

No hubo reconexiones, errores de Alembic o discrepancias de integridad en esta
reanudación final. Los bloqueos anteriores se conservan arriba como historial;
no deben interpretarse como el estado final de la migración.

Se omitió respaldo por decisión expresa del responsable. La línea base en memoria
no es un respaldo restaurable; no se exportó ni persistió. El riesgo de pérdida o
reconstrucción continúa asumido para este entorno de práctica. A02 sigue aceptado
temporalmente solo en local y debe revisarse antes de exposición externa.

No se accedió ni modificó usuarios_test o su contenedor. No se detuvieron Docker,
PostgreSQL u otros servicios, ni se eliminaron contenedores, volúmenes o tablas.
No se cambiaron dependencias, configuración JWT, proxy, contratos o código
productivo. No se realizaron login, creación de usuarios, aprovisionamiento ni
pruebas automatizadas contra desarrollo.

**Recomendación:** el esquema ya es compatible con el backend actual; se puede
revisar y autorizar el próximo inicio controlado de FastAPI y React, definiendo
explícitamente puertos, destino y proxy para no confundir pruebas con desarrollo.
No se arrancan automáticamente ni se considera publicado el sistema por haber
completado la migración. La puesta en marcha y las pruebas manuales posteriores
requieren la revisión solicitada; el aprovisionamiento permanece fuera de alcance.

**Operación finalizada: usuarios_dev en 0003, integridad conservada, barrera cerrada,
FastAPI/React detenidos. Se espera revisión antes de iniciar los servicios.**
