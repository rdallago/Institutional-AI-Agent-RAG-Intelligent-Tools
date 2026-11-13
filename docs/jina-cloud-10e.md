# Sprint 10E — Respaldo y restauración verificada: preparación

**Actualización final: ejecución autorizada completada el 10/11/2026. GO para
considerar el respaldo verificado.** Las secciones de preparación se conservan
como antecedente; sus estados «NO EJECUTADO» quedan supersedidos por la sección 5.

Fecha: 10 de noviembre de 2026, America/Buenos_Aires.
**GO para solicitar autorización; NO-GO para declarar respaldo/restauración verificados.**
No se ejecutó pg_dump, no se creó directorio ni base, no se restauró contenido.

## 1. Comprobaciones reales READ ONLY

| Comprobación | Resultado |
|---|---|
| Contenedor | api-usuarios-clean-postgres-1, healthy, activo hace 3 días |
| Puerto | 127.0.0.1:5434 → 5432 |
| pg_dump / pg_restore | Ambos 18.6, Debian 18.6-1.pgdg13+2 |
| pgvector | 0.8.2 |
| Tamaño usuarios_dev | 15.275.711 bytes |
| Disco D: libre | 112.664.690.688 bytes, aproximadamente 104,9 GiB |
| /tmp y volumen PostgreSQL: disponible reportado | 992.597.048 KiB en cada ruta; pertenecen al mismo almacenamiento, no sumar |
| Credencial existente | CONNECT, superusuario y CREATEDB; no se mostró identidad ni contraseña |
| Tablas public sin SELECT para el rol | 0 |
| DDL activo / otras transacciones en usuarios_dev | 0 / 0 al consultar |
| Locks no concedidos del servidor | 0 al consultar |
| Revisión | 0005_agent_memory |
| Documentos / versiones / fragmentos / vectores | 1 / 2 / 864 / 864 |
| Versión activa | 7cb4e79c-747d-574a-8abb-0ebcb2e07636 |

La conexión Python comprobó destino exacto y transaction_read_only=on, usó
default_transaction_read_only, connect_timeout=3, statement_timeout=5000 y rollback.
No se leyeron conversaciones, usuarios ni hashes de contraseñas. La integridad
de hashes/offsets detallada procede de 10D; se repetirá sobre origen y restauración.
La ausencia de concurrencia es una observación puntual, no un bloqueo de futuros
escritores. Revalidar inmediatamente antes de ejecutar.

El padre `D:\Downloads\api-usuarios-clean-backups` pertenece al usuario actual y
tiene herencia habilitada, incluyendo Usuarios autentificados Modify y Usuarios
ReadAndExecute. **No es un destino privado por sí solo.** No se cambiaron sus ACL.
Se necesita una subcarpeta nueva protegida, restringida al usuario actual y SYSTEM.
No se escribirán datos sensibles antes de comprobarla. Hay espacio preliminar
holgado; el tamaño del dump y restauración se comprobará realmente después.

## 2. Procedimiento preparado, NO ejecutado

La siguiente operación requiere autorización expresa. Un único UUID identifica
carpeta, archivo temporal del contenedor y base nueva `rag_restore_10e_<UUID32>`.
Nunca reutilizar usuarios_dev, usuarios_test o la base sintética de 10C.

Primero generar los nombres y comprobar que no existen. Crear la subcarpeta
privada sin modificar el padre, establecer DACL protegida para SID del operador y
SYSTEM (FullControl con herencia a hijos), comprobar propietario y todas las ACE.
No guardar nada si existen otras ACE, enlaces/reparse points o permisos amplios.
Conservar informes privados y originales; no sobrescribir ni limpiar automáticamente.

```powershell
# SOLO DESPUÉS DE AUTORIZACIÓN. Detenerse ante cualquier error.
$ErrorActionPreference='Stop'
$restoreRun=[guid]::NewGuid().ToString('N')
$backupDir="D:\Downloads\api-usuarios-clean-backups\10e-$restoreRun"
$restoreDb="rag_restore_10e_$restoreRun"
$containerDump="/tmp/usuarios-dev-10e-$restoreRun.dump"
# Crear y verificar ACL privada antes de ejecutar estos comandos de respaldo.
docker exec api-usuarios-clean-postgres-1 sh -c 'exec pg_dump -U "$POSTGRES_USER" -d usuarios_dev --format=custom --lock-wait-timeout=5s --file="$1"' sh $containerDump
if ($LASTEXITCODE -ne 0) { throw 'Fallo pg_dump; detenerse' }
docker cp "api-usuarios-clean-postgres-1:$containerDump" "$backupDir\usuarios_dev.dump"
if ($LASTEXITCODE -ne 0) { throw 'Fallo copia; detenerse' }
Get-FileHash -Algorithm SHA256 -LiteralPath "$backupDir\usuarios_dev.dump"
```

Antes de copiar, verificar permisos del archivo temporal del contenedor: ejecutar
el respaldo bajo umask 077 y comprobar modo 600, dueño y ruta UUID inexistente.
La línea pg_dump anterior expresa los argumentos exactos; al ejecutar se antepondrá
`umask 077;` al script sh. No imprimir el catálogo: dirigir pg_restore --list a
archivo de la carpeta privada, comprobar ExitCode, tamaño y legibilidad del archivo.
Comparar SHA-256 del archivo dentro del contenedor con el de Windows. El dump
contiene datos privados y hashes de credenciales: no imprimirlo ni publicarlo.
No usar redirección binaria mediante PowerShell para copiar el dump.

Revalidar destino y rol del contenedor sin mostrar variables/contraseñas; si la
autenticación local falla, detenerse y solicitar entrada privada al operador.
No crear credenciales ni roles y no usar contraseñas en argumentos o informes.
Registrar un manifiesto privado con tamaño, hashes, versiones y UUID activos.

### Restauración futura, exclusivamente en base nueva

Consultar pg_database con parámetro enlazado para comprobar que el nombre UUID
no existe. Capturar metadatos originales de encoding/locale/proveedor de locale,
propietario y ACL de base, esquema, tablas, secuencias y funciones sin datos de
usuarios. Crear la base vacía con características compatibles; los roles originales
ya existen en este servidor. No crear ni modificar roles globales.

```powershell
# Tras comprobación de inexistencia y autorización. Rol existente del contenedor.
docker exec api-usuarios-clean-postgres-1 sh -c 'exec createdb -U "$POSTGRES_USER" --template=template0 "$1"' sh $restoreDb
if ($LASTEXITCODE -ne 0) { throw 'Fallo creación; detenerse' }
# Comprobar current_database y vacío antes de restaurar.
docker exec api-usuarios-clean-postgres-1 sh -c 'exec pg_restore -U "$POSTGRES_USER" --exit-on-error --single-transaction -d "$1" "$2"' sh $restoreDb $containerDump
if ($LASTEXITCODE -ne 0) { throw 'Fallo restauración; conservar para diagnóstico' }
```

Si origen tiene locale no reproducido por los defaults, agregar sus opciones
verificadas a createdb ANTES de ejecutarlo. La extensión vector debe estar disponible
en el servidor y ser restaurada desde el dump a versión 0.8.2; no precrear objetos
que entren en conflicto con el archivo. No usar --clean, --no-owner ni --no-acl:
se necesitan propietarios y ACL fieles. Un pg_dump de base no contiene roles
globales ni el PDF externo. Este ensayo conserva los roles existentes y no prueba
recuperación ante pérdida del servidor completo. El respaldo del PDF y de roles
globales necesita alcance adicional; no se ejecuta implícitamente.

## 3. Validación de restauración

Conectar READ ONLY a la base nueva y verificar:

- Revisión 0005; un documento, dos versiones, 864 fragmentos y 864 embeddings.
- UUID activo original y 432 fragmentos/vectores para cada versión; ambas LISTA.
- SHA-256 de páginas y fragmentos, slices/offsets exactos y relaciones sin huérfanos.
- Hash de entrada de cada embedding, dimensión 768 y norma finita positiva;
  comparar vectores origen/restauración en memoria, sin imprimirlos.
- Ausencia de tablas cloud y preservación de metadatos de documento/versiones.
- Propietarios y ACL efectivos de objetos, además de propietarios/ACL de base:
  pg_dump sin --create no reproduce automáticamente propiedades de la base destino.
  Reproducir las ACL de base solo en la base nueva si difieren, registrándolo;
  no cambiar roles ni permisos en origen. No declarar fidelidad completa si faltan.
- Para autenticación/conversaciones, comparar conteos y huellas en memoria sin
  exponer contenido, credenciales o tokens; no iniciar aplicaciones sobre la copia.

Fijar una ventana sin escrituras autorizada o una referencia de snapshot consistente
para comparar todas las tablas: comparar con un origen que cambió después del dump
no demuestra pérdida de datos. No detener servicios bajo esta autorización inicial.
El snapshot del dump es consistente aunque la aplicación escriba; la comparación
integral exige esa coordinación adicional antes de comenzar el respaldo.

Conservar el dump y la base restaurada, incluso ante fallos; sin reintento automático
ni DROP. Un error de restauración deja la base de prueba para diagnóstico, nunca
justifica restaurar encima del origen. No hay Alembic, indexación, API cloud ni
activación RAG en este procedimiento. DOCUMENT_EXPORT_APPROVED sigue False.

## 4. Comandos efectivamente ejecutados y decisión

Ejecutados: lectura de 10D, consulta de disco/ACL, docker ps filtrado,
docker exec pg_dump --version, pg_restore --version, df; SELECT de metadatos,
privilegios, actividad, locks, revisión, conteos y versión activa con rollback.
La primera consulta Docker sin elevación falló por permisos locales; la misma
comprobación READ ONLY autorizada con elevación aprobó. No fue un fallo PostgreSQL.

**Respaldo: NO EJECUTADO. Restauración: NO EJECUTADA.** No se ejecutaron pruebas
de inferencia ni tests que escriban bases. Único archivo creado: este informe.

Solicitar autorización concreta para crear UNA carpeta privada 10e-UUID, generar
UN dump custom y copia verificada, crear UNA base rag_restore_10e_UUID y restaurar
exclusivamente allí, incluyendo comprobaciones privadas de integridad y ACL.
Conservar todos los artefactos. Revalidar precondiciones al recibir autorización;
no avanzar a 0006 ni exportación documental aunque la restauración apruebe.

## 5. Resultado efectivo de la ejecución autorizada

Se ejecutó una sola operación mediante `infra/_run_10e_authorized.py`, conservado
como evidencia operativa. **No volver a ejecutarlo automáticamente:** crea nuevos
artefactos y requiere autorización. No contiene credenciales, que se cargaron en
memoria desde la configuración existente, sin imprimirlas ni pasarlas como argumentos.

| Artefacto / resultado | Valor |
|---|---|
| Carpeta privada | `D:\Downloads\api-usuarios-clean-backups\10e-8ec23d77c150417db136e68c0a0f2d05` |
| Respaldo | `usuarios_dev.dump`, formato custom, 3.680.756 bytes |
| SHA-256 origen y copia, coincidentes | `93e1316a5c934b7e5e70008015db772a0b7b556f31e36ece996be648fb16c91b` |
| Copia conservada en contenedor | `/tmp/usuarios-dev-10e-8ec23d77c150417db136e68c0a0f2d05.dump` |
| Base restaurada nueva | `rag_restore_10e_8ec23d77c150417db136e68c0a0f2d05` |
| Restauración | COMPLETA, pg_restore exit code 0 |
| Duración desde inicio del dump a verificación final | 6,762 segundos |
| Revisión restaurada | 0005_agent_memory |
| Fragmentos / embeddings comparados | 864 / 864, coincidentes |
| Propietarios y ACL de relaciones y esquema public | Coincidentes |
| Propietario, ACL y parámetros de locale/encoding de base | Coincidentes |
| Todas las tablas public: conteos y huellas de filas | Coincidentes |
| Comparación final de origen | Sin diferencias respecto del snapshot auditado |

Se revalidaron herramientas 18.6, espacio Windows superior a 1 GiB disponible,
destino exacto y rol con permisos, actividad sin otras transacciones/solicitudes
activas en usuarios_dev y nombre de base inexistente. Se mantuvo una transacción
READ ONLY REPEATABLE READ en origen, se exportó su snapshot y se pasó a pg_dump
mediante `--snapshot`, de modo que el respaldo y la referencia de auditoría usan
la misma vista consistente sin detener servicios ni bloquear escrituras mediante DDL.

Secuencia real: pg_dump con umask 077 y ruta UUID inexistente, formato custom,
lock-wait-timeout=5s; comprobación stat de modo 600 en contenedor; pg_restore --list
guardado privadamente en `catalogo.txt`; docker cp; comparación SHA-256; CREATE
DATABASE con template0 y propietario/encoding/locale del origen; comprobación de
destino vacío; pg_restore --exit-on-error --single-transaction; auditoría READ ONLY.
No se omitieron propietarios o ACL mediante --no-owner/--no-acl.

Se compararon todas las filas de tablas public mediante hashes por fila y huellas
ordenadas, incluyendo datos de autenticación/conversaciones exclusivamente en memoria,
sin imprimir contenido. Los hashes de páginas y fragmentos, offsets/slices y hashes
de entrada de vectores fueron correctos. Cada vector tuvo 768 componentes finitos
y norma positiva. Las huellas exactas de filas incluyen vectores y todas sus relaciones.
No es una prueba de calidad semántica ni una ejecución de autenticación sobre la copia.

Ambas versiones siguen LISTA, con 72 páginas y 432 fragmentos cada una:

- Activa: `7cb4e79c-747d-574a-8abb-0ebcb2e07636`.
- Anterior: `9cab30cd-9554-5679-a2d9-35d85dd5ab85`.

La DACL de la carpeta está protegida, pertenece al operador y contiene exclusivamente
dos reglas para el usuario actual y SYSTEM. La verificación efectiva posterior de
`usuarios_dev.dump`, `catalogo.txt` y `manifest.json` confirmó únicamente esos dos
principales por herencia de la carpeta restringida. No se modificó la carpeta padre.
El temporal del contenedor permanece modo 600, accesible al propietario y a los
administradores privilegiados del host/contenedor; una ACL no impide acceso de root
o de un administrador capaz de tomar posesión. No se entregaron permisos a usuarios
ordinarios ajenos. El manifiesto privado conserva tamaño, hash y resultados saneados.

Incidencias: una consulta posterior de ACL tuvo un error de sintaxis PowerShell
antes de ejecutarse; se corrigió exclusivamente esa lectura y completó correctamente.
No hubo fallos, repeticiones o reintentos de pg_dump, creación de base o restauración.
No se borraron artefactos. No se ejecutaron Alembic, APIs, Ollama ni reindexación.
No hubo escrituras de aplicación o DDL dirigidas a usuarios_dev/usuarios_test y la
auditoría final del origen coincidió; esta comprobación no pretende demostrar que
nunca existió actividad externa entre instantes fuera de los snapshots observados.

**GO: respaldo completo de base restaurable verificado en el servidor actual.**
No incluye recuperación del servidor desde cero, roles globales, archivos PDF externos
ni cambios de infraestructura. **NO-GO todavía para aplicar 0006, exportar documentos,
indexar o activar Jina:** siguen requiriendo sus condiciones y autorizaciones propias.
DOCUMENT_EXPORT_APPROVED permanece False; no se modificaron .env o servicios.
