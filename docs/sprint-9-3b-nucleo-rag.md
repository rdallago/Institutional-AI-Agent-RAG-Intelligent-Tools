# Sprint 9.3B: núcleo RAG académico aislado

Fecha: **3 de noviembre de 2026**. **IMPLEMENTADO para el alcance de núcleo
aislado autorizado**. Sin despliegue, adaptadores operativos, ingesta del PDF,
embeddings reales, inferencia o conexiones a bases.

## 1. Archivos y arquitectura

Se revisaron el diseño aprobado 9.3A, DTO/puertos/caso de uso de IA directa,
autorización, admisión y convenciones de pruebas existentes. Archivos creados:

- `backend/src/app/application/rag/__init__.py`.
- `backend/src/app/application/rag/dto.py`: páginas, secciones, scope de versión y
  espacio de embeddings, fragmentos, candidatos, evidencias y resultados inmutables.
- `backend/src/app/application/rag/ports.py`: contratos documentales/vectoriales,
  embeddings, tokenizador, generación fundamentada y exclusión de trabajo.
- `backend/src/app/application/rag/core.py`: fragmentación, selección, presupuesto,
  render de contexto y resolución de citas.
- `backend/src/app/application/rag/use_cases.py`: `PrepararVersion` y
  `ResponderConDocumento`.
- `backend/src/app/infrastructure/llm/work_gate.py`: `MemoryModelWorkGate`.
- `backend/tests/rag/test_core.py`: 39 casos aislados con dobles.
- `docs/sprint-9-3b-nucleo-rag.md`: este informe.

No se editaron archivos preexistentes. Application conserva independencia de HTTP,
SQLAlchemy, pgvector y Ollama. No se añadieron dependencias, rutas o composición
en bootstrap/lifespan. Los casos nuevos requieren inyección explícita y no se
ejecutan al iniciar la aplicación.

## 2. Preparación y procedencia

`PrepararVersion` recibe páginas **ya extraídas** y un documento autorizado; no
abre archivos. Revalida acceso normal y delega staging idempotente a un puerto
que debe comprobar permiso de ingesta atómicamente: leer un documento no concede
por sí solo permiso para indexarlo. Esta fase prepara fragmentos; no publica una
versión ni certifica una ingesta completa.

Las páginas tienen números físicos positivos únicos. Las secciones explícitas
deben particionar cada página sin huecos o solapamientos; sin mapa se usa la página
completa. No hay detector automático de artículos. Se conservan texto original y
offsets Unicode `[start,end)`, sin normalización silenciosa y sin cruzar páginas o
secciones. Los fragmentos prefieren finales de párrafo/palabra; una unidad larga
puede dividirse por puntos Unicode para respetar el techo. Tablas y estructura
editorial compleja requerirán extracción y revisión específicas.

`ChunkPolicy` permite techo de 1–400 tokens y solape menor al techo, por defecto
400/50. La cuenta procede de un tokenizador inyectado con identidad versionada;
los tests usan un contador ficticio de puntos Unicode, **no un tokenizador real**.
No se declara la tokenización del PDF ni equivalencia caracteres/tokens. La
implementación recorre prefijos de texto: es sencilla pero puede ser costosa en
páginas largas; debe perfilarse antes de ingesta operativa. Se rechazan páginas de
más de 100000 puntos y entradas de más de 1000 páginas.

La huella SHA-256 incluye documento, versión, espacio, política, identidad del
tokenizador y páginas/secciones exactas. IDs de fragmento derivan de esa huella y
su ubicación. Repetir la misma entrada conserva huella/IDs; cambiar texto o política
los cambia. `put_prepared_once` exige deduplicación atómica por scope/huella y
`put_once` de vectores exige checkpoint por versión/fragmento/espacio sin reemplazos
silenciosos. Los tests acreditan determinismo y no duplicación en un doble; no
acreditan transacciones o restricciones UNIQUE de PostgreSQL todavía inexistentes.

## 3. Recuperación y respuesta fundamentada

`ResponderConDocumento` conserva la validación de pregunta de IA directa: 1000
puntos/3000 bytes, contenido no vacío, UTF-8 válido y sin NUL. Consulta la versión
activa autorizada antes de ejecutar modelos. Mantiene el Principal interno en
repositorios; no lo incluye en `GroundedInput`.

El puerto de embeddings tiene operaciones distintas para pregunta/documento.
Su adaptador futuro deberá fijar **nomic-embed-text**, digest/prefijos apropiados
y espacio versionado. El núcleo valida vectores de consulta de **768 dimensiones**,
numéricos finitos y norma no nula/finita. Coincidir en dimensión no permite mezclar
espacios. No existe un selector público de modelo ni un adaptador real nuevo.

`VectorRepository.search` exige ACL, versión LISTA activa y espacio filtrados
**antes** del top-k coseno. Recibe Principal/scope y límite 12. El núcleo rechaza
resultados de otro scope, cantidades superiores al límite, procedencia estructural
inválida y similitudes no finitas/fuera de [-1,1]. Ordena, deduplica por fragmento
y aplica un umbral explícito sin valor universal predeterminado. Su calibración
en español sigue pendiente. El doble verifica el scope de usuario; el adaptador
SQL futuro deberá demostrar el filtrado previo, no sustituirlo por filtrado Python.

Se seleccionan hasta tres fragmentos completos que quepan. Se cuenta el render
completo (instrucción, pregunta y fuentes JSON escapadas), con **4096 de contexto,
256 de salida y 512 de reserva**. No se aumenta el contexto ni se trunca la pregunta
o una evidencia. Si la pregunta/plantilla sola excede el presupuesto se rechaza;
si no cabe evidencia o ninguna supera el umbral, se devuelve localmente:

```text
strategy=RAG, status=SIN_EVIDENCIA, citations=(), finalization=None
```

Incluye una abstención fija y no llama al generador ni hace fallback a IA directa.
Índice/proveedor indisponible no debe representarse como una búsqueda vacía:
el contrato exige error. Una búsqueda vacía sí representa ausencia de evidencia.

`GroundedLLMProvider` recibe pregunta, evidencias y render acotado separados del
DTO directo. El futuro adaptador fijará qwen3:1.7b, think=false, parser estricto y
plantilla compatible con la reserva/tokenizador. **No hay implementación HTTP de
ese puerto en este incremento** y no se usó concatenación contra el proveedor
directo para eludir sus límites.

El resultado usa la validación de salida existente (texto y completa/limite).
Cada respuesta fundamentada debe contener al menos una cita canónica `[F1]`,
`[F2]` o `[F3]`, presente en las evidencias efectivamente enviadas. Referencias
desconocidas o marcadores F malformados se rechazan sin regeneración. Se resuelven
a fragmento/documento/versión/página/offsets del backend; las páginas declaradas
libremente en el texto del modelo no se consideran una fuente verificable.

Validar identificadores **no demuestra correspondencia semántica** entre cada
afirmación y el PDF. Esa evaluación, abstención del modelo ante fuentes insuficientes
y calidad en español requieren corpus de evaluación y piloto autorizado posterior.
No se implementa un verificador de entailment ni se promete eliminar alucinaciones.

## 4. Autorización, cuotas y recursos

Se reutilizan por inyección `NormalAccessAuthorizer` y `GenerationAdmission`.
Una operación RAG obtiene una sola admisión para embeddings/búsqueda/generación;
no llama al caso de IA directa ni duplica cuotas. Revalida acceso normal y versión
activa antes de entregar, incluso en abstención. Revocación o cambio de versión
impide entregar el resultado. Los adaptadores documentales deben revalidar ACL
también al finalizar; no se supone acceso universal de ADMIN.

El deadline total de la fase de modelos/recuperación es como máximo 60 s, con
enfriamiento mediante el lease de admisión al agotar tiempo. Errores de proveedor
se saneanean sin copiar contenido. Cancelación se propaga y los leases se liberan
en finally. No hay reintentos o tareas de fondo. Las comprobaciones de autorización
mantienen su contrato existente y no se convierten en errores de proveedor.

`MemoryModelWorkGate` tiene exclusión inmediata bajo lock, sin cola, y leases
idempotentes que no pueden liberar un trabajo posterior. Se mantiene durante
toda la operación RAG para impedir que otra operación que use **la misma instancia**
ejecute otro modelo simultáneamente. No sustituye cuotas ni es distribuido.

**Límite de integración deliberado:** el coordinador no se conectó al runtime
directo existente ni a una ingesta real. Hoy no puede garantizar exclusión frente
a IA directa operativa, otros procesos o clientes externos de Ollama. Esa garantía
solo existirá tras componer una instancia compartida entre todos los adaptadores
pertinentes y verificarla; hacerlo ahora alteraría la funcionalidad que debía
permanecer intacta. No se debe habilitar RAG hasta completar esa integración.

## 5. Pruebas ejecutadas

Desde backend, exclusivamente sin servicios externos:

```powershell
.\.venv\Scripts\python.exe -B -m pytest -q tests/rag -p no:cacheprovider --basetemp=.pytest-tmp-93b-rag --tb=short
.\.venv\Scripts\python.exe -B -m pytest -q tests/rag tests/ia -p no:cacheprovider --basetemp=.pytest-tmp-93b-isolated --tb=short
```

| Ejecución | Resultado |
| --- | --- |
| Primera dirigida RAG, antes de nueve casos adicionales | 30 aprobadas, 0,17 s |
| Final RAG + IA existente | **344 aprobadas, 4,87 s**, sin fallos |
| Desglose final | **39 RAG nuevas + 305 IA existentes** |

Cobertura nueva: offsets, secciones, solape, políticas inválidas, huella idempotente,
Unicode inválido, vectores sintéticos, selección/deduplicación, límites de contexto,
citas inexistentes/malformadas, completa/limite, abstención sin generador,
aislamiento de usuarios, rechazo de versión ajena, revocación/cambio de versión,
repr sin texto, ausencia de stdout, excepciones saneadas, timeout/deadline,
cancelación, concurrencia y liberación ante fallo de admisión.

Los 305 casos existentes incluyen contrato HTTP, autorización, cuotas, adaptador,
observador, lifespan y lanzador con dobles/MockTransport. Respaldan que la IA
directa mantiene su comportamiento en aislamiento. No se repitió toda la regresión
backend, no se ejecutaron tests PostgreSQL ni frontend. Permanece el aviso previo
Starlette/TestClient sobre httpx; no se instalaron paquetes para ocultarlo.

## 6. Pendientes y detención

Antes de integrar: implementar extracción/tokenizadores compatibles, repositorios
documentales/vectoriales con ACL/atomicidad probadas, adaptadores de embeddings y
generación fundamentada, checkpoints/publicación de versiones, composición común
del coordinador y pruebas de integración. PostgreSQL + pgvector sigue siendo el
destino aprobado; extensión/imagen/migraciones requieren su etapa autorizada.
La calidad española, presupuesto real de tokens, RAM y latencia no se acreditan
con vectores ni contadores sintéticos. No hay memoria conversacional o tools.

El PDF real `backend/data/documents/reglamento_academico.pdf` no se abrió, extrajo,
fragmentó o persistió en este sprint. No hubo acceso a usuarios_dev/usuarios_test,
Alembic, pgvector, cambios Docker/volúmenes, inferencias, embeddings reales,
descargas, instalaciones, cambios .env, React o contratos HTTP, ni detenciones
o reinicios. No se añadieron logs de contenido, JWT o datos personales.

**IMPLEMENTADO: núcleo aislado verificable. No desplegado ni habilitado.** Se
entrega para revisión y se detiene antes de integrar infraestructura o proveedores.
