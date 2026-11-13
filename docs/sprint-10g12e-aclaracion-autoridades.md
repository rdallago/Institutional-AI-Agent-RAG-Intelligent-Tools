# Sprint 10G12E — Aclaración de autoridades en consultas de funciones

13 de noviembre de 2026, America/Buenos_Aires.

**Implementación verificada con fixtures y mocks: 216 pruebas aprobadas.**
Aceptación E2E pendiente. No se conectaron bases reales ni proveedores externos.
La publicación institucional validada en 10G12D no fue modificada.

## Problema y comportamiento resultante

«¿Cuáles son las funciones del Rectorado?» entraba en la extracción estructural
de funciones. El apartado «Funciones del Rector» no coincide con ese órgano;
el resolver devolvía not_found y el caso de uso respondía SIN_EVIDENCIA genérico.
El diagnóstico previo identificó el artículo 28, páginas PDF 12–14. Esos números
no se codificaron en la corrección ni se volvieron a consultar en PostgreSQL.

Ahora, cuando no existe un encabezado exacto para funciones del Rectorado, se
busca como alternativa diferenciada un apartado de funciones del Rector. Solo
se ofrece si la resolución existente demuestra unicidad, cobertura y cierre, y
la transcripción literal existente acepta su integridad y límites. No se devuelve
el cuerpo de las funciones en esa aclaración.

La relación Rectorado → Rector se utiliza exclusivamente para sugerir una
autoridad distinta en esta rama. No es una equivalencia normativa ni un sinónimo
global; no cambia role_terms. No se infieren otras relaciones por similitud,
subcadenas o el LLM. Nuevas relaciones requieren evidencia y un alcance separado.

Un apartado exacto del Rectorado conserva prioridad. Un apartado relacionado
ambiguo, incompleto o fuera de límites no se ofrece. Una autoridad inexistente o
sin alternativa identificable conserva SIN_EVIDENCIA. Las resoluciones exactas
del Rector, Vicerrector y Consejo de Rectores mantienen su ruta original.

## Implementación y contratos

1. backend/src/app/application/rag/functions.py: RelatedFunctions contiene título,
   autoridad, sección documental, número de artículo y páginas tomados de los
   slices resueltos. FunctionsResolution extiende ArticleResolution con ese dato
   opcional; la alternativa no se devuelve como chunks de la autoridad solicitada.
2. backend/src/app/application/rag/use_cases.py: convierte esa alternativa en
   ACLARACION, indicando apartado, autoridad, artículo, sección y páginas, seguida
   de una pregunta de confirmación. Conserva la revalidación normal y del scope
   antes de entregar el resultado, igual que la transcripción anterior.
3. backend/tests/rag/test_authority_clarification_12e.py: casos controlados nuevos.
4. docs/sprint-10g12e-aclaracion-autoridades.md: este informe.

La aclaración no tiene fuentes F1–F3 porque no transcribe disposiciones ni representa
una respuesta normativa fundamentada; las páginas se indican como localización
del apartado alternativo autorizado. Se reutiliza el estado ACLARACION de RAG,
con fuentes vacías y finalizacion=null, ya admitido por API y iaApi.ts. No se
modificó frontend ni contrato HTTP. La metadata alternativa es exclusivamente
interna y procede de la lectura documental autorizada del repositorio.

No se agregó recuperación vectorial, generación ni llamadas externas. La ruta de
funciones sigue siendo estructural y anterior a embeddings/contexto LLM. Tampoco
se implementó interpretación nueva de una respuesta aislada «sí»: para confirmar,
el usuario debe formular explícitamente la consulta sobre funciones del Rector.

## Pruebas ejecutadas

Desde backend:

```powershell
& '.\.venv\Scripts\python.exe' -B -m pytest tests/rag/test_authority_clarification_12e.py tests/rag/test_literal_functions_12d.py tests/rag/test_literal_requirements_12d.py tests/rag/test_competition_relevance_12d.py tests/rag/test_academic_routing_final_12d.py tests/rag/test_article_continuity.py tests/rag/test_normative_articles.py tests/rag/test_semantic_planning.py tests/rag/test_memory_functional_12d.py tests/rag/test_institutional_publication_12d.py tests/ia/test_http_ia.py -q -p no:cacheprovider --basetemp=.pytest-tmp-authority-12e-final --tb=short
```

**216 aprobadas, 0 fallidas, 7,16 s.** Advertencia previa Starlette/HTTPX.
La ejecución inicial de 64 pruebas no se suma a esta cifra.

Cobertura: extracción del Rector; aclaración Rectorado sin cuerpo normativo;
prioridad de encabezado exacto del Rectorado; Vicerrector y Consejo de Rectores
sin confusión; autoridad inexistente y documento sin alternativa; alternativa
ambigua y documento sin cierre probado; denegación antes de leer; cambio de scope
antes de responder; cero llamadas de embeddings/generador; contrato HTTP existente
para ACLARACION. Las regresiones incluyen concursos/requisitos, artículos,
continuidad, memoria y publicación con dobles. No hubo escrituras en usuarios_dev
ni acceso a usuarios_test. Las escrituras temporales de pytest son archivos locales.

No se ejecutó toda la suite ni pruebas reales en Chrome. El fallo heredado de
test_relevance.py documentado en 10G12D no integra esta batería; no se declara
resuelto ni aprobado por esta intervención.

## Riesgos y aceptación desde navegador

La sugerencia está deliberadamente limitada a la relación explícita indicada;
otras autoridades siguen absteniéndose cuando no coinciden. Depende de que el
documento tenga encabezado y cierre reconocibles. Los límites de tres páginas,
8192 caracteres y 32768 bytes de la extracción existente siguen vigentes. La
respuesta usa la denominación de sección del resolver, que puede incluir jerarquía
documental, en lugar de inventar un nombre de norma.

Cuando el operador cargue el código por su procedimiento habitual y cuente con
autorización para las pruebas y la persistencia normal de sus turnos:

1. En Chrome, iniciar sesión normalmente como lector autorizado; comprobar en la
   respuesta nueva de /auth/me el rol, activo=true y debe_cambiar_password=false,
   sin compartir credenciales ni perfiles completos. Verificar el catálogo propio.
2. Enviar «¿Cuáles son las funciones del Rectorado?». Esperar ACLARACION con
   artículo 28, «Funciones del Rector», páginas 12 a 14 y pregunta de confirmación,
   sin transcribir funciones ni presentar al Rectorado y al Rector como equivalentes.
3. Enviar explícitamente «¿Cuáles son las funciones del Rector?». Esperar la
   transcripción completa existente, con F1/12, F2/13 y F3/14. Estas dos consultas
   estructurales no deben invocar Jina ni OpenRouter.
4. Comprobar Vicerrector y Consejo de Rectores contra sus propios apartados; una
   autoridad inexistente debe mantener SIN_EVIDENCIA. No intentar acceso a otro
   documento privado sin un caso y alcance de prueba expresamente autorizados.
5. Repetir concursos solo con autorización específica de consumo externo: esa
   consulta sí puede necesitar el embedding Jina, aunque la generación sea extractiva.

No se reiniciaron servicios, no se cambió configuración, contenido documental,
ACL, publicaciones, índices o embeddings, ni se ejecutaron migraciones. No se
declara aceptación E2E aprobada. El cambio queda listo para revisión y aceptación
manual, con las restricciones operativas y de proveedores conservadas.
