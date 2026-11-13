# Sprint 10G12F — Correcciones finales de falsos negativos y routing

13 de noviembre de 2026, America/Buenos_Aires.

**Estado técnico actual: vía literal de existencia bajo umbral implementada.
Últimas pruebas: 94 focalizadas aprobadas; regresión ampliada: 510 aprobadas y
3 fallidas heredadas. Los conteos anteriores son históricos, no se suman.
Aceptación E2E pendiente; no se declara cierre funcional completo del proyecto.**

## Alcance y archivos modificados

Se aplicaron exclusivamente las tres correcciones autorizadas a partir de
docs/cierre-tecnico-rag-institucional-diagnostico.md:

1. backend/src/app/application/rag/functions.py: reconocimiento acotado del sello.
2. backend/src/app/application/rag/existence.py, nuevo: intención y declaración
   explícita de existencia documental, con transcripción mínima verificable.
3. backend/src/app/application/rag/relevance.py: pertinencia para esa intención.
4. backend/src/app/application/rag/use_cases.py: salida extractiva de existencia,
   citas y revalidación de autorización/scope.
5. backend/src/app/application/agent/router.py: intención estructural institucional.
6. backend/src/app/application/agent/agent.py: bypass acotado del planner en AUTO.
7. backend/tests/rag/test_final_corrections_12f.py, nuevo: fixtures y dobles de prueba.
8. docs/sprint-10g12f-correcciones-finales-rag.md: este informe.

No se modificaron frontend ni contratos públicos. Se reutilizan FUNDAMENTADA,
SIN_EVIDENCIA y ACLARACION existentes. No hubo lecturas o escrituras en bases
reales, acceso a usuarios_test, llamadas externas, Alembic, regeneración de
embeddings, cambios de publicación/ACL/configuración ni reinicios. Los temporales
de pytest son archivos locales, no datos PostgreSQL. No se alteró el Reglamento.

## 1. Vicerrector: validar el sello sin eliminarlo

literal_functions conserva el reconocimiento directo de la primera viñeta.
Adicionalmente admite exactamente un bloque inicial con estas líneas:

- ES COPIA.
- Identificador decimal de uno a seis dígitos.
- Fecha con día de dos dígitos (admite separación entre ellos), mes de una lista
  cerrada de abreviaturas españolas y año 20xx. Se valida la fecha de calendario.
  Se permite el glifo de reemplazo conocido como separador previo al mes.
- Inmediatamente después, primera viñeta válida a./a), 1./1) o guion, como antes.

No se busca arbitrariamente una viñeta posterior. Prosa antes o después del sello,
otro sello, duplicación, mes desconocido o fecha inválida impiden la extracción.
La comprobación solo reconoce la estructura; no borra ni reconstruye texto OCR.

La respuesta conserva todos los slices originales, incluidos sello y fecha, con
offsets, texto, vínculo SHA-256 interno, continuidad, cierre y citas sin cambios.
El repositorio mantiene la validación del hash de cada página antes del resolver.
Los límites de tres páginas/fuentes, 8192 caracteres y 32768 bytes no se amplían.

El fixture reproduce la posición del sello entre título e inciso y la continuidad
PDF 15–16 con texto normativo sintético. No se copió ni modificó contenido real.
La extracción del Rector y la aclaración Rectorado → Rector de 12E siguen cubiertas.

## 2. Existencia documental de una coordinación

existence_target reconoce exclusivamente la forma «¿Existe información sobre
la/el coordinación de … en el reglamento?». Se separa ese marco de la identidad
del órgano. No se agregan stopwords, alias o stemming globales; para la identidad
se conservan el orden y todas las palabras sustantivas, admitiendo solo partículas
gramaticales opcionales. Nombres parecidos o reordenados no son equivalentes.

La pertinencia exige un encabezado explícito de artículo con número y nombre
coincidente, seguido de una oración completa y positiva «funciona bajo la
dependencia de la/el …». Una mención incidental, declaración negativa, órgano
distinto, frase incompleta o modalidad hipotética no acredita existencia.
Esta gramática deliberadamente acotada cubre el encabezado demostrado del 47;
otras formas documentales pueden seguir absteniéndose y no se adivinan.

La recuperación conserva vector, top-12, recovery hasta 48 y umbral configurado.
select_evidence sigue comprobando scope e integridad formal antes de pertinencia.
El fixture análogo al fragmento 159 usa PDF 26 y offset inicial 1383, con texto
previo ajeno y encabezado explícito. Un score 0,59 sigue rechazándose.

Tras la recuperación, solo una declaración inequívoca permite una respuesta
afirmativa. Dos localizaciones/declaraciones distintas causan abstención; copias
solapadas de la misma declaración no se consideran alternativas diferentes.
La respuesta contiene «Sí. Información documental localizada (extracto literal)»,
la declaración exactamente presente en el chunk y F1 con su página y scope.
No se generan otras atribuciones, requisitos o funciones.

El soporte de esta ruta es identidad literal del span completo seleccionado, no
aprobación por similitud ni una excepción al validador de claims generados. Se
ejecutan validate_output, resolve_citations y la revalidación normal/scope antes
de responder. Los validadores generativos generales no se relajaron.

La pregunta de existencia no exige expandir ni transcribir todo el artículo de
cuatro páginas. Por eso esta ruta acotada termina antes de continuidad y contexto
LLM, con máximo una fuente y salida de 3000 caracteres/9000 bytes (sin ampliar
límites anteriores). No llama al generador; el embedding de búsqueda sigue siendo
necesario en uso real. Se registra rag_existence mode=extractive sources=1 o
abstención existence_integrity, sin cuerpos privados.

## 3. Routing determinista institucional

institutional_functions exige la forma exacta reconocida por functions_target y
una autoridad sin calificadores: Rector, Rectorado, Vicerrector, Director,
Vicedirector o Consejo de Rectores. No se usa la palabra «funciones» aisladamente
ni se infieren autoridades arbitrarias. Las formas explicativas, comparativas,
programación y consultas con norma nombrada quedan fuera de este bypass.

En AUTO, esa intención es documental y evita el planner. Catálogo autorizado
vacío conserva SIN_EVIDENCIA; uno permite resolver; varios sin selección exigen
ACLARACION. No se elige el primero. Una selección explícita se revalida igual que
antes; se mantiene require_active y la revalidación final del resolver/RAG.

Un título documental o una cláusula «según» añadidos a la pregunta impiden este
atajo: conservan la lógica existente de selección explícita/desambiguación, sin
sustituir la norma nombrada por el único documento disponible. La prueba de título
contradictorio verifica que se alcanza esa planificación, sin hacer llamadas reales.
No se cambiaron las ramas previas de memoria/clima ni los modos RAG/LLM_DIRECTO.

Cuando la extracción literal se resuelve, no hay llamadas a planner, embeddings o
generador. No se promete una reducción E2E medida: no se midieron proveedores ni
latencia real. Las preguntas fuera del patrón mantienen el comportamiento previo.

## Pruebas y resultados exactos

Batería final desde backend:

```powershell
& '.\.venv\Scripts\python.exe' -B -m pytest tests/rag/test_final_corrections_12f.py tests/rag/test_authority_clarification_12e.py tests/rag/test_literal_functions_12d.py tests/rag/test_literal_requirements_12d.py tests/rag/test_competition_relevance_12d.py tests/rag/test_academic_routing_final_12d.py tests/rag/test_article_continuity.py tests/rag/test_normative_articles.py tests/rag/test_semantic_planning.py tests/rag/test_memory_functional_12d.py tests/rag/test_institutional_publication_12d.py tests/ia/test_http_ia.py -q -p no:cacheprovider --basetemp=.pytest-tmp-12f-release --tb=short
```

**260 aprobadas, 0 fallidas, 10,40 s**, advertencia previa Starlette/HTTPX.
Incluye los 44 casos del archivo nuevo, conservación de Rector/Rectorado,
Vicerrector, otras autoridades, requisitos/concursos, ambigüedad, artículos,
continuidad, memoria, publicación y contratos HTTP con dobles. También verifica
recuperación ampliada con un solo embedding, fuente negativa/ausente/ajena,
versión incorrecta, ACL inicial denegada, revocación y cambio de scope antes de
responder. Dos errores iniciales de expectativas de excepción en tests de
revocación se ajustaron al manejo existente: el fallo sigue cerrado y sin
entregar evidencia. No se cambió el manejo productivo de esas excepciones.

No sumar las ejecuciones intermedias de 113 o 258 aprobaciones a la cifra final.

### Regresión ampliada y fallos fuera de alcance

Se ejecutó además la misma selección anterior, antes del último ajuste de
metadata de logging, agregando:

```text
tests/rag/test_agent.py tests/rag/test_core.py tests/rag/test_tools_memory.py
tests/rag/test_weather_rag_functional_12d.py tests/rag/test_structured_output.py
tests/rag/test_evidence_memory_12d.py tests/rag/test_explicit_articles.py
```

Con --basetemp=.pytest-tmp-12f-final y las mismas opciones pytest:
**430 aprobadas, 2 fallidas, 16,98 s**. Los fallos son:

- test_auto_academic_selects_authorized_document_and_applies_real_skill: espera
  una lectura de catálogo; el recorrido existente hace dos.
- test_multiple_documents_require_selection_not_random_choice: su doble de
  catálogo omite titulo y explicit_document produce KeyError.

Ambos se reprodujeron en un proceso de prueba aislado desactivando únicamente
institutional_functions en memoria: **2 fallidas, 1,97 s**, mismos errores.
Las preguntas de esos casos no activan la rama nueva de existencia ni la de
sellos. Esta comprobación aísla el nuevo routing; no es una ejecución de un
checkout histórico completo. No se alteraron expectativas o código fuera de
alcance para ocultarlos. Los casos nuevos de múltiples documentos sí incluyen
el contrato de título y pasan conservando ACLARACION.

Ejecución separada:

```powershell
& '.\.venv\Scripts\python.exe' -B -m pytest tests/rag/test_relevance.py -q -p no:cacheprovider --basetemp=.pytest-tmp-12f-legacy --tb=short
```

**9 aprobadas, 1 fallida, 0,59 s**. Persiste
test_academic_evidence_and_real_page, documentado previamente: la respuesta
«Norma ficticia» no está sustentada por la evidencia de asistencia del fixture.
No se debilitó el soporte ni se modificó esa prueba. No se declara aprobada toda
la regresión del proyecto. No se repitió frontend porque no cambió su contrato.

## Riesgos pendientes y aceptación E2E

Los patrones son deliberadamente acotados; otros sellos, encabezados o preguntas
pueden abstenerse. No se sabe si el fragmento 159 estaba entre los candidatos del
turno histórico: admitirlo por pertinencia no garantiza que el ranking lo entregue.
No se implementaron reintentos ni llamadas adicionales para compensarlo.

Las tres fallas de tests fuera de alcance requieren seguimiento separado antes
de declarar una suite global limpia. Las comprobaciones con mocks no prueban
la versión cargada actualmente en FastAPI ni las sesiones reales del navegador.

Aceptación propuesta, NO ejecutada aquí, tras autorización para cargar el backend
y persistir los turnos de prueba; no iniciar otra instancia sobre un puerto ocupado:

1. Usar una sesión propia de USUARIO activo; comprobar /auth/me y catálogo con
   la misma sesión sin compartir JWT, cabeceras, contraseñas, perfiles completos o HAR.
2. En AUTO, «¿Cuáles son las funciones del Vicerrector?»: transcripción completa
   con sello preservado, continuidad y F1/15, F2/16. No debe aparecer planner ni
   llamadas a embeddings/generación para ese turno.
3. Rector: transcripción previa F1/12, F2/13, F3/14. Rectorado: aclaración de 12E,
   sin transcribir funciones del Rector como si fueran del órgano solicitado.
4. Solo con autorización adicional de consumo Jina, enviar una vez la pregunta
   completa de existencia sobre Apoyo Pedagógico. Esperar declaración literal del
   artículo 47, F1/página 26, sin generación OpenRouter tras retrieval. En AUTO
   esta consulta no estructural de funciones puede conservar planificación LLM:
   si se prueba así, también requiere autorizar esa llamada OpenRouter. RAG con
   selección documental explícita permite evaluar esta corrección sin planner.
5. Correlacionar solicitud/trace, rag_selection/recovery y rag_existence. Si no
   recupera el seed, analizar páginas/scores/ordinales autorizados sin bajar umbral.
6. Concursos solo con permiso de consumo externo; verificar su lista literal
   previa y cita página 33. No usar la identidad ADMIN para simular al lector ni
   modificar ACL/publicaciones para fabricar casos de prueba.

**Estado final: GO técnico para revisión y aceptación manual de las tres
correcciones; aceptación E2E y cierre integral del proyecto pendientes.**
Se termina esta intervención sin reinicios ni consultas reales.

## Cierre puntual autorizado: sello U+00B7 e instrumentación de recuperación

13 de noviembre de 2026. Esta continuación actualiza el estado técnico anterior:
**corrección puntual probada; aceptación funcional de ambos casos en React pendiente**.
No se reinició el backend, no se consultó PostgreSQL ni se ejecutó E2E.

### Cambio y archivos

1. `backend/src/app/application/rag/functions.py`: el separador opcional de fecha
   que admitía U+FFFD admite además U+00B7, exclusivamente en la misma posición.
   No cambian día, mes, año, sello, primera viñeta ni las guardas de extracción.
2. `backend/src/app/application/rag/retrieval_diagnostics.py`, nuevo: eventos
   `rag_retrieval_diagnostic` de metadata, opt-in local, con lista cerrada de campos
   y etapas. Un fallo del logger no se propaga al resultado.
3. `backend/src/app/application/rag/use_cases.py`: observación antes y después de
   selección inicial/recovery y justo antes de invocar `literal_existence`.
4. `backend/src/app/application/rag/dto.py`: ordinal interno opcional de Chunk,
   excluido de repr y comparación. No se agregó un campo HTTP.
5. `backend/src/app/infrastructure/rag/postgres.py`: conserva el ordinal ya
   incluido en `SELECT f.*`. SQL, filtros, orden, límites y ACL no cambian.
6. `backend/src/app/bootstrap.py`: pasa el entorno real de la configuración al
   servicio para impedir habilitación del diagnóstico fuera de local-development.
7. `backend/tests/rag/test_safe_retrieval_closure_12f.py`, nuevo: sello realista,
   negativos, metadata segura, gating local, invariancia y fallo del logger.
8. Este informe.

El fixture de dos páginas conserva literalmente:

```text
ES COPIA
1455
3 0 · JUL 2014
```

Se verifica extracción completa del artículo 33 sintético de páginas 15–16,
continuación, offsets originales y F1/F2. No se reescriben sellos, texto o hashes.
Esto valida una estructura realista controlada; no es una lectura nueva del
documento real ni certificación de lo actualmente cargado en FastAPI.

### Semántica exacta de los eventos

Campos únicos: `trace_id`, `stage`, `ordinal`, `page`, `score`,
`threshold_passed`, `scope_authorization`, `integrity`, `pertinent`,
`reached_literal_existence`. No se registran identificadores de usuarios,
fragmentos textuales, nombres de órganos, prompts, respuestas, JWT o vectores.
El trace acepta UUID/hex de 32 caracteres; otros valores se rotulan `isolated`.

Etapas: `initial`, `initial_selection`, `recovery`, `recovery_selection`,
`literal_existence`. Se conserva el orden recibido en cada etapa. La instrumentación
no ordena, descarta ni agrega candidatos al procesamiento productivo.

- `scope_authorization` indica coincidencia con el scope que ya pasó las guardas
  de autorización del repositorio. No es una nueva consulta ACL ni observa filas
  excluidas por SQL; no prueba permisos de identidades ajenas.
- `integrity` comprueba la validación formal pura de `select_evidence`, separada
  de scope. No recalcula hashes de páginas ni certifica integridad criptográfica.
- `threshold_passed` refleja score >= umbral vigente, sin cambiarlo.
- `pertinent` registra admisión efectiva al finalizar la selección existente.
  No vuelve a ejecutar AcademicRelevance. Antes de selección y cuando no corresponde
  evaluar pertinencia por scope/integridad/umbral se registra null; no inventa
  un rechazo léxico para un candidato que no alcanzó esa evaluación.
- En `literal_existence`, se registran los chunks efectivamente suministrados.
  Score y umbral son null porque esa etapa recibe chunks sin score; el score se
  correlaciona con el ordinal en eventos anteriores. El booleano de llegada no
  implica que el extractor haya aceptado la declaración.

Si la lista está vacía no hay eventos de fragmentos en esa etapa. Los logs
existentes `rag_selection`, `rag_recovery`, `rag_retrieval` y `rag_abstention`
conservan sus conteos y resultado. La ausencia de un ordinal en los candidatos
observados no demuestra ausencia del contenido en el índice. La instrumentación
no reconstruye los candidatos del turno histórico ni cambia la gramática existencial.

### Pruebas finales

Desde backend, selección focalizada:

```powershell
& '.\.venv\Scripts\python.exe' -B -m pytest tests/rag/test_safe_retrieval_closure_12f.py tests/rag/test_final_corrections_12f.py tests/rag/test_authority_clarification_12e.py -q -p no:cacheprovider --basetemp=.pytest-tmp-12f-safe-focused-final --tb=short
```

**Focalizadas: 73 aprobadas, 0 fallidas, 1,80 s.** Advertencia heredada Starlette/HTTPX.

Regresión ampliada ejecutada:

```powershell
& '.\.venv\Scripts\python.exe' -B -m pytest tests/rag/test_safe_retrieval_closure_12f.py tests/rag/test_final_corrections_12f.py tests/rag/test_authority_clarification_12e.py tests/rag/test_literal_functions_12d.py tests/rag/test_literal_requirements_12d.py tests/rag/test_competition_relevance_12d.py tests/rag/test_academic_routing_final_12d.py tests/rag/test_article_continuity.py tests/rag/test_normative_articles.py tests/rag/test_semantic_planning.py tests/rag/test_memory_functional_12d.py tests/rag/test_institutional_publication_12d.py tests/ia/test_http_ia.py tests/rag/test_agent.py tests/rag/test_core.py tests/rag/test_tools_memory.py tests/rag/test_weather_rag_functional_12d.py tests/rag/test_structured_output.py tests/rag/test_evidence_memory_12d.py tests/rag/test_explicit_articles.py tests/rag/test_relevance.py tests/rag/test_jina_cloud.py -q -p no:cacheprovider --basetemp=.pytest-tmp-12f-safe-verified --tb=short
```

**489 aprobadas; 3 fallidas; 8,15 s.** Advertencia heredada Starlette/HTTPX.
No sumar ejecuciones. Los tres fallos previamente documentados permanecen intactos:

- `test_agent.py::test_auto_academic_selects_authorized_document_and_applies_real_skill`:
  dos lecturas de catálogo frente a una esperada.
- `test_agent.py::test_multiple_documents_require_selection_not_random_choice`:
  fixture sin `titulo`, KeyError en selección documental explícita.
- `test_relevance.py::test_academic_evidence_and_real_page`: respuesta ficticia sin
  soporte, SIN_EVIDENCIA frente a FUNDAMENTADA esperada.

No se modificaron sus expectativas ni implementación. Las pruebas nuevas verifican
separadores desconocidos, sello duplicado, prosa inesperada, fecha inválida,
extracción literal, Rector/Rectorado, recovery, ordinal 159, scope, integridad,
umbral, trace saneado, logger fallido y resultados/candidatos sin cambios.
Los proveedores/repositorios son dobles o MockTransport; no hubo llamadas externas
ni escrituras en bases reales. Las pruebas nuevas bloquean conexiones externas
por socket; permiten loopback para el self-pipe de asyncio en Windows.
Una iteración del guard de pruebas bloqueó también ese self-pipe y ocasionó cinco
fallos nuevos de infraestructura de tests; se corrigió esa guarda, sin modificar
el código productivo para ocultarlos. La ejecución final solo conserva los tres
fallos heredados indicados.

### Habilitación temporal, NO ejecutada

Apagado por defecto. Se requieren **ambas** condiciones: entorno real del servicio
`local-development` y variable exactamente `AGENT_RAG_RETRIEVAL_DIAGNOSTICS=true`.
Los eventos usan WARNING para ser visibles con el logging habitual, sin cambiar
la configuración global del logger. No requiere captura privada de prompts/claims.

En una futura carga del backend autorizada, desde la terminal privada del operador:

```powershell
$env:AGENT_RAG_RETRIEVAL_DIAGNOSTICS='true'
Set-Location 'D:\Downloads\proyectos\api-usuarios-clean\backend'
$env:PYTHONPATH=(Join-Path (Get-Location) 'src')
& '.\.venv\Scripts\python.exe' -B -m app.presentation.cli.local_server --environment local-development --enable-llm --observe-llm --host 127.0.0.1 --port 8000
```

No ejecutar sobre un puerto ocupado ni reiniciar bajo esta intervención. Cambiar
la variable en otra terminal no habilita el proceso existente. Al terminar la
ventana de observación, retirar la variable de la terminal antes de una futura carga:

```powershell
Remove-Item Env:AGENT_RAG_RETRIEVAL_DIAGNOSTICS -ErrorAction SilentlyContinue
```

Retirarla de la terminal tampoco cambia el entorno del proceso ya iniciado.
No se editó .env ni se activó el flag en servicios desde esta intervención.

### Aceptación pendiente y riesgos

Después de autorizar carga y turnos reales, comprobar Vicerrector desde React:
artículo completo, sello original, F1/15 y F2/16, sin planner/embeddings/generación
en esa ruta estructural. Rector y aclaración Rectorado deben conservarse.
Para Apoyo Pedagógico, autorizar también los proveedores que requiera el modo
elegido: Jina en retrieval; AUTO puede utilizar además el planner OpenRouter.
Con el trace correlacionado, buscar ordinal 159 en cada etapa y distinguir ausencia
en candidatos, descarte por umbral/scope/integridad/selección y llegada al extractor.
Si llega y se abstiene, conservar esa evidencia antes de proponer otro parche.

El diagnóstico añade trabajo local y volumen de logs solo al habilitarlo. Sus
flags no certifican revisión de código cargada, ranking histórico o semántica final.
No hay cambios de umbral, top-k, recovery, ranking, existencia, ACL, publicaciones,
frontend, contratos públicos, proveedores o documento original.
No se ejecutaron migraciones, conexiones a usuarios_test, operaciones PostgreSQL,
embeddings nuevos, reinicios ni E2E. **No se declara cierre funcional**: ambos
casos deben verificarse en React. Se detiene aquí.

## Existencia literal independiente del umbral — última implementación autorizada

13 de noviembre de 2026. Esta sección sustituye la dependencia anterior del umbral
para la respuesta extractiva de existencia; no cambia el umbral de recuperación
general. **Implementación y regresiones terminadas; aceptación real pendiente.**

### Evidencia recibida y corrección

El operador informó para el trace `0288eca236b24a299d11a2c3344ebacf` que el ordinal
159, PDF 26, ocupó la primera posición, score **0.5442609896426569**, con scope e
integridad válidos, pero fue descartado por el umbral 0,60 en selección inicial y
recovery. Es evidencia E2E aportada, no un nuevo turno ejecutado por este agente.

Solo para preguntas reconocidas por `existence_target`, el caso de uso conserva
los chunks de los candidatos ya recuperados. Se conservan después de ejecutar
`select_evidence`: esa función valida TODOS los candidatos (incluidos los de
score inferior al umbral) antes de filtrar y ordenar su salida normal. Scope
incorrecto, score no finito/fuera de rango, texto inválido, página u offsets
incorrectos mantienen el rechazo existente. No se transforma un candidato inválido
en fuente admisible.

La selección normal continúa usando el mismo umbral y AcademicRelevance. El recovery
se ejecuta exactamente bajo la condición previa, con el mismo vector, sin nuevos
intentos. Si se ejecutó, se conservan también sus candidatos ya validados. Se examinan
los dos lotes, en su orden de recepción: máximo 12 iniciales y 48 de recovery,
hasta 60 entradas ya recuperadas contando repeticiones; no se solicitan candidatos
adicionales ni se agrega otra búsqueda. Incluir ambos lotes evita ocultar una
declaración distinta del inicial si recovery devuelve otra. Las copias solapadas
de la misma declaración se deduplican por el mecanismo literal existente.

Ese conjunto alimenta exclusivamente `literal_existence`, que sigue exigiendo
encabezado de artículo, identidad del órgano, declaración positiva completa y
una única localización/declaración inequívoca. Su gramática no cambia. Similitud
alta o baja no acredita el contenido. Si no se verifica la declaración, retorna
SIN_EVIDENCIA. La rama retorna siempre antes de continuidad, contexto generativo
y proveedor LLM; no hay fallback generativo ni aprobación de claims generales.

La lectura documental y sus controles productivos de autorización/integridad del
repositorio permanecen intactos. Se conservan documento/version activos, validación
de salida, cita/página verificable y revalidación de acceso normal y scope antes
de devolver la respuesta. Una revocación o cambio de versión falla cerrado con
las excepciones existentes. No se elimina ni normaliza texto documental.

### Archivos modificados en esta intervención

1. `backend/src/app/application/rag/use_cases.py`: conservación acotada de candidatos
   ya validados y suministro exclusivo al verificador literal de existencia.
2. `backend/tests/rag/test_literal_existence_threshold_12f.py`, nuevo: 21 regresiones
   con dobles, score reportado y umbral de producción 0,60.
3. `backend/tests/rag/test_final_corrections_12f.py`: se reemplaza la expectativa
   anterior de abstención literal bajo umbral por la respuesta extractiva ahora
   autorizada. No se tocaron los tres tests heredados fallidos.
4. Este informe.

No cambian `existence.py`, `relevance.py`, `core.py`, SQL, funciones institucionales,
routing, proveedor, frontend ni contratos públicos.

### Observabilidad e invariantes

La instrumentación previa sigue apagada por defecto y conserva su habilitación
local documentada arriba. `initial_selection` y `recovery_selection` siguen mostrando
`threshold_passed=false` y `pertinent=null` para el candidato bajo umbral. En
`literal_existence` ahora puede aparecer `reached_literal_existence=true` para ese
candidato. En esta etapa `pertinent` es null: solo se registra llegada al verificador,
no aceptación de la declaración. Score y umbral siguen null en dicha etapa sin score.
El resultado extractivo se confirma mediante `rag_existence` o la abstención
existente. No se agregaron campos, texto, prompts o datos personales al diagnóstico.

Rector, Rectorado, Vicerrector, requisitos, concursos y otras preguntas conservan
sus ramas. Una pregunta no existencial sigue filtrada a 0,60: las nuevas regresiones
comprueban explícitamente los bordes 0,599999 y 0,60 antes de pertinencia.

### Ejecuciones finales y resultados

Desde backend:

```powershell
& '.\.venv\Scripts\python.exe' -B -m pytest tests/rag/test_literal_existence_threshold_12f.py tests/rag/test_safe_retrieval_closure_12f.py tests/rag/test_final_corrections_12f.py tests/rag/test_authority_clarification_12e.py -q -p no:cacheprovider --basetemp=.pytest-tmp-12f-literal-final-focused --tb=short
```

**Focalizadas: 94 aprobadas, 0 fallidas, 5,35 s.**

```powershell
& '.\.venv\Scripts\python.exe' -B -m pytest tests/rag/test_literal_existence_threshold_12f.py tests/rag/test_safe_retrieval_closure_12f.py tests/rag/test_final_corrections_12f.py tests/rag/test_authority_clarification_12e.py tests/rag/test_literal_functions_12d.py tests/rag/test_literal_requirements_12d.py tests/rag/test_competition_relevance_12d.py tests/rag/test_academic_routing_final_12d.py tests/rag/test_article_continuity.py tests/rag/test_normative_articles.py tests/rag/test_semantic_planning.py tests/rag/test_memory_functional_12d.py tests/rag/test_institutional_publication_12d.py tests/ia/test_http_ia.py tests/rag/test_agent.py tests/rag/test_core.py tests/rag/test_tools_memory.py tests/rag/test_weather_rag_functional_12d.py tests/rag/test_structured_output.py tests/rag/test_evidence_memory_12d.py tests/rag/test_explicit_articles.py tests/rag/test_relevance.py tests/rag/test_jina_cloud.py -q -p no:cacheprovider --basetemp=.pytest-tmp-12f-literal-final-expanded --tb=short
```

**Regresión ampliada: 510 aprobadas, 3 fallidas, 35,85 s.** No sumar ejecuciones.
Ambas ejecuciones presentan la advertencia heredada Starlette/HTTPX.

Fallos, sin modificaciones ni ocultamiento:

- `test_agent.py::test_auto_academic_selects_authorized_document_and_applies_real_skill`:
  dos lecturas de catálogo, expectativa de una.
- `test_agent.py::test_multiple_documents_require_selection_not_random_choice`:
  KeyError `titulo` en el doble de catálogo.
- `test_relevance.py::test_academic_evidence_and_real_page`: respuesta ficticia
  sin soporte, SIN_EVIDENCIA frente a FUNDAMENTADA esperada.

La batería nueva verifica ordinal 159/PDF 26 con el score real informado,
recovery sin llamadas adicionales y una sola invocación de embedding simulada;
candidato sin declaración, otro órgano, negación, texto incompleto, encabezado
ausente, ambigüedad entre lotes, documento/version incorrectos, ACL denegada o
revocada, offsets/página/texto inválidos y NaN. También verifica límites 12/48,
orden de candidatos, umbral no existencial y metadata de llegada al extractor.
Las regresiones previas cubren Rector/Rectorado/Vicerrector y concursos.

Una ejecución inicial tuvo dos fallos nuevos en assertions de configuración del
fixture: el helper sintético anterior usa umbral 0,70. Se fijó explícitamente 0,60
en el nuevo helper de pruebas para reproducir producción; no se cambió la constante
productiva para aprobarlos. Los resultados finales anteriores corresponden a esa
corrección y no contienen nuevos fallos. Proveedores y repositorios son dobles o
MockTransport; la guarda de red de las pruebas nuevas impide conexiones externas.

### Pendiente funcional

No se reinició el backend ni se habilitó observabilidad en su proceso. No hubo
conexiones/escrituras PostgreSQL, migraciones, embeddings nuevos, accesos a
usuarios_test, cambios de documentos, ACL/publicaciones o llamadas externas.
La implementación requiere una futura carga autorizada para ser usada por React.

Tras autorizar carga, persistencia y consumo externo necesario, repetir una vez
la pregunta exacta con la sesión propia autorizada. Comprobar declaración del
artículo 47, F1/PDF 26, respuesta literal sin generación LLM y correlación del trace.
Puede seguir viéndose selección normal con cero pertinentes; eso ya no impide
la verificación literal independiente. No afirmar éxito solo por llegada al extractor:
verificar el resultado y sus citas. **Aceptación E2E y cierre funcional pendientes.**
Se termina la implementación aquí, sin ejecutar esa prueba real.
