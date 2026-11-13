# Sprint 9.3G: pertinencia documental y selección AUTO

Fecha: **3 de noviembre de 2026**. **IMPLEMENTADO y servido; aceptación manual
con modelos reales pendiente de confirmación del responsable.** No se presenta
la interfaz con MSW como una ejecución autenticada contra Ollama real.

## Diagnóstico y reproducción

El mensaje informado corresponde al manejo HTTP **502** en React. Su rechazo
local de contrato tiene otro mensaje. El núcleo anterior aceptaba candidatos
por coseno >= 0,60 sin comprobar conceptos de la pregunta. Una respuesta general
sin citas, aun con HTTP upstream 200 y done_reason=stop, se rechaza correctamente
en resolve_citations y se convierte en IA_RESPUESTA_INVALIDA.

Se reprodujo ese recorrido con un candidato sintético de similitud 0,90 y una
respuesta general sin citas: **502 lógico/IARespuestaInvalida en citas**. Con la
política nueva, el mismo candidato no pertinente produce SIN_EVIDENCIA antes de
llamar al generador. No se debilitó la validación de referencias para aceptarlo.

**Límite de atribución histórica:** los logs existentes backend-93f contienen
cinco eventos del observador; los tres últimos tienen upstream 200, modelo/done
válidos y stop. No tienen correlación con cada acción ni etapa del rechazo.
No permiten demostrar cuál de ellos corresponde al fallo informado ni descartar
otra validación del adaptador. No se afirma haber reproducido ese evento histórico
con sus cuerpos: no se guardaron ni extrajeron prompts/respuestas del navegador.

La inspección controlada READ ONLY confirmó **una versión LISTA y 432 embeddings**.
El filtro léxico, aplicado en memoria a los fragmentos existentes sin imprimirlos,
encuentra **0** que cubran API REST y **8** que cubran los conceptos de la pregunta
de regularidad/unidad curricular. Es cobertura léxica sobre el corpus completo,
no un resultado top-k ni prueba de fundamentación semántica de una respuesta real.

Después se contrastó el ranking real con **nomic-embed-text**, solo embeddings de
consulta secuenciales no persistidos, coordinados por el mismo bloqueo local y
con las guardas de memoria. Inspección administrativa READ ONLY de la versión
activa, propietario activo, espacio/dimensión y procedencia, sin inventar sesiones
o saltarse permisos en el endpoint:

| Pregunta | Top-k | Superan 0,60 | Pertinentes | Coseno máximo | Páginas pertinentes |
| --- | ---: | ---: | ---: | ---: | --- |
| API REST | 12 | 12 | **0** | **0,6409** | Ninguna |
| Regularidad de unidad curricular | 12 | 12 | **4** | **0,7393** | **54, 55** |

Esto confirma falsos positivos del umbral en el corpus real y que el filtro no
descarta todos los candidatos académicos. No certifica una respuesta Qwen ni el
resultado HTTP autenticado. El primer intento diagnóstico falló por referenciar
un nombre de columna incorrecto en la consulta de inspección; se corrigió esa
consulta, con rollback, sin cambiar SQL productivo o datos. Fueron tres embeddings
de consulta en total, ninguno almacenado y ninguna generación Qwen.

## Implementación

- Nuevo `backend/src/app/application/rag/relevance.py`: política académica v1,
  normalización para comparación sin alterar textos, palabras completas, términos
  funcionales excluidos y equivalencias explícitas de singular/plural y conceptos.
- `use_cases.py`: política inyectada después de validar candidatos/coseno y antes
  del contexto. La composición operativa la exige mediante `AcademicRelevance()`.
  Sin fuentes pertinentes se devuelve SIN_EVIDENCIA, fuentes vacías y explicación
  para reformular o seleccionar manualmente LLM_DIRECTO. Nunca hay fallback.
- Diagnóstico seguro en backend: `rag_failure stage=<etapa> kind=<categoría>`.
  Etapas embedding/retrieval/context/generation/output/citations; categorías
  timeout/unavailable/invalid. No se interpolan excepciones, texto, identidad,
  identificadores documentales o secretos. El observador upstream conserva sus
  ocho campos; estos diagnósticos separados no agregan campos a sus eventos.
- `respuestas.py`: AUTO elige una sola estrategia por política determinista de
  términos académicos. API REST -> LLM_DIRECTO; regularidad/unidad curricular ->
  RAG. RAG exige documento explícito; una pregunta académica AUTO sin documento
  devuelve 422, sin desviarse a directo. El acceso al documento lo valida el
  mismo repositorio/caso de uso con ACL. AUTO general no lee el documento elegido.
- React `iaApi.ts` y `ConsultaIAPage.tsx`: opción AUTO, documentos autorizados,
  explicación del modo y validación de estrategia/estado/fuentes de la respuesta.
  La pantalla muestra la estrategia realmente ejecutada. Directo manual mantiene
  su llamada y contrato anteriores `/ia/consultas`.

Coseno **0,60 no se recalibró ni se presenta como relevancia demostrada**: se
conserva y se añade cobertura de todos los términos específicos en cada fuente.
Esta política conservadora puede abstenerse ante paráfrasis, sinónimos no previstos
o evidencia distribuida entre fragmentos. AUTO tampoco es un clasificador semántico
universal; preguntas ambiguas pueden requerir elección manual. Las citas válidas
solo acreditan procedencia, no entailment de cada afirmación. No se ocultan estas
limitaciones aumentando el score, inventando páginas o aceptando errores como
SIN_EVIDENCIA. La abstención exacta del modelo sigue siendo admisible; respuesta
malformada, cita inexistente, timeout e indisponibilidad siguen siendo errores.

## Pruebas

Archivos nuevos/modificados de pruebas: `backend/tests/rag/test_relevance.py`,
`backend/tests/rag/test_adapters.py`, `frontend/src/features/ia/ia.test.tsx`.

| Verificación | Resultado |
| --- | --- |
| Backend RAG + IA, incluido contrato anterior | **390 aprobadas**, 5,36 s |
| Revisión final dirigida de HTTP/adaptadores/relevancia | **29 aprobadas**, 3,00 s; incluidas en la cobertura anterior |
| React real con AuthProvider y MSW | **46 aprobadas**, 21,58 s |
| TypeScript y ESLint | Aprobados |

Se verificaron selección AUTO de una sola operación, ausencia de generación al
abstenerse, fuente/página de evidencia académica sintética, errores 502/503 sin
estado de abstención, rechazo de citas inválidas y logs sin contenido de pregunta.
Las pruebas existentes conservan cobertura de ACL, revocación, cuotas, timeout,
exclusión de modelos y contratos. No se suman repeticiones como casos distintos.
Permanece el aviso previo Starlette/TestClient; no se instalaron dependencias.

Durante la edición se corrigió un problema de codificación introducido por la
herramienta de escritura; las suites finales incluyen la validación Unicode y
los mensajes originales restaurados. No queda una excepción de pruebas ignorada.

## Estado servido y preservación

Se revalidaron ejecutables, creación exacta, comandos, parentesco y listener del
backend padre 5996/hijo 3048 antes de detener exclusivamente esa instancia.
Nuevo padre **29384**, arranque **21:01:46 -03:00**, con los mismos flags LLM y
observador, sin aprovisionamiento. Logs técnicos en el directorio protegido de
9.3E, prefijo `backend-93g-20261103-210146`. No se detuvieron otros servicios.

GET posteriores: OpenAPI **200**, enum de modos **LLM_DIRECTO/RAG/AUTO**;
documentos anónimos **401**; React/login **200**; Ollama/ps **200**, sin modelos
cargados. RAM disponible **2,000 GiB** al comenzar lecturas y **1,867 GiB** tras
cargar la corrección; son muestras, no mínimos durante generación. Se mantienen
guardas de RAM, keep_alive=0 y coordinación/exclusión de los modelos existentes.

No se ejecutaron generaciones Qwen por el agente. Se realizaron únicamente los
embeddings transitorios de consulta descritos, sin modificar los 432 vectores,
fragmentos o documento. No hubo acceso a usuarios_test, cambios
de migraciones, Docker/Compose, infraestructura, roles o contraseña del administrador.
Todas las conexiones diagnósticas fueron READ ONLY a usuarios_dev y terminaron
con rollback. Cierre a las **21:04:55 -03:00**: FastAPI y React **200**, Ollama sin
modelos cargados y RAM disponible **1,573 GiB**. No se certifica RAM mínima durante
la carga breve de Nomic a partir de estas muestras posteriores.

## Prueba manual en React

Recargar `http://127.0.0.1:5173/ia` e ingresar por el flujo normal si hace falta,
sin compartir credenciales. Ejecutar los casos secuencialmente, sin ingesta:

1. **RAG académico**, Reglamento académico, «¿Qué es una API REST?»:
   esperar **RAG / SIN_EVIDENCIA**, sin fuentes ni finalización de generación.
2. **AUTO**, misma pregunta: esperar **LLM_DIRECTO / GENERADA**, sin fuentes.
3. **AUTO**, Reglamento académico, «¿Cuáles son los requisitos para mantener la
   regularidad de una unidad curricular?»: esperar **RAG / FUNDAMENTADA**, con
   fuentes cuyas páginas físicas PDF deben contrastarse con el reglamento.
4. Errores técnicos se prueban aisladamente con dobles, sin detener Ollama ni
   provocar una avería en los servicios reales. Deben mostrar error, no abstención.

Se solicitó al responsable informar únicamente estrategia, estado, páginas o error
de A/B/C. **Pendiente esa confirmación autenticada real**; no se extrajo su sesión
ni se usó un Principal inventado para eludir permisos. No se declara completada
la aceptación real de extremo a extremo antes de recibirla.
