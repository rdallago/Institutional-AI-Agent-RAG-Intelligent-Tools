# Revisión puntual de extracción del artículo 24

Fecha: 6 de noviembre de 2026. Estado: implementada y pendiente de ingesta autorizada.

Fuente inmutable: `backend/data/documents/reglamento_academico.pdf`, SHA-256
`1decdfbfd41cc8eea5a9bb097949d0c8ade3aa3e504be23950b4b842875a2c71`.
Procedencia: cotejo visual del PDF, páginas físicas 11 y 12, renderizado en memoria
mediante Windows.Data.Pdf; transcripción aprobada por el responsable en la sesión.
No se ejecutó un nuevo OCR ni se reconstruyeron palabras con un modelo.

Revisión: `rom-art24-visual-20261106-r1`. La implementación conserva hashes de las
dos páginas originales y reemplaza exclusivamente los slices [2062,2315) de
página 11 y [124,351) de página 12. Conserva encabezados, pies y el texto del
artículo 25 y siguientes. Las coordenadas nuevas se calculan sobre las páginas
corregidas por el fragmentador existente. El PDF nunca se escribe.

La transcripción aprobada está en `article24_revision.py`, PARTS/TRANSCRIPTION.
La huella incluye la revisión, hash del PDF, hashes originales, límites y contenido
de la corrección. Huella nueva:
`28e505dba7c3941f1100b5d536fdc74eab6e8d83d89810a94a351fff141c5de8`.
`extractor_version` registra `pypdf-6.21.4+rom-art24-visual-20261106-r1`.

## Procedimiento previsto, no ejecutado

1. La CLI existente `app.presentation.cli.ingest_academic` comprueba destino
   usuarios_dev/127.0.0.1:5434, revisión SQL y propietario administrativo autorizado.
2. Extrae todas las páginas y aplica únicamente la revisión ligada al hash.
3. `stage(..., extraction_revision=REVISION)` contrasta todas las páginas antes
   de abrir una transacción. Deriva una nueva versión UUID del mismo documento
   con hash PDF + huella nueva. No actualiza la versión anterior ni su puntero.
4. Fragmenta con la política existente: **432 fragmentos previstos**, contados en
   memoria. Como los UUID pertenecen a otra versión, habrá **432 embeddings nuevos**
   con Nomic, secuenciales; no se implementó copia/reutilización incremental.
5. `missing`/`checkpoint` permiten lotes y reanudación. `checkpoint` verifica vector
   y hash de entrada; `publish` comprueba número de fragmentos/embeddings, slices,
   dimensión/norma y páginas antes de marcar LISTA y cambiar el puntero activo
   en la misma transacción.

Atención: la CLI actual publica automáticamente al completar el último lote.
No tiene una pausa adicional de aprobación entre el último embedding y publish.
Por eso no se debe ejecutar ni el primer lote sin autorización posterior para
las escrituras y el procedimiento completo. No se ejecutó ningún lote ahora.

El tiempo no está medido para esta ingesta: será aproximadamente
432 × latencia media de embedding + cargas/descargas + SQL/verificaciones.
No se presenta la latencia de una consulta como benchmark documental.
Riesgos: presión de RAM, interrupción, duración de 432 cargas secuenciales y nueva
abstención por generación/soporte aun con texto corregido. El contador de chunks
igual no implica igualdad de IDs, offsets, hashes o embeddings.

## Reversión

La versión anterior y sus 432 embeddings se conservan. Antes de publicar se debe
registrar su `activa_version_id`. Una reversión posterior requeriría una operación
administrativa autorizada, transaccional, que verifique que esa versión sigue LISTA
y pertenece al mismo documento y restaure el puntero. No existe un comando CLI
dedicado de reversión; no se implementó ni ejecutó uno. Los historiales con scope
antiguo pueden quedar temporalmente inaccesibles por la revalidación de versión
activa; no se borran ni se migran automáticamente.
