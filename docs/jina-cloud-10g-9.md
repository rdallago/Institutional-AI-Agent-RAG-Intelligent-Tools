# Sprint 10G.9 — Verificación final READ ONLY de embeddings Jina

10 de noviembre de 2026, America/Buenos_Aires.
**GO técnico para solicitar autorización de validación oficial.** No se ejecutó
validación que escriba estados ni activación.

## Método y alcance

Conexión efectiva a usuarios_dev, 127.0.0.1:5434, connect_timeout=10,
default_transaction_read_only=on y statement_timeout=10000. Se comprobó
transaction_read_only=on. Todas las lecturas se realizaron en una única
transacción REPEATABLE READ, terminada con ROLLBACK; después se cerró el engine.

Se reutilizaron CloudPostgresRAG.export_manifest(), missing_cloud() y
validate_vector(). Los métodos de lectura compartieron la conexión y snapshot
mediante un wrapper temporal en memoria, sin cambios productivos. No se invocaron
validate_cloud(), _validate_connection(), activate(), prepare_existing() ni
checkpoint_cloud(): algunos de estos métodos escriben estados o toman locks.

El script de auditoría se ejecutó por entrada estándar con el Python del backend,
-B, sin guardar una nueva infraestructura de auditoría. Resultado del proceso: 0.
Solo se imprimieron conteos, estados, UUID y resúmenes numéricos. Textos y vectores
se procesaron exclusivamente en memoria. No se imprimieron credenciales.

## Identidad y conteos verificados

| Comprobación | Resultado |
|---|---|
| Alembic | 0006_cloud_embeddings |
| Documento | 8ac0c745-1307-5bb4-9d56-93dfbee0b3b8 |
| Versión activa | 7cb4e79c-747d-574a-8abb-0ebcb2e07636 |
| Propietario | 32eabde4-7d17-4029-a47a-60e2e38faf05, ADMIN activo |
| Fingerprint | 1f0482094b5531fc5d3406985eb3ba0ec870af28871c4b2b7c4c6f12b6c37ed1 |
| Identidad almacenada | Coincide exactamente con EmbeddingConfig: Jina, jina-embeddings-v3, 768, retrieval.passage / retrieval.query y normalización definida |
| Espacios cloud / ingestas | 1 / 1 |
| Fragmentos activos en manifiesto íntegro | 432 |
| Embeddings para versión y fingerprint exactos | 432 |
| Fragmentos distintos con checkpoint | 432 |
| Pendientes según missing_cloud | 0 |
| Embeddings del mismo espacio en otras versiones | 0 |
| Total de embeddings cloud | 432 |
| Total de fragmentos históricos | 864 |
| Total de embeddings históricos | 864 |

export_manifest confirmó documento no archivado, propietario ADMIN activo y
versión LISTA que continúa siendo la activa del documento. La identidad coincide
con la prevista; esta auditoría de almacenamiento no certifica los pesos internos
ni una revisión inmutable del modelo upstream.

## Integridad vectorial y documental

Los 432 vectores Jina superaron validate_vector: 768 componentes numéricos finitos
y vector no nulo. También se comprobó dimensión declarada 768 y norma L2 con
abs(norma - 1) <= 0,01, igual que el checkpoint/validador del proyecto.

- Norma mínima: 0,9999998934774159.
- Norma máxima: 1,000000097245997.
- Errores vectoriales, hashes contradictorios y fragmentos repetidos: 0.

Para cada checkpoint se comparó hash_entrada con hash_texto del fragmento y con
el manifiesto íntegro. El manifiesto comprobó SHA-256 de página y fragmento,
página inicial igual a final, offsets no negativos y crecientes y coincidencia
exacta del slice de la página con el texto del fragmento. Los 432 identificadores
son distintos y no hay pendientes. No se detectaron checkpoints contradictorios
en el estado persistido; esto no reconstruye intentos anteriores no almacenados.

## Embeddings históricos y versiones

Se leyeron los 864 embeddings históricos junto con sus fragmentos/páginas.
Todos conservaron dimensión 768, componentes finitos, norma positiva y finita,
hash de entrada correcto, SHA-256 de textos/páginas y offsets/slices correctos.
No se impuso norma unitaria Jina a los vectores históricos Nomic.

| Versión | Estado | Embeddings históricos íntegros |
|---|---|---:|
| 7cb4e79c-747d-574a-8abb-0ebcb2e07636, activa | LISTA | 432 |
| 9cab30cd-9554-5679-a2d9-35d85dd5ab85, anterior | LISTA | 432 |

Errores de integridad históricos: 0. Ambas versiones pertenecen al documento
esperado. Se confirma conservación por conteo e integridad actual; no se comparó
cada componente histórico contra el dump de 10E en esta intervención, por lo que
no se afirma igualdad bit a bit con aquel snapshot. Tampoco se auditó el contenido
de usuarios o conversaciones, fuera del alcance de este pedido.

## Estado y decisión

La única ingesta cloud continúa en **PREPARANDO**. No está VALIDADA.
rag_cloud_activos contiene **0 filas**: no existe puntero activo hacia este índice
ni hacia otro espacio cloud. ACTIVADA no es un estado del CHECK de ingestas: la
publicación se representa mediante el puntero, que sigue ausente.

**Anomalías encontradas: ninguna en las comprobaciones realizadas.**
**GO para solicitar autorización expresa de validación oficial.** La comprobación
READ ONLY es satisfactoria, pero no sustituye esa operación: validate_cloud vuelve
a comprobar integridad y escribe VALIDADA. No se autoriza ni ejecuta publicación.
Antes de la futura operación deberán revalidarse identidad y estado para detectar
cambios posteriores a este snapshot. La activación requiere autorización propia.

No hubo escrituras SQL, migraciones, llamadas Jina/OpenRouter/Ollama, consumo de
créditos, cambios de configuración, reinicios o activación. No se modificó
DOCUMENT_EXPORT_APPROVED ni se borraron artefactos. Único archivo del proyecto
creado en este sprint: docs/jina-cloud-10g-9.md.
