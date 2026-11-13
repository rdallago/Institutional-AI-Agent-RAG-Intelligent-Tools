# Sprint 10G.11 — Activación real del índice vectorial Jina

10 de noviembre de 2026, America/Buenos_Aires.
**COMPLETADO: COMMIT confirmado. GO técnico para preparar las pruebas funcionales posteriores.**
No se ejecutaron consultas RAG, llamadas externas ni reinicios.

## Autorización y revisión

El usuario autorizó expresamente la publicación del índice exacto mediante el
repositorio oficial, sin extender el permiso a otros índices o servicios.
Se revisaron cloud_postgres.py, reindex_jina.py, index_jina_all.py y el informe 10G.10.
El CLI de indexación sigue bloqueando activate; no se modificó su autorización.

Firma real utilizada, una sola vez:

```python
CloudPostgresRAG.activate(actor, version)
# actor = 32eabde4-7d17-4029-a47a-60e2e38faf05
# version = 7cb4e79c-747d-574a-8abb-0ebcb2e07636
```

activate() ejecuta internamente _validate_connection(..., 432), que valida ACL,
versión activa e integridad y reafirma VALIDADA; luego inserta el puntero cloud.
Ese UPDATE interno no cambió el valor de la ingesta. No se invocó validate_cloud()
por separado ni se omitieron verificaciones. No hubo SQL manual de activación.

## Precondiciones verificadas

| Comprobación | Resultado |
|---|---|
| Destino configurado y current_database | usuarios_dev, 127.0.0.1:5434 |
| Alembic | 0006_cloud_embeddings |
| Documento no archivado | 8ac0c745-1307-5bb4-9d56-93dfbee0b3b8 |
| Versión activa LISTA | 7cb4e79c-747d-574a-8abb-0ebcb2e07636 |
| Propietario ADMIN activo | 32eabde4-7d17-4029-a47a-60e2e38faf05 |
| Fingerprint | 1f0482094b5531fc5d3406985eb3ba0ec870af28871c4b2b7c4c6f12b6c37ed1 |
| Espacio UUID | 1f048209-4b55-31fc-5d34-06985eb3ba0e |
| Configuración efectiva y almacenada | Jina / jina-embeddings-v3 / 768 / retrieval.passage y retrieval.query; identidad exacta coincidente |
| Embeddings y fragmentos distintos con checkpoint | 432 / 432 |
| Pendientes | 0 |
| Embeddings históricos | 864 |
| Ingesta | VALIDADA |
| Punteros cloud antes de activar | 0 |

Se reutilizaron export_manifest(), missing_cloud() y validate_vector(). Se validaron
hashes SHA-256 de páginas/fragmentos, hash_entrada, páginas únicas por fragmento,
offsets y slices exactos. Los 432 vectores Jina tienen 768 valores finitos y norma
L2 dentro de ±0,01. Los 864 históricos tienen 768 valores finitos y norma positiva
finita. No se imprimieron textos, vectores o secretos.

## Ejecución y protección frente a carreras

Ejecutor puntual por entrada estándar al Python del entorno virtual:
backend/.venv/Scripts/python.exe -B -. No se creó un comando permanente.
Se utilizó el repositorio sin modificar su código, con un contexto temporal ligado
a la conexión externa para preservar una sola transacción hasta auditar el resultado.

1. Auditoría inicial en transacción READ ONLY REPEATABLE READ, SHOW confirmado.
2. Transacción de activación con connect_timeout=10 s, lock_timeout=2 s y
   statement_timeout=15 s. Locks SHARE ROW EXCLUSIVE de todas las tablas public
   existentes, en orden determinista, antes de repetir las precondiciones.
   Esto impidió DML concurrente entre las comprobaciones protegidas y la activación.
3. Una llamada a activate(OWNER, VERSION); el método conservó su FOR UPDATE documental.
4. Auditoría y comparación de huellas antes del COMMIT. Única diferencia lógica
   permitida y observada: rag_cloud_activos. La ingesta siguió VALIDADA.
5. COMMIT y liberación de locks. Nueva transacción READ ONLY para comprobar el
   puntero confirmado y las huellas posteriores, sin nuevas escrituras.

No se hicieron reintentos ni se detuvieron servicios. Si hubiera fallado una
precondición, la transacción se habría detenido sin publicar.

## Resultado efectivo

**Código de salida 0. Resultado VERIFIED. COMMIT confirmado.**
Duración de auditoría/activación: **3,214 segundos**, no solo tiempo de INSERT.

| Métrica | Antes | Después |
|---|---:|---:|
| Punteros cloud totales | 0 | 1 |
| Ingesta | VALIDADA | VALIDADA |
| Embeddings Jina | 432 | 432 |
| Fragmentos distintos con checkpoint | 432 | 432 |
| Pendientes | 0 | 0 |
| Embeddings históricos | 864 | 864 |

El único puntero publicado corresponde exactamente a la versión autorizada y al
espacio 1f048209-4b55-31fc-5d34-06985eb3ba0e; la versión pertenece al documento
autorizado y su propietario ADMIN y UUID activo no cambiaron.

**Tabla con cambio de contenido: únicamente rag_cloud_activos.** El método oficial
también ejecutó el UPDATE interno de rag_cloud_ingestas reafirmando VALIDADA,
sin diferencia lógica en sus filas. Se compararon todas las tablas public mediante
conteos y huellas ordenadas (MD5 por fila JSON y SHA-256 del conjunto), exclusivamente
en memoria. Todas las demás filas conservaron sus huellas, incluidos embeddings
cloud/históricos, documentos, ambas versiones, usuarios y conversaciones.
La comprobación operacional de huellas no es una certificación forense frente a
colisiones deliberadas. La configuración efectiva se leyó; no fue modificada.

Anomalías detectadas: ninguna. No se añadieron tests ni cambió implementación;
la evidencia es la ejecución real única y las verificaciones transaccionales.
Único archivo incorporado: docs/jina-cloud-10g-11.md.

## Límites y decisión

No hubo llamadas a Jina/OpenRouter/Ollama, consumo de créditos, embeddings nuevos,
indexación, migraciones, reinicios o escrituras en otras bases. No se modificaron
.env, credenciales o DOCUMENT_EXPORT_APPROVED=False. No se borraron datos ni se
publicaron otros índices.

**GO técnico para preparar las pruebas funcionales posteriores.** El índice está
publicado en PostgreSQL y la ingesta permanece VALIDADA. Esto no demuestra aún
recuperación semántica ni generación RAG correcta desde FastAPI/React. No se afirma
que un backend ya iniciado haya cargado la configuración actual ni sus credenciales.
Las consultas reales, consumo de APIs y cualquier arranque/reinicio permanecen
fuera de esta autorización. Se detiene la intervención tras verificar el COMMIT.
