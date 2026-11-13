# Sprint 9.2.5F: recursos y diagnóstico PostgreSQL controlado

Fecha: **3 de noviembre de 2026**. **Resultado: BLOQUEADO para piloto inmediato**,
por margen de RAM aún reducido. La identidad/revisión y compatibilidad mínima de
desarrollo quedaron verificadas por lectura; no se inició la aplicación o modelo.

## 1. Alcance y revisión

Se revisaron los informes 9.2.5E/9.2.5D, cargador de base, construcción de engine,
alembic.ini, migrations/env.py, revisión 0003, Compose de desarrollo/pruebas y
configuración/payload LLM. No se modificaron código, observador o configuración.
No se ejecutó Alembic: ScriptDirectory solo leyó la cadena local de revisiones.

## 2. Recursos actuales

Una única medición, **06:51:25 -03:00**, antes de las pruebas dirigidas:

| Recurso | Observado |
| --- | ---: |
| RAM física total | **7,851 GiB** |
| RAM física disponible | **0,997 GiB** |
| Compromiso global | **13,237 GiB** |
| Límite de compromiso | **25,851 GiB** |

GetPerformanceInfo proporcionó datos actuales. Ocupación física aproximada 87 %;
el compromiso no equivale a RAM residente ni acredita paginación medida. No se
midieron fallos de página o presión durante inferencia y no se cargó el modelo
para estimarla. La muestra no acredita capacidad suficiente para sumar modelo,
FastAPI, React y navegador. La experiencia favorable previa con Qwen3 comunicada
por el responsable sigue siendo antecedente, no una prueba actual.

Principales working sets en una muestra de procesos cercana:

| PID | Proceso | MiB |
| --- | --- | ---: |
| 6064 | vmmem | 546,8 |
| 11364 | chrome | 473,4 |
| 12036 | chrome | 419,9 |
| 7608 | Code | 402,1 |
| 5968 | MsMpEng | 279,6 |
| 5780 | Code | 265,6 |
| 2728 | Memory Compression | 223,7 |
| 28096 | Code | 198,8 |

No sumar como consumo exclusivo: puede haber páginas compartidas. No se leyó
contenido de documentos/pestañas o líneas completas de comandos.

El responsable podría **voluntariamente**, después de guardar trabajo, cerrar
pestañas o ventanas de Chrome y proyectos/ventanas de Code que reconozca como
innecesarios, o elegir otra ventana de menor carga. No se propone terminar vmmem,
Docker/PostgreSQL, Memory Compression o protección del sistema, ni modificar
pagefile/configuración Windows. No se cerró ninguna aplicación.

**No se repitió la medición.** Una nueva muestra tras ajustes queda pendiente de
confirmación expresa del responsable. La referencia previa de 2 GiB disponibles
es un objetivo conservador sujeto a evaluación, no garantía automática de aptitud.

## 3. Docker y Ollama

Lecturas Docker permitidas fuera de restricción: version y ps, sin operaciones
de arranque/parada ni exec. Engine **29.8.1** responde.

| Contenedor propio | Estado | Publicación |
| --- | --- | --- |
| api-usuarios-clean-postgres-1 | Up, healthy | **127.0.0.1:5434 → 5432** |
| api-usuarios-clean-tests-postgres-1 | Up, healthy | **127.0.0.1:5435 → 5432** |

La segunda fila es solo inventario Docker: no se conectó a usuarios_test ni se
utilizó su servicio para pruebas. No se tocaron contenedores o volúmenes.

GET locales de metadatos /api/version, /api/tags y /api/ps, con proxy ignorado y
timeout 3 s: **200**. Ollama **0.40.13**, modelo **qwen3:1.7b** instalado,
1359293444 bytes en disco; digest
`8f68893c685c3ddff2aa3fffce2aa60a30bb2da65ca488b61fff134a4d1730e7`.
**Cero modelos cargados** al observar. Los otros tags existentes no se utilizan
como fallback. No se hicieron run/pull/generate/chat/load/unload.

Código conserva think=false, contexto **4096**, salida **256 tokens**, deadline
backend **60 s**, una generación concurrente, cuotas 5/usuario y 15 globales por
minuto, enfriamiento 30 s, stream=false y keep_alive=0. Observador requiere
--enable-llm --observe-llm, sin aprovisionamiento. Disponibilidad de metadatos no
certifica compatibilidad real, done_reason, tokenización, cancelación o latencia.

## 4. Destino PostgreSQL y solo lectura

Se realizó **una sola conexión diagnóstica**, usando usuario y secreto de la
configuración existente, sin cuentas alternativas, SET ROLE o elevación DB.
Antes de conectar se exigió coincidencia exacta de host/puerto/base configurados:
**127.0.0.1:5434 / usuarios_dev**. No se imprimió URL ni contraseña.

Se abrió Psycopg con:

- connect_timeout=5 s.
- default_transaction_read_only=on desde opciones de conexión.
- statement_timeout=10000 ms y lock_timeout=2000 ms, limitados a esa sesión.
- conn.read_only=True antes de la primera sentencia.

Se revalidaron host/puerto/dbname de conn.info y luego current_database(),
current_user y transaction_read_only. La base efectiva fue **usuarios_dev**;
el usuario efectivo coincidió con el configurado, sin reproducir su identificador
en resultados. **transaction_read_only=on** quedó confirmado antes de consultar
la revisión y los metadatos. No se modificaron valores persistentes de PostgreSQL.
Al terminar se efectuó **rollback y cierre**, sin commit.

Las condiciones de parada implementadas incluían destino/identidad/solo lectura
inesperados, tabla de versión ausente, revisiones múltiples o distintas de 0003,
y metadatos incompatibles. Ninguna se produjo. Errores de conexión/configuración
se habrían reportado solo por tipo, sin excepción completa o secretos.

## 5. Revisión y metadatos observados

| Comprobación | Resultado |
| --- | --- |
| Único head del repositorio | **0003** |
| Predecesor de 0003 | **0002** |
| public.alembic_version | **Existe** |
| Revisión efectiva leída | **0003**, una única fila |
| Comparación con repositorio e informes previos | **Coincide**, sin discrepancia observada |
| Columnas mapeadas de las cuatro tablas de aplicación | Todas presentes según information_schema |

La única tabla con valores consultados fue **alembic_version**, autorizada para
leer version_num. No se consultaron filas, conteos o valores de usuarios,
credenciales, sesiones o intentos. Sus nombres y columnas se revisaron únicamente
como catálogo del esquema para compatibilidad mínima.

| Columna añadida por 0003 | Tipo | Nulabilidad | Default actual |
| --- | --- | --- | --- |
| usuario_credenciales.debe_cambiar_password | boolean | NOT NULL | Ninguno |
| usuario_credenciales.password_inicial_hash | text | NULL permitido | Ninguno |
| auth_sesiones.restringida | boolean | NOT NULL | Ninguno |

Se verificó el CHECK validado **ck_credenciales_password_inicial**, equivalente a
`NOT debe_cambiar_password OR password_inicial_hash IS NOT NULL`.
Se inspeccionó el nombre/tipo de la columna de hash, **nunca su contenido**.

Esto resuelve la incertidumbre de identidad/revisión y las comprobaciones
estructurales mínimas autorizadas, pero **no certifica integridad de registros
históricos, disponibilidad de cuentas o igualdad de datos después de WSL**.
No se hizo comparación exhaustiva de tipos/PK/FK/índices ni Alembic check; no se
presenta la comprobación de columnas como una auditoría completa del esquema.

## 6. Pruebas aisladas pertinentes

Sin modificar código se ejecutaron únicamente configuración de persistencia,
LLMConfig, lifespan IA, lanzador y observador, con dobles/memoria/MockTransport.
Estas pruebas no usan la conexión diagnóstica ni leen datos de desarrollo;
no requieren PostgreSQL u Ollama reales. Sockets de pruebas efímeros, sin
servidores persistentes. No se repitió la regresión completa.

```powershell
# Desde backend, sin --run-postgres:
.\.venv\Scripts\python.exe -B -m pytest -q tests/unit/infrastructure/test_database_configuration.py tests/ia/test_llm_configuration.py tests/ia/test_ia_lifespan.py tests/ia/test_local_llm_launcher.py tests/ia/test_ollama_observation.py -p no:cacheprovider --basetemp=.pytest-tmp-925f-targeted --tb=short
```

**126 aprobadas, sin fallos, 2,15 s**. Permanece el aviso previo
Starlette/TestClient sobre httpx; no se instalaron paquetes para ocultarlo.
Las 738 aprobaciones/162 omisiones de 9.2.5E son antecedentes, no una repetición
actual. Artefactos temporales de pruebas en su ruta ignorada; ningún archivo de
aplicación, prueba, .env u observador se modificó.

## 7. Bloqueos y siguiente etapa

El bloqueo DB de identidad/revisión mínima quedó resuelto **al momento de la
inspección**. No hace falta ni se propone migrar, stamp, downgrade o restaurar.
El siguiente bloqueo es operativo de recursos: recuperar margen mediante acciones
voluntarias y confirmar los ajustes antes de repetir la medición. Tampoco se
inició o certificó una aplicación activa durante esta etapa.

Después, solicitar autorización diferenciada para arranque local y comprobaciones
sin inferencia; revalidar destino/estado si cambiaron las condiciones. El permiso
de SELECT no autoriza login/logout ni sus escrituras normales en sesiones/intentos.
Una futura prueba autenticada debe contemplarlas expresamente, sin usar cuentas
en scripts, extraer tokens o modificar perfiles para lograr acceso.

La única consulta real con observador requerirá otra decisión sobre RAM, ventana,
arranque loopback/worker único, credenciales introducidas por el responsable y
monitorización sin contenido. Conservar gate de aprovisionamiento cerrado y no
reintentar automáticamente ante timeout, presión de memoria o razón inválida.

## 8. Finalización

Único entregable creado: este informe. No se modificó código/configuración o
infraestructura. No hubo DML/DDL, migraciones, modificación de registros,
acceso a usuarios_test, inicio/detención de servicios, inferencia o descarga.
La única lectura de datos SQL fue el registro de versión Alembic; el resto fueron
identidad/configuración de transacción y catálogos autorizados. No se revelaron
URLs completas, secretos o datos personales.

**BLOQUEADO para piloto inmediato por recursos pendientes.** Se entrega el
diagnóstico y se detiene; no se repite RAM sin confirmación de ajustes ni se
inicia la aplicación o piloto automáticamente.
