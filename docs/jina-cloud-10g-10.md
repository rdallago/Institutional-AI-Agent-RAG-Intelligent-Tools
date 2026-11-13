# Sprint 10G.10 — Validación oficial real de embeddings Jina

10 de noviembre de 2026, America/Buenos_Aires.
**COMPLETADO. GO técnico para solicitar autorización de activación.**
La ingesta quedó VALIDADA mediante el repositorio oficial; no se publicó el índice.

## Autorización y método

El pedido adjunto del usuario autorizó expresamente la escritura necesaria para
PREPARANDO → VALIDADA, exclusivamente sobre usuarios_dev, sin activación.
Se revisaron cloud_postgres.py, reindex_jina.py e index_jina_all.py.
El CLI de indexación mantiene bloqueadas validate/activate; no se modificó esa guarda.

Se utilizó directamente la firma existente:

```python
CloudPostgresRAG.validate_cloud(OWNER, VERSION, expected=432)
```

El método verifica ACL y versión activa mediante _guard (FOR UPDATE del documento),
completitud, hashes, páginas, offsets, vectores y norma antes de actualizar la ingesta.
No se cambió su lógica y no se utilizó SQL manual para forzar VALIDADA.
No fue necesario crear un entrypoint permanente ni modificar código productivo.
El ejecutor puntual se envió por entrada estándar a backend/.venv/Scripts/python.exe -B -.
Un wrapper temporal de contexto vinculó el repositorio a la conexión/transacción
externa, permitiendo auditar antes del COMMIT sin realizar commits intermedios.
No otorga capacidades de exportación ni se instala en FastAPI.

## Precondiciones reales

Se verificaron primero mediante una transacción READ ONLY REPEATABLE READ, con
SHOW transaction_read_only=on. Se repitieron dentro de la transacción protegida,
antes de llamar al método oficial.

| Comprobación | Resultado |
|---|---|
| Configuración y current_database | usuarios_dev, 127.0.0.1:5434 |
| Revisión | 0006_cloud_embeddings |
| Documento | 8ac0c745-1307-5bb4-9d56-93dfbee0b3b8 |
| Versión activa LISTA | 7cb4e79c-747d-574a-8abb-0ebcb2e07636 |
| Propietario | 32eabde4-7d17-4029-a47a-60e2e38faf05, ADMIN activo |
| Fingerprint | 1f0482094b5531fc5d3406985eb3ba0ec870af28871c4b2b7c4c6f12b6c37ed1 |
| Identidad almacenada | Coincide exactamente con Jina / jina-embeddings-v3 / 768 / retrieval.passage / retrieval.query |
| Fragmentos autorizados y checkpoints distintos | 432 / 432 |
| Pendientes | 0 |
| Vectores históricos | 864 |
| Estado inicial de la ingesta exacta | PREPARANDO |
| Punteros cloud activos totales | 0 |

Se reutilizaron export_manifest, missing_cloud y validate_vector. Se comprobaron
SHA-256 de páginas y fragmentos, correspondencia hash_entrada, identidad de los
432 fragmentos, página inicial/final y slices/offsets. Cada vector Jina tiene
768 valores finitos, dimensión declarada correcta y norma L2 dentro de ±0,01.
La identidad completa almacenada coincide con EmbeddingConfig y su fingerprint.
Los vectores históricos tienen 768 componentes finitos y norma positiva finita.

## Ejecución transaccional

- connect_timeout=10 s; lock_timeout=2 s; statement_timeout=15 s.
- Un único intento y una única llamada oficial a validate_cloud().
- Antes de escribir se adquirieron locks SHARE ROW EXCLUSIVE en todas las tablas
  public existentes, en orden determinista, dentro de la misma conexión/transacción.
  Se impidió DML concurrente durante la comparación y validación; no se detuvieron servicios.
- _guard conservó además su bloqueo de fila documental habitual.
- Antes del COMMIT se repitió la auditoría y se compararon huellas de filas de
  todas las tablas public, incluidos vectores, usuarios y conversaciones.
- Solo cambió rag_cloud_ingestas. Los locks se liberaron mediante COMMIT.
- Después se abrió otra transacción READ ONLY en la misma conexión y se verificó
  el estado confirmado y la coincidencia de las huellas posteriores.

Las huellas se calcularon en memoria a partir de filas JSON: MD5 por fila y
SHA-256 del conjunto ordenado, con conteos. No se imprimieron filas ni huellas
sensibles. Constituyen una comprobación operacional de cambios, no una prueba
criptográfica forense frente a un adversario con capacidad de fabricar colisiones.

## Resultado efectivo y auditoría posterior

**Código de salida: 0. Resultado: VERIFIED. COMMIT confirmado.**
Duración del recorrido de auditoría/validación: **3,657 segundos**; no representa
solo el tiempo del UPDATE.

| Métrica | Antes | Después |
|---|---:|---:|
| Estado de ingesta | PREPARANDO | VALIDADA |
| Embeddings Jina | 432 | 432 |
| Pendientes | 0 | 0 |
| Embeddings históricos | 864 | 864 |
| Punteros cloud activos | 0 | 0 |

Norma mínima Jina: 0,9999998934774159; máxima: 1,000000097245997.
El método oficial devolvió 432. Documento, versión activa, propietario y espacio
permanecen sin cambios. Las filas de todas las tablas public, excepto la ingesta,
conservaron sus huellas; esto incluye fragmentos, ambas versiones, embeddings
históricos/cloud, usuarios y conversaciones. La ingesta exacta fue la única
actualizada por el método oficial. No hubo errores ni anomalías detectadas.

## Pruebas y archivos

No se creó un entrypoint nuevo ni se modificó implementación; por ello no se
agregaron o ejecutaron pruebas con mocks de un entrypoint. La evidencia de este
sprint es la ejecución real única del repositorio y las auditorías pre/post.
No se repitieron suites anteriores ni se presenta esta operación como regresión
completa del proyecto.

Único archivo incorporado: docs/jina-cloud-10g-10.md. El ejecutor puntual no se
guardó como comando reutilizable, para evitar repeticiones accidentales.

## Seguridad y decisión

No se llamó a Jina, OpenRouter u Ollama, no se consumieron créditos, no se generaron
embeddings ni se reindexó. No se ejecutaron migraciones, reinicios o borrados.
No se modificaron .env, claves ni DOCUMENT_EXPORT_APPROVED=False. No se escribió
en otras bases. No se ejecutó activate() ni se escribió en rag_cloud_activos.

**GO para solicitar autorización expresa de activación, no para activarla ahora.**
La ingesta está VALIDADA y el índice sigue sin publicar. La futura activación
requiere su autorización y una nueva comprobación de identidad/estado; el éxito
de esta validación no autoriza consultas reales, reinicios ni consumo de APIs.
Se detiene la intervención en este punto.
