# Sprint 10B — Validación previa de Jina AI

Consulta y pruebas: **9 de noviembre de 2026**, America/Buenos_Aires.
**NO-GO para migración, exportación del reglamento y activación.**
La preparación sintética está lista; su ejecución real requiere autorización adicional.
No se modificaron `.env`, credenciales, adaptadores productivos, Dots3-Note, datos,
vectores Nomic ni servicios. No se ejecutaron APIs de inferencia/embeddings ni E2E.

## 1. Privacidad: evidencia y límites

| Punto | Resultado | Fuente oficial / límite |
|---|---|---|
| Entrenamiento con solicitudes, entradas y salidas | La FAQ declara que no se utilizan para entrenar modelos. | [FAQ de embeddings](https://jina.ai/embeddings/), sección “Is my API data used to train your models?”. Es una declaración del proveedor, no una auditoría independiente. |
| Almacenamiento | Los términos dicen que entradas/salidas pueden almacenarse en lo necesario para prestar el servicio. | [Legal, 4.6](https://jina.ai/legal/). No equivale a cero retención. |
| Plazo exacto para textos y vectores devueltos | **Pendiente**; no se identificó un plazo específico de esta API/cuenta. | No inferirlo a partir de la política general del sitio. |
| Metadatos operativos | El texto legal contempla retención y uso agregado/anónimo. | [Legal, 10.4](https://jina.ai/legal/). |
| Documentos legales aplicables | Jina remite a Elastic y advierte que términos anteriores pueden estar desactualizados. | [Aviso legal](https://jina.ai/legal/), encabezado. |
| Eliminación | El DPA remite al acuerdo/política de retención, con excepciones legales. No fija un número universal de días para esta API. | [DPA Elastic, sección 5](https://www.elastic.co/pdf/v100623-0-elastic-customer-dpa.pdf). |
| Cuenta gratuita | Falta confirmar qué acuerdo concreto y condiciones de retención aplican a la clave del usuario. | No se accedió al panel autenticado. |
| Uso comercial | La tabla gratuita indexada indica uso no comercial. La FAQ distingue servicio hospedado de licencias de pesos; no usar estas últimas para justificar un plan gratuito comercial. | [Precios](https://jina.ai/api-dashboard/pricing/), [licencias/API](https://jina.ai/embeddings/). |

La [declaración general de privacidad de Elastic](https://www.elastic.co/legal/privacy-statement)
separa datos del sitio de contenido tratado por cuenta del cliente; no certifica
por sí sola el tratamiento específico de entradas y vectores Jina.

**Conclusión:** mejoró la evidencia sobre ausencia de entrenamiento respecto de 10A,
pero sigue faltando el plazo de retención aplicable y confirmación contractual de
la cuenta gratuita. No se levantó `DOCUMENT_EXPORT_APPROVED=False`.

Preguntas para soporte: plazos de textos/vectores, logs/backups y borrado;
subprocesadores/región; aplicación de la FAQ y el DPA al plan gratuito;
licencia de uso educativo; vigencia de tokens y ausencia de cargos al agotarse.
No enviar documentos, claves ni datos personales en esa consulta.

## 2. Cuota y costos

Fuentes consultadas el 9/11/2026:

- [Precios oficiales](https://jina.ai/api-dashboard/pricing/): el resultado oficial
  indexado muestra “Toy Experiment”, 10 millones de tokens, gratuito y no comercial.
  La representación directa actual no expone todas las tarjetas. Confirmar oferta
  vigente y saldo en el panel; no asumir que el usuario tiene diez millones.
- [Reader oficial](https://jina.ai/en-US/reader/) también anuncia 10M iniciales.
  Es una asignación de bienvenida, no una renovación mensual demostrada.
- La tabla de precios publica 100 RPM/100.000 TPM para embeddings gratuitos.
  [OpenAPI oficial](https://docs.jina.ai/openapi.json), versión 2026.10.13.1624,
  publica 500 RPM/1M TPM. **Existe discrepancia oficial**: usar el límite menor
  para planificar hasta confirmación; no presentar ninguno como capacidad garantizada.
- Precios ofrece recarga automática usando el medio guardado. No se consultó ni
  cambió su estado en la cuenta. Debe comprobarse manualmente que esté deshabilitada.
- OpenAPI documenta saldo insuficiente con HTTP 403 / AUTHZ_INSUFFICIENT_BALANCE.
  El adaptador ya rechaza 403 sin reintento. No afirma que este sea el único estado
  posible ni que una cuenta con auto-recarga habilitada no pueda recibir cargos.
- La FAQ indica que las claves no caducan; esto no prueba vigencia ilimitada de
  créditos gratuitos. Duración/transferencia de esos créditos: pendiente del panel/proveedor.

No se compraron tokens, agregaron medios de pago ni habilitaron recargas.

### Estimación local del reglamento

Sin SQL ni envío de contenido, se reconstruyó localmente la extracción y fragmentación
vigentes del PDF: **72 páginas, 432 fragmentos, 159.779 bytes UTF-8 incluyendo
solapamientos; fragmentos entre 64 y 400 bytes**. No se imprimió el texto.
Es reconstrucción local, no una nueva auditoría de los registros PostgreSQL.

Escenario orientativo de 2–4 bytes por token: aproximadamente **40.000–80.000 tokens**.
No es tokenización Jina medida. Como reserva preliminar, prever 200.000 tokens
para documentos y margen, más consultas y verificaciones posteriores. Esto sería
2 % de una asignación hipotética de 10M, no 2 % de un saldo real comprobado.
Los fallos inciertos pueden consumir cuota si se autorizan nuevas solicitudes;
no garantizar idempotencia de facturación. El importe efectivo depende del saldo,
plan y uso informado por Jina. No se afirma costo real cero para esta cuenta.

## 3. Prueba sintética de retrieval.passage

Preparada en `infra/diagnose_jina_passage.py`. Texto único e inmutable:

> El Instituto de Prueba tiene una biblioteca con veinte libros de programación.

Modelo jina-embeddings-v3, retrieval.passage, 768 dimensiones, normalización
solicitada y comprobada, validación compartida con el adaptador. No admite archivos,
URLs o texto desde argumentos. Reutiliza solo el transporte interno con esta
constante sintética: no cambia la guarda del método público embed_document.
Sin reintentos, redirects, fallback o impresión de claves/vectores/cuerpos upstream.

**Resultado real: NO EJECUTADA.** Dos casos con MockTransport comprobaron respuesta
válida y dimensión incorrecta. Sin --execute se detiene antes de crear el cliente.
El informe imprime HTTP, duración, dimensión, finitud, norma y tipo controlado de error.

Comando preparado, **solo después de otra autorización**, con JINA_API_KEY ya en
la memoria de la terminal y sin transcripción:

```powershell
Set-Location 'D:\Downloads\proyectos\api-usuarios-clean'
& '.\backend\.venv\Scripts\python.exe' -B '.\infra\diagnose_jina_passage.py' --execute
```

No hay necesidad de activar Jina en `.env`, cambiar la cuenta ni levantar el bloqueo
documental para esta prueba inventada.

## 4. Diagnóstico de las tres pruebas fallidas

Se ejecutaron exclusivamente los tres tests heredados: **3 fallaron**, reproduciendo
los resultados de 10A. No se editaron sus archivos o expectativas.

| Prueba | Causa comprobada | Clasificación |
|---|---|---|
| test_auto_academic_selects_authorized_document_and_applies_real_skill | agent.py lee catálogo para título explícito y vuelve a leerlo en el recorrido sin planner. Hay dos lecturas; la respuesta es FUNDAMENTADA, cita válida y skill correcta. | Expectativa de conteo desactualizada/lectura redundante; no fallo funcional demostrado de respuesta. |
| test_multiple_documents_require_selection_not_random_choice | El doble devuelve solamente id; explicit_document exige titulo. Al proporcionar títulos válidos en un ensayo separado se obtiene ACLARACION. | Fixture incumple el contrato real del catálogo. El router no tolera ese contrato interno defectuoso; no se observó en el repositorio SQL. |
| test_academic_evidence_and_real_page | El proveedor por defecto devuelve “Norma ficticia [F1].”; evidencia: “La regularidad de una unidad curricular exige asistencia.” Faltan norma/ficticia; polaridad coincide. Una afirmación equivalente al texto sí supera soporte. | Rechazo correcto; fixture positivo incorrecto, no falso negativo demostrado. |

Estos recorridos usan dobles del núcleo; no usan Jina, composición operacional ni
CloudPostgresRAG. No se encontró una causa atribuible a 10A. No hay repositorio Git
utilizable en esta copia (`git rev-parse` falla); no se pudo ejecutar una revisión
anterior como baseline. **No se afirma cuándo aparecieron históricamente.**
No se corrigió producción ni se cambiaron tests para ocultar esos fallos.

## 5. Migración: análisis estático y mocks

Historial en disco comprobado con ScriptDirectory, sin env.py, conexión ni SQL:
**0006_cloud_embeddings → 0005_agent_memory → 0004_rag**, una sola cabeza.
No se volvió a consultar la revisión aplicada de usuarios_dev; el último registro
previo era 0005 y no se usa como comprobación actual.

| Propiedad | Evidencia / límite |
|---|---|
| Aditiva | Cuatro CREATE TABLE rag_cloud_*, sin ALTER/UPDATE/DELETE sobre Nomic. Mock op.execute confirma DDL. |
| Compatibilidad | vector(768), tablas referenciadas y UUID coinciden con 0004. Sintaxis/semántica PostgreSQL reales pendientes de integración aislada autorizada. |
| Espacio independiente | Nuevo fingerprint, tablas cloud, PK(fragmento,espacio), dimensión 768. Igual dimensión no significa mismo espacio. |
| Referencias | FK hacia fragmentos, versiones, espacio y pareja ingesta/espacio. El estado VALIDADA se exige en aplicación; la FK por sí sola no exige ese estado. |
| Publicación | activate revalida 432 vectores, hashes y offsets y actualiza puntero cloud dentro de una transacción, con lock del documento. Mocks rechazan publicación incompleta. |
| Checkpoints | Cada inserción confirma fragmento/espacio/hash/vector, ON CONFLICT sin sobrescritura. missing_cloud busca pendientes por espacio. La CLI no publica al terminar un lote. |
| Concurrencia | Gate compartido entre procesos locales y transacciones cortas; no hay una garantía distribuida de ingesta entre varias máquinas. Alcance local de este proyecto. |
| Recuperación | Nomic y versión textual se conservan. Volver por configuración a Nomic exige Ollama disponible; no es rollback cloud autónomo ni fallback automático. |
| Downgrade | Rechaza borrar tablas/vectores automáticamente. Rollback operativo no equivale a downgrade Alembic. |

La prueba PostgreSQL preparada sigue sin ejecutarse. No se declara validada la
migración contra un motor real ni aplicado el DDL. No se requiere modificar 0006
con base en esta revisión estática; quedan las verificaciones reales previas al corte.

## 6. Ruta cloud y pruebas

Ejecutado, sin servicios: **59 aprobadas**, 5,55 s; aviso preexistente Starlette.
Incluye:

- Nueva auditoría de los fixtures y grafo Alembic.
- Prueba sintética optativa, sin red por defecto y con payload fijo comprobado.
- Configuración y claves ocultas; rechazos HTTP, JSON, vectores y límites.
- Lifespan FastAPI con dependencias simuladas que falla si construye embeddings
  Ollama; confirma Jina y CloudPostgresRAG, cierre de recursos y tareas correctas.
- Separación Nomic/Jina, ACL y publicación incompleta, continuidad documental.
- Pruebas existentes Dots3-Note con AtlasCloud y sus esquemas.

Comando local utilizado:

```powershell
Set-Location 'D:\Downloads\proyectos\api-usuarios-clean\backend'
& '.\.venv\Scripts\python.exe' -B -m pytest tests/rag/test_jina_10b_audit.py tests/rag/test_jina_cloud.py tests/ia/test_dots_openrouter.py tests/rag/test_article_continuity.py -q -p no:cacheprovider --basetemp=.pytest-tmp-jina-10b --tb=short
```

Separadamente: **3 fallos heredados reproducidos**, sin corrección. No sumar
repeticiones ni presentar 59 aprobadas como regresión completa.

## 7. Archivos incorporados en 10B

1. `infra/diagnose_jina_passage.py`.
2. `backend/tests/rag/test_jina_10b_audit.py`.
3. `docs/jina-cloud-10b.md`.

No se modificó código productivo, migración 0006, bloqueo de privacidad, fixtures
heredados, Dots3-Note, configuración o datos reales durante 10B.

## 8. Riesgos y decisión

**NO-GO para migración real y activación.** Pendientes: retención contractual,
condiciones del paquete gratuito, saldo/auto-recarga del usuario, prueba real
sintética de passage y ensayo PostgreSQL aislado. El alias de modelo no ofrece
un digest inmutable verificado: antes de una ingesta larga definir evidencia
sintética de referencia y procedimiento ante cambios upstream.

**GO para solicitar una única prueba sintética**, con el comando anterior, tras
confirmar autorización y saldo. No necesita PostgreSQL ni documentos reales.

Antes de cualquier SQL real, exportación del reglamento o activación, solicitar
otra autorización concreta. El bloqueo documental sigue activo y no se avanza
automáticamente a migración/reindexación aunque passage responda correctamente.
