# Sprint 9.3E: integración PostgreSQL, pgvector y esquema RAG

Fecha: **3 de noviembre de 2026**. **Estado vigente: COMPLETADO**, continuación
verificada a las **19:33 -03:00**, según **sección 7**. usuarios_dev funciona con
PostgreSQL 18.6, vector 0.8.2 y revisión Alembic 0004_rag; FastAPI está operativo.
Las secciones 1–6 conservan como historial la primera intervención, detenida a
las 17:27 por comparación textual de dos CHECK; ese bloqueo quedó resuelto.

## 1. Autorización y operaciones ejecutadas

La autorización permitió mantenimiento real, respaldo, restauración en volumen
nuevo, sustitución y esquema RAG secuenciales. También exigió no avanzar a la
siguiente fase ante un fallo. No se convirtió la comparación fallida en permiso
para ignorarla o modificar restricciones.

Revalidaciones iniciales:

- Docker responde; desarrollo y pruebas running/healthy.
- Imagen candidata existente, con la identidad de 9.3C.
- Origen: usuarios_dev / 127.0.0.1:5434, PostgreSQL **18.6**, revisión **0003**.
- Volumen original `api-usuarios-clean_postgres_data` e imagen anterior intactos.
- RAM inicial **1,182 GiB**, carga física 84 %, D: libre **105,22 GiB**.
  No se volvió a bloquear por la referencia preventiva previa de 2 GiB: se aplicó
  la autorización operativa, sin compilaciones, descargas o cargas de modelos.

Se revalidó por CIM la instancia FastAPI previa: padre **16760**, hijo/listener
**17948**, creación 11:43:07, ejecutables y lanzador del workspace, ambos flags IA
y observador presentes y aprovisionamiento ausente. Se detuvo exclusivamente esa
instancia. No se detuvieron React, Docker, PostgreSQL original, Ollama o WSL.

Con el backend detenido, una conexión controlada READ ONLY comprobó **cero otros
clientes** de usuarios_dev. Se obtuvo una línea base privada de datos/metadatos;
después del dump se volvió a comprobar ausencia de clientes y coincidencia íntegra
del origen. Son comprobaciones puntuales y comparación antes/después, no una
restricción global de acceso permanente a PostgreSQL.

## 2. Respaldo real protegido

Ubicación fuera del repositorio:

```text
D:\Downloads\api-usuarios-clean-backups\93e-20261103\
```

ACL con herencia deshabilitada, acceso FullControl solo para el usuario Windows
actual y SYSTEM mediante SIDs. No se incorporaron respaldos a Git o al informe.

| Archivo | Tamaño | Verificación |
| --- | ---: | --- |
| usuarios_dev.dump | **11962 bytes** | pg_dump custom, tamaño positivo, pg_restore --list correcto, SHA-256 verificado |
| roles.sql | **546 bytes** | pg_dumpall --globals-only --no-role-passwords, tamaño positivo, SHA-256 verificado |

El manifiesto SHA-256 queda en `backup-manifest.private.json` dentro del mismo
directorio protegido. **No se imprimen las huellas**, credenciales o contenido de
datos. `baseline.private.json` conserva solo metadatos, conteos y huellas internas
de comparación, no filas de negocio. Es información protegida y no debe publicarse.

Los dumps se generaron con `-f` dentro del contenedor original y se copiaron con
docker cp, sin redirección binaria de PowerShell. Quedan también sus copias
temporales `/tmp/usuarios-dev-93e.dump` y `/tmp/roles-93e.sql` en el contenedor
original; no se limpiaron sin autorización. Son archivos en su capa temporal,
**no cambios de tablas ni del volumen original**.

Incidencia inicial: la construcción de una regla ACL con SYSTEM como nombre no
se resolvió. Se corrigió dentro de la misma fase usando SecurityIdentifier y se
verificaron las dos reglas antes de crear el respaldo. No se generaron dumps
con una ACL sin verificar ni se inició la sustitución por ese error.

## 3. Restauración aislada efectivamente realizada

Recursos nuevos, conservados para revisión:

| Recurso | Identidad / estado final |
| --- | --- |
| Volumen nuevo | **api-usuarios-clean-pgvector-93e-data** |
| Contenedor de restauración | **api-usuarios-clean-93e-restore** |
| ID completo | `c09e8fadf49ac959bd8529fe4b16e7e9d7cf2c0b78d321c8bbca6bde338f100d` |
| Imagen | Candidata pgvector 18-0.8.2-93c fijada por identidad de 9.3C |
| Red y puertos | network none, sin puertos publicados, PostgreSQL sin escucha TCP |
| Almacenamiento | Solo volumen nuevo en /var/lib/postgresql |
| Recursos | 256 MiB, sin swap adicional, 0,5 CPU, shared_buffers 32 MiB |
| Estado final | **Detenido**, sin OOM, volumen retenido |

Se verificaron las huellas de ambos archivos antes de restaurar. Se inicializó
solo el nuevo clúster, con un rol técnico nuevo y contraseña aleatoria no impresa;
se restauraron roles con ON_ERROR_STOP y la base con pg_restore --create
--exit-on-error. Las credenciales DB existentes se aplicaron únicamente en la
copia mediante SQL parametrizado/citado por stdin, sin argumentos o logs de secretos.
No se usó trust de red ni se cambió la contraseña del origen.

El rol técnico de inicialización queda en el clúster nuevo; su deshabilitación
programada era posterior a aprobar la comparación y **no llegó a ejecutarse**.
La copia está detenida y aislada. Antes de cualquier promoción futura hay que
deshabilitar ese rol técnico y revisar la configuración; no es un candidato ya
aprobado para producción/desarrollo.

### Resultado de comparación

Comparación privada entre origen congelado y copia restaurada:

| Control | Resultado |
| --- | --- |
| Todas las filas de tablas public, multiconjunto completo | **Coinciden** |
| Conteos por tabla | **Coinciden** |
| PostgreSQL/encoding/locale/propietario/ACL de base | **Coinciden** |
| Columnas y tipos | **Coinciden** |
| Índices | **Coinciden** |
| Propietarios y permisos de tablas/esquema | **Coinciden** |
| Atributos de roles originales, excluyendo el técnico nuevo | **Coinciden** |
| Revisión Alembic | **0003 en ambos** |
| Restricciones | **43 en ambos; dos textos no coinciden** |

**Bloqueo exacto:** el comparador exige igualdad textual de pg_get_constraintdef.
PostgreSQL reformuló dos CHECK durante dump/restauración:

- `usuarios.ck_usuarios_rol`.
- `auth_intentos.ck_intentos_ambito`.

En origen el CHECK convierte un array de constantes varchar a text[] antes de
compararlo mediante ANY. En la copia convierte cada constante varchar a text
dentro del array. Las constantes y columnas son las mismas. La reformulación
es consistente con equivalencia de esos CHECK y **no demuestra corrupción ni
incompatibilidad de pgvector**. Tampoco se presenta el fallo textual como pérdida
de filas: la comparación de datos completa sí pasó.

Sin embargo, la operación de verificación devolvió fallo; conforme a la instrucción
de parada, **no se relajó automáticamente el comparador ni se inició la fase 2**.
Los detalles de ambas definiciones quedan en
`constraint-difference.private.json`, fuera del repositorio. Falta cerrar esta
verificación semántica de restricciones para aprobar la copia, no repetir un
preflight general o implementar almacenamiento vectorial temporal.

## 4. Recuperación segura y estado de servicios

Tras identificar la diferencia:

1. Se revalidaron etiqueta/ID/montaje/red del contenedor nuevo y se detuvo solo
   esa copia para liberar recursos; no se eliminó el contenedor ni su volumen.
2. Se comprobó otra vez por READ ONLY que el origen coincidía **exactamente con
   la línea base anterior al respaldo**, incluidos datos y metadatos/revisión.
3. Se reinició únicamente FastAPI, con su configuración anterior:

```powershell
.\.venv\Scripts\python.exe -B -m app.presentation.cli.local_server --environment local-development --enable-llm --observe-llm --host 127.0.0.1 --port 8000
```

La restauración de flags previos no ejecutó inferencias ni cargó modelos. No se
añadió aprovisionamiento. Inicio oculto, logs en el directorio protegido del
respaldo, sin habilitar logging de acceso/cuerpos. Nuevo padre **16448**, listener
**13624** en 127.0.0.1:8000. Application startup complete y sin ERROR/Traceback.

Comprobaciones finales anónimas GET:

- FastAPI /openapi.json: **200**, ruta IA existente presente.
- React /login: **200**; Vite no se reinició.
- RAM final **1,189 GiB**, carga física 84 %; sin OOM reportado en los contenedores.

No hubo login/logout por scripts ni solicitudes POST a la aplicación. Las
comprobaciones no son una nueva prueba autenticada ni una prueba RAG.

| Recurso previo | Conservación final |
| --- | --- |
| PostgreSQL desarrollo `ce41dbdca5f0` | Running, misma imagen, mismo inicio 2026-11-03T09:38:30.533051573Z |
| api-usuarios-clean_postgres_data | Mismo montaje; nunca usado para la restauración |
| PostgreSQL pruebas `80172da97281` | Running, mismo inicio 2026-11-03T09:38:55.177531537Z |
| usuarios_test | Sin conexiones SQL, exec, migraciones o cambios por este sprint |
| Imagen anterior | Conservada |
| React, Ollama, Docker | Sin detenciones/reinicios por esta intervención |

No se afirma que otros usuarios no puedan escribir después de reabrir FastAPI.
Por eso la copia restaurada **no debe promoverse posteriormente sin congelar otra
vez escritores y revalidar frescura del respaldo**; podría haberse quedado atrás.

## 5. Estado por fase y archivos

| Fase | Estado |
| --- | --- |
| 1: respaldo | **Completado y verificado** |
| 1: restauración SQL | **Completada en volumen nuevo** |
| 1: aprobación de integridad | **Detenida por dos diferencias textuales de CHECK** |
| 2: override y sustitución | **No ejecutada** |
| 3: CREATE EXTENSION y revisión RAG posterior a 0003 | **No ejecutada** |
| Recuperación del servicio original | **Completada** |

Archivos del repositorio creados:

- `infra/pgvector/maintenance_93e.py`: fases explícitas backup/restore, sin
  ejecución al importar, fallos saneados y estado privado fuera del repositorio.
  Es una herramienta acotada a esta intervención, con IDs/rutas explícitos y
  guardas de no sobrescritura; no un comando genérico de despliegue. Invocación
  con PYTHONPATH=backend/src y el Python del backend, fase por fase.
- `docs/sprint-9-3e-integracion-pgvector.md`: este informe.

No se editaron Compose, .env, aplicación, contratos o migraciones. No se creó
una migración RAG todavía porque no se alcanzó esa fase. No se ejecutaron tests
aislados repetidos, Alembic, CREATE EXTENSION, generación/embeddings, builds,
descargas, DROP DATABASE, CASCADE, prune o eliminación de recursos anteriores.

## 6. Bloqueo y continuación pendiente

**No se cumplió todavía el objetivo completo**: usuarios_dev sigue en su imagen
original PostgreSQL 18.6, revisión 0003, sin vector activado o tablas RAG nuevas.
La causa de parada es concreta: aprobar correctamente la equivalencia de dos
restricciones reformuladas, sin sustituir la comprobación por ignorar constraints.
Los datos restaurados y originales coinciden según la verificación realizada.

Se conserva el respaldo protegido, el volumen original, la imagen anterior y la
copia nueva detenida. No se limpian ni sobrescriben. Se requiere revisión y
reanudación expresa tras esta parada; cualquier continuación debe considerar
las posibles escrituras posteriores al reinicio del backend y cerrar de nuevo
la ventana antes de respaldar/promover una copia vigente.

**PARCIAL, detenido con origen verificado y FastAPI recuperado.** No se ejecuta
automáticamente la siguiente fase ante la comprobación fallida.

## 7. Continuación expresamente autorizada: COMPLETADA

### 7.1 Equivalencia de restricciones: APROBADA

Se revisó el comparador y se añadió una allowlist de **dos pares de expresiones
completas**, vinculados a tabla/nombre de restricción. No se quitan casts mediante
regex genérica ni se omiten restricciones. Para cualquier otro CHECK o cualquier
variación fuera de esos pares continúa exigiéndose igualdad estricta.

Demostración para estos pares: el cast PostgreSQL varchar[] → text[] aplica el
cast a cada elemento y conserva orden, forma y NULL. Construir el mismo array
con esos elementos convertidos a text produce los mismos valores, tipo y collation
efectiva. Ambos lados convierten la misma columna a text y utilizan el mismo
operador de igualdad con ANY; por tanto tienen igual lógica de tres valores,
incluido el resultado desconocido para NULL que un CHECK admite. No se generalizó
esta propiedad a otros tipos/casts, arrays de expresiones, operadores o collations.

Se evaluaron ambos lados en PostgreSQL con valores permitidos/prohibidos, NULL,
vacío, mayúsculas/minúsculas, espacios y Unicode mediante IS DISTINCT FROM:
**cero diferencias**. Además se comprobaron convalidated/conenforced en origen
y copia. Los casos de muestra corroboran la justificación del par restringido;
no se presentan como prueba exhaustiva de cualquier SQL arbitrario.

Pruebas offline nuevas: **15 aprobadas**, 1,55 s, que incluyen rechazo de cambios
de operador, valor, columna, OR true, NULL agregado, collation y tabla ajena.
El resto de datos/metadatos conserva comparación estricta.

### 7.2 Copia restaurada actualizada: SÍ, vigente y verificada

Se revalidó FastAPI padre **16448**, hijo **13624**, creación exacta 17:26:36,
ejecutables y lanzador, listener loopback y flags previos. Se detuvo solo esa
instancia para volver a cerrar escritores; React/Ollama/Docker/pruebas continuaron
sin intervención. Se exigió ausencia de otros clientes antes de comparar.

La base original **no tenía cambios respecto del respaldo**: comparación completa
de filas y metadatos con la línea base privada aprobada. La copia restaurada también
coincidía con esa base vigente usando la equivalencia restringida. Por ello no fue
necesario generar otro dump o reconstruir/sobrescribir un volumen. Se repitió la
comprobación antes de promover y tras conectar al servicio final.

**Rol técnico:** PostgreSQL rechazó quitar SUPERUSER al rol bootstrap inicial,
una restricción propia del servidor. Dentro de fase B se sustituyó esa operación
por `NOLOGIN CONNECTION LIMIT 0 PASSWORD NULL`. Se comprobó que no tenía miembros,
no podía iniciar sesión y carecía de contraseña. El atributo SUPERUSER interno
del bootstrap permanece por imposición del servidor; no se afirma que fue eliminado.
No se cambió ningún rol de negocio ni las credenciales del usuario DB existente.

Una primera consulta sintética de equivalencia tuvo un paréntesis incorrecto al
extraer el cuerpo del CHECK; se corrigió antes de aprobar fase A. No cambió datos
o restricciones. Ninguno de estos errores se ignoró para saltar a una fase siguiente.

### 7.3 Sustitución controlada: APROBADA

Se validó la configuración Compose combinada **en memoria**, sin publicar sus
variables secretas: una sola definición de servicio, un montaje en el destino
esperado, puerto loopback 5434, mismas credenciales, red, restart y healthcheck.

Se detuvo primero la copia de ensayo y luego PostgreSQL original. Compose recreó
solo el servicio postgres de desarrollo con el volumen restaurado. Nunca hubo
dos servidores corriendo sobre ese volumen. El procedimiento disponía de retorno
al Compose base y volumen original si fallaban inicio o comparación; **no fue
necesario ejecutar esa reversión**.

| Propiedad final | Evidencia |
| --- | --- |
| Contenedor de desarrollo | `02f8d1472a4ba18758cfc1a27f8295aa7e82ee2f2d77cdc4c2135ca62db90493` |
| Nombre de servicio conservado | api-usuarios-clean-postgres-1 |
| Imagen | `api-usuarios-clean/pgvector@sha256:a1336b54a1b49085474132cceb0636b314707b011fdb242afa694ae08ffcc3e6` |
| Volumen promovido | **api-usuarios-clean-pgvector-93e-data** |
| Montaje | /var/lib/postgresql, PGDATA 18/docker heredado |
| Puerto | **127.0.0.1:5434 → 5432** |
| Inicio | 2026-11-03T22:29:40.283327818Z, 19:29:40 -03:00 |
| Healthcheck | **healthy** |
| Conexión con contraseña existente | **Correcta** |
| Antes de reabrir escritores | Datos, esquema anterior, permisos y revisión 0003 coincidentes |
| OOM | false |

El override se creó inicialmente como `compose.pgvector.yaml` y se renombró a
**compose.override.yaml** al finalizar, para que el arranque predeterminado
`docker compose up` no vuelva inadvertidamente al volumen antiguo. Se validó por
lectura que la configuración predeterminada usa la imagen/volumen nuevos. No se
reinició el contenedor por ese cambio de nombre. El archivo Compose base permanece
sin editar. El Compose de pruebas explícito continúa separado.

Operación normal de desarrollo, desde la raíz:

```powershell
docker compose -f compose.yaml -f compose.override.yaml up -d --no-deps --pull never postgres
```

No usar **solo** `-f compose.yaml` para operación normal: representa la configuración
anterior y cambiaría el volumen. El retorno al volumen antiguo requiere revisar
datos escritos desde esta promoción y una autorización de reversión.

### 7.4 pgvector y esquema definitivo RAG: APROBADOS

Con el backend todavía detenido se verificó nuevamente usuarios_dev / 127.0.0.1:5434,
imagen/volumen nuevos y revisión única 0003. Por conexión administrativa controlada
se ejecutó CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA public VERSION 0.8.2.
Se comprobó su versión y después se aplicó exclusivamente:

```powershell
# Ejecutado con el Python del backend; no se usó target=test.
.\backend\.venv\Scripts\python.exe -B -m alembic -c backend/alembic.ini -x allow-development=true upgrade 0004_rag
```

Revisión nueva **0004_rag**, posterior a **0003**. Tablas creadas en public:

- rag_documentos y rag_documento_permisos.
- rag_versiones y rag_paginas.
- rag_fragmentos y rag_fragmento_paginas.
- rag_espacios_embeddings y rag_embeddings.
- rag_ingestas.

Incluyen propietario/ACL explícitos, visibilidad PRIVATE por defecto, versiones e
idempotencia por huella, páginas físicas/offsets, procedencia mediante FK compuestas,
versión activa perteneciente al documento, espacios de embeddings versionados,
modelo nomic-embed-text, dimensión 768 y columna **vector(768)** no nula con norma
positiva. Hay claves únicas, índices btree y exclusión por índice parcial de
ingestas activas duplicadas. No se construyeron índices aproximados pesados.

Los UUID internos de fragmento tienen además identificador_estable de 64 caracteres
para la huella determinista del núcleo 9.3B. La adaptación entre DTO/espacio interno
y IDs de repositorio queda para los adaptadores RAG. No se añadió una selección
pública de modelo o contexto ni se modificó POST /api/v1/ia/consultas.

**Límites explícitos del esquema:** no se activó RLS ni repositorios operativos;
la aplicación futura deberá aplicar ACL antes de top-k y revalidarlas al entregar.
La publicación LISTA requiere validar cobertura de embeddings y procedencia del
texto bajo transacción en el futuro repositorio. No se afirma que una FK por sí
sola pruebe esos invariantes semánticos. No hay nuevas rutas RAG, memoria o tools.
La migración no crea vector administrativamente ni lo elimina al revertir;
downgrade destructivo requiere procedimiento explícito y se bloquea por defecto.

### 7.5 Pruebas y datos conservados

Se ejecutó `infra/pgvector/verify_rag_93e.py` exclusivamente contra usuarios_dev
promovida, con guardas de imagen/volumen/destino. **17 controles aprobados**:

- Extensión 0.8.2, columna vector(768), constraints e índices válidos.
- Filas/metadatos de todas las tablas preexistentes conservados, salvo el avance
  esperado de alembic_version de 0003 a 0004_rag.
- Inserción sintética 768 y coseno identidad/ortogonal correctos.
- Rechazo de versión activa de otro documento, página de otra versión y permiso
  de ingesta sin lectura.
- Rechazo de dimensión errónea, vector cero, dimensión/selector de modelo inválidos.
- Idempotencia de versión e ingesta activa duplicada.

Las fixtures solo afectaron tablas RAG dentro de una transacción **ROLLBACK**.
Se utilizó un UUID de propietario existente únicamente en memoria para probar FK,
sin imprimirlo o modificar usuarios. Se verificó después que el snapshot completo
coincidía con el anterior a esas fixtures y que las nueve tablas RAG estaban vacías.
No se persistió el PDF, documentos, prompts, respuestas o embeddings reales.

Pruebas aisladas finales desde backend:

```powershell
.\.venv\Scripts\python.exe -B -m pytest -q tests/rag tests/ia -p no:cacheprovider --basetemp=.pytest-tmp-93e-final --tb=short
```

**359 aprobadas, sin fallos, 15,71 s**: 305 IA existentes, 39 núcleo RAG y 15 nuevas
del comparador. No se ejecutó la suite PostgreSQL de usuarios_test. Permanece el
aviso previo Starlette/TestClient; no se cambiaron dependencias para ocultarlo.

### 7.6 FastAPI, recursos y estado final

Se reinició solo el backend detenido con su configuración anterior, incluidos
enable-llm y observe-llm y sin aprovisionamiento. Padre **13384**, listener hijo
**30616**, 127.0.0.1:8000. Startup completo, sin ERROR/Traceback. Logs bajo ACL
protegida en backend-resumed.stdout.log/backend-resumed.stderr.log, sin trazas de
HTTP o contenido. No se automatizaron login/logout ni solicitudes de generación.

Comprobaciones posteriores:

| Control | Resultado |
| --- | --- |
| FastAPI /openapi.json | **200** |
| React /login | **200**, sin reiniciar Vite |
| Conexión DB de lectura con credenciales existentes | **Correcta** |
| PostgreSQL | **18.6 (Debian 18.6-1.pgdg13+2)** |
| vector | **0.8.2** |
| Alembic | **0004_rag** |
| Ollama /api/ps | **200, cero modelos cargados** |
| RAM final, 19:33:12 | **0,594 GiB**, carga 92 % |

Hubo una lectura intermedia de **0,455 GiB** antes de la promoción con dos
PostgreSQL disponibles. Se mantuvo la secuencia de un único candidato de ensayo,
se cerró ese servidor antes de iniciar el definitivo y no hubo OOM reportado.
La muestra Docker final informó 32,18 MiB para el servicio en ese instante; no
representa pico ni todo Docker/WSL. No se certifica rendimiento sostenido o ausencia
de paginación. Con el margen final escaso no se ejecutaron nuevas cargas ni modelos.
El responsable debe evitar trabajos pesados adicionales simultáneos.

### 7.7 Respaldos, reversión y archivos

**Conservados y comprobados:** respaldo/roles/manifiesto fuera del repositorio,
ACL protegida, imagen anterior y volumen **api-usuarios-clean_postgres_data**.
Los SHA-256 del respaldo original siguen coincidiendo, sin imprimirse. No se
generó respaldo nuevo porque no había diferencias de datos antes del corte.

Compose recreó el contenedor original del servicio; las copias temporales de
/tmp que existían en su capa no se consideran respaldos duraderos. Los archivos
principales protegidos, su manifiesto y el volumen anterior permanecen conservados.
El volumen original no se restauró, migró ni reutilizó como candidato; PostgreSQL
solo realizó su cierre normal. No se promete identidad binaria de sus archivos
frente a antes de ese cierre.

El contenedor **api-usuarios-clean-93e-restore** queda detenido, junto a su volumen
ahora promovido. **No arrancarlo:** comparte ese volumen con el servicio activo.
No se eliminaron recursos de reversión. La imagen anterior no contiene vector:
nunca montarle el volumen nuevo que ya tiene esa extensión.

Tras reabrir FastAPI, el volumen antiguo puede quedar desactualizado. Revertir a
él ahora exige congelar escritores y reconciliar los cambios posteriores; no usar
el retorno automático preapertura del helper como reversión tardía. La reversión
de revisión RAG tampoco debe eliminar documentos o extensión por CASCADE.

Archivos creados/modificados en esta continuación:

- `infra/pgvector/maintenance_93e.py`: comparación restringida, revisión esperada
  parametrizable, deshabilitación bootstrap y promoción con rollback preapertura.
- `backend/tests/rag/test_maintenance_checks.py`: 15 pruebas offline.
- `compose.override.yaml`: imagen fijada y volumen externo nuevo; base sin editar.
- `backend/migrations/versions/0004_rag.py`: nueve tablas RAG y sus restricciones.
- `infra/pgvector/verify_rag_93e.py`: comprobaciones reales y fixtures con rollback.
- Este informe: continuación y estado vigente, conservando el historial.

Usuarios_test mantiene contenedor **80172da97281**, imagen original e inicio
**2026-11-03T09:38:55.177531537Z**, sin SQL, exec, migraciones o cambios por esta
intervención. No se afirma comparación de sus filas porque no se accedió a ellas.
React, Ollama, Docker y WSL no se detuvieron. No hubo inferencias, OCR, procesamiento
del PDF, embeddings reales, descargas, compilaciones o limpieza destructiva.

**Resultado final:** equivalencia APROBADA; copia vigente SÍ; PostgreSQL con
pgvector activo SÍ; Alembic 0004_rag y tablas RAG APROBADOS; FastAPI OPERATIVO;
usuarios_test sin intervención; respaldos y volúmenes conservados.
**Integración completada. Se detiene sin iniciar el RAG operativo.**
