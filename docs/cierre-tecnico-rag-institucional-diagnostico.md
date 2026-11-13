# Cierre técnico del RAG institucional — diagnóstico pendiente de corrección

13 de noviembre de 2026, America/Buenos_Aires. Solo diagnóstico; sin cambios de
código, datos, ACL, publicaciones, embeddings, configuración o servicios.

## Resultado

No corresponde declarar el RAG completamente aprobado. Se reprodujeron dos
falsos negativos locales distintos y una dependencia evitable del planificador.
No se ejecutaron consultas HTTP nuevas ni llamadas a proveedores. Las pruebas
E2E siguen pendientes. La publicación institucional validada no es la causa
demostrada de estas abstenciones.

Las lecturas se restringieron a usuarios_dev, 127.0.0.1:5434, con
default_transaction_read_only=on, connect_timeout=5, statement_timeout de
10000–15000 y rollback final. Se verificaron current_database() y READ ONLY.
Muestra inicial: 2026-11-13 14:57:17 UTC, 11:57:17 Buenos Aires.
Se leyeron 72 páginas de la versión
7cb4e79c-747d-574a-8abb-0ebcb2e07636 del documento
8ac0c745-1307-5bb4-9d56-93dfbee0b3b8. Todos los hashes SHA-256 de página coincidieron.
No se accedió a usuarios_test ni se imprimieron credenciales o vectores.

## 1. Vicerrector: condición concreta del rechazo

El apartado existe: **artículo 33, Funciones del Vicerrector**.

| Página PDF | Slice del resolver | Caracteres |
|---|---|---:|
| 15 | 106–2069 | 1963 |
| 16 | 0–287 | 287 |

El resolver devuelve next_article; identifica el encabezado y el sujeto correctos,
reconstruye la continuidad y prueba el cierre por el siguiente artículo. El vínculo
de integridad del grupo coincide. Los fragmentos ordinales 85–91 que intersectan
esos slices están representados en el espacio Jina autorizado
1f048209-4b55-31fc-5d34-06985eb3ba0e.

**Falla literal_functions, en functions.py, al exigir que el cuerpo comience con
la primera viñeta:** `re.match(r'\s*(?:a[.)]|1[.)]|-)\s+', body)`.
En el texto real, después del título aparecen «ES COPIA», «1455» y una fecha
con extracción irregular, antes de `a) Desarrollar…`. El tramo previo a la lista
ocupa offsets 146–178 de página 15. Por tanto, la expresión anclada no coincide.

No falla por ausencia del artículo, confusión de autoridad, falta de cierre,
número de páginas o presupuesto. Hay dos slices y 2250 caracteres documentales,
por debajo de los límites extractivos. functions_integrity es una etiqueta común
para fallos del extractor, no una prueba de hash corrupto ni rechazo del modelo.
La rama retorna antes de embeddings, búsqueda vectorial y generación.

Como experimento diagnóstico, se quitó ese preámbulo exclusivamente de una copia
en memoria, ajustando la metadata de la copia y reconstruyendo su vínculo; la
transcripción pasó. No se modificó la fuente almacenada. Esta manipulación no es
una solución productiva ni demuestra integridad de una salida respecto del texto
original; solo aísla el chequeo de arranque como causa del falso negativo.

El fixture de test_authority_clarification_12e.py contiene directamente:
`Articulo 33. Funciones del Vicerrector.` seguido de `a. Asistir al titular.`.
Las 216 pruebas no modelaban sellos entre encabezado e inciso. Probar el nombre
de autoridad con una lista sintética limpia no cubría la estructura real observada.

Se encontró un turno persistido de la pregunta exacta, solicitud
ba4553f0-9180-4537-a1d1-bbd9ca2c2a3e, 14:09:55 UTC (11:09:55 Buenos Aires),
RAG/SIN_EVIDENCIA y respuesta reportada. No se afirma correlación uno a uno con
el trace 1e9e894892be4c76b6979936559f7ce4: el resultado normal no conserva ese trace.

**Corrección mínima propuesta, sin implementar:** distinguir un preámbulo de
autenticación documental acotado del comienzo de la lista. Verificar exactamente
el tipo de bloque permitido y la primera viñeta posterior, preservando texto,
offsets, hash y slices originales en la transcripción. No buscar cualquier `a)`
arbitrariamente ni permitir prosa desconocida antes de la lista. No eliminar sellos
del Reglamento, reconstruir OCR, aceptar listas incompletas ni rebajar el cierre.

## 2. Coordinación de Apoyo Pedagógico: evidencia y pertinencia

**Hay evidencia explícita suficiente para responder que existe información.**
Página PDF **26**, encabezado del **artículo 47**:
«Coordinacion de Apoyo Pedagogico a las Escuelas: funciona bajo la dependencia
de la Secretaria Academica». Es texto extraído, sin corregir su redacción.
El tramo siguiente describe su carácter estable e incluye asesoramiento a escuelas
y desarrollo de materiales didácticos. La existencia puede fundamentarse con el
encabezado y su oración; no exige reproducir todas las funciones o requisitos.

Denominaciones realmente presentes, sin declararlas equivalentes por suposición:

- Artículo 44, página 24: «Asesoramiento Pedagogico a Escuelas» en la enumeración
  de coordinaciones de áreas.
- Artículo 45, página 25: «Apoyo Pedag6gico a las Escuelas» entre coordinaciones.
- Página 26: mención de «Coordinaci6n de Apoyo Pedag6gico a Escuelas» y encabezado
  explícito del artículo 47, con «Pedagogico» sin el error OCR de otras menciones.
- Página 30: «Coordinaci6n de Asesoramiento Pedag6gico a las Escuelas» en una
  disposición de articulación con investigación.

El fragmento **159**, página **26**, offsets **1383–1780**, contiene el encabezado
del artículo 47 (comienza en offset 1498 de página). Está indexado, al igual que
160–161, que continúan el texto de página 26, y 162–168 de página 27.
El resolver por número devuelve un rango estructural del artículo 47 en páginas
26–29: 26/1498–2269, 27/0–2181, 28/0–2116 y 29/0–599. Esta medición es del resolver
actual; no se presenta como validación semántica exhaustiva de todas sus disposiciones.
No se propone usar automáticamente ese rango de cuatro páginas para una pregunta
de existencia, ni ampliar por eso el límite extractivo de tres fuentes.

Para la pregunta proporcionada, terms conserva:
`apoyo, coordinacion, escuelas, existe, informacion, pedagogico`.
La rama genérica de AcademicRelevance.pertinent_units exige todos esos términos
en una misma unidad. En el fragmento 159 están los conceptos del órgano; faltan
**existe** e **informacion**, que pertenecen al marco interrogativo y no a su nombre.

Reproducción con texto real, sin modificar filtros:

- Pregunta completa: fragmento 159 rechazado por pertinente_units.
- Solo el objeto «Coordinacion de Apoyo Pedagogico a las Escuelas»: el mismo
  fragmento sí tiene una unidad pertinente con el filtro existente.

Esto demuestra un falso negativo léxico para una fuente explícita sobre la
existencia del órgano. Otras menciones agregan dificultades independientes:
coordinaciones/coordinación y errores OCR como pedag6gico/pedagógico no se
normalizan globalmente. No hace falta resolver esas variantes para demostrar el
caso 159, cuyo encabezado ya contiene los términos del objeto consultado.

### Qué prueban y qué no prueban los logs aportados

En bootstrap el umbral es 0,60. La búsqueda entrega hasta 12 candidatos; ante cero
fuentes pertinentes, recover usa el mismo vector y amplía a 48. select_evidence
aplica scope, integridad y umbral; AcademicRelevance.select aplica pertinencia.
Después viene expansión de continuidad y construcción de contexto, si hay fuentes.
No se identificó una etapa separada de reranking mediante proveedor en ese flujo.

Los logs 12/48 y relevant=0 demuestran candidatos recuperados pero ninguna fuente
admitida por el conjunto de filtros. No incluyen aquí ordinales, páginas ni scores
que permitan asegurar que 159 estuvo entre los 48. El falso negativo local está
probado; **la contribución exacta del ranking al turno histórico sigue pendiente**.
No se reconstruyó un embedding ni un top-k histórico mediante llamadas externas.
Con cero fuentes, no_context ocurre antes del generador: no es abstención del LLM.

La búsqueda persistida de preguntas que contienen apoyo y escuelas encontró una
solicitud 603e3c4b-277f-46b0-a654-dd2fd3bc5b7f, 14:09:38 UTC, RAG/SIN_EVIDENCIA.
Su texto no coincide exactamente con la pregunta suministrada; no se la atribuye
al trace 0542660318204843b796fa56b2278f85. No se encontraron los traces en los
archivos locales .log/.json examinados de docs y backend. No se leyó memoria o
entorno del servidor. Conversations genera trace en memoria y lo registra en logs;
el payload normal persistido guarda resultado/solicitud/conversación, no ese trace
ni el ranking completo. No se inventan resultados históricos ausentes.

**Corrección mínima propuesta:** reconocer de manera acotada preguntas de existencia
documental y separar su marco («existe información sobre… en el reglamento») del
objeto. Exigir después encabezado o declaración explícita del mismo órgano, dentro
de scope autorizado, sin convertir una mención dispersa o un nombre parecido en
respuesta. No agregar existe/informacion como stopwords globales ni bajar umbral.
Revisar también el soporte final para permitir una respuesta de existencia
respaldada por esa declaración, sin relajar otros predicados. Si falta el seed
en candidatos reales, diagnosticar ranking por separado con metadata autorizada.

## 3. Planificador: routing y latencia

Agent._execute evita el planner en AUTO para memoria explícita, título documental
inequívoco reconocido, clima con argumentos completos y requisitos institucionales
acotados. No existe una exclusión equivalente basada en functions_target.
Un único documento autorizado no basta por sí solo para evitar el planner.

Además AgentRouter.intent clasifica «funciones del Vicerrector» como **general**:
su patrón normativo incluye rector/rectorado, pero no vicerrector. functions_target
sí reconoce esa pregunta estructural. En AUTO el planner puede reconducirla a RAG,
y solo entonces se ejecuta la extracción local. «Funciones del Rector» se clasifica
documentary, pero también puede planificarse si no hay título explícito ni otra
exclusión. En modo RAG explícito la condición del planner no se cumple.

Los 6–10 segundos son duraciones informadas de llamadas externas. El código del
transporte mide la petición, no desglosa cola remota, inferencia o red. No se
certifica una causa upstream concreta ni se midió latencia nueva. Evitar una
llamada innecesaria puede retirar ese tramo, pero no garantiza una latencia E2E.

**Propuesta:** reconocer como intención documental solo la forma estructural
acotada ya aceptada por functions_target y omitir el planner para ella, conservando
selección por catálogo autorizado, require_active, ambigüedad entre documentos y
modos explícitos. Resolver antes referencias a instrumentos concretos: no elegir
otro documento por ser el único accesible si el usuario nombró una norma distinta.
No clasificar por la palabra «funciones» sola (puede referirse a programación), ni
enviar preguntas explicativas/comparativas al extractor literal por aproximación.

Riesgos: cambios de precedencia con clima/memoria, clasificación de autoridades
genéricas fuera del ámbito institucional y selección indebida con varios documentos
o títulos contradictorios. No se propone un bypass global del planner ni de ACL.

## Regresiones necesarias y criterios de aceptación

Antes de modificar código, autorizar los ajustes anteriores. Después verificar
con fixtures/mocks, sin bases reales ni proveedores:

1. Vicerrector con el bloque de sello entre título y primer inciso, continuidad
   entre dos páginas y conservación exacta de texto/offsets/citas. Prosa desconocida,
   sellos intercalados no reconocidos, omisiones, hash alterado y cierre ausente
   deben fallar cerrados; Rector y aclaración Rectorado no deben cambiar.
2. Existencia del órgano con el encabezado realista del 159, pregunta completa y
   evidencia ausente/otro órgano. Score alto sin declaración explícita no basta.
   Verificar negación, nombres distintos, fuente ajena, versión equivocada,
   citas y soporte final; requisitos/concursos y preguntas no existenciales intactos.
3. AUTO estructural con planner que falla si es llamado, cero embeddings/generación,
   catálogo vacío, único, múltiple, selección contradictoria y norma explícita ajena.
   Conservar memoria, clima, programación y preguntas comparativas/explicativas.
4. ACL denegada antes de leer y revocación/cambio de versión antes de responder,
   sin revelar títulos, páginas o funciones de documentos privados.

Para aceptación real posterior, autorizar carga del código y persistencia de turnos,
y para la pregunta semántica autorizar la llamada Jina que pudiera requerir.
Con sesión propia del lector verificada por /auth/me: Vicerrector debe transcribir
el apartado íntegro con citas PDF 15–16; la pregunta de existencia debe responder
solo lo respaldado y citar el encabezado pertinente de página 26. Correlacionar
solicitud/trace con etapas reales. AUTO estructural no debe registrar planner ni
proveedores. Si la consulta semántica no recupera el seed, inspeccionar metadata
de candidatos sin asumir que el filtro corregido arregla también el ranking.

No se ejecutaron suites nuevas, escrituras SQL, migraciones, reconstrucciones,
reinicios ni pruebas E2E durante este diagnóstico. Las reproducciones fueron
funciones puras sobre texto leído y copias temporales en memoria. Único archivo
creado: este informe. Se detiene a la espera de autorización para cambiar código.
