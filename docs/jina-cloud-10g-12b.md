# Sprint 10G.12B — Recuperación por artículo explícito

11 de noviembre de 2026. Implementación mínima probada localmente; **pendiente
resolver ambigüedad documental antes de declarar corregida la consulta real al artículo 24**.

## Diagnóstico demostrado

bootstrap compone CloudPostgresRAG con Jina y OpenRouter. CloudPostgresRAG redirige
las tablas vectoriales del SQL histórico a cloud, exige espacio activo VALIDADA
y conserva filtros ACL/documento/versión. No hay fallback Nomic en este recorrido.
No se inspeccionó el objeto en memoria del servidor ya iniciado.

scores contiene similitudes coseno (1 - distancia coseno, acotada a [-1,1]), no
confianza ni probabilidad. search pide top-12 ordenados por distancia y UUID;
si la selección queda vacía, recover pide hasta 48 usando el mismo vector y filtros.
Los 48 no se convierten en 12 nuevos: son una ampliación independiente. El filtro
select_evidence exige 0,60, seguido por AcademicRelevance. Los máximos comunicados
por el usuario (~0,5669) no superan 0,60: ese hecho explica relevant=0 antes de
completar artículos. Además, pertinent_units exige cobertura léxica de la pregunta
(por ejemplo establece), lo cual perjudica consultas puramente identificadoras.
No se redujo globalmente el umbral.

## Existencia real, READ ONLY

Se consultaron páginas y metadatos de fragmentos únicamente en usuarios_dev con
conexiones default_transaction_read_only=on. Sin APIs, escrituras o texto completo
impreso. En la versión 7cb4e79c-747d-574a-8abb-0ebcb2e07636:

- Artículo 24: encabezado en página 58, offset 686, fragmento ordinal 346;
  hay cinco fragmentos que alcanzan el encabezado o lo siguen en esa página.
  Artículo 25 comienza en offset 1370: el cuerpo supera un fragmento individual.
- **También existe encabezado 24 en página 11**, con variante de extracción
  rtículo reconocida por el parser. La búsqueda inicial omitió ese caso; la
  comprobación con ARTICLE definitivo detectó la duplicidad y se corrigió el diagnóstico.
- Artículo 52: página 32, offset 1327, fragmento ordinal 196; tres fragmentos
  alcanzan o siguen el encabezado. No se demostró otro encabezado siguiente en
  la ventana de dos páginas posteriores; el nuevo recorrido se abstiene.

No se puede elegir automáticamente uno de los dos artículos 24 por número sin
interpretar qué sección normativa pide el usuario. No se sustituyeron textos ni
se reparó OCR. La visibilidad/ACL permanece intacta.

## Cambios

1. application/rag/continuity.py: requested_article detecta una referencia numérica
   única; ARTICLE reconoce Artículo, Articulo, Art. y variante extraída rtículo.
   El número se compara como entero, evitando confundir 2, 24 y 124.
2. infrastructure/rag/postgres.py: explicit_article heredado por cloud exige
   require_active antes/después; consulta páginas con ACL, documento y versión
   activa exactos, verifica SHA-256, limita a 100 páginas y exige encabezado único.
   Reutiliza complete_article con páginas exactas en ventana acotada; exige cierre
   por siguiente encabezado y conserva offsets y páginas para citas.
3. application/rag/use_cases.py: referencias explícitas con repositorio compatible
   usan ese recorrido antes de generar embeddings; no dependen del score coseno.
   Preguntas generales conservan búsqueda semántica y umbral. No se aplica dos
   veces la expansión de continuidad al artículo ya completado. El presupuesto de
   contexto sigue impidiendo publicar artículos truncados.
4. application/rag/relevance.py: una fuente con encabezado exacto y único del número
   solicitado se evalúa por sus unidades documentales, sin exigir que contenga el
   verbo genérico de la pregunta. El soporte léxico de afirmaciones se conserva.
5. tests/rag/test_explicit_articles.py: casos sintéticos nuevos.
6. docs/jina-cloud-10g-12b.md: este informe.

Todos los paths anteriores de implementación son relativos a backend/src/app.
No se modificaron datos, embeddings, ACL, configuración o proveedores.

## Pruebas

Desde backend:

```powershell
& '.\.venv\Scripts\python.exe' -B -m pytest tests/rag/test_explicit_articles.py tests/rag/test_article_continuity.py tests/rag/test_jina_cloud.py tests/rag/test_core.py -q -p no:cacheprovider --basetemp=.pytest-tmp-10g12b-final-pass --tb=short
```

**95 aprobadas, 0 fallidas, 3,15 s**, aviso previo Starlette/HTTPX.
Cubren variantes 24/52, numeraciones vecinas, cierre entre páginas, usuario no
autorizado, versión cambiada, artículo inexistente/duplicado/sin cierre, consulta
sin referencia y recorrido del caso de uso con citas/página y cero embeddings.
Las suites existentes comprueban continuidad, cloud y casos generales.

Una ejecución ampliada anterior con test_relevance.py dio **103 aprobadas y 1
fallida**: test_academic_evidence_and_real_page, el fallo heredado documentado en
10B (respuesta ficticia sin respaldo en su fixture). No se corrigió ni ocultó;
la suite completa no está aprobada. Hubo errores iniciales en fixtures nuevos
(None como principal y caracteres de prueba dañados al enviar Python por stdin),
corregidos antes de la ejecución final. Un intento desde raíz no pudo importar
tests; el comando final se ejecutó desde backend.

## Resultado y repetición manual

La recuperación exacta funciona con datos sintéticos autorizados y artículo único.
La comprobación READ ONLY usando el repositorio nuevo sobre el reglamento real
produjo **cero slices para 24 y 52**: 24 por encabezados duplicados y 52 por falta
de cierre probado en ventana. Esto es abstención deliberada; no se declara resuelta
la consulta real ni funciona como prueba de generación.

Para cerrar el caso real hace falta identificar la sección normativa deseada del
artículo 24 y ampliar la selección por identidad de sección con evidencia y tests;
no elegir arbitrariamente página 11 o 58. También queda demostrar el cierre del 52.
En artículos multipágina la recuperación conserva slices por página; el validador
de respuesta puede seguir absteniéndose si una fuente de continuación carece de
encabezado propio. Esa limitación no se levantó mediante confianza artificial.

No se reiniciaron servicios. Después de cargar el cambio mediante reinicio manual
en la terminal con credenciales, abrir http://127.0.0.1:5173/ia, usar cuenta autorizada
y nueva conversación, enviar una vez «¿Qué establece el artículo 24 del reglamento
académico?». El log rag_article sources distingue este recorrido; en el documento
actual se espera abstención por ambigüedad hasta resolver la sección solicitada.
No repetir consultas de pago para diagnosticar esa ambigüedad local.

**GO para recuperación estructurada única probada con mocks; NO-GO para afirmar
corregida la consulta real de este reglamento.** No hubo APIs, consumo de créditos,
reindexación, migraciones, cambios .env o DOCUMENT_EXPORT_APPROVED, ni reinicios.
