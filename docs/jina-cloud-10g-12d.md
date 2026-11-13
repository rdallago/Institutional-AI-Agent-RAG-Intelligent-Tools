# Sprint 10G12D — Evidencia RAG y memoria conversacional

11 de noviembre de 2026, America/Buenos_Aires.
**PUBLICACIÓN INSTITUCIONAL VALIDADA por persistencia y autorización READ ONLY
(12 de noviembre, Buenos Aires). Publicación ejecutada por el operador en Chrome;
una fila activa de la versión exacta, actor propietario ADMIN y AUTHENTICATED.
Tres USUARIO activos con lectura efectiva; administración reservada al propietario.
ACL individuales y embeddings coinciden con la restauración validada.
Acceso real de lectores por navegador y E2E RAG pendientes, no certificados.
Esta verificación no publicó ni modificó datos. Ver cierre al final.**

## Alcance completado

Se incorporo la continuacion recibida del mismo Sprint 10G12D, sin descartar la
implementacion anterior ni crear otro sprint. El ejemplo concreto de memoria fue
reproducido y corregido con mocks, incluidos estados SIN_EVIDENCIA y ACLARACION.
El log completo confirma all_claims_rejected, pero sigue sin incluir los textos de
los claims ni missing_terms; no se inventa una causa particular del turno real.

No se hicieron llamadas externas, reinicios, escrituras SQL o cambios de claves.

## A. Validación de afirmaciones RAG

supported_text valida cada Claim contra sus source_ids y AcademicRelevance;
all_claims_rejected significa que ninguna afirmación superó soporte. No implica
que haya fallado retrieval ni la API de embeddings.

Defecto reproducido: una fuente de artículo verificado puede respaldar literalmente
«La asistencia es obligatoria», pero la introducción «El artículo 24 establece
que…» agrega términos de atribución que el filtro compara como si fueran parte
del predicado normativo. El número/encabezado y el cuerpo aparecen en unidades
separadas de la fuente. Así se rechaza contenido válido por su marco discursivo.

Corrección en relevance.py: antes de la comparación léxica se separan únicamente
introducciones acotadas de artículo («establece/dispone/indica/señala que» o
«Según el artículo N,») cuando existe un único ArticleLink verificable:

- Número igual al solicitado.
- Mismo enlace y scope en todas las citas.
- Cierre estructural demostrado.
- Si la introducción nombra una sección, debe coincidir normalizada con la sección
  del enlace documental. No se acepta otra norma.

El texto mostrado al usuario no se reescribe: la normalización solo afecta la
comparación del soporte. Se conservan predicado, sujeto, porcentajes, cantidades,
negaciones y citas. Sin vínculo estructural, la regla no se aplica. No se agregaron
sinónimos generales ni aprobación basada solamente en score. No se acepta una
paráfrasis libre por tener el número correcto. Las políticas de artículos homónimos,
continuidad y contexto completo permanecen intactas.

Se probó también supported_text seguido de supports_answer sobre la respuesta
con cita: la corrección cubre ambos pasos de validación, no solo el primero.

**Límite:** esto corrige el falso negativo demostrado. No garantiza aceptar cada
paráfrasis del modelo ni demuestra la razón exacta del turno reportado sin sus
claims/diagnóstico saneado. No se aflojó el validador para forzar FUNDAMENTADA.

## B. Memoria conversacional

Defectos reproducidos en context.py:

1. resolve_conversation_memory exigía una sola pregunta candidata, aun ante
   «mi última pregunta» con varios turnos previos.
2. El detector no reconocía formulaciones temporales/plurales habituales.
3. Conversations.turn recortaba siempre a ocho mensajes antes del agente, aun
   cuando se solicitaban varias preguntas anteriores.

Corrección integrada:

- Se reconocen referencias explícitas a última, penúltima, primera y preguntas
  anteriores, incluyendo últimas N. No se cambia el routing de preguntas normativas
  como «¿Qué establece el artículo anterior?».
- Las referencias temporales usan el orden de los turnos del usuario, conservando
  repeticiones. La última pregunta puede ser también una consulta de memoria: no
  se la salta silenciosamente en favor de un turno anterior.
- No se usan respuestas del asistente como memoria de preguntas ni como evidencia.
- Solo para consultas explícitas de memoria, Conversations pasa hasta 100 mensajes
  del historial ya autorizado de ESA conversación. Las demás consultas conservan
  ocho mensajes. El repositorio ya limita su lectura a 100; no se amplió SQL.
- Máximo diez preguntas por selección, con límite de salida. Si falta el número
  explícitamente pedido o no hay historial, se devuelve aclaración sin proveedores.
- «Primera» se presenta como parte del **historial disponible**: no se afirma
  recuperar el comienzo global si la conversación excede los 100 mensajes visibles.
- Las consultas temáticas de órgano conservan su resolución conservadora previa;
  el recuerdo literal no prueba contenido del reglamento.

El acceso al historial continúa pasando por propietario de conversación, usuario
activo y revalidación documental de referencias. No existe memoria compartida
entre conversaciones ni se sustituyen identidades.

## Archivos modificados

1. backend/src/app/application/rag/relevance.py.
2. backend/src/app/application/agent/context.py.
3. backend/src/app/application/agent/conversations.py.
4. backend/tests/rag/test_evidence_memory_12d.py, nuevo.
5. docs/jina-cloud-10g-12d.md, este informe.

No cambió React, API pública, esquema SQL, embeddings, ACL, proveedores, .env o
DOCUMENT_EXPORT_APPROVED. No se modificaron los resolvers de artículos 12B/12C.

## Pruebas ejecutadas

Desde backend:

```powershell
& '.\.venv\Scripts\python.exe' -B -m pytest tests/rag/test_evidence_memory_12d.py tests/rag/test_conversation_memory_intent.py tests/rag/test_answer_diagnostics.py tests/rag/test_structured_output.py tests/rag/test_normative_articles.py tests/rag/test_tools_memory.py tests/rag/test_core.py tests/rag/test_explicit_articles.py tests/ia/test_http_ia.py -q -p no:cacheprovider --basetemp=.pytest-tmp-10g12d-final --tb=short
```

**188 aprobadas, 0 fallidas, 3,88 s.** Advertencia previa Starlette/HTTPX.
No sumar a esa cifra las 87 aprobadas en la ejecución inicial, previa al último ajuste.

Cobertura nueva y de regresión:

- Claims con atribución documental verificada aceptados y citas preservadas.
- Artículo/versión/sección incorrectos, negación invertida, porcentaje inventado y
  predicado ajeno rechazados; atribución sin enlace no concede soporte.
- Última, penúltima, primera y últimas N; duplicados y faltantes.
- Rama de memoria con cero llamadas de planner, RAG/embeddings o proveedor directo.
- Conversations con más de ocho mensajes y seis preguntas recordadas; una segunda
  conversación vacía sigue sin acceder al historial de la primera.
- Artículos homónimos, continuidad, presupuesto, citas, contratos HTTP y validación
  estructurada existentes.

El fallo heredado test_academic_evidence_and_real_page, documentado en 12C, no se
modificó ni se presenta como aprobado. Su pregunta carece de referencia explícita
a artículo y su fuente no tiene ArticleLink: no recorre la nueva normalización.
No se ejecutó toda la regresión ni pruebas E2E reales.

## Comprobación manual posterior

No se reinició FastAPI ni React y no se hizo ninguna consulta real. Tras reiniciar
manualmente el backend del proyecto desde la terminal privada que conserva las
claves, abrir http://127.0.0.1:5173/ia con cuenta autorizada y una conversación nueva.

1. Enviar una vez: «¿Qué establece el artículo 24 del reglamento académico, en el
   Régimen Académico Marco?» Comprobar página 58, citas y soporte de cada afirmación.
2. En esa misma conversación, enviar otra pregunta breve y luego «¿Cuál fue mi
   última pregunta?»; debe reproducir el turno inmediatamente anterior del usuario.
3. Probar «¿Cuáles fueron mis últimas 2 preguntas?» y comprobar orden y literalidad.
   Las consultas de memoria también cuentan como turnos previos del usuario.
4. En otra conversación nueva, pedir la última pregunta: debe aclarar que no tiene
   una pregunta anterior identificable, sin tomar datos de la primera conversación.

Si persiste all_claims_rejected, es necesario correlacionar el request ID con
missing_terms/polarity del diagnóstico privado saneado. No se debe inferir su causa
sin ver ese detalle ni enviar prompts privados, claves o respuestas completas al chat.

**GO técnico para prueba manual del cambio integrado.** No se declara aceptación
funcional real: falta repetir el turno desde React. La continuacion queda incorporada en la seccion final; no hubo APIs, consumo de créditos, escrituras SQL,
reindexación, migraciones, reinicios o cambios de seguridad documental.


## Continuacion integrada: traza de memoria y casos concretos

Esta seccion completa y actualiza el resultado de pruebas anterior; las 188 pruebas
son una ejecucion intermedia, no se suman a las 225 finales.

Recorrido inspeccionado:

1. ConversationPanel mantiene selected con UUID de conversacion. Al crear usa un
   UUID estable pendiente de creacion y conserva la identidad al enviar. api.turn
   usa /ia/conversaciones/{UUID}/mensajes y solicitud_id distinto por turno nuevo.
   Cambiar de conversacion cambia selected y recarga su historial; no manda un
   historial construido por el navegador al agente.
2. La ruta FastAPI recibe UUID y principal mediante get_current_user. Conversations
   delega autorizacion y propiedad al repositorio en cada operacion.
3. PostgresConversations guarda agent_conversaciones, agent_solicitudes y
   agent_mensajes. history consulta hasta 100 mensajes por id descendente y los
   invierte para entregar orden cronologico. No se leyeron filas reales durante
   esta continuacion: la traza procede del codigo y pruebas con repositorio doble.
4. reserve no incorpora el texto actual a agent_mensajes. history se lee antes de
   agent.execute; complete guarda usuario y asistente al finalizar. Por eso la
   pregunta actual no esta duplicada dentro del historial recibido por el agente.
5. Los mensajes ACLARACION y SIN_EVIDENCIA se persisten y se recuperan: no existe un
   filtro de exito que elimine sus preguntas. El defecto observado era la exigencia
   de unicidad en resolve_conversation_memory, no un descarte de SIN_EVIDENCIA.
6. En consultas normales se envian ocho mensajes al agente. planning_context incluye
   solo preguntas previas de referencias contextuales, hasta 160 caracteres cada
   una, bajo un presupuesto JSON de 2400 bytes; no recicla respuestas RAG como prueba.
7. direct_context incluye historial solo para referencias contextuales, excluyendo
   estrategias RAG/TOOL y con limite 1000 caracteres/3000 bytes. history_included=False
   pertenece al recorrido directo y no demuestra ausencia de historial en la rama
   de memoria. Esta rama responde literalmente sin planificador ni generador.
8. Para referencias explicitas de memoria se permiten hasta 100 mensajes ya
   autorizados. El resultado se limita a 3000 caracteres/9000 bytes y a diez
   preguntas cuando se solicita una lista. No se manda ese historial ampliado al LLM.
9. history revalida todas las referencias documentales antes de devolverlas. Cambiar
   usuario o conversacion no reutiliza el historial de otra identidad. No se
   relajo el acceso a memoria historica cuando una ACL documental fue revocada.

Casos adicionales implementados y probados:

- "Sobre que te habia preguntado antes", "Que te pregunte antes" y "De que veniamos
  hablando" recuperan la ultima pregunta del usuario, aun con otras anteriores.
- "Que me respondiste anteriormente" y "Podes repetir tu respuesta anterior"
  reproducen la ultima respuesta del asistente con el rotulo de registro
  conversacional, no evidencia nueva; no se envian al LLM ni al RAG.
- "Y que establece el siguiente" exige un numero unico en el turno inmediatamente
  anterior del usuario. Se conserva literalmente documento/seccion de esa pregunta,
  se incrementa el numero y se recorre nuevamente el catalogo autorizado, version,
  require_active y recuperacion. No se usan afirmaciones del asistente para inferir
  la numeracion ni se busca un antecedente mas antiguo saltando temas intermedios.
- Sin antecedente inequ?voco se devuelve ACLARACION sin proveedores. No se promete
  resolver seguimientos sucesivos si el ultimo turno solo contiene "el siguiente"
  y ya no trae un numero explicito; se requiere aclaracion en ese caso.

Archivo adicional modificado dentro del MISMO sprint:
backend/src/app/application/agent/agent.py, para detener seguimientos normativos sin
antecedente y usar la pregunta expandida como referencia documental; no cambia ACL.

### Resultado final que sustituye el conteo intermedio

Comando desde backend:

```powershell
& '.\.venv\Scripts\python.exe' -B -m pytest tests/rag/test_evidence_memory_12d.py tests/rag/test_conversation_memory_intent.py tests/rag/test_semantic_planning.py tests/rag/test_tools_memory.py tests/rag/test_answer_diagnostics.py tests/rag/test_structured_output.py tests/rag/test_normative_articles.py tests/rag/test_core.py tests/rag/test_explicit_articles.py tests/ia/test_http_ia.py -q -p no:cacheprovider --basetemp=.pytest-tmp-10g12d-integrated --tb=short
```

**225 aprobadas, 0 fallidas, 4,49 s**, aviso previo Starlette/HTTPX.
Incluye los ejemplos concretos de la continuacion, memoria de respuestas,
SIN_EVIDENCIA/ACLARACION, articulo siguiente reautorizado y rama de aclaracion sin
antecedente. Un error inicial de import relativo del helper de continuidad se
corrigio antes de esta ejecucion final. No se suman ejecuciones previas.

**GO tecnico para repetir manualmente los ejemplos desde React**, tras cargar el
codigo en el backend desde la terminal privada habitual. No se reiniciaron servicios
ni se repitieron consultas externas. La aceptacion real sigue pendiente; el
falso negativo RAG reproducible quedo corregido pero no se certifica la razon exacta
de cada claim real no aportado. No se modificaron documentos, indices, proveedores,
.env, ACL ni DOCUMENT_EXPORT_APPROVED. Todo permanece en un unico Sprint 10G12D.

## Validación funcional React y correcciones posteriores

Continuación del MISMO Sprint 10G12D, 11 de noviembre de 2026. Esta sección
sustituye el conteo de 225 pruebas como último resultado de implementación.

### Evidencia recibida desde React

El usuario informó, después de su reinicio manual:

- Artículo 24 RAM: FUNDAMENTADA parcial, F1, página 58. Esto acredita ese turno
  real parcialmente fundamentado; no acredita que todas las afirmaciones omitidas
  fueran correctas o que la respuesta tenga cobertura integral.
- Artículo 52: cuatro fuentes localizadas, abstención article_context_budget.
- «¿De qué te estuve preguntando?» llegó al planner y recibió aclaración de fecha.
- «En el día de la fecha ¿sobre qué te estuve preguntando?» llegó al planner y
  terminó en planner_document_not_selected, con un documento autorizado.

No se ejecutaron nuevas consultas reales desde esta intervención.

### Causa exacta y corrección del enrutamiento

conversation_memory_reference reconocía «pregunté antes», «veníamos hablando» y
otras formas, pero no la construcción «te estuve preguntando» ni «qué temas
estuvimos tratando». Por ello Agent._execute no entraba a la rama determinista y
permitía al planificador decidir clima/documentos. El catálogo autorizado con una
fila no explicaba el error: la intención de esa consulta era memoria, no RAG.

Se agregó conversation_topics_reference con patrones acotados para las formas
reportadas y variantes pedidas. Se usa antes del planificador y antes de herramientas.
La rama distingue:

- Última/penúltima/primeras/últimas N: orden literal de los turnos del usuario.
- Preguntas anteriores: lista acotada de preguntas, sin usar respuestas como prueba.
- Temas tratados: se muestran preguntas reales previas como referencias de esos
  temas, excluyendo metaconsultas de memoria y respuestas del asistente. No se
  inventa una síntesis normativa ni se atribuye al usuario un tema no mencionado.
  Se usan como máximo diez preguntas distintas de los cien mensajes disponibles.
- Respuesta anterior: reproducción literal rotulada como registro, no evidencia nueva.

No hay filtro por éxito: SIN_EVIDENCIA, FUNDAMENTADA y ACLARACION conservan las
preguntas y respuestas previas. La selección de la conversación y la autorización
siguen en el repositorio y en Conversations; no se mezclan usuarios/conversaciones.
El historial amplio no se envía al LLM para estos casos.

### Referencias temporales

memory_date_history detecta «hoy» y «en el día de la fecha». Usa creado_at real,
aceptando datetime con zona o ISO con offset/Z, y convierte a America/Buenos_Aires
mediante ZoneInfo. La fecha actual se obtiene con esa misma zona, no por una fecha
inventada ni por la posición de un mensaje. Un test comprueba el cambio de día
UTC que todavía corresponde al día anterior en Buenos Aires.

Si falta una marca temporal, es inválida, es naive o no está disponible la zona,
no se afirma que los mensajes pertenecen a hoy: se informa que no se puede
verificar el día. No se invoca clima, Jina ni OpenRouter. Sin historial pertinente
se pide aclaración. Los límites de salida de memoria siguen siendo 3000 caracteres
/ 9000 bytes; las consultas normales mantienen su ventana anterior.

### Artículo 52: presupuesto técnico comprobado

Se efectuó exclusivamente una lectura protegida en usuarios_dev con el repositorio
cloud, usando el propietario autorizado, espacio activo y versión exacta. Se
procesaron texto y contexto solo en memoria, imprimiendo números y páginas.
No hubo escritura SQL ni API.

| Límite o medida | Valor verificado |
|---|---:|
| Páginas del artículo | 32, 33, 34, 35 |
| Caracteres de texto | 4802 |
| Bytes UTF-8 del cuerpo | 4806 |
| Prompt renderizado completo, sin instrucciones adicionales del skill | 6526 bytes |
| Presupuesto total local | 4096 unidades conservadoras |
| Reserva de salida / plantilla | 256 / 512 |
| Presupuesto de contexto documental utilizable | 3328 bytes con ConservativeCounter |
| Fuentes necesarias / admitidas | 4 / 3 |

ConservativeCounter cuenta bytes UTF-8; no mide tokens del tokenizer Dots ni
certifica una ventana remota de 4096 tokens. El DTO usa context_tokens=4096 y
max_output_tokens=256 como contrato local, mientras que el transporte comprueba
además len(prompt UTF-8)+256 <= 4096. El tamaño del artículo y las cuatro páginas
ya exceden esos controles antes de una petición externa.

Controles concretos que impiden resolverlo aumentando solo una constante:

1. core.build_context: 4096 - 256 - 512 y máximo tres Evidence.
2. GroundedProvider.generate_grounded: máximo tres fuentes, render exacto y
   ConservativeCounter(render)+256+512 <= 4096.
3. OpenRouterProvider._generate_validated: prompt bytes + 256 <= 4096.
4. Prompt/citas y contratos React/API actuales: F1–F3 / hasta tres fuentes.
5. structured_output limita a tres claims por respuesta; una respuesta aceptada
   no es garantía de cobertura integral de todas las disposiciones de un artículo.

El límite remoto efectivo del endpoint Dots no se volvió a consultar: está
prohibido hacer llamadas externas en esta intervención. El código local examinado
no fija ni verifica una ventana remota ampliada. No se atribuye el bloqueo a una
incapacidad demostrada del proveedor; es un bloqueo de aplicación verificable.

**Solución aplicada:** conservar recuperación completa y la abstención explícita
article_context_budget, sin truncar ni perder páginas. **Bloqueo pendiente para
la generación completa del 52:** ampliar coherentemente estos contratos y verificar
capacidad del endpoint, o diseñar una síntesis por partes con soporte final.
No se amplió el presupuesto a ciegas, no se cambió el modelo y no se implementó
una ejecución multillamada automática.

Alternativa evaluada, NO implementada/activada: una llamada de extracción por cada
una de cuatro páginas más una síntesis final supondría hasta cinco generaciones,
frente a una, además de revalidar cada claim intermedio y conservar citas de cuatro
páginas. El costo/cuota y latencia reales no están medidos y una síntesis podría
seguir excediendo tres fuentes. No se presenta como una solución lista ni se
activa consumo adicional. El criterio de este pedido permite dejar documentado
este bloqueo técnico exacto; la recuperación y la seguridad se mantienen.

### Artículo 24: respuesta parcial y validación

La evidencia comunicada prueba una afirmación aceptada y otras omitidas, pero no
aporta sus textos ni missing_terms/polaridad. No puede certificarse que aquellas
omisiones concretas fueran correctas ni atribuirlas a un falso negativo específico.

Se mantuvo la corrección previa de atribuciones documentales verificadas y se
agregaron fixtures diferenciados:

- Parcial legítima: fuente sintética respalda asistencia obligatoria; se acepta esa
  afirmación y se rechazan becas/presupuesto u 80 % inexistentes. Se conserva F1 y
  partial=true; no se recuperan afirmaciones rechazadas por una respuesta más larga.
- Falso rechazo sintético corregido: introducciones «El artículo N establece que»
  y «Según el artículo N» se aceptan cuando número/sección/scope están verificados
  y el predicado sí está respaldado.
- Negación invertida, número/versión/sección incorrectos y predicados inventados
  siguen siendo rechazados. El parser JSON Schema, source_ids, segmentación y
  política de citas no se desactivaron.

Se agregó un log sin contenido: rag_claims generated=N accepted=N rejected=N.
No imprime claims, preguntas, textos, claves ni términos privados. El diagnóstico
privado existente conserva su política previa y no se habilitó captura de cuerpos.
Para decidir sobre los claims reales omitidos haría falta correlacionar ese turno
con un diagnóstico autorizado saneado; no se modificó la validación por conjetura.

### Archivos modificados en esta continuación

- backend/src/app/application/agent/context.py: intención de temas y fechas reales.
- backend/src/app/application/rag/structured_output.py: solo conteos seguros en log.
- backend/tests/rag/test_memory_functional_12d.py: nuevo.
- docs/jina-cloud-10g-12d.md: este mismo informe.

Se conservan los cambios previos del sprint. No se modificó React productivo, API
pública, documentos, ACL, embeddings, .env, modelos ni proveedores.

### Pruebas ejecutadas y fallos heredados

Desde backend:

```powershell
& '.\.venv\Scripts\python.exe' -B -m pytest tests/rag/test_memory_functional_12d.py tests/rag/test_evidence_memory_12d.py tests/rag/test_conversation_memory_intent.py tests/rag/test_semantic_planning.py tests/rag/test_tools_memory.py tests/rag/test_answer_diagnostics.py tests/rag/test_structured_output.py tests/rag/test_normative_articles.py tests/rag/test_core.py tests/rag/test_explicit_articles.py tests/ia/test_http_ia.py -q -p no:cacheprovider --basetemp=.pytest-tmp-10g12d-functional --tb=short
```

**257 aprobadas, 0 fallidas, 5,50 s.** Advertencia previa Starlette/HTTPX.
Las ocho formulaciones pedidas se prueban con SIN_EVIDENCIA, FUNDAMENTADA y
ACLARACION; el planner simulado falla si se lo invoca. También se cubren fechas
con/sin zona, ventana larga, conversación nueva, aislamiento por cuenta y por
conversación, presupuestos dentro/fuera de contexto, citas multipágina, invención
rechazada, respuesta parcial legítima y falso rechazo sintético. Las pruebas HTTP
verifican el contrato que consume React; no son un navegador contra FastAPI real.
No se repitió la suite React porque no cambió su contrato ni implementación.

Ejecución separada de test_relevance.py: **9 aprobadas, 1 fallida, 0,35 s**.
Persiste test_academic_evidence_and_real_page: la respuesta del fixture es «Norma
ficticia [F1].», sin soporte en la fuente de asistencia. No pasa por referencia
explícita de artículo ni por memoria. Se reprodujo y no se modificó para ocultarlo.
No sumar repeticiones ni afirmar que toda la regresión está aprobada.

### Decisión y repetición manual

**GO técnico para repetir las consultas de memoria y el artículo 24 desde React**
una vez que el operador cargue estos cambios mediante su reinicio manual habitual.
No se reiniciaron servicios. En una conversación autorizada, comprobar las dos
preguntas reales y luego las variantes de última pregunta, temas y respuesta
anterior; en otra conversación vacía debe aclarar, sin reutilizar recuerdos ajenos.
Para «hoy» confirmar que el historial real entregue creado_at con zona, sin copiar
mensajes privados o credenciales al informe.

**NO-GO para respuesta integral del artículo 52 con los contratos actuales.**
Puede repetirse la comprobación local sin API; no tiene sentido consumir créditos
para un presupuesto que falla antes del proveedor. Se conserva la abstención
precisa hasta una modificación coherente del contexto y contrato de fuentes.

No se declara éxito funcional completo ni explicación de todos los claims reales
omitidos sin su evidencia. No hubo nuevas APIs, consumo de créditos, escrituras SQL,
reindexación, migraciones, cambios de ACL/proveedor/configuración, fallback Ollama,
reinicios o cambios de DOCUMENT_EXPORT_APPROVED=False.

## Corrección funcional RAG y herramienta meteorológica

11 de noviembre de 2026. Continuación del MISMO Sprint 10G12D. Esta sección y el
encabezado actualizado sustituyen los conteos históricos como estado actual.
La memoria validada no se modificó en esta intervención.

### Diagnóstico del rechazo RAG intermitente

El turno aportado recuperó el artículo, construyó contexto de página 58 y recibió
una respuesta del proveedor. generated=1 accepted=0 rejected=1 sitúa el rechazo
en soporte del claim, después del parseo estructurado; no demuestra un error de
recuperación, JSON ni source_ids inventados. Si el parser hubiera rechazado el
contrato, ese turno no habría alcanzado esos conteos de validación.

Recorrido inspeccionado: resolve_article → ArticleLink y slices verificados →
build_context/render → OpenRouterGroundedProvider → JSON Schema → parse →
supported_text → AcademicRelevance.explain_answer → resolve_citations → soporte final.
Se conservan ACL, scope/version, páginas, pertenencia de source_ids al conjunto
permitido, polaridad y rechazo de afirmaciones inventadas.

El parser no divide libremente la respuesta en nuevas afirmaciones: recibe hasta
tres claims JSON y conserva sus source_ids; el validador compara las unidades de
cada claim contra unidades de sus fuentes citadas. La segmentación por oraciones
puede ser conservadora ante paráfrasis y cambios de vocabulario. La similitud o
el número de artículo correcto no prueban por sí solos el predicado.

Una página idéntica no implica claims idénticos. El transporte de generación no
fija temperature cuando no recibe ese parámetro; los logs aportados no contienen
la salida del modelo ni prueban determinismo del proveedor. Un turno puede generar
una afirmación respaldada y otro una paráfrasis no admitida o contenido inventado.
No se atribuye el rechazo real a una de esas causas sin datos adicionales.

**Información que falta:** el diagnóstico por claim del turno correlacionado,
resultado de headers/pertinencia, comparaciones léxicas y polaridad. No se conoce
el texto del claim real y no se lo reconstruyó por suposición. Los falsos negativos
sintéticos de atribución documental ya corregidos siguen cubiertos; no se agregó
una excepción para artículo 24 ni se relajó el soporte para forzar FUNDAMENTADA.

### Diagnóstico local opcional y seguro

Nuevo opt-in de proceso: AGENT_RAG_SAFE_DIAGNOSTICS=true. Ausente o distinto de true,
no se emiten los eventos detallados. No se modificó .env ni se habilitó en servicios.

Eventos rag_safe_diagnostic acotados:

- Etapa parser: valid / structured_contract_rejected, validez JSON, cantidad de
  fuentes/claims. La segunda razón incluye contrato JSON/estructura/finalización;
  no se afirma identificar automáticamente cuál campo falló.
- Etapa claim_support: accepted, header_identity_mismatch, no_pertinent_units,
  polarity_mismatch, lexical_gap o support_rejected.
- Índice del claim, request_id, fuentes y páginas, resultado de headers, número de
  términos faltantes por comparación y resultado booleano de polaridad.

No se imprimen términos faltantes, frases, claims completos, prompts, texto de
fuentes, cuerpos HTTP ni claves. Solo números, identificadores de fuente y razones
controladas. Una negación ausente se clasifica como discrepancia de polaridad
cuando el resto de los términos coincide, sin cambiar su rechazo. Los fallos al
emitir el diagnóstico no cambian la validación. Se mantienen los controles del
registro privado anterior y no se habilita captura literal.

El nuevo diagnóstico determina tipo/etapa de discrepancia; si solo muestra una
brecha léxica, no certifica por sí solo si la paráfrasis era correcta. Una revisión
semántica del caso requeriría inspección local autorizada de la salida y evidencia,
sin publicarlas en logs operativos o en el chat. No se promete inferirla de conteos.

Se evaluó un modo extractivo: para transcripción explícita de una disposición
única y completa podría reducir variación y evitar paráfrasis, conservando scope,
offsets y citas. No se activó como reemplazo silencioso de respuestas explicativas:
cambiaría el comportamiento solicitado y seguiría requiriendo desambiguación,
budget y validación de completitud. No se introdujeron proveedores, fallback,
reintentos o llamadas adicionales.

### Causa demostrada del fallo de clima

weather_arguments extraía desde «en …» hasta el final y separaba ciudad/provincia/
país por comas. Para la frase real «en la ciudad de Vera, Santa Fe, Argentina»,
el campo ciudad quedaba literalmente **la ciudad de Vera**. Ese texto cumplía el
validador de caracteres y se enviaba al geocodificador. Después se comparaba
exactamente con name=Vera, provocando cero coincidencias válidas incluso con una
respuesta correcta. El mismo defecto afecta Rosario y Goya.

Además, OpenMeteo concatenaba ciudad y provincia en el parámetro name. Esto
mezclaba nombre de localidad y criterio administrativo en la búsqueda, aunque la
provincia se comprobaba nuevamente en admin1. La normalización eliminaba algunos
prefijos administrativos pero no sufijos como «Santa Fe Province».

**Corrección:**

1. Quitar solo prefijos lingüísticos acotados «la ciudad de», «localidad de» o
   «el municipio de» del componente de ciudad. No se eliminan palabras internas
   de nombres propios ni se deriva la ubicación con el LLM.
2. Enviar name=ciudad y countryCode=ISO del país. El parser conserva provincia y
   país explícitos y la intención temporal se procesa separadamente.
3. Comparar nombre por tildes/caja/espacios normalizados, país por código ISO y
   provincia por nombre normalizado, con prefijos y sufijos administrativos.
   Santa Fé y Santa Fe son equivalentes de comparación.
4. Exigir exactamente UN candidato que cumpla todos los filtros. Varias filas
   igualmente válidas siguen siendo ambiguas; no se toma la primera ni se inventan
   coordenadas. Cero coincidencias pide aclaración. Errores de red/contrato siguen
   siendo errores técnicos, sin pronóstico vacío ni reintentos.

No se hardcodearon coordenadas, localidades argentinas ni un catálogo de ciudades.
Las coordenadas de los tests son sintéticas y no acreditan clima real.

### Archivos modificados en esta intervención

- backend/src/app/application/agent/tools.py: extracción determinista de ciudad.
- backend/src/app/infrastructure/rag/weather.py: búsqueda y normalización geográfica.
- backend/src/app/application/rag/diagnostics.py: opt-in seguro de razones de rechazo.
- backend/tests/rag/test_weather_rag_functional_12d.py: nuevo.
- docs/jina-cloud-10g-12d.md: este mismo informe, incluido encabezado consolidado.

No se cambió context.py, agent.py o conversations.py en esta intervención; la
memoria funcional previamente validada conserva su implementación.

### Pruebas y regresiones

Comando final desde backend:

```powershell
& '.\.venv\Scripts\python.exe' -B -m pytest tests/rag/test_weather_rag_functional_12d.py tests/rag/test_geographic_normalization.py tests/rag/test_weather_dates.py tests/rag/test_rag_private_diagnostics.py tests/rag/test_memory_functional_12d.py tests/rag/test_evidence_memory_12d.py tests/rag/test_conversation_memory_intent.py tests/rag/test_semantic_planning.py tests/rag/test_tools_memory.py tests/rag/test_answer_diagnostics.py tests/rag/test_structured_output.py tests/rag/test_normative_articles.py tests/rag/test_core.py tests/rag/test_explicit_articles.py tests/ia/test_http_ia.py -q -p no:cacheprovider --basetemp=.pytest-tmp-10g12d-rag-weather-final --tb=short
```

**313 aprobadas, 0 fallidas, 12,18 s**, advertencia previa Starlette/HTTPX.
Incluye la cobertura de las 257 anteriores y pruebas adicionales de clima/diagnóstico.
No se suman las ejecuciones repetidas.

Fixtures nuevos verifican las tres preguntas reales completas a través del agente,
con selección correcta entre candidato válido, homónimo en otra provincia y otro
país; tildes, nombres administrativos, coincidencia única, inexistencia, respuesta
vacía, múltiples candidatos y fallo de red sin forecast/reintento. MockTransport
intercepta geocodificación y pronóstico; no se hicieron llamadas Open-Meteo.
También se verifica diagnóstico RAG apagado por defecto, rechazo de invención y
polaridad invertida, y ausencia de cuerpos o palabras privadas en el log opcional.

Una primera prueba detectó que la razón diagnóstica de negación invertida aparecía
como lexical_gap: se ajustó la clasificación de diagnóstico, sin alterar el rechazo.
No se modificaron expectativas para aceptar claims inventados.

Regresión heredada ejecutada por separado desde backend:

```powershell
& '.\.venv\Scripts\python.exe' -B -m pytest tests/rag/test_relevance.py -q -p no:cacheprovider --basetemp=.pytest-tmp-10g12d-rag-weather-legacy-checked --tb=short
```

**9 aprobadas, 1 fallida, 0,42 s.** Persiste
 test_academic_evidence_and_real_page: «Norma ficticia» no está sustentada por la
fuente de asistencia del fixture. No se corrigió el test ni se rebajó el soporte.
Una invocación previa desde raíz falló en colección por importar tests; el comando
correcto desde backend produjo el resultado anterior. No se declara aprobada toda
la suite. No se reinició ni probó React real durante esta intervención; sus contratos
HTTP y las pruebas de memoria existentes se conservan.

### Procedimiento exacto para repetición manual desde React

No ejecutar automáticamente. En la terminal privada habitual del operador, detener
con Ctrl+C solo el backend propio para cargar el código; conservar las claves ya
presentes sin imprimirlas. Para habilitar únicamente el diagnóstico sin texto:

```powershell
$env:AGENT_RAG_SAFE_DIAGNOSTICS='true'
Set-Location 'D:\Downloads\proyectos\api-usuarios-clean\backend'
$env:PYTHONPATH=(Join-Path (Get-Location) 'src')
& '.\.venv\Scripts\python.exe' -B -m app.presentation.cli.local_server --environment local-development --enable-llm --observe-llm --host 127.0.0.1 --port 8000
```

No iniciar otra instancia si 8000 sigue ocupado; no cambiar .env ni copiar claves.
Con React ya disponible en http://127.0.0.1:5173/ia y cuenta autorizada:

1. Nueva conversación: enviar una sola vez «¿Qué establece el artículo 24 del
   reglamento académico, en el Régimen Académico Marco?». Registrar request_id,
   rag_claims y rag_safe_diagnostic. Si falla, compartir únicamente los campos
   seguros (razón/fuente/página/conteos/polaridad), no mensajes, claims ni prompts.
2. Enviar por separado, una vez cada una: «¿Cómo está el clima hoy en la ciudad de
   Vera, Santa Fe, Argentina?», la misma formulación para Rosario/Santa Fe y para
   Goya/Corrientes. Comprobar localidad, provincia, país, referencia temporal y
   atribución del proveedor. No repetir automáticamente ante ambigüedad/error.
3. Confirmar que una consulta de memoria sigue refiriéndose solo a esa conversación.

El flag afecta al proceso que se inicia con él; no cambia el servidor ya ejecutado.
Para futuras sesiones sin diagnóstico quitarlo de la terminal antes de iniciar:
Remove-Item Env:AGENT_RAG_SAFE_DIAGNOSTICS -ErrorAction SilentlyContinue.
No se habilitó el flag ni se reinició el servidor desde esta intervención.

### Decisión y riesgos pendientes

**GO técnico para repetir clima y capturar el diagnóstico del artículo 24.**
El defecto geográfico está corregido y probado con fixtures; la respuesta real
actual de Open-Meteo y su disponibilidad no se certificaron sin una prueba posterior.
La ambigüedad geográfica real sigue causando aclaración segura.

**Pendiente la causa semántica exacta del claim RAG real rechazado.** El diagnóstico
nuevo permite distinguir el tipo de rechazo sin filtrar contenido. El caso no se
da por resuelto solo porque otra generación haya sido parcial y fundamentada.
No se activó modo extractivo ni se relajó la política documental.

El bloqueo de contexto del artículo 52 permanece igual y fuera del alcance de
estos dos fallos. No se modificaron documentos, embeddings, ACL, versión, .env,
proveedores, modelos o DOCUMENT_EXPORT_APPROVED=False. No hubo APIs externas,
consumo de créditos, SQL de escritura, migraciones, reindexación o reinicios.

## Corrección final de consultas académicas

Continuación del MISMO Sprint 10G12D, 11 de noviembre de 2026.
Sin APIs, escrituras SQL, cambios de configuración o reinicios.

### Concursos: causa y cambio mínimo

La consulta «¿Cuáles son los requisitos para acceder a concursos de Coordinaciones
de Carreras?» ya cumplía la condición academic_action de AgentRouter.intent:
requisitos + carreras. No fallaba inicialmente la clasificación documental.

El defecto estaba en Agent._execute: AUTO con planner habilitado solo evitaba
planificar cuando había un título documental explícito reconocido (o clima con
argumentos completos). La consulta no nombraba un título del catálogo; aun siendo
documental, se enviaba al planner, cuya petición HTTP 400 impedía llegar al RAG.

Nueva regla institutional_requirements: requiere requisitos + concurso/acceso/cargo
+ objeto académico concreto (coordinación/coordinaciones de carrera/carreras o
cargo/concurso docente). Excluye clima, programación y definiciones generales.
Si se nombra un instrumento concreto (reglamento, resolución, ROM, anexo o una
cláusula «según»), no utiliza el atajo: conserva la selección documental explícita
anterior y no sustituye ese instrumento por cualquier documento disponible.

El atajo solo evita el planner para ese intent procedural. No fija un documento,
no concede permisos y no promete que el catálogo contenga los requisitos:

- Catálogo autorizado vacío: SIN_EVIDENCIA, sin embeddings/generación.
- Varios documentos sin selección: ACLARACION, sin elegir el primero.
- Un documento o selección válida: require_active y servicio RAG existente,
  preservando ACL, scope/versión, evidencia, citas y abstención por falta de soporte.
- Runtime RAG no compuesto: error técnico; no se inventa un catálogo vacío.

No se alteraron memoria, resolver de artículos, validación de claims, umbrales,
clima, modelos o versión activa. No se introdujo un catálogo de requisitos ni una
respuesta fija sobre concursos.

### HTTP 400 del planificador

Inspección de JSONPlanner y OpenRouterProvider, con MockTransport:

- POST https://openrouter.ai/api/v1/chat/completions.
- Modelo operativo Dots3-Note :free y proveedor exclusivo atlas-cloud.
- Mensajes system y user; stream=false, temperature=0, max_tokens=256,
  reasoning.enabled=false.
- response_format=json_schema, strict=true, schema=Proposal.json_schema().
- Require_parameters=true, allow_fallbacks=false, data_collection=deny,
  max_price prompt/completion=0.
- El planner verifica su presupuesto de prompt+system+reserva+salida <=4096 bytes
  conservadores; el transporte además verifica prompt bytes+256 <=4096. No se
  cambió ese presupuesto ni se enviaron solicitudes reales.
- El schema actual tiene raíz $defs, discriminator y oneOf, correspondiente a la
  unión discriminada. Los mocks comprueban contrato enviado y parser válido/inválido;
  NO certifican que el endpoint real acepte cada construcción de ese schema.

El log histórico no contiene error upstream ni cuerpo saneado específico del 400.
No se puede afirmar que lo provocó oneOf, un parámetro, longitud u otra condición.
No se cambió el schema ni se quitaron opciones por una hipótesis. La consulta
procedural corregida ya no depende del planner; otras consultas que sí lo requieran
podrían seguir encontrando ese rechazo upstream pendiente de causa específica.

Cambio aplicado al manejo seguro: HTTP 400 registra classification=request_rejected,
stage=chat_completion (o metadata para otros recorridos) y mantiene
IARespuestaInvalida → HTTP 502. No registra prompts, cuerpos de error, claves ni
respuestas privadas. No se interpreta como falta de evidencia, no se reintenta y
no se cambia a otro modelo/proveedor. Los demás errores mantienen sus excepciones.

### Claims reales del artículo 24

La evidencia aportada demuestra parser válido, tres claims, uno aceptado y dos
rechazados por brecha léxica, con headers válidos y polaridad coincidente. Esto
sitúa la diferencia en cobertura de términos/unidades; NO demuestra que los dos
claims rechazados fueran paráfrasis correctas ni que fueran invenciones.

Se revisaron código y pruebas existentes sin modificar el validador. La búsqueda
local no encontró archivos agent-private del turno dentro del proyecto. En este
ejecutor tampoco está configurado AGENT_PRIVATE_DIAGNOSTIC_DIR. Los diagnósticos
seguros disponibles no incluyen los claims ni las palabras faltantes; el resultado
persistido normal conserva la respuesta filtrada, no necesariamente los claims
rechazados. No se inspeccionó memoria privada de FastAPI ni se asumió su entorno.

Se pidió únicamente ruta local y request_id de un archivo privado existente para
poder revisar en memoria los textos dentro del entorno autorizado. No se recibió
esa evidencia durante la ejecución. No se generaron nuevos datos mediante API ni
se habilitó captura privada automáticamente.

**Resultado del análisis: no clasificable semánticamente todavía.** Falta la salida
estructurada original de ese turno y su evidencia exacta (o un diagnóstico privado
correlacionado que permita revisarlas). Si se facilita su ruta, podrán compararse
localmente sin imprimir cuerpos ni copiarlos al informe. No basta el índice 0/2
ni la etiqueta lexical_gap para decidir equivalencia jurídica o factual.

No se agregó una regresión de un supuesto defecto real no demostrado. Las pruebas
sintéticas previas conservan aceptación de afirmaciones respaldadas, atribución
verificada y rechazo de afirmaciones inventadas; no se aceptan paráfrasis por
conjetura. No se relajaron polaridad, citas, source_ids, scope o ACL.

### Clima: regresión, sin cambiar resolución

El usuario confirmó funcionamiento real en React para Vera, Rosario y Goya.
El 503 transitorio anterior a la respuesta correcta no acredita ambigüedad.
No se modificó la geocodificación ni su extracción. Fixtures nuevos comprueban:

- HTTP 503: IANoDisponible, un solo GET, sin datos meteorológicos inventados.
- HTTP 200 sin resultados: ACLARACION, un solo GET, sin forecast.

Una repetición manual posterior del usuario es una solicitud nueva, no un reintento
automático introducido por esta corrección.

### Archivos modificados ahora

1. backend/src/app/application/agent/router.py: regla conservadora procedural.
2. backend/src/app/application/agent/agent.py: evita planner solo en esa regla.
3. backend/src/app/infrastructure/llm/openrouter.py: clasificación segura del HTTP 400.
4. backend/tests/rag/test_academic_routing_final_12d.py: nuevo.
5. docs/jina-cloud-10g-12d.md: este informe y encabezado consolidado.

No se modificó memoria ni clima, ni se amplió artículo 52.

### Pruebas ejecutadas

Batería integrada desde backend:

```powershell
& '.\.venv\Scripts\python.exe' -B -m pytest tests/rag/test_academic_routing_final_12d.py tests/ia/test_dots_openrouter.py tests/rag/test_weather_rag_functional_12d.py tests/rag/test_geographic_normalization.py tests/rag/test_weather_dates.py tests/rag/test_rag_private_diagnostics.py tests/rag/test_memory_functional_12d.py tests/rag/test_evidence_memory_12d.py tests/rag/test_conversation_memory_intent.py tests/rag/test_semantic_planning.py tests/rag/test_tools_memory.py tests/rag/test_answer_diagnostics.py tests/rag/test_structured_output.py tests/rag/test_normative_articles.py tests/rag/test_core.py tests/rag/test_explicit_articles.py tests/ia/test_http_ia.py -q -p no:cacheprovider --basetemp=.pytest-tmp-10g12d-academic-final --tb=short
```

**335 aprobadas, 0 fallidas, 10,59 s**, aviso previo Starlette/HTTPX. La invocación
precede a los dos tests adicionales de regresión HTTP 503/ambigüedad, que se ejecutaron
en la comprobación posterior; no se presenta una suite conjunta de 337 ejecutada.

Los tests nuevos prueban consulta exacta de concursos sin planner, catálogo vacío,
múltiples documentos, ausencia de evidencia pertinente, exclusiones de regla y
petición del planner con HTTP 400, sin cuerpos en log y sin reintento. Las suites
previas cubren contratos JSON válidos e inválidos, artículos/citas, memoria, clima,
soporte correcto e invención rechazada.

Ejecución posterior separada:

```powershell
& '.\.venv\Scripts\python.exe' -B -m pytest tests/rag/test_academic_routing_final_12d.py tests/rag/test_relevance.py -q -p no:cacheprovider --basetemp=.pytest-tmp-10g12d-academic-legacy --tb=short
```

**20 aprobadas, 1 fallida, 2,44 s**: incluye los once casos del archivo nuevo,
entre ellos las dos regresiones meteorológicas, y test_relevance.py.
El único fallo sigue siendo test_academic_evidence_and_real_page: «Norma ficticia»
no está respaldada por su fuente de asistencia. No se cambió su fixture ni se
rebajó el validador. No sumar pruebas repetidas ni declarar toda la suite aprobada.

### GO/NO-GO y repetición manual

**GO técnico para repetir la consulta de concursos desde React** una vez cargados
los cambios mediante el reinicio MANUAL habitual del operador; no se reinició aquí.
En cuenta y conversación autorizadas, enviar una vez la pregunta exacta aportada.
Debe verse source=rules intent=documentary y entrada al RAG, sin stage=planner
para ese turno. El resultado puede ser fundamentado, abstención o aclaración
según catálogo/evidencia: aún NO se declara que contenga requisitos correctos.
Comprobar referencias, páginas y soporte si genera una respuesta.

**Pendiente**: clasificar los dos claims reales del artículo 24 y determinar la
causa específica del HTTP 400 para consultas que todavía necesiten planner.
El HTTP 400 ya se distingue de ausencia documental, pero su causa upstream no
se reconstruye sin evidencia. No se propone otra consulta de pago para adivinarla.

La memoria y el clima real confirmado mantienen sus rutas. No hubo nuevas APIs,
consumo de créditos, SQL, modificaciones de embeddings, reindexación, migraciones,
cambios de ACL/.env/modelos/proveedores o DOCUMENT_EXPORT_APPROVED=False,
fallback Ollama, reinicios ni ampliación del artículo 52.

### Correlación del turno informado — cierre de evidencia disponible

Request ID aportado por el usuario: 42b13b27-0920-48ec-bd6e-be8cebf1009f.
Diagnóstico confirmado: generated=3, accepted=1, rejected=2; claims 0 y 2 con
lexical_gap, F1/página 58; claim 1 aceptado; headers válidos y polaridad coincidente.
No se reconstruyeron textos a partir de estos datos.

El proyecto SÍ implementa persistencia privada opcional en
application/agent/diagnostics.py: AGENT_PRIVATE_DIAGNOSTIC_DIR debe designar un
directorio existente con ACL restringida y el registro RAG verifica sus permisos.
Sin ese directorio, solo hay un buffer en memoria de hasta 64 eventos, no expuesto
por HTTP. La salida literal se guarda solo si, además, el proceso recibió
AGENT_PRIVATE_CAPTURE_RAG_JSON=true; nunca entra al buffer. Su existencia como
capacidad de código NO demuestra que estuviera habilitada en el turno informado.

Comprobación local efectuada sin mostrar contenidos: este ejecutor no tiene un
directorio privado configurado y no se encontraron archivos agent-private-*.json
en docs, infra, backend/data, data o .diagnostics. Registros accesibles coincidentes:
0. No se inspeccionó el entorno/memoria del servidor en ejecución ni se buscaron
archivos arbitrarios fuera de los destinos conocidos. No se afirma que una carpeta
privada externa desconocida no pueda existir.

**Conclusión para este turno: los textos reales no están disponibles en la evidencia
accesible.** No es posible clasificar semánticamente los dos rechazos. No se
modificó el validador, no se habilitó captura ni se ejecutó otro turno real. Las
correcciones de routing, clasificación HTTP 400 y resultados de mocks documentados
arriba permanecen vigentes; no se repitieron tests al actualizar solo esta evidencia.

Si posteriormente fuese indispensable revisar un nuevo turno, el procedimiento a
proponer para aprobación previa es: directorio temporal NUEVO y privado fuera del
repositorio, ACL solo operador/SYSTEM verificada por restricted_directory; habilitar
la captura únicamente en la terminal privada del servidor, con alcance temporal
acordado; una consulta manual autorizada; correlacionar por request_id; inspección
local en memoria de claims, fuentes exactas y resultado del mismo validador, sin
imprimirlos ni adjuntarlos al informe. Después deshabilitar las variables para
futuros procesos y conservar el artefacto privado con acceso restringido hasta que
el titular decida su retención/eliminación. El flag actual tiene alcance de proceso,
NO filtro por request_id: habría que garantizar que no se atiendan otros turnos
durante esa ventana, o implementar y probar primero una guarda de request_id único.
No se considera suficiente habilitar el flag en un servidor con tráfico concurrente.

Esta es únicamente una propuesta: requiere autorización de captura y del nuevo
turno, y de cualquier reinicio necesario; no se ejecutó ni se capturó información
sensible adicional. No se publicarán claims, prompts o contenido documental.

## Diagnóstico de pertinencia RAG para concursos

11 de noviembre de 2026. Continuación del MISMO Sprint 10G12D.
**Hay una disposición pertinente en la versión activa. Se demostró y corrigió un
falso negativo del filtro; no se bajó el umbral ni se modificaron datos.**

### Documento y contenido comprobados READ ONLY

Se usó CloudPostgresRAG.require_active con el propietario autorizado, sin asumir
permisos implícitos de ADMIN. Destino verificado: usuarios_dev, 127.0.0.1:5434;
conexiones default_transaction_read_only=on, connect_timeout=10 y
statement_timeout=5000. Se verificó transaction_read_only en la consulta principal.
Las lecturas directas finalizaron con rollback; el repositorio usó conexiones
igualmente forzadas a READ ONLY. No hubo escrituras SQL ni llamadas externas.

- Documento: 8ac0c745-1307-5bb4-9d56-93dfbee0b3b8.
- Versión activa: 7cb4e79c-747d-574a-8abb-0ebcb2e07636.
- Espacio: Jina configurado, comprobado activo/VALIDADA por require_active.
- Disposición pertinente: **artículo 52 del Reglamento Orgánico Marco**, bajo el
  título de Gestión. Contexto del artículo en páginas 32–35.
- Bloque específico: **«Requisitos del Coordinador de Carrera»**, página **33**.
- Ubicación del bloque completo: offsets **666–1122**, 456 caracteres con encabezado;
  cuerpo de lista de 417 caracteres, tres puntos, antes del siguiente apartado
  de evaluación del proyecto.
- El encabezado está en el fragmento ordinal **200**, offsets 347–740. Hay
  continuidad hacia fragmentos posteriores para completar la lista.

Se inspeccionaron menciones y encabezados de coordinaciones, cargos, concursos y
requisitos en su contexto, sin imprimir cuerpos normativos completos. El bloque
es una lista explícita de condiciones del cargo, incluyendo formación docente;
no se dedujeron requisitos a partir de una mera mención de concurso/coordinación.
No se publica aquí una lista de condiciones reconstruida ni se afirma que el
bloque cubra todo trámite o requisito externo de una convocatoria particular.
La respuesta debe limitarse a lo que efectivamente establece esa sección.

Las páginas 22 y 32 no deben aprobarse únicamente por compartir vocabulario con
la consulta. La página 33 aporta el encabezado específico de requisitos del rol.
Se conservó la distinción entre un cargo mencionado, sus funciones, su selección
y una lista explícita de requisitos.

### Por qué relevant=0 con scores mayores a 0,60

En producción el umbral es 0,60. Los scores aportados (~0,6607, 0,6225 y 0,6163)
superan ese umbral: para esos candidatos no se explica el descarte por similitud.
search recupera hasta 12 candidatos; si no hay evidencia, recover obtiene hasta
48 usando el mismo vector, mismo umbral y filtros documentales. select_evidence
verifica scope, integridad formal y umbral, y después AcademicRelevance.select
aplica pertinencia léxica. «Relevant» cuenta el resultado de esas etapas, no el
número de candidatos que superan solamente el coseno.

Defectos comprobados en AcademicRelevance:

1. La rama especial de requisitos reconocía «concurso de» / «cargo de», pero no
   **«concursos de»**, como en la pregunta real.
2. Al no activar esa rama, la regla genérica exigía en una misma unidad los términos
   **acceder, concursos, coordinaciones, carreras**. El bloque normativo usa
   «Requisitos del Coordinador de Carrera» y su lista, no esos cuatro vocablos
   literales. Incluso sobre la página completa, el filtro anterior daba cero.
3. role_terms ya normalizaba coordinación/coordinador/coordinaciones a la raíz del
   mismo rol, pero dejaba **Carreras** y **Carrera** distintos, lo que también impedía
   equiparar el sujeto de la consulta con el del encabezado.
4. El primer fragmento contiene el encabezado y solo el inicio de la lista. La
   expansión de continuidad se ejecuta DESPUÉS de seleccionar fuentes pertinentes;
   al descartarse el encabezado, nunca se completaba la sección.

No se encontraron fallos de ACL ni de versión en la lectura autorizada. No se
regeneró el embedding de la pregunta ni se reconstruyó el top-48 histórico: los
logs aportados no identifican todos los ordinales ni sus scores exactos. Por ello
no se afirma que el ordinal 200 estuviera en una posición concreta o tuviera uno
de esos tres scores. Sí se demostró el rechazo del texto real por el filtro y su
aceptación tras la corrección, independientemente del ranking.

### Corrección mínima y verificación con el repositorio real

Único archivo productivo modificado: application/rag/relevance.py.

- Reconocer concurso/concursos y cargo/cargos en la rama de requisitos.
- Normalizar Carreras → Carrera únicamente dentro de role_terms para comparar
  identidades del cargo; no cambiar terms global ni introducir sinónimos amplios.
- Mantener coincidencia del rol del encabezado, fuentes, umbral, polaridad y soporte.

No se agregó una ruta de recuperación nueva, una respuesta fija, una condición
por artículo/página o una excepción al validador. No se considera una fuente
pertinente solo por su similitud ni por tener la palabra concurso.

Comprobación local READ ONLY después del cambio:

1. El texto real del ordinal 200 pasa pertinent_units para la pregunta exacta.
2. Se llamó a article_context existente con ese seed y el scope autorizado.
3. La reconstrucción del artículo y requirement_section existentes devuelven un
   slice exacto en página 33, offsets 666–1122, sin el apartado siguiente.
4. build_context con ConservativeCounter confirma que ese slice entra COMPLETO
   en el presupuesto y el filtro reconoce la sección reconstruida.

La selección queda rotulada como sección normativa parcial del artículo: la lista
recuperada es completa para ese apartado, pero no se presenta como reproducción
integral del artículo 52. No se amplió el presupuesto del artículo extenso.
No se generó ninguna respuesta real ni se revisaron claims privados para este
problema, que es de recuperación/pertinencia.

### Archivos modificados en esta intervención

1. backend/src/app/application/rag/relevance.py: dos ajustes acotados de comparación.
2. backend/tests/rag/test_competition_relevance_12d.py: nuevo, fixtures sintéticos.
3. docs/jina-cloud-10g-12d.md: este informe y encabezado actualizado.

No se modificaron los resolvers de artículo, ACL, almacenamiento, embeddings,
versiones, modelo, proveedores, configuración, memoria ni geocodificación.

### Pruebas y resultado

Desde backend:

```powershell
& '.\.venv\Scripts\python.exe' -B -m pytest tests/rag/test_competition_relevance_12d.py tests/rag/test_article_continuity.py tests/rag/test_normative_articles.py tests/rag/test_answer_diagnostics.py tests/rag/test_structured_output.py tests/rag/test_evidence_memory_12d.py tests/rag/test_academic_routing_final_12d.py tests/rag/test_jina_cloud.py tests/rag/test_core.py tests/rag/test_explicit_articles.py tests/rag/test_memory_functional_12d.py tests/rag/test_weather_rag_functional_12d.py tests/ia/test_http_ia.py -q -p no:cacheprovider --basetemp=.pytest-tmp-10g12d-competition-final --tb=short
```

**266 aprobadas, 0 fallidas, 11,00 s**, aviso previo Starlette/HTTPX.
No se suman las 91 aprobadas de una selección inicial. Esta selección es distinta
de la batería histórica de 335; no se presenta como ejecución de toda la suite.

Pruebas nuevas demuestran pregunta exacta/plurales, encabezado correcto, ausencia
de requisitos explícitos, cargo distinto, similitud 0,99 insuficiente sin respuesta,
requisitos divididos que se expanden antes de generar, página/cita/offsets correctos,
rechazo bajo 0,60 incluso con encabezado correcto, versión equivocada y usuario
ajeno sin acceso. Se conservan regresiones de artículo 24, claims inventados,
continuidad, routing, memoria, clima y contratos HTTP mediante mocks.

Separadamente, test_relevance.py: **9 aprobadas, 1 fallida, 0,65 s**. Persiste
 test_academic_evidence_and_real_page, ya documentado: respuesta «Norma ficticia»
sin soporte en la fuente de asistencia del fixture. No se modificó su expectativa
ni el validador para ocultarlo. No se declara toda la regresión aprobada.

### Decisión

**GO técnico para repetir una vez la consulta real de concursos desde React**,
tras cargar el cambio mediante el reinicio MANUAL habitual desde la terminal con
credenciales. No se reinició ningún servicio aquí.

Pregunta: «¿Cuáles son los requisitos para acceder a concursos de Coordinaciones
de Carreras?» Debe conservar routing por reglas y, si el ranking devuelve el seed
pertinente por encima del umbral, seleccionar/completar el apartado de página 33.
Comprobar cita y página, etiqueta de cobertura parcial y soporte de cada afirmación.
No se declara FUNDAMENTADA real antes de repetirla: la generación y el ranking
real no se ejecutaron ni se deducen de estos mocks.

Si no aparece el seed pertinente en los candidatos, los nuevos resultados deberán
analizarse sin bajar umbral ni inferir requisitos; no se prometió que esta corrección
cambie el ranking vectorial. Los errores de proveedor siguen siendo técnicos.

No hubo llamadas Jina/OpenRouter/Open-Meteo, consumo de créditos, SQL de escritura,
reindexación, migraciones, cambios de ACL/.env/proveedor/modelo, captura privada de
claims, reinicios ni cambios a DOCUMENT_EXPORT_APPROVED=False. Se cierra este
avance dentro del mismo Sprint 10G12D.

## Requisitos académicos: enumeración literal con integridad demostrada

11 de noviembre de 2026. Continuación del MISMO Sprint 10G12D.
**Ruta extractiva implementada y probada. Sin nuevos servicios, generación o
modificaciones de documentos. GO técnico para repetir la consulta desde React.**

### Evidencia recibida y límites de la causa histórica

Turno: 1f8bd770-5968-4589-985b-ca3caf5da12f. El log confirma recuperación de un
contexto de página 33, parser válido, tres claims rechazados con brechas léxicas
de 5/4/3 términos y polaridad coincidente. No se dispone de sus textos; por tanto
no se afirma que los tres fueran correctos ni se reconstruyen a partir del conteo.
La causa demostrada es el rechazo por el criterio léxico de afirmaciones generadas,
no un fallo del parser o falta del apartado. Sigue sin poderse clasificar la causa
semántica de cada claim histórico sin su contenido.

La solución funcional elegida para esta clase de pregunta no intenta aprobar esas
paráfrasis desconocidas: devuelve exclusivamente las disposiciones literales de
una lista normativa completa y verificada. El validador generativo no se relajó.

### Inspección y verificación reales READ ONLY

Se usó usuarios_dev, 127.0.0.1:5434, con destino comprobado,
default_transaction_read_only=on, connect_timeout=10 y statement_timeout=5000.
SHOW confirmó READ ONLY en las lecturas directas, finalizadas con rollback. El
repositorio también recibió conexiones forzadas a READ ONLY. require_active comprobó
ACL, versión activa y espacio Jina publicado/VALIDADA antes de extraer contexto.

Se recuperó el seed del ordinal 200 y se ejecutó article_context/requirement_section
existentes. La sección completa conservó página **33**, offsets **666–1122**.
Se verificaron **tres puntos**, delimitados por spans exactos de página:

- 705–740.
- 740–995.
- 995–1122.

Estos son metadatos, no el contenido de los requisitos. No se imprimió texto
normativo, claims, prompts, claves o vectores. Se comprobó en memoria que la salida
literal puede conservar los tres puntos y **tres referencias [F1]**, y que
validate_output y resolve_citations aceptan su contrato. No se ejecutó Jina ni
OpenRouter, ni una consulta HTTP de conversación.

La primera comprobación encontró que un punto intermedio no termina en punto
final. No se corrigió su redacción: los puntos intermedios se delimitan por la
siguiente viñeta verificada; el último exige el cierre que ya comprobó el repositorio.
No se reconstruyeron palabras ni se agregó puntuación normativa ausente.

### Implementación mínima y alcance

1. **RequirementList**: metadata interna inmutable del scope, página, límites,
   SHA-256 del texto exacto de sección y spans de todos sus puntos. No contiene
   texto adicional, credenciales ni una autorización de acceso. No está expuesta
   como un campo nuevo del contrato HTTP.
2. **requirement_section** la emite únicamente al delimitar una sección de
   requisitos dentro de un artículo reconstruido, con encabezado y cierre por el
   siguiente apartado. Se conservan los controles y límites existentes. No basta
   una similitud, un título parcial o el final arbitrario de un chunk.
3. **enumeration_target** limita la ruta a solicitudes identificables de enumeración
   de requisitos para concursos/cargos. Usa la identidad del rol del encabezado,
   no un artículo o página hardcodeados. Explicaciones, comparaciones, preguntas
   generales y referencias explícitas a artículos siguen su ruta anterior.
4. **literal_requirements** exige una sola fuente F1, mismo scope/documento/versión,
   página y offsets exactos, hash íntegro, rol coincidente, todas las viñetas y spans
   idénticos a la metadata de sección. Rechaza texto alterado, lista incompleta,
   metadata ausente, página cambiada, referencia ajena o salida fuera de límites.
5. La respuesta conserva cada punto con sus palabras y puntuación originales,
   incluidos saltos de línea internos, y agrega solo [F1] al final. Se eliminan
   únicamente espacios/saltos finales entre puntos para insertar las citas. Se
   identifica como transcripción literal con cobertura limitada a ese apartado.
6. **ResponderConDocumento** aplica esta ruta después de relevancia, continuidad y
   construcción completa del contexto, antes de invocar al generador. Valida el
   contrato de salida y resuelve citas con los mecanismos existentes. Revalida
   autorización y versión antes de entregar el resultado, como en el recorrido normal.
7. Para una enumeración reconocida sin integridad suficiente se devuelve
   SIN_EVIDENCIA, sin recurrir al LLM para completar o inferir puntos. No se introduce
   un fallback a un modelo distinto. Se registra rag_requirements mode=extractive
   cuando se completa, o requirements_integrity cuando no es verificable.

La ruta generativa conserva supported_text, AcademicRelevance, polaridad, source_ids
y soporte final sin cambios. La transcripción determinista usa comprobación de
identidad exacta de los spans, no una excepción permisiva al soporte léxico de
claims LLM. La metadata se genera dentro del backend después de la lectura
autorizada; no es una firma criptográfica ni una defensa contra código malicioso
en el mismo intérprete con control de los objetos internos.

No se cambia la recuperación por similitud: en uso real esa fase sigue generando
el embedding de pregunta mediante Jina. Esta corrección elimina la generación
OpenRouter para la enumeración verificada; no añade llamadas. Las pruebas de esta
intervención usaron embeddings simulados o extracción local directa, nunca APIs.

### Archivos modificados

- backend/src/app/application/rag/dto.py: metadata de lista, opcional en Chunk.
- backend/src/app/application/rag/continuity.py: emisión al verificar sección completa.
- backend/src/app/application/rag/extractive.py: nuevo extractor determinista.
- backend/src/app/application/rag/use_cases.py: ruta acotada y abstención de integridad.
- backend/tests/rag/test_literal_requirements_12d.py: nuevo.
- backend/tests/rag/test_competition_relevance_12d.py: verifica ahora cita/contexto
  devueltos y ausencia del generador en la enumeración, manteniendo las expectativas
  de contenido, límites y separación del apartado.
- docs/jina-cloud-10g-12d.md: este mismo informe y encabezado actualizado.

No se modificaron relevance.py, proveedor/modelo, .env, ACL, memoria, clima o
resolver de artículos. No se amplió la respuesta al artículo 52 completo.

### Pruebas y resultados verificables

Comando final desde backend:

```powershell
& '.\.venv\Scripts\python.exe' -B -m pytest tests/rag/test_literal_requirements_12d.py tests/rag/test_competition_relevance_12d.py tests/rag/test_academic_routing_final_12d.py tests/ia/test_dots_openrouter.py tests/rag/test_weather_rag_functional_12d.py tests/rag/test_geographic_normalization.py tests/rag/test_weather_dates.py tests/rag/test_rag_private_diagnostics.py tests/rag/test_memory_functional_12d.py tests/rag/test_evidence_memory_12d.py tests/rag/test_conversation_memory_intent.py tests/rag/test_semantic_planning.py tests/rag/test_tools_memory.py tests/rag/test_answer_diagnostics.py tests/rag/test_structured_output.py tests/rag/test_normative_articles.py tests/rag/test_core.py tests/rag/test_explicit_articles.py tests/ia/test_http_ia.py -q -p no:cacheprovider --basetemp=.pytest-tmp-10g12d-literal-verified --tb=short
```

**364 aprobadas, 0 fallidas, 11,82 s**, aviso previo Starlette/HTTPX.
Incluye integridad de tres puntos sintéticos, signos intermedios sin reescritura,
contenido añadido o suprimido rechazado, página 33/F1, documento/versión incorrectos,
ACL, contexto incompleto, ausencia de LLM y regresiones de artículo 24, memoria,
clima, routing, claims generados y contratos HTTP. La estructura de los tres
puntos reales se verificó separadamente mediante READ ONLY, sin publicar sus textos.
No se suman las 47 o 362 aprobaciones de iteraciones previas.

Comprobación separada después de afinar la puerta de preguntas explicativas:
test_literal_requirements_12d.py + test_competition_relevance_12d.py +
test_article_continuity.py + test_relevance.py: **42 aprobadas, 1 fallida, 2,50 s**.
El único fallo es el heredado test_academic_evidence_and_real_page: la respuesta
«Norma ficticia» del fixture no está sustentada por su evidencia de asistencia.
No se cambió esa expectativa ni se debilitó el validador. La batería final limpia
arriba no incluye ese archivo heredado, y no equivale a toda la regresión aprobada.

### Decisión y repetición desde React

**GO técnico para repetir una vez la pregunta exacta sobre requisitos de concursos**
después de que el operador cargue el cambio con su reinicio manual habitual.
No se reinició FastAPI ni React desde esta intervención.

En una cuenta/conversación autorizada, enviar:
«¿Cuáles son los requisitos para acceder a concursos de Coordinaciones de Carreras?»

Comprobar tres puntos literales, cobertura limitada al apartado, F1/página 33 y
log rag_requirements mode=extractive. Para ese turno no debe aparecer una llamada
OpenRouter de generación después de recuperar el contexto. La consulta aún depende
de que la recuperación entregue el seed pertinente y de la disponibilidad de Jina;
no se promete éxito del ranking o del transporte sin repetir la consulta real.

**Pendiente aceptación funcional desde React.** Los textos de los claims históricos
siguen sin estar disponibles y no se declaró por conjetura cuál era su error.
No se habilitó captura privada, no hubo nuevas APIs/consumo, escrituras SQL,
embeddings nuevos, reindexación, migraciones, cambios de documento/ACL/.env/modelos,
proveedores/keys o DOCUMENT_EXPORT_APPROVED=False, ni reinicios.

## Funciones institucionales y artículos extensos — continuación del 12 de noviembre

**Implementado dentro del mismo Sprint 10G12D. GO técnico para repetir la consulta
del Rector desde React. La aceptación real sigue pendiente.**

### Causa y contenido verificados

La lectura se realizó exclusivamente sobre usuarios_dev, 127.0.0.1:5434, con
default_transaction_read_only=on, connect_timeout=10 y statement_timeout=5000.
Se comprobó SHOW transaction_read_only=on; las conexiones de lectura finalizaron
sin commit. CloudPostgresRAG.require_active comprobó ACL, versión activa e índice
Jina VALIDADA/publicado. Se conservaron documento y versión identificados arriba.
No se imprimieron cuerpos normativos, vectores, claves ni respuestas privadas.

El encabezado pertinente es **artículo 28, Funciones del Rector**, en el Reglamento
Orgánico Marco. Las otras coincidencias de encabezados sobre Consejo de Rectores
(artículo 9, página 6) y Vicerrector (artículo 33, página 15) corresponden a sujetos
distintos y no se usan como funciones del Rector. Existe otro artículo 28 en otro
cuerpo normativo; el número por sí solo resulta ambiguo. Se exige coincidencia
única del encabezado completo y del sujeto, manteniendo la jerarquía documental.

| Página | Slice exacto del artículo | Caracteres | Cita |
|---|---|---:|---|
| 12 | 740–2129 | 1389 | F1 |
| 13 | 0–2278 | 2278 | F2 |
| 14 | 0–1099 | 1099 | F3 |

El encabezado empieza dentro del fragmento ordinal 68; la cobertura persistida
del artículo recorre los ordinales 68–82, incluidos los solapamientos. El cierre
se demuestra por el artículo siguiente en página 14, offset 1099. Es una
enumeración alfabética con continuaciones entre páginas, no tres listas autónomas.
Hay irregularidades OCR en algunos marcadores: no se reenumeran, reparan ni
reconstruyen disposiciones. La integridad se refiere al texto extraído verificado.
Se conserva todo el artículo identificado, sin afirmar que agote cualquier función
que pudiera establecer otra norma o una disposición adicional.

El total es **4766 caracteres documentales** antes de rótulo y citas. La continuidad
sí permite demostrar el cierre. El rechazo original se produce al construir
contexto: el presupuesto documental es 3328 unidades conservadoras y el artículo
no entra íntegro; el caso local reproduce contexto parcial y su rechazo obligatorio.
Las tres páginas no exceden el máximo de tres fuentes. No se encontró ausencia
del artículo ni un motivo para bajar el umbral de similitud.

Además, una transcripción íntegra alcanza **4879 caracteres**, superando el límite
anterior de 4096 del cliente y de agent_mensajes.contenido. Resolver solo el
presupuesto de entrada habría dejado fallos de contrato/persistencia en React.

### Solución aplicada

- Nueva ruta estructural únicamente para preguntas identificables de enumeración
  de funciones, atribuciones o competencias de un sujeto concreto. No contiene
  Rector, artículos o páginas en condiciones productivas. Las preguntas generales,
  explicativas, por número de artículo, requisitos, clima y memoria conservan sus
  rutas. No se cambia el filtro de pertinencia ni los validadores generativos.
- El repositorio reutiliza la lectura autorizada de páginas, comprobación SHA-256,
  límites de 100 páginas/un millón de caracteres y resolver normativo existentes.
  Exige documento completo comprobado, continuidad y una sola sección inequívoca.
  La selección estructural no necesita embeddings ni genera una respuesta LLM.
- Para un artículo dedicado a las funciones se usan todos sus slices exactos.
  También admite una subsección pequeña con encabezado explícito dentro de un
  artículo extenso: se delimita por el siguiente encabezado normativo reconocido
  o el cierre probado del artículo. Un simple renglón con dos puntos no cierra
  la lista. Si no se prueba integridad o unicidad, se abstiene.
- Un vínculo interno compromete SHA-256 del conjunto ordenado de páginas, offsets,
  texto y metadata de artículo/scope. Omisiones, cambios de texto, página, sección,
  documento o versión invalidan la extracción. Es una comprobación interna, no una
  firma contra código malicioso con control del intérprete.
- La transcripción conserva literalmente cada slice y agrega su cita de página.
  Una función que continúa en otra página conserva ambos tramos y sus referencias.
  No se resume ni se completa con información externa. Se resuelven las citas
  con resolve_citations y se revalidan usuario y versión antes de responder.
- La ruta tiene límites independientes de **tres páginas/fuentes**, **8192 caracteres
  y 32768 bytes de salida**. Es una capacidad acotada de transcripción/transporte
  para el caso medido de 4879 caracteres; no amplía contexto, salida ni presupuesto
  del LLM. Continúan los límites generativos y la abstención de artículos extensos
  consultados por número, incluido el artículo 52 integral.

### Historial y React sin migraciones

agent_solicitudes.resultado ya conserva el resultado completo del turno en JSONB,
en la misma transacción que sus dos mensajes. Para una respuesta RAG fundamentada,
completa y dentro del límite extractivo, el repositorio conserva allí el texto
íntegro y guarda en contenido un rótulo explícito de registro extenso. No almacena
una versión truncada que parezca completa ni crea mensajes o solicitudes extra.
El historial une por solicitud Y conversación y recupera ese resultado exacto;
conserva las referencias documentales y la revalidación ACL/versionado habitual.
Un rótulo sin resultado válido falla cerrado. Las respuestas cortas no cambian.

El cliente admite el tamaño ampliado solo para respuestas RAG fundamentadas con
fuentes y para sus mensajes de historial. La generación directa, preguntas,
respuestas sin evidencia y herramientas conservan sus límites anteriores. No se
agregan campos HTTP ni se cambian los identificadores F1–F3. La memoria continúa
con sus límites y reglas previos; no se amplía el historial enviado al LLM.

La adaptación de persistencia se probó mediante una conexión SQL simulada:
actualización JSONB íntegra e inserciones de mensajes dentro del CHECK existente,
en una misma transacción. **No se ejecutó esa escritura sobre PostgreSQL real**.
No se ejecutaron migraciones ni cambios de esquema.

### Archivos modificados en esta continuación

1. backend/src/app/application/rag/functions.py, nuevo: resolución y transcripción.
2. backend/src/app/application/rag/use_cases.py: ruta extractiva antes del contexto LLM.
3. backend/src/app/infrastructure/rag/postgres.py: lectura verificada compartida.
4. backend/src/app/infrastructure/rag/conversations.py: registro extenso en resultado
   existente y restauración íntegra del historial autorizado.
5. backend/tests/rag/test_literal_functions_12d.py, nuevo.
6. frontend/src/features/ia/api/iaApi.ts: límite de transporte RAG fundamentado.
7. frontend/src/features/ia/api/conversationsApi.ts: límite correspondiente de historial.
8. frontend/src/features/ia/api/literalFunctions.test.ts, nuevo.
9. docs/jina-cloud-10g-12d.md: este mismo informe.

### Pruebas ejecutadas

Desde backend:

```powershell
& '.\.venv\Scripts\python.exe' -B -m pytest tests/rag/test_literal_functions_12d.py tests/rag/test_literal_requirements_12d.py tests/rag/test_competition_relevance_12d.py tests/rag/test_academic_routing_final_12d.py tests/ia/test_dots_openrouter.py tests/rag/test_weather_rag_functional_12d.py tests/rag/test_geographic_normalization.py tests/rag/test_weather_dates.py tests/rag/test_rag_private_diagnostics.py tests/rag/test_memory_functional_12d.py tests/rag/test_evidence_memory_12d.py tests/rag/test_conversation_memory_intent.py tests/rag/test_semantic_planning.py tests/rag/test_tools_memory.py tests/rag/test_answer_diagnostics.py tests/rag/test_structured_output.py tests/rag/test_normative_articles.py tests/rag/test_article_continuity.py tests/rag/test_jina_cloud.py tests/rag/test_core.py tests/rag/test_explicit_articles.py tests/ia/test_http_ia.py -q -p no:cacheprovider --basetemp=.pytest-tmp-functions-complete --tb=short
```

La batería cubre reproducción de presupuesto insuficiente, lista multipágina y
continuaciones, artículos/subsecciones, omisión e invención rechazadas, cambios
de sección/scope/versión, homónimos, hashes, ACL antes/después, persistencia simulada,
contrato HTTP extenso y regresiones de requisitos, artículo 24, memoria y clima.
**429 aprobadas, 0 fallidas, 6,94 s**, advertencia previa Starlette/HTTPX.
Incluye el caso que impide cerrar una lista por un renglón interno con dos puntos.
No se suman ejecuciones intermedias ni se declara aprobada toda la suite del proyecto.

Desde frontend:

```powershell
& 'C:\Program Files\nodejs\node.exe' node_modules/vitest/vitest.mjs run src/features/ia/api/literalFunctions.test.ts src/features/ia/ia.test.tsx --maxWorkers=1
& 'C:\Program Files\nodejs\node.exe' node_modules/typescript/bin/tsc --noEmit
```

**58 pruebas aprobadas, 2 archivos, 50,44 s; TypeScript sin errores, salida 0.**
Incluye respuesta extensa íntegra, recarga de historial, límites y rechazo de
generación directa extensa. Son pruebas con mocks, no navegador contra APIs reales.

Separadamente, test_relevance.py: **9 aprobadas y 1 fallida, 0,33 s**. Persiste
test_academic_evidence_and_real_page, con la respuesta ficticia no respaldada ya
documentada. No se cambió su expectativa ni el validador para ocultarlo.

### Límites y decisión

**GO técnico para repetir «¿Cuáles son las funciones del Rector?» desde React**
después del reinicio manual habitual del operador. No se reinició ningún servicio.
Comprobar texto literal completo, F1/página 12, F2/13 y F3/14, log
rag_functions mode=extractive sources=3, y recarga íntegra en esa misma conversación.
Esta ruta no debe llamar a Jina ni OpenRouter. La prueba real y su persistencia
mediante endpoints permanecen pendientes: no se declara aceptación E2E por mocks.

Si hay varias secciones con el mismo sujeto, cierre no demostrado, cuatro páginas,
salida superior al límite o estructura no reconocida, se mantiene abstención
explícita. No se fusionan disposiciones de artículos diferentes ni se presenta
una síntesis global de todas las competencias de una autoridad. La solución cubre
el apartado completo inequívoco; no promete resolver cualquier forma documental.

No hubo APIs externas, créditos, escrituras PostgreSQL, migraciones, reindexación,
modificación de embeddings, ACL, documento original, claves, .env, modelos,
proveedores ni DOCUMENT_EXPORT_APPROVED=False; tampoco captura privada o reinicios.

## Acceso entre usuarios y publicación institucional — 12 de noviembre

Continuación del MISMO Sprint 10G12D. El adjunto contiene dos instrucciones:
primero diagnóstico y luego una decisión funcional que autoriza implementar la
publicación institucional. Se aplicó esta última para código/pruebas. **No autoriza
la publicación efectiva ni la migración real**, que quedan pendientes.

### Diagnóstico demostrado y límite de la comparación real

La política anterior de PostgresRAG.ACL permitía leer cuando el usuario estaba
activo, el documento no estaba archivado y era propietario, tenía una concesión
puede_leer o el documento tenía visibilidad AUTHENTICATED. Las consultas también
exigen versión activa LISTA. CloudPostgresRAG.require_active agrega espacio exacto,
puntero activo e ingesta VALIDADA. El espacio pertenece a la versión documental,
no a cada usuario: compartir lectura no requiere un índice por persona.

El estado PRIVATE, propietario ADMIN y ausencia de concesiones de lectura estaban
verificados en las intervenciones anteriores de este informe. Bajo esas condiciones,
la exclusión de otro usuario es **intencional por ACL**, no un defecto de embeddings
o selección del catálogo. Ser ADMIN tampoco permite leer cualquier documento ajeno.
La activación vectorial de 10G.11 no cambió visibilidad ni publicó institucionalmente.

**Comprobación actual limitada:** se intentó conectar a usuarios_dev, 127.0.0.1:5434,
con default_transaction_read_only=on, connect_timeout=10 y statement_timeout=5000.
La conexión agotó el tiempo antes de ejecutar las consultas. No hay resultados SQL
nuevos de usuarios, permisos, documento o estado del índice en esta intervención.
No se reiniciaron servicios ni se buscó la identidad del segundo usuario por datos
personales. Por tanto, no se certifica que el estado anterior siga idéntico ni se
atribuye un UUID concreto al segundo usuario. La causa actual es compatible con
la ACL y el estado previo, pero debe ratificarse READ ONLY cuando PostgreSQL esté
disponible. El timeout no demuestra por sí solo por qué el servidor no respondió.

| Situación | Control responsable / resultado esperado |
|---|---|
| Documento inexistente | No integra catálogo; require_active no devuelve scope |
| Existe pero el principal no tiene lectura | ACL lo excluye; sin selección documental autorizada |
| Sin versión activa LISTA | JOIN/estado lo excluyen incluso teniendo lectura |
| Sin puntero o ingesta cloud VALIDADA | No aparece en catálogo cloud; require_active falla técnicamente |
| Catálogo autorizado con varios documentos | El agente conserva selección/aclaración; no toma el primero |
| Propietario frente a lector de publicación | Mismo documento, versión, espacio, páginas y vectores; distinta capacidad administrativa |

Estas diferencias se comprobaron con SQL y repositorios sobre datos sintéticos
aislados, no con filas actuales de usuarios_dev. La API no revela a un lector
no autorizado detalles de documentos ajenos para distinguir existencia de denegación.

### Identidad, tablas y política única implementada

FastAPI obtiene Principal mediante get_current_user → AuthService.authenticate:
verifica token, sesión, usuario activo y acceso normal (sin cambio de contraseña
pendiente). El navegador no aporta un rol confiable ni se sustituye el principal
del lector por el ADMIN. Las operaciones administrativas consultan además rol y
propiedad actuales directamente en usuarios/rag_documentos.

Se reutilizan visibilidad y ACL existentes. La nueva tabla
**rag_publicaciones_institucionales** registra documento, versión exacta, actor y
fecha de publicación, y actor/fecha de revocación. Tiene una fila por documento,
FK compuesta documento/versión y coherencia entre los campos de revocación.
No duplica texto, fragmentos, permisos individuales ni embeddings.

La rama compartida de la ACL ahora exige simultáneamente:

- Usuario autenticado normal y activo, documento no archivado.
- visibilidad AUTHENTICATED.
- Publicación institucional explícita, no revocada, de ESA versión activa.
- Versión LISTA y, en cloud, índice del espacio configurado activo/VALIDADA.

Un mero AUTHENTICATED sin registro explícito ya no concede lectura colectiva.
Cambiar la versión activa no publica la nueva; hay que autorizarla expresamente.
La migración no crea publicaciones ni modifica visibilidades al subir.

La misma expresión ACL se utiliza en catálogo, require_active, búsqueda/recovery,
lectura estructural de artículos/funciones y continuidad. El catálogo cloud añade
el estado vectorial en la consulta SQL: una falla SQL continúa siendo error técnico,
no se convierte en catálogo vacío. list_sources revalida el scope después de leer
los títulos. El caso RAG vuelve a comprobar permiso y versión antes de responder.
Las citas conservan scope y versión; history/replay revalidan sus referencias.

La publicación **solo concede lectura**. Se conservaron las guardas de ingesta,
validación y activación: ADMIN activo y propietario. El cambio no incorpora
interfaces de edición o borrado. Tampoco habilita exportación documental hacia
Jina ni modifica DOCUMENT_EXPORT_APPROVED=False.

### Publicar y revocar: administración controlada

Se agregaron dos operaciones autenticadas:

```text
POST   /api/v1/ia/documentos/{documento_id}/publicacion
DELETE /api/v1/ia/documentos/{documento_id}/publicacion
Cuerpo JSON: {"version_id":"UUID de la versión exacta"}
```

Se rechazan campos extra como rol/propietario. El repositorio exige al propietario
ADMIN activo y bloquea documento/usuario dentro de una transacción corta. No basta
ser otro ADMIN o un lector institucional. Para publicar exige versión activa LISTA,
puntero del espacio configurado e ingesta VALIDADA, con bloqueos de lectura de esas
filas. Publicación y visibilidad cambian en el mismo commit. La revocación conserva
el registro marcado como revocado y deja visibilidad PRIVATE; no borra contenido.
Puede revocarse también un documento archivado, sin volver a habilitarlo.

Revocar impide nuevos accesos basados en esa publicación, consultas en curso que
fallen su revalidación final y nuevas lecturas de historial/replay con esa referencia.
**No borra información ya recibida por un navegador.** Se mantiene la propiedad
de las conversaciones; el ADMIN no obtiene acceso a conversaciones ajenas por haber
publicado su fuente. El dueño del documento y las concesiones ACL independientes
conservan sus permisos preexistentes: revocar publicación no elimina permisos
explícitos individuales. Retirarlos requeriría una operación separada autorizada.

### Migración preparada y compatibilidad operativa

**0007_institutional_publication**, dependiente de 0006_cloud_embeddings, crea la
tabla de publicación y sus restricciones. downgrade retira la tabla y deja PRIVATE
los documentos registrados, para que un binario anterior no interprete un flag
residual como permiso global. La reversión revoca publicación; no la restaura
automáticamente después de otro upgrade ni conserva un historial de todas las
publicaciones anteriores. No se modifican propietarios ni vectores.

Se probaron upgrade/downgrade y restricciones en SQLite en memoria, con esquema
public aislado. El adaptador de pruebas traduce referencias de esquema y omite
FOR UPDATE/FOR SHARE/SET LOCAL, incompatibles con SQLite. Los bloqueos PostgreSQL
se verifican como contrato SQL; **no se certifica concurrencia ni ejecución DDL
real en PostgreSQL con esos tests**. Falta la comprobación específica de despliegue
en PostgreSQL antes de aprobar una operación real. No se ejecutó migración en
usuarios_dev ni usuarios_test, ni se crearon bases reales.

**No cargar esta versión del backend contra revisión 0006:** la ACL nueva necesita
la tabla 0007. Sin ella, las lecturas fallan cerradas como error técnico. El despliegue
requiere coordinar migración autorizada y carga del código; no hubo reinicios.

### Archivos modificados

1. backend/migrations/versions/0007_institutional_publication.py, nuevo.
2. backend/src/app/infrastructure/rag/postgres.py: ACL compartida por versión y
   revalidación de títulos del catálogo.
3. backend/src/app/infrastructure/rag/cloud_postgres.py: catálogo con índice válido,
   publicación/revocación transaccionales restringidas al propietario ADMIN.
4. backend/src/app/presentation/http/ia/respuestas.py: operaciones autenticadas.
5. backend/tests/rag/test_institutional_publication_12d.py, nuevo.
6. docs/jina-cloud-10g-12d.md: este informe y encabezado actualizado.

No cambió React en esta intervención; conserva el catálogo y los contratos previos.

### Pruebas ejecutadas

Desde backend:

```powershell
& '.\.venv\Scripts\python.exe' -B -m pytest tests/rag/test_institutional_publication_12d.py tests/rag/test_literal_functions_12d.py tests/rag/test_literal_requirements_12d.py tests/rag/test_competition_relevance_12d.py tests/rag/test_academic_routing_final_12d.py tests/ia/test_dots_openrouter.py tests/rag/test_weather_rag_functional_12d.py tests/rag/test_geographic_normalization.py tests/rag/test_weather_dates.py tests/rag/test_rag_private_diagnostics.py tests/rag/test_memory_functional_12d.py tests/rag/test_evidence_memory_12d.py tests/rag/test_conversation_memory_intent.py tests/rag/test_semantic_planning.py tests/rag/test_tools_memory.py tests/rag/test_answer_diagnostics.py tests/rag/test_structured_output.py tests/rag/test_normative_articles.py tests/rag/test_article_continuity.py tests/rag/test_jina_cloud.py tests/rag/test_core.py tests/rag/test_explicit_articles.py tests/ia/test_http_ia.py -q -p no:cacheprovider --basetemp=.pytest-tmp-publication-final --tb=short
```

**457 aprobadas, 0 fallidas, 7,56 s**, advertencia previa Starlette/HTTPX.
Incluye 28 casos nuevos de aislamiento/publicación: propietario y usuario normal
leen el mismo documento sin duplicación, requisitos con tres puntos/F1/página 33,
funciones con páginas/citas coincidentes, rechazo de publicación/revocación por
usuario común u otro ADMIN, ingesta/validación/activación denegadas a lectores,
sesión anónima rechazada por HTTP y campos de rol rechazados, documentos privados,
no publicados, revocados, archivados, sin versión, versión nueva no publicada,
índice ausente/no validado, usuario inactivo, FK y revocación coherentes, historial
y replay revocados y aislamiento de conversaciones. Las regresiones previas de
artículo 24, requisitos, funciones extensas, memoria, clima y HTTP siguen incluidas.

Comprobación separada del archivo nuevo y test_relevance.py: **37 aprobadas,
1 fallida, 2,28 s**. Persiste únicamente el caso heredado de respuesta ficticia sin
soporte ya documentado. No se modificó su expectativa ni el validador. No se suman
iteraciones ni se declara aprobada toda la suite. No se repitió frontend: no cambió
en esta intervención. No hubo transportes externos en las pruebas.

### Procedimiento preparado, NO ejecutado

1. Cuando PostgreSQL esté disponible, repetir READ ONLY con ambos principales reales
   autorizados y comprobar identidad, visibilidad, ACL, revisión, versión e índice.
   No usar el principal ADMIN en lugar del segundo usuario. No registrar nombres,
   emails, contraseñas ni tokens en el informe.
2. Revisar respaldo y prueba PostgreSQL aislada de la migración; aprobar expresamente
   la migración y la publicación de la versión exacta. La autorización de código
   de este sprint no sustituye ese permiso operativo.
3. Solo después de esa aprobación, comando preparado desde backend:

```powershell
$env:PYTHONPATH=(Join-Path (Get-Location) 'src')
& '.\.venv\Scripts\python.exe' -B -m alembic -c alembic.ini -x allow-development=true upgrade 0007_institutional_publication
```

4. Coordinar la carga del backend únicamente con permiso de reinicio. Con la sesión
   normal del propietario ADMIN, enviar el POST de publicación, documento
   8ac0c745-1307-5bb4-9d56-93dfbee0b3b8 y cuerpo de versión
   7cb4e79c-747d-574a-8abb-0ebcb2e07636, tras reconfirmarla activa. Autenticación
   exclusivamente por el mecanismo local normal; no copiar tokens al chat/.env.
   La publicación no llama a proveedores ni modifica los 432/864 vectores.
5. Verificar READ ONLY el registro, propietario intacto, visibilidad y catálogo
   de ambos usuarios. Después, con autorización para consultas reales que pudieran
   consumir APIs, probar las preguntas desde React en sesiones/conversaciones
   separadas. Una prueba real no queda autorizada automáticamente por estos mocks.
6. Para retirar lectura colectiva, usar DELETE con la misma versión y sesión del
   propietario ADMIN. Comprobar nueva consulta, catálogo e historial citado del
   lector sin concesión individual; no eliminar documentos o embeddings.

### Decisión y opciones

Se recomienda la publicación institucional explícita por versión implementada.
Las ACL individuales siguen siendo útiles para excepciones privadas; no sustituyen
esta decisión de compartir con todos los usuarios normales autenticados. Cambiar
solo visibilidad era posible en el esquema anterior, pero no vinculaba el permiso
a la versión publicada ni dejaba constancia del actor/revocación. Duplicar índices
o usar la identidad del ADMIN no es necesario y no se implementó.

**GO de implementación local; NO-GO para probar el nuevo acceso con dos usuarios
reales todavía.** La base no pudo consultarse actualmente y faltan migración,
publicación y despliegue autorizados. No se publicaron documentos actuales ni se
cambiaron roles, permisos, propietarios, documentos, vectores, .env, API keys,
modelos/proveedores o DOCUMENT_EXPORT_APPROVED=False. No hubo escrituras en bases
reales, APIs externas, consumo, migraciones reales o reinicios.

## Autorización condicionada de 0007 y publicación — 12 de noviembre

**Autorización recibida para migrar/publicar solo después de cumplir todas las
precondiciones. Operación detenida en el paso 4: falta un respaldo actualizado que
permita recuperar también el índice Jina. No se fuerza la migración.**

Esta sección actualiza el estado operativo; no invalida las evidencias históricas
anteriores ni suma ejecuciones de pruebas.

### Pasos 1–2: conectividad y estado real READ ONLY

El destino configurado coincidió exactamente con usuarios_dev, 127.0.0.1:5434.
La conexión TCP respondió y PostgreSQL aceptó la sesión. Se comprobó
current_database(), SHOW transaction_read_only=on y revisión Alembic
**0006_cloud_embeddings**, con connect_timeout=5 y statement_timeout=5000 y
default_transaction_read_only=on. Las lecturas finalizaron con rollback.

El timeout anterior **no se reprodujo**. No se dispone de evidencia suficiente
para adjudicarle una causa histórica concreta. La consulta inicial de conexiones
del sistema no aportó un listener verificable, pero la prueba TCP directa y la
sesión SQL sí funcionaron: no se interpretó aquel resultado como caída del servidor.
El acceso inicial sin elevación al API local de Docker fue denegado por permisos;
las inspecciones necesarias se realizaron después con elevación autorizada. Eso
no demuestra un fallo de PostgreSQL. No se cambió configuración ni se reinició
ningún servicio existente.

| Precondición real | Resultado |
|---|---|
| Documento | 8ac0c745-1307-5bb4-9d56-93dfbee0b3b8 |
| Versión activa exacta | 7cb4e79c-747d-574a-8abb-0ebcb2e07636 |
| Estado documental | LISTA; documento no archivado |
| Propietario esperado | 32eabde4-7d17-4029-a47a-60e2e38faf05, ADMIN activo |
| Visibilidad | PRIVATE |
| Índice cloud | Puntero del espacio 1f048209-4b55-31fc-5d34-06985eb3ba0e e ingesta VALIDADA |
| Fragmentos de la versión | 432 |
| Embeddings del espacio/versión exactos | 432 |
| Embeddings históricos totales | 864 |
| Concesiones individuales puede_leer del documento | 0 |
| Otros usuarios activos | 3; los tres USUARIO |

La comparación SQL evaluó cada identidad por separado, sin ejecutar consultas RAG
con la identidad ADMIN en nombre de otro usuario. El propietario resultó autorizado;
los tres usuarios normales activos quedaron excluidos por la ACL vigente anterior
a 0007. No se imprimieron sus UUID, nombres, emails, claves ni tokens.

**Causa del aislamiento ratificada:** documento PRIVATE, dueño diferente y cero
concesiones individuales. El índice ya está activo; no falta un espacio por usuario.
No hay evidencia de error de catálogo para este caso. No se ejecutó el repositorio
nuevo contra una tabla 0007 inexistente para simular un resultado operativo.

### Paso 3: prueba real en PostgreSQL aislado

Se creó únicamente para esta prueba un contenedor **rag-pub-12d-isolated-20261112**,
con imagen local api-usuarios-clean/pgvector:18-0.8.2-93c, PostgreSQL **18.6**,
base sintética **publication_test**, puerto publicado exclusivamente en
127.0.0.1:58565. Sin descargas, volúmenes del proyecto ni datos reales: almacenamiento
tmpfs de 256 MiB, memoria limitada a 512 MiB y una CPU. No se conectó a usuarios_test.
La creación de este entorno corresponde exclusivamente al paso de prueba aislada
expresamente autorizado; no modifica otras bases existentes.

Se ejecutaron los DDL documentales/cloud necesarios con usuarios y documentos
sintéticos. La migración 0007 se ejecutó mediante Operations/MigrationContext
reales de Alembic contra PostgreSQL, sin traducción SQLite. Las operaciones de
publicación/revocación se ejecutaron con CloudPostgresRAG y SQL transaccional real.
No se crearon vectores ni se llamó a proveedores.

**Resultado VERIFIED, salida 0: ocho controles aprobados**:

1. Usuario común y ADMIN no propietario no pueden publicar.
2. Publicación por el propietario y lectura del mismo scope/catálogo por ambos usuarios.
3. FK compuesta documento/versión y CHECK de revocación rechazan estados inválidos,
   comprobados con savepoints PostgreSQL.
4. Una conexión mantiene FOR UPDATE del documento; la operación concurrente agota
   lock_timeout con SQLSTATE 55P03 y revierte sin revocar la publicación vigente.
5. Revocar impide lectura y catálogo del usuario común sin ACL independiente.
6. Compartir lectura no concede prepare_existing, validate_cloud ni activate.
7. Una ingesta no VALIDADA no puede publicarse.
8. Upgrade → publicación → downgrade → upgrade reales: downgrade deja PRIVATE y
   elimina la tabla; upgrade recrea la tabla vacía, sin publicaciones automáticas.

Se probaron el módulo DDL y las operaciones oficiales; no se presenta esto como
ejecución del comando completo de despliegue Alembic sobre usuarios_dev ni como
prueba de una sesión HTTP real del propietario. La batería de 457 mocks/SQL aislado
anterior sigue siendo evidencia complementaria, no se volvió a ejecutar aquí.

El contenedor de pruebas se conserva con datos exclusivamente sintéticos en tmpfs.
No se detuvo ningún proceso existente ni se eliminó una base del usuario. No debe
usarse este entorno con autenticación de laboratorio para restaurar datos privados
sin preparar antes el aislamiento y acceso restringido correspondientes.

### Paso 4: respaldo encontrado y motivo exacto de detención

La copia Windows documentada anteriormente en
D:\Downloads\api-usuarios-clean-backups\10e-8ec23d77c150417db136e68c0a0f2d05\usuarios_dev.dump
no existe actualmente en esa ruta. La inspección de metadatos, incluidos ocultos,
dentro de la raíz conocida de respaldos encontró únicamente directorios y logs de
frontend anteriores, sin otro dump. No se leyeron esos logs ni se buscó contenido
arbitrario fuera de los destinos conocidos.

**Sí existe la copia histórica dentro del contenedor del proyecto**:
/tmp/usuarios-dev-10e-8ec23d77c150417db136e68c0a0f2d05.dump.
Se comprobó en memoria:

- pg_restore --list termina correctamente: archivo custom legible.
- SHA-256 coincide con el manifiesto 10E previamente registrado:
  93e1316a5c934b7e5e70008015db772a0b7b556f31e36ece996be648fb16c91b.
- El catálogo contiene datos de rag_embeddings históricos.
- **No contiene rag_cloud_embeddings ni rag_cloud_activos**.

No se imprimieron filas, documentos, propietarios del catálogo del dump o secretos.
La restauración histórica verificada en 10E acredita aquel punto antiguo; no se
restauró nuevamente ese dump en esta intervención. Es un respaldo histórico íntegro
respecto de su manifiesto, pero **no protege el estado actual con 432 embeddings
Jina y su publicación vectorial**. Su legibilidad no acredita recuperación completa
del estado previo a 0007. No se declara que no pueda existir un respaldo desconocido
en otra ubicación, ni se presenta el respaldo antiguo como inexistente.

Por esa insuficiencia se detiene la secuencia antes de la ventana de escritura.
**No se creó un nuevo respaldo**, porque el usuario exige autorización específica
si falta uno adecuado. Procedimiento a autorizar: UN dump actualizado de usuarios_dev
en una carpeta nueva privada, verificación SHA-256 y catálogo, y prueba de restauración
en un PostgreSQL aislado con acceso restringido. La comprobación debe incluir revisión
0006, documento/versión exactos, 432 cloud, 864 históricos y puntero/ingesta, además
de las tablas y restricciones necesarias. No debe modificar usuarios_test ni borrar
respaldos anteriores. La copia deberá quedar fuera del repositorio y sin credenciales
en archivos de comandos o en el informe.

### Pasos pendientes y estado efectivo

| Paso | Estado |
|---|---|
| 1–2: conexión y preflight READ ONLY | Aprobados en esta intervención |
| 3: PostgreSQL aislado | Aprobado con ocho controles reales |
| 4: recuperación del estado actual | NO superado; requiere respaldo actualizado autorizado |
| 5: ausencia de escritores/ventana segura | No iniciado por la parada obligatoria |
| 6: revalidación inmediatamente antes de escribir | No iniciada; el preflight anterior no la sustituye |
| 7–8: migrar y verificar conservación | No ejecutados; revisión inicial comprobada 0006 |
| 9: cargar backend compatible | No ejecutado; un reinicio requerirá autorización específica |
| 10: endpoint con sesión del propietario | No invocado; ninguna publicación ejecutada |
| 11: lectura institucional posterior | No disponible por esta intervención; PRIVATE en el preflight |

Único archivo del proyecto modificado en esta intervención: docs/jina-cloud-10g-12d.md.
El ejecutor puntual de prueba se envió por stdin y no se guardó como herramienta
reutilizable. No se cambiaron roles, propietarios, ACL individuales, documentos,
embeddings, proveedores/modelos, claves, .env o DOCUMENT_EXPORT_APPROVED=False.
No hubo APIs externas ni consumo. Las únicas escrituras fueron sobre el entorno
PostgreSQL sintético autorizado; no hubo escrituras en usuarios_dev/usuarios_test.

**NO-GO para despliegue y pruebas React con dos usuarios.** Se solicita autorización
para crear y verificar el respaldo actualizado. La autorización condicionada de
migración/publicación ya recibida sigue vigente; no se pedirá de nuevo para esos
mismos actos si se superan todas sus condiciones. No se solicita aún un reinicio
ni se autoriza implícitamente ninguna consulta externa.

## Respaldo actualizado autorizado — creación y parada previa a restauración

12 de noviembre de 2026. Continuación del MISMO Sprint 10G12D.
**Se ejecutó UN pg_dump. El respaldo quedó conservado e íntegro como archivo.
No se aprueba todavía su recuperación: pg_restore no llegó a ejecutarse.**

### Origen y snapshot comprobados

Se confirmó que api-usuarios-clean-postgres-1 estaba funcionando y exponía
5432 únicamente mediante 127.0.0.1:5434. La configuración cargada correspondía
exactamente a usuarios_dev. Se comprobó current_database() y READ ONLY, con
connect_timeout=5 y statement_timeout=60000. La transacción de origen fue
REPEATABLE READ READ ONLY; se exportó su snapshot para el único pg_dump.

Antes de crear el respaldo se reconfirmaron:

- Revisión 0006_cloud_embeddings.
- Documento 8ac0c745-1307-5bb4-9d56-93dfbee0b3b8.
- Versión activa 7cb4e79c-747d-574a-8abb-0ebcb2e07636, LISTA y visibilidad PRIVATE.
- Propietario esperado ADMIN activo.
- 432 embeddings cloud del espacio/version autorizados y 864 históricos.
- Puntero del espacio Jina exacto e ingesta VALIDADA.
- Restricciones existentes en public validadas.

Se calcularon en memoria conteos/huellas de filas de todas las tablas public y
metadata de propietarios, ACL y restricciones, como preparación de la comparación
de recuperación. **Esa comparación con destino no se realizó**. No se imprimieron
filas, documentos, vectores, contraseñas, hashes de credenciales o tokens. Se
leyeron atributos no secretos de roles necesarios para preparar una restauración
compatible; no se modificaron roles reales.

### Único respaldo creado

| Propiedad | Resultado |
|---|---|
| Carpeta privada nueva | D:\Downloads\api-usuarios-clean-backups\10g12d-0007-4f42adbf6ad14adb8d5d4c1fcc6873c7 |
| Archivo | usuarios_dev.dump |
| Formato | PostgreSQL custom, esquema y datos completos sin filtros de tablas |
| Tamaño | **5.173.323 bytes** |
| SHA-256 | **58bf705e1e66c9835c321fb3434b212138b52de30d6bc35bb0e7941255121acb** |
| Copia del contenedor origen | /tmp/usuarios-dev-10g12d-4f42adbf6ad14adb8d5d4c1fcc6873c7.dump |
| pg_dump | Una invocación; salida 0 |
| pg_restore --list | Salida 0; catálogo legible conservado como catalogo.txt |
| Permisos del dump en contenedor | 600, umask 077 |
| NTFS | Carpeta sin herencia externa; acceso solo operador y SYSTEM, verificado también en los artefactos |

pg_dump recibió el snapshot exportado, --format=custom y
--lock-wait-timeout=5s. No se usaron --no-owner, --no-acl ni exclusiones. El catálogo
contiene datos de rag_cloud_embeddings, rag_cloud_activos, rag_cloud_ingestas,
rag_embeddings, rag_documento_permisos y alembic_version, además del resto del dump.

Se copió con docker cp, sin redirección binaria por PowerShell. El SHA-256 coincidió
entre archivo del contenedor y copia Windows; se volvió a calcular al cerrar la
intervención y permaneció idéntico. La carpeta restringida se verificó antes de
colocar bytes sensibles y nuevamente después. No se sobrescribió ni eliminó
ningún respaldo anterior. Se conservan dump, catálogo y failure-safe.json con
estado operativo y sin cuerpos privados.

### Fallo exacto de preparación aislada

Se creó el contenedor nuevo **rag-restore-12d-4f42adbf6ad1**, imagen PostgreSQL 18
con pgvector local ya disponible, con almacenamiento independiente tmpfs de
512 MiB, memoria limitada a 1 GiB, una CPU y **--network none**, sin puertos
publicados ni montajes del proyecto. No se descargaron imágenes.

La preparación indicó POSTGRES_HOST_AUTH_METHOD=reject y omitió una contraseña
inicial. La imagen exige POSTGRES_PASSWORD cuando no se utiliza trust. **Fue un
error de preparación del ejecutor:** el entrypoint terminó con código 1 antes de
iniciar PostgreSQL; la comprobación de disponibilidad no pudo aprobarse. Se
confirmó la categoría del error leyendo logs en memoria, sin imprimirlos.

La base nueva prevista era rag_restore_12d_4f42adbf6ad14adb8d5d4c1fcc6873c7.
No se ejecutó su CREATE DATABASE ni se invocó pg_restore, ni se copiaron datos
reales al contenedor fallido. No hubo errores de restauración que se hayan
ignorado: **no hubo una restauración**. Tampoco se usaron opciones para desactivar
restricciones o saltar errores.

Conforme a la instrucción «si alguna comprobación falla, detenerse», no se
reintentó el arranque, no se reemplazó el contenedor ni se generó otro dump. El
contenedor fallido quedó detenido por su propio entrypoint; no se reinició ni
detuvo ningún servicio existente del proyecto. La transacción READ ONLY del
origen se cerró con rollback al registrar la parada.

La continuación requiere corregir exclusivamente la preparación de un entorno
aislado con autenticación inicial compatible y acceso restringido, y restaurar
**este mismo dump conservado**. No hace falta repetir pg_dump por este fallo de
arranque. La prueba deberá preservar propietarios/ACL, activar restricciones
normalmente y comprobar revisión, documento, versión, datos, vectores y estados
antes de considerar aprobado el paso 4. No se propone utilizar trust con datos
privados ni modificar credenciales existentes o archivos .env.

### Estado y decisión

| Criterio | Estado |
|---|---|
| Dump custom creado sin error | Aprobado, una invocación |
| Catálogo legible y tablas cloud/históricas incluidas | Aprobado |
| Tamaño, hash coincidente y conservación privada | Aprobado |
| Arranque del nuevo PostgreSQL aislado | Fallido: falta contraseña inicial exigida por la imagen |
| Restauración, roles/ACL de destino y comparación completa | No ejecutados |
| Paso 4 recuperable | **NO aprobado** |
| Paso 5 sin escritores y ventana segura | No iniciado por la parada |
| Paso 6 revalidación inmediata | No iniciado |
| Migración 0007 / publicación / despliegue | No ejecutados |

**NO-GO para migración, publicación y pruebas React.** La legibilidad y hash del
archivo no sustituyen la restauración exigida. La autorización condicionada de
0007/publicación y la autorización del respaldo se conservan; esta intervención
no declara cumplidas sus condiciones ni pide autorización para otro dump.

Único archivo del proyecto modificado: docs/jina-cloud-10g-12d.md. Los ejecutores
puntuales se enviaron por stdin. No hubo escrituras de datos, migraciones ni
publicaciones en usuarios_dev; no se tocó usuarios_test. No se modificaron
documentos, vectores, propietarios, roles, ACL individuales, modelos, proveedores,
.env, credenciales ni DOCUMENT_EXPORT_APPROVED=False. No hubo APIs externas,
créditos o reinicios de servicios existentes. No se eliminaron respaldo ni catálogo.

## Paso 4 completado — restauración aislada del mismo dump

12 de noviembre de 2026. Continuación del MISMO Sprint 10G12D.
**GO para el paso 4. Se completó la restauración real y su comprobación READ ONLY.
Se detiene la intervención antes de iniciar la ventana del paso 5.**

### Respaldo existente, sin repetir pg_dump

Se verificaron nuevamente permisos NTFS y SHA-256 antes de preparar la recuperación:

- Archivo: D:\Downloads\api-usuarios-clean-backups\10g12d-0007-4f42adbf6ad14adb8d5d4c1fcc6873c7\usuarios_dev.dump.
- Tamaño: **5.173.323 bytes**.
- SHA-256: **58bf705e1e66c9835c321fb3434b212138b52de30d6bc35bb0e7941255121acb**.
- Coincidencia exacta con el hash registrado; verificado de nuevo al finalizar.
- Carpeta con herencia externa deshabilitada y artefactos accesibles únicamente
  al operador y SYSTEM. El dump original, catálogo y registro de la preparación
  fallida anterior permanecen conservados, sin sobrescritura ni eliminación.

**Invocaciones de pg_dump en esta continuación: cero.** Tampoco se creó otro dump.

### Nuevo entorno y corrección de autenticación

Se creó un contenedor nuevo, sin modificar o reiniciar el contenedor fallido ni
los contenedores del proyecto:

| Propiedad | Valor |
|---|---|
| Contenedor | rag-recovery-12d-b9a9204365a8 |
| Base nueva restaurada | rag_restore_12d_b9a9204365a84a7a9bc2c86c3380ba87 |
| Imagen local | api-usuarios-clean/pgvector:18-0.8.2-93c |
| PostgreSQL / pgvector | PostgreSQL 18; pgvector 0.8.2 comprobado |
| Red | none; sin PortBindings ni puertos publicados |
| Almacenamiento | tmpfs independiente, 512 MiB; sin montajes del proyecto |
| Límites de recursos | 1 GiB de memoria, una CPU |
| Autenticación local y host | scram-sha-256; reglas HBA sin errores y ninguna regla trust |

Se generó localmente una contraseña temporal aleatoria de 48 bytes de entropía
para el administrador del nuevo entorno. Se transmitió mediante variables de
entorno del proceso Docker, sin el valor en argumentos, logs, archivos del
repositorio o informe. No se reutilizó ni cambió ninguna contraseña existente.
El acceso al entorno y a su metadata Docker requiere los permisos locales del
operador; no existe acceso de red desde el host u otros equipos.

Se prepararon roles compatibles exclusivamente en el entorno aislado, sin copiar
contraseñas del origen. Los roles auxiliares se crearon NOLOGIN y con atributos
de privilegio compatibles; se reprodujeron las membresías necesarias. La base
nueva se creó con propietario, codificación, proveedor de locale y collation del
origen. No se creó ni alteró ningún rol o base del servidor original.

### Restauración real

Se copió el mismo archivo al contenedor aislado, se comprobó su hash idéntico y se
restringió a modo 600. Se ejecutó una sola restauración con:

```text
pg_restore --exit-on-error --single-transaction -d BASE_NUEVA usuarios_dev.dump
```

La autenticación se suministró sin mostrarla; se preservaron propietarios y ACL.
**Salida 0.** No se utilizaron --no-owner, --no-acl, --disable-triggers ni opciones
para ignorar errores. Las restricciones se restauraron y validaron normalmente.

### Comparación READ ONLY y diferencia de representación CHECK

Las huellas de la creación anterior habían quedado solo en memoria y no se
presentan como un manifiesto persistido recuperado. Para esta comprobación se
volvieron a calcular en el origen, mediante REPEATABLE READ READ ONLY, y se
compararon con la restauración fija del dump cuyo SHA-256 no cambió. Se repitió
la comparación de datos al cerrar la verificación. No se tomó un nuevo respaldo.

Se compararon **las 21 tablas public completas**, incluidos usuarios, historial,
documentos, páginas, fragmentos, permisos y embeddings. Por tabla: conteo y SHA-256
del conjunto ordenado de MD5 de cada fila JSONB. Los cálculos se realizaron dentro
de PostgreSQL, con la misma zona UTC; no se imprimieron filas, textos o vectores.
**Todos los conteos y huellas coinciden.** Es una comprobación operacional de
igualdad, no una certificación forense frente a colisiones deliberadas.

También coinciden los propietarios y ACL de relaciones/esquema public y las
propiedades de propietario, ACL, codificación, locale y collation de la base.

La primera comparación textual estricta de pg_get_constraintdef detectó nueve
diferencias entre **256 restricciones** y dejó la aceptación en pausa. Se
diagnosticaron exclusivamente en READ ONLY, sin alterar ninguna definición:

- **247 definiciones son textualmente idénticas.**
- Ocho CHECK de pertenencia a enumeraciones aplican el cast varchar→text al array
  completo en el origen o a cada elemento en la representación restaurada. Se
  comprobaron exactamente el mismo campo, literales y orden, y los patrones de
  esos casts. Ambos representan la misma pertenencia al mismo conjunto de textos.
- El CHECK de longitud de agent_mensajes.contenido reagrupa con paréntesis las
  mismas tres condiciones: longitud mínima 1, máxima 4096 y máximo 16384 bytes.
  Solo interviene AND, asociativo también bajo la lógica SQL con NULL.

La comprobación de equivalencia se limitó a esas formas exactas; cualquier otra
diferencia habría mantenido NO-GO. No se eliminaron genéricamente condiciones,
literales, casts o validaciones para aprobarlas. No faltan ni sobran restricciones;
coinciden nombres, tablas, tipos, validación y atributos de diferibilidad.
**Las 256 están validadas y su definición es idéntica o de equivalencia demostrada.**
La diferencia era de representación SQL tras el round trip, no un fallo de
integridad. No se reintentó pg_restore ni se modificó la base restaurada para
igualar textos de catálogo.

### Resultados efectivos

| Comprobación | Restauración verificada |
|---|---|
| Revisión Alembic | 0006_cloud_embeddings |
| Documento autorizado | Existe, UUID exacto |
| Versión activa | 7cb4e79c-747d-574a-8abb-0ebcb2e07636 |
| Estado / visibilidad | LISTA / PRIVATE |
| Propietario esperado | Conservado; ADMIN activo |
| ACL documental | Filas idénticas; cero concesiones individuales de lectura del documento |
| Embeddings Jina del espacio/versión | 432 |
| Integridad vectorial cloud | 768 dimensiones, norma dentro de ±0,01 |
| Embeddings históricos | 864, filas y vectores idénticos por huella |
| Puntero / ingesta | Espacio exacto activo / VALIDADA |
| Tablas public comparadas | 21, conteos y huellas iguales |
| Restricciones | 256 validadas; sin faltantes ni adicionales |
| Propietarios/ACL y propiedades de base | Coincidentes |
| pg_restore | Salida 0, sin errores omitidos |
| Respaldo original | Conservado, hash idéntico |

La aceptación procede de PostgreSQL real y de una restauración real, no de mocks.
Las lecturas de comparación del destino usaron BEGIN READ ONLY y rollback; el
origen recibió conexiones forzadas a READ ONLY. No se accedió a usuarios_test.

### Estado y parada antes del paso 5

**Paso 4 APROBADO. GO para coordinar el paso 5; la ventana no se inició.**
No se consultó ni declaró todavía la ausencia de escritores para una migración,
ni se realizó la revalidación inmediatamente anterior a escribir del paso 6.
No se aplicó 0007, no se publicó ningún documento y no se cargó/reinició el backend.
La autorización condicionada anterior sigue pendiente de sus demás condiciones.

El contenedor restaurado queda conservado sin red y con almacenamiento tmpfs:
su permanencia es temporal y no sustituye el dump durable protegido en Windows.
No se eliminaron el respaldo, el catálogo o los contenedores anteriores.
No hubo llamadas externas, créditos, cambios de API keys, .env, modelos,
proveedores o DOCUMENT_EXPORT_APPROVED=False. No se imprimieron datos personales,
contraseñas, contenido documental o vectores. Las únicas escrituras de base fueron
la preparación y restauración autorizadas en el nuevo entorno aislado.

Único archivo del proyecto actualizado en esta continuación:
docs/jina-cloud-10g-12d.md. Los ejecutores puntuales se enviaron por stdin.
**Las pruebas React siguen en NO-GO hasta completar el despliegue compatible y
obtener autorización para cualquier llamada externa requerida.**

## Paso 5A — verificación previa a 0007, sin ejecución

12 de noviembre de 2026. Continuación del MISMO Sprint 10G12D.
**Revisión y diseño comprobados; ventana de escritura aún no garantizada.
NO APTO todavía para solicitar autorización de ejecución inmediata.** Se detiene
la intervención después de estas verificaciones, conforme al pedido más reciente.
Un nuevo GO explícito será necesario antes de ejecutar la migración.

### Revisión real, destino y archivo existente

Se cargó la configuración sin imprimir secretos y se exigió coincidencia exacta
con usuarios_dev, 127.0.0.1:5434. La sesión PostgreSQL usó connect_timeout=5,
default_transaction_read_only=on, statement_timeout=10000 y REPEATABLE READ.
SHOW transaction_read_only confirmó on; las consultas terminaron con rollback.

| Control actual | Resultado |
|---|---|
| Revisión aplicada | 0006_cloud_embeddings |
| Tabla rag_publicaciones_institucionales | Todavía no existe |
| Documento autorizado | Existe, no archivado, PRIVATE |
| Versión activa autorizada | 7cb4e79c-747d-574a-8abb-0ebcb2e07636, LISTA |
| Propietario esperado | Conservado; ADMIN activo |
| Concesiones individuales de lectura | 0 |
| Espacio cloud autorizado | Puntero activo e ingesta VALIDADA |
| Embeddings cloud / históricos totales | 432 / 864 |
| Tablas public | 21 |

Se verificó físicamente backend/migrations/versions/0007_institutional_publication.py.
El grafo Alembic, leído sin ejecutar env.py ni upgrade, tiene una única cabeza:
0007_institutional_publication, dependiente de 0006_cloud_embeddings.
SHA-256 del archivo inspeccionado:
82b85278bf08430277dea73ae72cb892bfe1e1746fed67f3c3c14f6c240623c8.

upgrade crea únicamente public.rag_publicaciones_institucionales, con PK por
documento, FK al documento y actores, FK compuesta documento/versión y CHECK que
exige coherencia de revocado_por/revocado_at. No inserta publicaciones ni cambia
visibilidades, propietarios, ACL individuales, texto, fragmentos o embeddings.
Alembic actualizará su revisión dentro de la transacción de migración.

La PK evita duplicar publicaciones por documento; la FK compuesta impide asociar
una versión de otro documento. La operación administrativa hace upsert de esa fila:
no es un historial inmutable de todas las publicaciones anteriores.

### Sesiones, procesos y bloqueos observados

Se consultaron pg_stat_activity, pg_locks, pg_blocking_pids y transacciones
preparadas, sin imprimir consultas de aplicaciones, nombres de usuarios o secretos.

| Sesión PostgreSQL distinta de la auditoría | Estado | Transacción abierta | XID asignado | Capacidad de escritura en tablas public |
|---|---|---|---|---|
| PID 96713 | idle | No | No | Sí |
| PID 96730 | idle | No | No | Sí |

No se observaron bloqueos de esas sesiones sobre usuarios, rag_documentos,
rag_versiones o alembic_version; tampoco sesiones bloqueadas ni transacciones
preparadas de esta base. La espera observada en sesiones idle no acredita una
espera por bloqueo. Estos resultados describen una muestra, no una garantía de
que no empiecen escrituras después.

La inspección de metadatos del sistema, con elevación para poder observar procesos
y sockets, identificó:

- Backend Python PID 29416, escuchando en 127.0.0.1:8000, con dos conexiones cliente
  establecidas a 127.0.0.1:5434; lanzador Python del proyecto PID 19708.
- Vite/Node PID 4576 escuchando en 127.0.0.1:5173. Su ruta de proyecto no quedó
  confirmada por los metadatos filtrados; el navegador puede originar solicitudes.
- El listener 5434 pertenece al proxy Docker, no a un proceso que deba detenerse
  para coordinar la aplicación.

No se imprimieron líneas de comandos ni entornos de procesos. No se atribuye cada
PID interno PostgreSQL a un socket Windows concreto sin correlación adicional.
No se certificó qué revisión de código tiene cargada el backend en memoria.
**El backend activo y las sesiones con capacidad de escribir impiden declarar
una ventana sin escritores.** No se detuvo, reinició ni bloqueó ningún proceso.

### Permisos, publicación y aislamiento

La ACL común exige usuario activo y documento no archivado, y después propiedad,
concesión individual puede_leer o publicación institucional. Esta última exige
simultáneamente AUTHENTICATED y un registro explícito no revocado de la versión
activa exacta. Las consultas exigen versión LISTA y el recorrido cloud añade
espacio configurado, puntero activo e ingesta VALIDADA.

PRIVATE no se comparte por ser académico ni por estar indexado. AUTHENTICATED
sin publicación explícita de esa versión tampoco basta. Publicar una versión no
publica automáticamente otra. No hacen falta copias de vectores por usuario.
Los propietarios y las concesiones individuales conservan sus accesos propios;
revocar publicación no elimina esas concesiones.

El endpoint administrativo exige sesión autenticada normal y revalida ADMIN
activo y propietario del documento en SQL. Bloquea documento/actor, comprueba
versión e índice y cambia publicación/visibilidad en el mismo commit. Un lector
institucional u otro ADMIN no adquiere facultades de ingesta, validación o
activación. El cuerpo solo admite version_id; no acepta roles del navegador.
El alcance autorizado sigue siendo exclusivamente el documento
8ac0c745-1307-5bb4-9d56-93dfbee0b3b8 y la versión indicada arriba.

Catálogo, recuperación y lectura estructural reutilizan la ACL; se revalidan
scope y versión antes de entregar respuesta. Historial/replay conservan propiedad
de conversación y revalidación de citas. No se concede acceso a conversaciones
ajenas por publicar una fuente. La lectura compartida no autoriza exportación a
proveedores ni modifica DOCUMENT_EXPORT_APPROVED=False.

Estos controles son de aplicación: las conexiones del backend tienen privilegios
SQL de escritura. No se presenta la ACL de usuarios de la aplicación como una
restricción de privilegios del rol PostgreSQL ni como aislamiento RLS demostrado.

### Riesgos y controles necesarios

CREATE TABLE con claves foráneas necesita bloqueos sobre las tablas referenciadas;
puede esperar o competir con DML/DDL. La muestra sin bloqueos no sustituye la
ventana coordinada. El módulo 0007 y env.py no fijan por sí mismos lock_timeout
ni statement_timeout para el despliegue. Deben acotarse solo en el proceso de
migración, con parada ante timeout y sin reintento automático.

El env.py exige allow-development=true para desarrollo y verifica usuarios_dev,
pero no sustituye la comprobación explícita de host/puerto, revisión y estado
inmediatamente antes de escribir. El código ACL nuevo necesita la tabla 0007;
cargarlo contra 0006 falla cerrado con error técnico. La carga del backend debe
coordinarse con el DDL, sin dar por hecho que el proceso actual contiene ese código.

El upgrade no transforma ni duplica datos existentes ni reconstruye índices
vectoriales. Debe comprobarse su conservación después, sin generar embeddings.
El downgrade sí cambia a PRIVATE los documentos registrados y elimina la tabla
de publicación: pierde esos registros y no restaura publicaciones al volver a
subir. No es una reversión neutra ni debe ejecutarse automáticamente.

### Procedimiento propuesto para la ventana y verificación posterior

Este procedimiento queda documentado, NO ejecutado:

1. Coordinar con el operador una ventana sin solicitudes, ingestas ni trabajos
   administrativos. Identificar también otros clientes con capacidad de escribir.
   Si requiere detener o reiniciar el backend u otros procesos, obtener autorización
   específica para los procesos identificados; no detener PostgreSQL ni Docker.
2. Repetir inmediatamente la inspección de sesiones, transacciones, locks y
   transacciones preparadas. La ausencia momentánea de actividad no basta sin
   impedir operativamente nuevos escritores durante toda la operación. Si no se
   puede garantizar, mantener NO-GO.
3. Verificar disponibilidad del respaldo validado del paso 4 y su SHA-256, sin
   crear otro dump. Registrar en memoria una línea base READ ONLY de tablas,
   huellas, restricciones, propietarios/ACL y estados documentales/vectoriales.
4. Reconfirmar destino exacto usuarios_dev en 127.0.0.1:5434, revisión única 0006,
   tabla 0007 ausente, archivo/grafo sin cambios, documento/versión autorizados,
   LISTA, PRIVATE, propietario e índice activo/VALIDADA. Ante discrepancia, parar.
5. Solo tras un nuevo GO explícito, desde backend y con la configuración privada
   normal, preparar PYTHONPATH=src y PGOPTIONS temporal del proceso con
   lock_timeout=2s y statement_timeout=15000. Conservar y restaurar cualquier valor
   previo de esas variables; no editar .env. El comando previsto es:
   .\.venv\Scripts\python.exe -B -m alembic -c alembic.ini -x allow-development=true upgrade 0007_institutional_publication
   No usar target=test. Un timeout o error exige diagnosticar antes de continuar.
6. Comprobar salida 0 y, en una nueva sesión READ ONLY, revisión única 0007, tabla
   nueva vacía y sus PK/FK/CHECK. Comparar datos de las 21 tablas originales contra
   la línea base, excluyendo únicamente el cambio esperado de alembic_version;
   propietarios/ACL preexistentes y restricciones anteriores deben conservarse.
   Revalidar 432 cloud, 864 históricos, versión, LISTA, PRIVATE e índice VALIDADA.
   Verificar que no hubo publicaciones ni cambios en otros documentos.
7. Coordinar la carga del backend compatible con permiso específico de reinicio
   si resulta necesario. Antes de abrir tráfico, verificar catálogo/autorización
   sin llamadas a proveedores. La publicación posterior requiere su propia
   coordinación y sesión real del propietario; no se incluye como efecto de 0007.
8. Tras una publicación autorizada, comprobar exactitud de documento/versión y
   actor, lectura institucional sin escritura, privados excluidos y aislamiento
   de conversaciones. Las pruebas React con proveedores siguen requiriendo
   autorización de llamadas externas y despliegue compatible completo.

### Recuperación basada en el respaldo validado

Se conserva como referencia el dump del paso 4, sin crear nuevas copias:
D:\Downloads\api-usuarios-clean-backups\10g12d-0007-4f42adbf6ad14adb8d5d4c1fcc6873c7\usuarios_dev.dump.
Tamaño registrado: 5.173.323 bytes. SHA-256 registrado:
58bf705e1e66c9835c321fb3434b212138b52de30d6bc35bb0e7941255121acb.
Su restauración previa terminó con código 0 y comprobó 21 tablas, 256 restricciones
equivalentes, propietarios/ACL y estados cloud/históricos. Esta intervención no
repitió pg_dump ni pg_restore y no convierte esa evidencia previa en una prueba nueva.

Si el DDL falla antes del commit, verificar revisión y tabla en una conexión nueva
antes de decidir; no asumir rollback solo por el mensaje del cliente. Si se
confirma commit pero falla la carga compatible, mantener la ventana y diagnosticar.
Cualquier downgrade exige aprobación y evaluación de sus efectos sobre visibilidad
y publicaciones. Para recuperación completa, restaurar primero el dump verificado
en una base nueva aislada PostgreSQL 18/pgvector compatible, con roles/privilegios
compatibles, pg_restore --exit-on-error --single-transaction y todos los controles
del paso 4. Un reemplazo de usuarios_dev exige autorización operativa separada y
plan para cambios posteriores al snapshot; restaurar el dump antiguo perdería
esos cambios si existieran. Nunca restaurar encima de usuarios_test ni sobrescribir
la base original como reacción automática.

### Decisión y alcance efectivo

**NO APTO todavía para solicitar autorización de ejecución inmediata.** El diseño
es compatible con publicación explícita por versión y protección de privados, y
el respaldo recuperable está validado. Falta coordinar y garantizar la ventana
sin escritores, resolver la carga compatible y efectuar la revalidación inmediata.
Después podrá solicitarse el nuevo GO con esas condiciones concretas satisfechas.

Se termina aquí el paso 5A. No se ejecutó alembic upgrade, SQL de escritura,
publicación, reinicio, nuevo respaldo o regeneración de embeddings. No se accedió
a usuarios_test ni a proveedores externos. No se modificaron credenciales, .env,
roles, propietarios o ACL. No se repitieron suites con mocks para esta revisión de
solo lectura. Único archivo actualizado: docs/jina-cloud-10g-12d.md.

## Paso 5B — ventana sin escritores de aplicación

12 de noviembre de 2026. Continuación del MISMO Sprint 10G12D.
**VENTANA SEGURA en las comprobaciones efectuadas. Backend detenido; se espera
GO explícito para el paso 5C. No se ejecutó la migración ni se reinició el backend.**

### Identificación antes de detener

La inspección actual confirmó los mismos procesos, sin basarse solo en los PID
históricos. Se inspeccionaron rutas y líneas de comandos en memoria, mostrando
únicamente rutas de ejecutables y clasificaciones sin secretos:

| PID | Función comprobada | Vinculación al proyecto |
|---|---|---|
| 19708 | Lanzador Python, padre de 29416 | Ejecutable backend/.venv/Scripts/python.exe dentro de api-usuarios-clean; módulo app.presentation.cli.local_server |
| 29416 | Backend Python, listener 127.0.0.1:8000 | Línea de comandos con ruta del proyecto y el mismo módulo; hijo de 19708 |

29416 tenía dos sockets establecidos a 127.0.0.1:5434. El lanzador local revisado
exige usuarios_dev, 127.0.0.1:5434 antes de iniciar y configura workers=1,
reload=False. Se reconfirmó además el destino de la configuración local y la
identidad SQL real, sin imprimir credenciales. La inspección de origen mostró dos
sesiones de usuarios_dev, PID PostgreSQL 96713 y 96730, idle, sin transacción
abierta ni XID asignado, con capacidad de escritura y sin bloqueos reportados.
La desaparición de ambas después del cierre aporta correlación adicional; no se
confunden los PID Windows con los PID internos PostgreSQL.

No se detuvo un proceso únicamente porque su línea de comandos mencionara una
ruta del proyecto. En particular, el proceso de documentos encontrado no era un
backend y no fue intervenido. PostgreSQL, Docker, Vite y otros proyectos quedaron
fuera de la acción de cierre.

### Cierre dirigido y resultado

Se adjuntó un ejecutor temporal a la consola del backend y se envió CTRL_BREAK
exclusivamente al grupo de procesos 19708, sin difusión al grupo 0. Windows aceptó
la señal. La comprobación posterior encontró ausentes tanto 19708 como 29416 y
cero listeners en 8000. No fue necesario Stop-Process, taskkill, terminación
forzada, reinicio ni cambio de configuración.

Esto acredita la salida tras la señal dirigida y el cierre de sockets/sesiones;
no se recogieron logs privados ni se afirma haber auditado cada callback interno
de apagado de Uvicorn. No se cerró la terminal del operador ni se enviaron señales
globales a otros procesos de su consola.

### Ausencia de escritores y de relanzamiento observado

Se revisaron metadatos de procesos, sockets, servicios Windows, acciones de tareas
programadas y contenedores activos. No se imprimieron líneas de comandos completas,
entornos ni acciones que pudieran contener secretos.

- Ningún proceso restante de backend/worker reconocido con ruta o módulo del
  proyecto. No se observó reloader, supervisor o worker del proyecto en ejecución.
- Cero servicios Windows con ruta del proyecto y cero tareas programadas con esa
  ruta en ejecutable, argumentos o directorio de trabajo.
- Cero sockets cliente establecidos hacia 5434 y cero listeners en 8000 en la
  inspección posterior. No se abrió otra instancia del backend.
- Los contenedores activos listados son PostgreSQL del proyecto y entornos de
  restauración/pruebas ya existentes; no hay contenedor de aplicación activo.
  Los archivos compose revisados definen PostgreSQL, sin servicio de backend que
  lo relance. El restart de PostgreSQL no es un supervisor del backend y no se tocó.

Las consultas posteriores a pg_stat_activity encontraron **cero sesiones restantes
para usuarios_dev excluyendo la propia auditoría**, no solamente cero sesiones
activas. No quedaron sesiones idle con capacidad de escritura. Cero transacciones
preparadas. No se cancelaron ni terminaron sesiones desde PostgreSQL.

Última muestra SQL: **2026-11-12 14:43:53 UTC (11:43:53, Buenos Aires)**:

| Control | Resultado |
|---|---|
| Base comprobada | usuarios_dev, destino configurado 127.0.0.1:5434 |
| transaction_read_only de auditoría | on |
| Otras sesiones de esa base | 0 |
| Transacciones preparadas de esa base | 0 |
| Revisión aplicada | 0006_cloud_embeddings |
| Tabla de publicación institucional | Ausente en la comprobación posterior al cierre |
| Backend al terminar | Detenido, sin reinicio |

Las conexiones de auditoría usaron default_transaction_read_only=on,
connect_timeout=5 y statement_timeout=10000 y finalizaron con rollback. Una consulta
auxiliar para rotular la hora falló porque PostgreSQL no reconoció el alias
America/Buenos_Aires; se cerró esa transacción y se obtuvo la marca en UTC en una
nueva lectura satisfactoria. Ese error no modificó datos ni afectó las consultas
previas de sesiones/revisión. No se cambió la zona del servidor.

### Dictamen, vigencia y riesgos pendientes

**VENTANA SEGURA para preparar el paso 5C, con el backend mantenido detenido.**
La evidencia actual no muestra escritores de aplicación ni mecanismos identificados
de relanzamiento automático. No se bloquearon credenciales ni nuevas conexiones:
un arranque manual, una tarea no identificable por su ruta o un cliente externo
que se conecte después puede invalidar la ventana. La inspección no constituye
una prohibición técnica permanente de escritura.

El operador debe mantener cerradas las operaciones de aplicación y no iniciar
backend, ingestas o scripts administrativos durante la ventana. Antes de escribir,
el paso 5C deberá repetir sesiones, bloqueos, transacciones y revisión y revalidar
las restantes precondiciones documentales, el archivo 0007 y el respaldo. Si
aparece cualquier escritor o no puede mantenerse esa coordinación, volver a
VENTANA NO SEGURA y no migrar. Se conservan los riesgos y el procedimiento de
recuperación documentados en 5A, incluidos timeouts y carga compatible posterior.

Se termina este paso y se espera autorización explícita para 5C. No se ejecutó
alembic upgrade ni publicación; no hubo cambios en tablas/registros, roles, ACL,
embeddings, .env, credenciales, modelos o proveedores. No se tocó usuarios_test,
no se detuvo PostgreSQL ni se hicieron llamadas externas o nuevos respaldos.
Único archivo actualizado: docs/jina-cloud-10g-12d.md.

## Paso 5B — revalidación solicitada y conservación de datos

12 de noviembre de 2026. Se mantiene el MISMO Sprint 10G12D.
**VENTANA APTA en la nueva comprobación.** Los PID 19708 y 29416 ya habían sido
identificados y detenidos mediante CTRL_BREAK dirigido en la ejecución anterior
del paso 5B, documentada arriba. No volvieron a aparecer; no se detuvieron nuevos
procesos ni se repitió una señal sobre PID potencialmente reutilizados.

La identificación previa comprobó ruta del ejecutable del entorno del proyecto,
módulo app.presentation.cli.local_server, relación padre/hijo, listener 8000 y dos
conexiones hacia 127.0.0.1:5434. No se obtuvo directamente el directorio de trabajo
del proceso; no se lo presenta como evidencia disponible. Las líneas de comandos
se inspeccionaron localmente sin reproducir valores privados en el informe.

### Evidencia posterior ampliada

La nueva inspección de procesos y mecanismos de inicio encontró:

- Cero procesos Python/backend reconocidos del proyecto y cero listeners en 8000.
- Cero sockets cliente establecidos hacia 5434.
- Cero servicios Windows y tareas programadas vinculados a la ruta del proyecto.
- No se identificó un mecanismo de relanzamiento del backend que requiera modificar
  su configuración. La revisión de contenedores/compose del paso anterior sigue
  documentada; no se detuvo ni reinició ninguno.

Se comparó usuarios_dev con la restauración aislada validada, contenedor
rag-recovery-12d-b9a9204365a8 y su base nueva documentada en el paso 4. Se utilizó
exclusivamente SQL READ ONLY en ambas bases, con zona UTC, connect_timeout=5 en
origen y statement_timeout=30000. El origen se leyó en REPEATABLE READ y terminó
con rollback; psql del destino también recibió default_transaction_read_only=on.
No se ejecutó una nueva restauración ni un respaldo.

**Las 21 tablas public coinciden en conteos y huellas con la restauración validada.**
La comparación ordena los MD5 de cada fila JSONB y compara su agregado completo
en memoria; no imprime filas, huellas de credenciales, contenido o vectores.
Esto incluye propietarios y concesiones almacenados en las tablas, documentos,
fragmentos, índices lógicos cloud e historial. Se verificaron además los conteos
actuales y la validación de restricciones; no se declara una nueva comparación
textual de todas sus definiciones, ya evaluadas en el paso 4.

Última muestra: **2026-11-12 15:02:31 UTC (12:02:31, Buenos Aires)**.

| Comprobación actual | Resultado |
|---|---|
| Destino | usuarios_dev, 127.0.0.1:5434 |
| Revisión Alembic | 0006_cloud_embeddings |
| Tablas iguales a la restauración | 21 de 21 |
| Restricciones public / validadas | 256 / 256 |
| Embeddings cloud Jina | 432, datos iguales por huella |
| Embeddings históricos | 864, datos iguales por huella |
| Otras sesiones de usuarios_dev | 0, excluida la auditoría |
| Transacciones preparadas | 0 |
| Locks pendientes o de escritura/incompatibles de otros PID en esa base | 0 |
| Puerto 8000 | Libre en la inspección de sockets |

No quedan transacciones de aplicación: no quedan sesiones de aplicación. Las
únicas transacciones abiertas durante la comprobación fueron las lecturas de
auditoría, cerradas al terminar. PostgreSQL permaneció funcionando.

### Decisión y parada

**APTA: ventana segura sin escritores de aplicación observados**, manteniendo el
backend detenido. No se instalaron barreras permanentes a nuevas conexiones:
el operador debe evitar iniciar backend, scripts o trabajos administrativos.
Un nuevo arranque manual o un cliente posterior invalidaría esta evidencia;
se requiere revalidación inmediata antes de cualquier escritura en el paso 5C.

Se detiene aquí y se espera la siguiente autorización explícita. No se ejecutó
alembic upgrade, 0007, publicación o revocación. No se modificaron usuarios_test,
tablas, registros, embeddings, índices Jina, roles, .env o credenciales; no hubo
reinicios de backend/frontend, cierres de procesos ajenos ni llamadas a proveedores.
Único archivo actualizado en esta revalidación: docs/jina-cloud-10g-12d.md.

## Paso 7 — aplicación controlada de 0007 en usuarios_dev

12 de noviembre de 2026. Continuación del MISMO Sprint 10G12D.
**MIGRACIÓN 0007 APLICADA Y VALIDADA.** Se detiene la intervención después de
verificarla. No se publica el documento ni se inicia el backend.

### Precondiciones inmediatamente anteriores

Preflight SQL aprobado a las **15:44:13 UTC (12:44:13, Buenos Aires)**, con destino
configurado comprobado exactamente usuarios_dev, 127.0.0.1:5434 y confirmación de
current_database(). Las conexiones de auditoría fueron READ ONLY, REPEATABLE READ,
zona UTC, connect_timeout=5 y statement_timeout=30000; terminaron con rollback
antes de abrir la conexión de migración.

- Revisión única 0006_cloud_embeddings y tabla de publicación ausente.
- Cero sesiones ajenas a la auditoría, transacciones preparadas o locks pendientes/
  de escritura incompatibles de otros PID en la base.
- Backend detenido, puerto 8000 libre, sin servicios ni tareas programadas del
  proyecto identificados que lo relancen. No se modificaron esos mecanismos.
- Documento 8ac0c745-1307-5bb4-9d56-93dfbee0b3b8 existente, no archivado, PRIVATE,
  propietario esperado ADMIN activo y versión activa exacta
  7cb4e79c-747d-574a-8abb-0ebcb2e07636 en LISTA.
- Espacio 1f048209-4b55-31fc-5d34-06985eb3ba0e con puntero activo e ingesta VALIDADA;
  432 embeddings de ese espacio/versión y 864 registros históricos.
- Las 21 tablas public completas coincidieron en conteos y huellas con la base
  restaurada y validada del paso 4, consultada nuevamente en READ ONLY.

El dump conservado fuera del repositorio volvió a comprobarse: 5.173.323 bytes y
SHA-256 58bf705e1e66c9835c321fb3434b212138b52de30d6bc35bb0e7941255121acb,
idéntico al registro del paso 4. Se mantiene su ruta privada documentada arriba.
No se creó otro respaldo ni se repitió la restauración. El éxito previo de
pg_restore y la nueva comparación con ese destino respaldan la recuperabilidad;
no se sustituye esa evidencia por mocks.

El archivo 0007 conservó SHA-256
82b85278bf08430277dea73ae72cb892bfe1e1746fed67f3c3c14f6c240623c8,
igual al revisado en 5A. No se modificaron migraciones ni código productivo.

### Ejecución efectiva

Destino explícito, sin usar head:

```text
alembic -c alembic.ini -x allow-development=true upgrade 0007_institutional_publication
```

Se invocó el punto de entrada CLI oficial alembic.config.main con esos argumentos,
desde backend y con el Python .venv del proyecto. Se utilizó la configuración
normal del proyecto, exigiendo nuevamente host, puerto y base autorizados al
construir el engine. No se utilizó target=test ni se inyectó configuración de otra
base. El env.py verificó además current_database().

El engine fija opciones propias de conexión; por ello se añadió exclusivamente
en memoria un hook do_connect de SQLAlchemy para incorporar lock_timeout=2000 y
statement_timeout=15000 a esas opciones, conservando timezone=UTC. No se cambiaron
.env, roles, configuración persistente o archivos de código. La operación DDL y
la actualización de alembic_version se efectuaron por Alembic, sin SQL manual
alternativo. Alembic retornó normalmente; la incidencia posterior se explica abajo.

### Incidencia posterior, sin reparación ni repetición de migración

El ejecutor completo terminó inicialmente con salida 1 por una aserción del
verificador posterior, DESPUÉS de que Alembic retornara. No se presenta esa salida
como una ejecución integral sin incidencias. Antes de esa aserción ya habían
pasado la nueva revisión, estados documentales/cloud, conteos, comparación de
las 20 tablas anteriores distintas de alembic_version y conservación de metadata
preexistente de columnas, restricciones, relaciones/ACL, índices y esquema public.

Se detuvieron las operaciones de escritura y se diagnosticó exclusivamente con
lecturas. El conteo del verificador esperaba seis entradas en pg_constraint para
la tabla nueva. PostgreSQL 18 registra además sus cuatro NOT NULL como tipo n:
**diez entradas en total**, todas validadas. No había una restricción inesperada
ni faltante. La lectura diagnóstica comprobó exactamente:

- PK (documento_id).
- FK documento_id → rag_documentos(id).
- FK (documento_id, version_id) → rag_versiones(documento_id, id).
- FK publicado_por y revocado_por → usuarios(id).
- CHECK de nulidad simultánea de revocado_at y revocado_por.
- NOT NULL de documento_id, version_id, publicado_por y publicado_at.

También comprobó las seis columnas, sus tipos UUID/timestamptz, nulabilidad y
DEFAULT CURRENT_TIMESTAMP de publicado_at. No se alteraron expectativas para
aceptar una diferencia de esquema: esas cuatro restricciones son las NOT NULL
expresas del DDL revisado. No se ejecutó de nuevo upgrade, downgrade, reparación,
publicación o escritura adicional. La validación final procede del estado real
comprometido y de las lecturas diagnósticas satisfactorias.

### Resultado de integridad y estado final

Última verificación SQL: **15:44:52 UTC (12:44:52, Buenos Aires)**.

| Control posterior | Resultado |
|---|---|
| Revisión única | 0007_institutional_publication |
| Tablas public | 22; solo se agregó rag_publicaciones_institucionales |
| Tabla nueva | Seis columnas y diez entradas de restricción, todas validadas |
| Publicaciones | 0 filas; ninguna publicación automática |
| Tablas previas | 20 de 20 sin cambios de datos; alembic_version cambió como estaba previsto |
| Metadata preexistente | Columnas, restricciones, relaciones/propietarios/ACL, índices y esquema iguales a la línea base anterior |
| Reglamento autorizado | Sigue PRIVATE, mismo propietario y versión activa LISTA |
| Espacio cloud autorizado | Sigue activo y VALIDADA |
| Embeddings Jina / históricos | 432 / 864, huellas de tablas conservadas |
| Otras sesiones de usuarios_dev / transacciones preparadas | 0 / 0 |
| Backend / listener 8000 | Detenido / ausente en inspección posterior |
| usuarios_test | No se abrió conexión ni se ejecutó operación sobre esa base |

La conservación se comprobó comparando conteos y SHA-256 de los agregados ordenados
de MD5 de filas JSONB obtenidos antes/después en memoria, sin imprimir filas,
credenciales, documentos o vectores. Las relaciones nuevas se excluyeron únicamente
al comparar metadata anterior; las restantes debían coincidir exactamente. No se
certifica usuarios_test mediante una lectura nueva de su contenido: su protección
procede del destino restringido y de no haberla conectado ni operado.

**Estado final: MIGRACIÓN 0007 APLICADA Y VALIDADA, con incidencia del verificador
registrada y aclarada por READ ONLY.** No hubo pérdida ni duplicación observada
de datos previos. No se publicaron/revocaron documentos, reiniciaron servicios,
regeneraron embeddings o realizaron llamadas externas. El backend permanece
detenido. No se modificaron claves, .env, modelos o proveedores.

Se espera autorización para publicación y despliegue. Pruebas React en NO-GO
hasta completar el despliegue compatible y autorizar las llamadas que requieran.
Único archivo del proyecto actualizado: docs/jina-cloud-10g-12d.md; la intervención
SQL autorizada se limita a la migración 0007 y su revisión Alembic en usuarios_dev.

## Paso 8 — despliegue y publicación detenidos antes del arranque

12 de noviembre de 2026. Continuación del MISMO Sprint 10G12D.
**DETENIDA con causa precisa: falta JINA_API_KEY en el entorno de este ejecutor.**
La autorización de despliegue/publicación fue recibida; no se pide nuevamente.
La limitación actual es disponer de la configuración privada de ejecución y,
después del arranque satisfactorio, de la sesión real del propietario.

### Precondiciones revalidadas

Se comprobó nuevamente destino exacto usuarios_dev, 127.0.0.1:5434, mediante
configuración del proyecto y lecturas con default_transaction_read_only=on,
connect_timeout=5 y statement_timeout=10000. Las conexiones finalizaron con rollback.

| Control | Resultado |
|---|---|
| Revisión Alembic única | 0007_institutional_publication |
| Backend previo al despliegue | Ningún proceso del módulo local_server identificado |
| Puerto 8000 | Sin listener |
| Documento autorizado | 8ac0c745-1307-5bb4-9d56-93dfbee0b3b8, PRIVATE, no archivado |
| Versión activa exacta | 7cb4e79c-747d-574a-8abb-0ebcb2e07636, LISTA |
| Propietario esperado | Conservado; ADMIN activo |
| Espacio Jina autorizado | Puntero activo e ingesta VALIDADA |
| Embeddings cloud / históricos | 432 / 864 |
| Publicaciones institucionales activas | 0 |
| Respaldo existente | SHA-256 coincide con el registrado en el paso 4 |

El dump sigue en la ubicación privada documentada y su SHA-256 es
58bf705e1e66c9835c321fb3434b212138b52de30d6bc35bb0e7941255121acb.
Su restauración satisfactoria es la verificada anteriormente; no se repitió
pg_dump ni pg_restore. La primera lectura del archivo fue bloqueada por los
permisos del ejecutor sin elevación; la lectura elevada autorizada comprobó el
hash sin cambiar ACL. Una aserción auxiliar inicial comparó siete campos de
estado documental con una expectativa de seis y falló por ese defecto del
verificador; la lectura diagnóstica y la comprobación completa posterior
confirmaron los siete campos previstos. No fue un cambio del documento.

### Impedimento de configuración privada

Se revisó el lanzador local y su composición, sin ejecutarlos. La configuración
selecciona OpenRouter y Jina; la configuración OpenRouter puede cargarse, pero
load_embedding_config obtiene JINA_API_KEY exclusivamente del entorno del proceso,
y en este ejecutor está ausente. No se imprimieron valores de claves.

Aunque el DTO de configuración admite ese valor vacío, JinaEmbeddings.__init__
lo rechaza y el lifespan del backend intenta construirlo al habilitar IA. Por eso
se conoce que el arranque habitual con --enable-llm fallaría aquí. No se ejecutó
para producir un fallo evitable, no se deshabilitó RAG como sustituto y no se
cambió proveedor, modelo, .env o credencial. No se inspeccionó el entorno de otras
terminales ni se intentó recuperar claves desde procesos o archivos privados.

### Publicación y pruebas: estado efectivo

| Actividad | Estado |
|---|---|
| Arranque del backend actualizado | No ejecutado; falta configuración privada en este ejecutor |
| API autenticación/RAG contra instancia desplegada | No comprobada; no hay backend escuchando |
| Sesión real del propietario disponible al ejecutor | No disponible; no se fabricaron ni extrajeron tokens |
| POST de publicación autorizado | No invocado |
| Usuario publicador efectivo | Ninguno |
| Lectura de los tres usuarios mediante RAG | Pendiente, documento aún PRIVATE |
| Denegación de administración, privados e historial/citas mediante sesiones reales | Pendiente |
| Embeddings | Conteos conservados; sin regeneración |
| usuarios_test | Sin conexión ni operación sobre esa base |

No se declara PUBLICACIÓN INSTITUCIONAL VALIDADA por inspección de código o por
pruebas históricas. Tampoco se simula al lector con la identidad ADMIN.

### Continuación necesaria sin divulgar secretos

El operador debe iniciar el backend desde la terminal privada habitual que
conserva las claves válidas, sin copiarlas al chat ni modificar .env. El comando
habitual autorizado sigue siendo, desde backend:

```powershell
$env:PYTHONPATH=(Join-Path (Get-Location) 'src')
& '.\.venv\Scripts\python.exe' -B -m app.presentation.cli.local_server --environment local-development --enable-llm --observe-llm --host 127.0.0.1 --port 8000
```

Antes de ejecutarlo, confirmar que 8000 sigue libre; no iniciar otra instancia.
La observabilidad indicada registra metadatos; no habilitar captura privada de
prompts/claims para este paso. Después de confirmar el arranque, autenticarse
normalmente como el ADMIN propietario en el cliente local. **Se solicita esa
autenticación real, sin enviar contraseña o token al chat.** La mera existencia
de sesiones en PostgreSQL no permite reconstruir su token ni sustituye el login.

Solo tras comprobar el despliegue y disponer de esa sesión podrá enviarse el POST
exacto autorizado y continuar las verificaciones. Las comprobaciones sin proveedor
pueden usar catálogo y lectura estructural autorizada; no se ejecutarán consultas
que consuman Jina/OpenRouter sin una prueba expresamente autorizada. No se ejecutó
ningún POST, revocación ni consulta de conversación en esta intervención.

**Resultado final del paso 8: DETENIDA antes del despliegue y publicación.**
No hubo nuevos procesos iniciados, reinicios, migraciones, escrituras SQL,
publicaciones, cambios de otros documentos, ACL, roles, embeddings o índices.
No se realizaron llamadas externas. Único archivo actualizado:
docs/jina-cloud-10g-12d.md. Se mantiene la parada hasta resolver el entorno privado
de arranque y la autenticación requerida.

## Validación previa a publicación — servicios ya iniciados por el operador

12 de noviembre de 2026. Continuación del MISMO Sprint 10G12D.
**NO APTO PARA PUBLICAR: no se pudo verificar desde Codex la identidad de la sesión
autenticada del navegador.** Se detiene antes de cualquier publicación, conforme
al requisito expreso. Esta sección sustituye el estado anterior de backend detenido.

### Servicios y evidencia Jina sin secretos

| Lectura HTTP local | Resultado |
|---|---|
| 127.0.0.1:8000/openapi.json | 200; contrato JSON legible |
| Rutas declaradas de autenticación, catálogo y publicación | Presentes en OpenAPI |
| 127.0.0.1:5173/ | 200; HTML recibido |
| GET /api/v1/auth/me sin credencial en el cliente de auditoría | 401 |
| GET /api/v1/ia/documentos sin credencial en ese cliente | 401 |

El listener 127.0.0.1:8000 corresponde al PID 36768, Python, con ruta del proyecto,
módulo app.presentation.cli.local_server y banderas --enable-llm y --observe-llm.
Se inspeccionaron únicamente metadatos y presencia de banderas, sin mostrar la
línea completa ni leer el entorno del proceso. No se inició otra instancia.

La composición de bootstrap exige proveedor OpenRouter y embeddings Jina al
habilitar IA operativa; construye JinaEmbeddings antes de completar el lifespan.
Ese constructor rechaza una clave vacía. El backend en servicio con ese lanzador
y esas banderas aporta evidencia indirecta de composición local compatible y
clave no vacía en SU proceso. No se afirma haber inspeccionado su memoria ni
verificado directamente su app.state. La falta de clave en el ejecutor documentada
antes no demuestra que falte en el backend iniciado por el operador.

**Límite:** el constructor no valida la clave contra el proveedor. No se probó su
validez remota, cuota, disponibilidad ni una llamada real de embeddings. No se
realizaron llamadas Jina/OpenRouter ni se regeneraron vectores para demostrarlo.
Un 200 de OpenAPI tampoco prueba por sí solo una consulta RAG autenticada o la
compatibilidad SQL de todo su recorrido.

### Estado real READ ONLY

Última muestra SQL: **2026-11-12 18:53:43 UTC (15:53:43, Buenos Aires)**.
Se exigió configuración usuarios_dev, 127.0.0.1:5434; current_database() confirmó
usuarios_dev y transaction_read_only=on. connect_timeout=5,
statement_timeout=10000; cierre con rollback. No se conectó usuarios_test.

| Precondición | Resultado |
|---|---|
| Alembic | 0007_institutional_publication |
| Documento | 8ac0c745-1307-5bb4-9d56-93dfbee0b3b8, existente, no archivado |
| Versión activa exacta | 7cb4e79c-747d-574a-8abb-0ebcb2e07636 |
| Estado / visibilidad | LISTA / PRIVATE |
| Propietario | Coincide con 32eabde4-7d17-4029-a47a-60e2e38faf05; ADMIN activo |
| Espacio | 1f048209-4b55-31fc-5d34-06985eb3ba0e, puntero activo e ingesta VALIDADA |
| Embeddings de ese espacio/versión | 432 |
| Embeddings históricos totales | 864 |
| Publicaciones institucionales activas, globales | 0 |

Se comprobaron estados y conteos; no se presenta esta intervención como una nueva
comparación íntegra de huellas o restauración del respaldo. No se imprimieron
filas privadas, documentos, vectores, claves o tokens.

### Identidad autenticada: límite que impide aprobar

La condición ADMIN activo y propietario en SQL está confirmada para el UUID
esperado, pero **no demuestra que la sesión actualmente abierta en el navegador
pertenezca a ese usuario**. El cliente HTTP del ejecutor no comparte la sesión del
frontend: su GET /auth/me respondió 401. Ese resultado no significa que el usuario
esté desconectado en su navegador.

El frontend conserva el token en una referencia React en memoria; no hay una
sesión autenticada del navegador disponible en las herramientas utilizadas para
emitir /auth/me dentro de ese mismo contexto. No se extrajo memoria del navegador,
no se leyeron cookies/tokens ni se solicitaron contraseñas o credenciales. Tampoco
se reconstruyó un token a partir de sesiones SQL ni se sustituyó el principal.

La continuación requiere evidencia de /api/v1/auth/me obtenida dentro de la sesión
real y que compruebe el UUID esperado, rol ADMIN y acceso normal, sin compartir el
token ni datos personales. La mera inspección del registro del propietario no
sustituye ese control. Se respeta la instrucción de detenerse al no poder verificar
esta identidad desde Codex; no se envió ningún POST de publicación.

### Resultado y alcance

**NO APTO PARA PUBLICAR.** Servicios disponibles y precondiciones SQL satisfechas;
identidad de sesión pendiente y capacidad remota Jina no certificada. No se declara
validación funcional RAG ni publicación institucional por estas lecturas.

No hubo migraciones, publicación/revocación, cambios de ACL, regeneración de
embeddings, reinicios, detención de servicios ni operaciones de escritura en la
base. No se modificó usuarios_test ni se hicieron llamadas a proveedores.
Único archivo actualizado: docs/jina-cloud-10g-12d.md. Se finaliza la intervención.

## Identidad del ADMIN propietario — mecanismo inspeccionado

12 de noviembre de 2026. MISMO Sprint 10G12D. Sin publicación.

Existe GET /api/v1/auth/me. Verifica el bearer firmado y la sesión vigente, usuario
activo y contexto de credencial; devuelve el perfil propio con id, rol, activo y
debe_cambiar_password=False para acceso normal. Un contexto restringido devuelve
solo id/debe_cambiar_password=True y no sirve para aprobar publicación.

En frontend, AuthProvider mantiene el token exclusivamente en una referencia en
memoria y refreshProfile llama a ese endpoint con la sesión de la pestaña.
La pantalla /mi-perfil ofrece el botón «Actualizar perfil». Muestra rol y estado,
pero NO muestra el UUID: verla como ADMIN no demuestra por sí sola el id esperado.

El ejecutor no tiene acceso autorizado al contexto autenticado de esa pestaña.
No se extrajo ni solicitó su token, no se generó otra sesión y no se confundió
el cliente HTTP de Codex con el del navegador. Por tanto, identidad de sesión y
rol de esa sesión siguen NO VERIFICADOS desde Codex.

Una lectura nueva, forzada READ ONLY y finalizada con rollback, confirmó que el
documento autorizado pertenece al UUID 32eabde4-7d17-4029-a47a-60e2e38faf05 y que
ese propietario está activo y tiene rol ADMIN. Esto verifica la propiedad del
registro, no la identidad del usuario actualmente conectado en la pestaña.

Procedimiento seguro disponible para el operador, sin cambiar código:

1. En la pestaña autenticada abrir «Mi perfil» y las herramientas del navegador,
   panel Red/Network. No recargar la aplicación: el token vive en memoria.
2. Pulsar «Actualizar perfil» y seleccionar la nueva petición GET terminada en
   /api/v1/auth/me, con estado 200. Examinar únicamente su pestaña Response/Respuesta.
3. Comprobar localmente id=32eabde4-7d17-4029-a47a-60e2e38faf05, rol=ADMIN,
   activo=true y debe_cambiar_password=false. Si hay 401/error o campos distintos,
   detenerse; los datos anteriores de pantalla pueden estar conservados en caché
   de estado si la actualización falla.
4. No abrir/copiar cabeceras Authorization, no exportar HAR ni usar «Copy as cURL».
   No compartir la respuesta completa, nombres/email o capturas con datos privados.
   Comunicar solamente si esos cuatro controles coinciden y el estado HTTP.

Resultado del ejecutor: identidad autenticada NO VERIFICADA; rol ADMIN de la
sesión NO VERIFICADO; propiedad del documento por el UUID esperado VERIFICADA;
publicación institucional NO EJECUTADA. No se modificaron datos, permisos,
credenciales o servicios, no se conectó usuarios_test ni se generaron embeddings.
Solo se actualiza este informe; se detiene antes de cualquier publicación.

## QA funcional ADMIN y USUARIO — pruebas detenidas por sesiones no disponibles

12 de noviembre de 2026. MISMO Sprint 10G12D.
**NO APTO para avanzar a las pruebas de publicación institucional.** Falta ejecutar
las pruebas reales con ambas identidades; no se detectó en esta intervención un
fallo funcional del RAG ni se presume que funciona por los mocks anteriores.

### Alcance ejecutado y límite de autorización

EJECUTADO: revisión del recorrido HTTP y persistencia para preparar las pruebas.
NO EJECUTADO: login, consultas RAG, lectura HTTP autenticada de conversaciones,
pruebas cruzadas de acceso o llamadas a Jina/OpenRouter.

Las herramientas disponibles no comparten las sesiones reales del navegador.
La intervención anterior identificó /api/v1/auth/me, pero no verificó la sesión
ADMIN desde ese contexto. Tampoco hay una sesión USUARIO autorizada disponible.
No se solicitaron credenciales, se extrajeron tokens/cookies, se reutilizaron
sesiones ajenas ni se construyeron principales para simular autenticación HTTP.
Conforme al pedido, se detienen las pruebas A, B y C antes de sus operaciones.

Además, Conversations.turn reserva la solicitud y guarda mensajes al completar.
Enviar preguntas nuevas mediante el panel conversacional escribe en la base,
aunque la respuesta sea SIN_EVIDENCIA. La prohibición actual de modificar la base
impide ejecutar esos nuevos turnos. Existe POST /api/v1/ia/respuestas, que llama
al agente sin reserve/complete del repositorio conversacional; permitiría evaluar
respuestas sin crear conversaciones, pero requiere una invocación autorizada desde
cada sesión real y revisar cualquier efecto adicional del recorrido. No se usó
para eludir la falta de sesiones ni se declara probado su carácter sin escritura
mediante esta mera inspección. No se creó un formulario ni se cambió código.

### Matriz de resultados

| Prueba | ADMIN | USUARIO | Resultado |
|---|---|---|---|
| Autenticación | NO EJECUTADA: sesión real no disponible | NO EJECUTADA: sesión real no disponible | No se verificó identidad/rol de las sesiones |
| Artículo 28 | NO EJECUTADA | NO EJECUTADA | Sin respuesta ni recuperación real registrada |
| Coordinaciones | NO EJECUTADA | NO EJECUTADA | Sin respuesta ni recuperación real registrada |
| Artículo 52 | NO EJECUTADA | NO EJECUTADA | Sin respuesta ni recuperación real registrada |
| Control de acceso | NO EJECUTADA por HTTP autenticado | NO EJECUTADA por HTTP autenticado | No se certifica denegación o acceso real por estas pruebas |
| Aislamiento | NO EJECUTADA entre sesiones reales | NO EJECUTADA entre sesiones reales | No se certifica aislamiento E2E en esta intervención |

No hay respuestas nuevas para transcribir o resumir. Los resultados SQL y de
servicios anteriores son evidencia previa, no sustituyen ninguna celda de esta
matriz. No se reconsultó la base para presentar datos anteriores como actuales.

### Intervención manual necesaria y criterios de aceptación

1. Mantener dos contextos de navegador separados (perfiles o ventanas aisladas),
   cada uno con su propia sesión. Desde «Mi perfil» → «Actualizar perfil», revisar
   únicamente la respuesta /auth/me: ADMIN propietario con id
   32eabde4-7d17-4029-a47a-60e2e38faf05 y la segunda cuenta con rol USUARIO;
   ambos activos y debe_cambiar_password=false. No exportar HAR, copiar cabeceras
   ni compartir respuestas completas, emails o secretos.
2. Antes de enviar preguntas nuevas por el panel, resolver expresamente la
   restricción de escritura: autorizar solo la persistencia normal de los turnos
   QA, o acordar una prueba sin persistencia usando el endpoint existente desde
   cada sesión real. Esta intervención no presupone esa autorización.
3. Con el alcance permitido resuelto, realizar una sola vez por cuenta las tres
   preguntas exactas solicitadas, manteniendo PRIVATE y cero publicaciones activas.
   No sustituir «según el artículo 28» por una consulta distinta para evitar su
   recorrido por número de artículo. El artículo 52 integral tiene un límite de
   contexto documentado: abstenerse por presupuesto puede ser correcto y debe
   distinguirse de falta de permiso o ausencia del artículo.
4. Para ADMIN, comprobar recuperación de la versión autorizada, páginas/artículos,
   cobertura completa o parcial explícita y soporte de cada afirmación. Una cita
   por sí sola no demuestra ausencia de invenciones. Registrar estado, estrategia,
   fuentes/páginas, request_id seguro y valoración local del texto; no copiar
   contenido privado al informe sin un alcance específico para ello.
5. Para USUARIO sin concesión individual, el documento no debe aparecer en catálogo
   ni aportar fragmentos/citas. Una respuesta GENERATED/LLM_DIRECTO sin fuentes
   no demuestra recuperación autorizada del Reglamento ni debe aceptarse como
   respuesta normativa fundamentada. Si afirma contenido privado o cita el
   documento, detenerse y analizar evidencia antes de atribuir automáticamente
   el origen a retrieval o a memoria del ADMIN.
6. Para aislamiento, comprobar con lecturas que cada catálogo/historial solo muestra
   recursos autorizados. Si hay conversaciones existentes conocidas de ambas
   cuentas, solicitar su lectura cruzada con la sesión propia debe ser denegado,
   sin revelar contenido. No crear conversaciones nuevas mientras rija la
   prohibición de escritura. Compartir un identificador de prueba no autoriza
   compartir tokens ni datos del historial.

Comunicar únicamente resultados saneados de esos controles; no credenciales.
La identidad de cada sesión y la ausencia de ACL individual deben acreditarse,
no inferirse de un nombre visible o del rol guardado en un registro distinto.

### Decisión final

**NO APTO para avanzar a pruebas de publicación institucional**, por pruebas reales
pendientes y sesiones no disponibles, además del alcance de persistencia por
resolver. Este dictamen no declara que el RAG haya fallado: declara que no existe
la evidencia funcional requerida para aprobarlo.

Publicación institucional NO EJECUTADA. No hubo modificaciones de la base, ACL,
permisos, código, migraciones o servicios; no se tocó usuarios_test ni se generaron
embeddings. Único archivo actualizado: docs/jina-cloud-10g-12d.md. Se detiene aquí.

## Diagnóstico del SIN_EVIDENCIA reportado desde React

12 de noviembre de 2026. MISMO Sprint 10G12D. Solo inspección y SQL READ ONLY.
Pregunta reportada: «¿Cuáles son los requisitos para acceder a concursos de
Coordinaciones de Carreras?». Los logs aportados indican rules/documentary y
final RAG/SIN_EVIDENCIA; no incluyen identidad ni correlación completa del turno.

### Etapa exacta identificada por el mensaje

El texto «No hay evidencia documental autorizada disponible para esta consulta
institucional.» se emite en Agent._execute, application/agent/agent.py, en la
rama que termina sin document_id y sin necesidad de aclaración. Es anterior a
skills.load('academic-rag'), stage=rag y skill.execute del servicio documental.

En el recorrido AUTO sin planificación semántica, el agente consulta
CloudPostgresRAG.list_documents(principal). El router selecciona automáticamente
un documento únicamente si el catálogo autorizado contiene exactamente uno.
Un catálogo vacío deja document_id=None y produce ese mensaje; varios documentos
sin selección producen ACLARACION. El acceso normal se revalida antes de devolver
la abstención. Un runtime no compuesto genera error técnico, no ese mensaje.

**Demostrado en el código inspeccionado:** esa respuesta señala ausencia de
selección documental, no candidatos vectoriales descartados. En esa ejecución de
la rama no se llegó a embeddings de consulta, search/recover, pertinencia, expansión
de requisitos ni validación de claims. RAG como etiqueta de estrategia no prueba
que hubiera retrieval. Los logs genéricos sin el texto por sí solos no permitirían
localizarlo; aquí se utiliza el mensaje exacto aportado por el usuario.

Sin request_id/payload saneado no se certifican el modo, document_id recibido ni
la correspondencia con una ejecución concreta del servidor. Una respuesta
recuperada del historial/replay también puede mostrar un resultado anterior.
La ubicación identificada corresponde a la generación original de ese texto en
el código actual, no demuestra cuándo se generó el resultado mostrado.

### Identidad: recorrido y límite de evidencia

React usa createConversationsApi.turn y POST
/api/v1/ia/conversaciones/{UUID}/mensajes, con prompt, modo, solicitud_id y documento
opcional. El cliente protegido agrega Authorization desde la referencia privada
al token del AuthProvider; no envía usuario_id o rol como autoridad. fetch usa
credentials=omit: no depende de cookies implícitas. La misma sesión autentica las
lecturas de catálogo y perfil. Un envío directo puede usar /api/v1/ia/respuestas,
que también exige get_current_user.

FastAPI obtiene Principal con get_current_user → AuthService.authenticate,
verificando token, sesión, usuario activo y acceso normal. Conversations revalida
ese Principal y la propiedad del historial y lo pasa a agent.execute; el catálogo
usa principal.usuario_id como actor. No se encontró sustitución por ADMIN ni un
usuario hardcodeado en ese recorrido. El análisis de código no certifica los
valores reales del turno del navegador.

Si el turno realmente alcanzó esa rama mediante HTTP autenticado, el recorrido
normal ya validó una sesión; una credencial ausente/inválida produciría 401 antes
del agente. Eso permite distinguir sesión válida de sesión del propietario: una
cuenta válida USUARIO puede producir exactamente esta abstención. El 401 anterior
del cliente de auditoría no demuestra un 401 del navegador ni un fallo de
propagación. **Identidad de la sesión del turno: NO VERIFICADA.**

### Permiso efectivo comprobado en el estado actual

Se verificó destino usuarios_dev, 127.0.0.1:5434, con conexión forzada a READ ONLY,
connect_timeout=5, statement_timeout=10000 y rollback final. Se evaluó por SQL la
misma expresión ACL central y el filtro de catálogo cloud, parametrizados con el
UUID esperado. Esto es evaluación de permisos de un registro conocido, NO una
sesión HTTP fabricada ni una ejecución del agente con identidad suplantada.

| Comprobación READ ONLY | Resultado |
|---|---|
| Espacio derivado de la configuración local | Coincide con 1f048209-4b55-31fc-5d34-06985eb3ba0e |
| Catálogo cloud del UUID propietario esperado | 1 documento |
| Reglamento autorizado en ese catálogo | Sí |
| Documento | 8ac0c745-1307-5bb4-9d56-93dfbee0b3b8, PRIVATE |
| Versión activa exacta | Coincide con 7cb4e79c-747d-574a-8abb-0ebcb2e07636; LISTA |
| Índice del espacio configurado | Satisface puntero activo e ingesta VALIDADA del catálogo |
| Publicaciones activas del documento | 0 |
| Concesiones individuales puede_leer del documento | 0 |

La ACL permite al propietario activo leer PRIVATE sin publicación. La publicación
institucional es una rama alternativa, no requisito para el dueño. Para otro
usuario sin concesión, PRIVATE y cero publicaciones justifican la exclusión.
El catálogo cloud comprueba versión LISTA e índice activo/VALIDADA en SQL; errores
SQL se propagan como técnicos, no se convierten en catálogo vacío. En el estado
leído no se reprodujo exclusión del propietario por esos filtros.

### Causa demostrada y asuntos pendientes

Demostrado: el mensaje se genera por falta de selección documental antes de
retrieval; el propietario esperado sí tiene permiso efectivo en el estado actual.
No está demostrada la identidad que tenía el turno React ni la causa específica
de que no seleccionara documento. Hipótesis por comprobar: sesión de otro usuario,
resultado antiguo/replay, payload/modo distinto, configuración del proceso distinta
de la inspeccionada localmente o código cargado diferente. No se inspeccionó su
entorno privado. No se atribuye el fallo al ranking, al umbral, a ausencia de una
lista de requisitos, a Jina o a all_claims_rejected: no explican esta rama temprana.

Corrección mínima recomendada, SIN aplicar: verificar primero la sesión y usar
la del propietario si la prueba pretende acceso administrativo a su PRIVATE.
Si la sesión resulta USUARIO sin concesión, la abstención es el comportamiento
correcto; no corresponde corregirla relajando ACL. Si /me confirma al propietario
y su catálogo real omite el Reglamento, correlacionar esa petición con el proceso,
configuración de espacio y payload del turno antes de proponer un parche. No hay
un defecto productivo demostrado que justifique cambiar código o visibilidad.

### Repetición segura desde React, sin ejecutarla aquí

1. En la misma pestaña, «Mi perfil» → «Actualizar perfil»: revisar solo la respuesta
   200 de /api/v1/auth/me. Comparar id esperado, ADMIN, activo=true y
   debe_cambiar_password=false. No compartir cabeceras, tokens, HAR o perfil completo.
2. Revisar la respuesta del GET /api/v1/ia/documentos de ESA sesión y comprobar si
   contiene el documento autorizado. Es una lectura sin embeddings. Si no hay un
   mecanismo autenticado accesible para obtenerla, detenerse; no copiar un token
   a la consola o al cliente de Codex para forzarla.
3. Para el turno ya realizado, comprobar localmente solicitud_id, modo y presencia
   de documento_id en su payload, estado HTTP y si el resultado era replay/historial.
   Compartir solo metadata saneada y los booleanos anteriores. No reenviar el turno
   como diagnóstico automático.
4. Una repetición nueva puede persistir mensajes y llamar a Jina/OpenRouter. Requiere
   autorizar esos efectos antes de ejecutarla bajo estas restricciones. Si se
   autoriza después, enviar una sola vez y correlacionar trace/request_id: distinguir
   final sin stage=rag de recuperación efectiva, pertinencia y soporte posteriores.

Se detiene el diagnóstico al requerir la sesión no disponible. No hubo consultas
reales a proveedores, publicación, cambios de ACL/código/base, migraciones,
reinicios o nuevos turnos. No se accedió a usuarios_test ni se imprimieron secretos
ni contenido privado. Único archivo actualizado: docs/jina-cloud-10g-12d.md.

## Publicación, ACL, sesiones y timeouts — diagnóstico READ ONLY consolidado

12 de noviembre de 2026. MISMO Sprint 10G12D. Sin modificaciones operativas.
**Estado de publicación institucional: INACTIVA.** La migración habilitó el esquema;
no compartió automáticamente el Reglamento.

### Evidencia actual de base y permisos

SELECT ejecutados exclusivamente contra usuarios_dev, 127.0.0.1:5434, con
conexión forzada READ ONLY, connect_timeout=5, statement_timeout=10000 y rollback.
Marca de consulta: **21:39:08 UTC (18:39:08, Buenos Aires)**.

| Control | Resultado |
|---|---|
| Alembic | 0007_institutional_publication |
| Registros de publicación del documento autorizado | 0 |
| Registros no revocados del documento | 0 |
| Publicación no revocada de la versión exacta | 0 |
| Documento | PRIVATE, no archivado |
| Versión activa | Exacta autorizada, LISTA |
| Concesiones individuales puede_leer | 0 |
| ADMIN propietario activo | 1; expresión ACL concede lectura |
| USUARIO activos distintos del dueño | 3; expresión ACL excluye a los tres |
| Versión e índice para ambos grupos | LISTA y puntero/ingesta del espacio autorizado VALIDADA |

Se evaluó la expresión ACL productiva parametrizada en SQL, agrupando únicamente
rol y condición de propietario; no se imprimieron identidades de lectores ni se
fabricaron sesiones. La exclusión de los USUARIO no se debe en esta consulta a
versión o índice inválidos. No se ejecutó el agente con el principal del ADMIN
para simular una cuenta común.

La publicación vigente requeriría documento AUTHENTICATED, fila no revocada del
mismo documento y versión activa, usuario activo, documento no archivado, versión
LISTA y espacio configurado activo/VALIDADA. Cumplidas conjuntamente, la rama
institucional concede lectura a un USUARIO sin ACL individual. Una fila sola
sobre PRIVATE no basta; una publicación de otra versión tampoco. Publicar no
concede ingestión, validación, activación o administración. La operación oficial
actualiza registro y visibilidad transaccionalmente; NO se ejecutó aquí.

**Causa demostrada de la diferencia de permisos actual:** el propietario accede
por propiedad; los otros tres usuarios no tienen ninguna rama de lectura válida.
Eso es compatible con ADMIN fundamentado y USUARIO SIN_EVIDENCIA reportados. No
verifica retrospectivamente qué identidades enviaron cada turno real.

### Catálogo, selección y sesión en el frontend

CloudPostgresRAG.list_documents usa la ACL común, versión activa LISTA y EXISTS
del espacio activo/VALIDADA. Un usuario sin lectura no recibe el documento en
catálogo. AgentRouter.decide selecciona un único documento autorizado si no se
indicó uno; con catálogo vacío termina sin selección. El mensaje exacto analizado
en la sección anterior aparece antes de embeddings/search/relevancia. No prueba
que los 432 vectores falten o que no existan requisitos pertinentes.

Hay dos recorridos de interfaz que no deben confundirse:

- ConsultaIAPage consulta /ia/documentos al entrar en AUTO/RAG, valida el catálogo
  y conserva como selección inicial su primer id si existe. Catálogo vacío deja
  selección vacía; el selector muestra «Sin documentos disponibles».
- ConversationPanel llama api.turn en AUTO con documento vacío. El backend realiza
  la selección desde el catálogo de la identidad autenticada; no hereda el selector
  documental del otro formulario.

AuthProvider conserva el token en memoria y utiliza el mismo cliente protegido
para /auth/me, catálogo y turnos. No envía un rol confiable desde React ni cookies
implícitas; Authorization se agrega internamente. /auth/me se consulta al login,
al actualizar perfil y al recuperar foco/visibilidad. La expiración local o un
401 puede invalidar la sesión; una petición independiente puede recibirlo aunque
un turno previo haya completado SIN_EVIDENCIA con credencial válida.

Por tanto, **401 y SIN_EVIDENCIA no se atribuyen al mismo turno sin correlación**:
comparar endpoint, hora, estado y request/solicitud_id saneado. Un 401 local de
/auth/me o catálogo no acredita que el POST conversacional haya recibido 401.
Una autenticación ausente/inválida en el POST se rechaza antes de ejecutar el
agente. Los datos disponibles no correlacionan ningún 401 concreto.

### Backend en ejecución y proxy

El listener 8000 sigue asociado a Python PID 36768 con ruta del proyecto y módulo
local_server. Su inicio fue **18:51:56 UTC**, posterior a la última modificación
de postgres.py (11:54:04 UTC), cloud_postgres.py (11:55:14 UTC) y respuestas.py
(11:49:58 UTC). OpenAPI actual devuelve 200 y declara POST/DELETE de publicación
con requisito de autenticación. Esto confirma presencia del contrato de publicación
en la aplicación servida, sin invocar ninguno de esos métodos.

Son evidencias compatibles con el backend actualizado. **No prueban igualdad
criptográfica de todo el código cargado con los archivos actuales**: no hay una
huella de despliegue runtime verificada y no se inspeccionó memoria del proceso.
No se certifica la implementación interna de la ACL solo por OpenAPI.

Vite PID 4576 usa explícitamente vite.development.config.ts. Ese archivo dirige
/api a 127.0.0.1:8000; el vite.config.ts aislado apunta a 8001 y no debe confundirse
con la configuración usada. No se cambió el proxy. El GET /openapi.json directo
a 5173 devolvió contenido no JSON, esperable en una ruta de SPA fuera de /api;
no demuestra fallo del proxy autenticado.

### Timeouts de embeddings cercanos a tres segundos

JinaEmbeddings crea httpx.Timeout(config.timeout, connect=3), transporte sin
reintentos, trust_env=False y follow_redirects=False. Existe además un límite
asyncio.timeout(config.timeout) alrededor de la llamada. El valor general se
carga de EMBEDDING_TIMEOUT_SECONDS (por defecto 30); no se inspeccionó el entorno
privado del proceso para certificar su valor efectivo actual.

Un fallo cercano a tres segundos es **compatible, no demostración**, con el
límite de establecimiento de conexión: DNS/resolución según el transporte,
conexión TCP o negociación TLS, problemas de ruta/salida, filtrado de firewall
o indisponibilidad del destino. trust_env=False significa que un proxy de red
requerido no se adopta automáticamente de variables del entorno. Son hipótesis,
no diagnósticos de red ejecutados. Un read timeout, un límite total configurado
cerca de tres segundos o un timeout HTTP upstream también requieren considerar
la etapa y excepción reales; la duración sola no distingue esas situaciones.

El adaptador convierte TimeoutError/httpx.TimeoutException en IATiempoAgotado y
HTTP 408/504 en la misma familia. HTTP upstream 401/402/403/429 se clasifica como
IANoDisponible: no equivale automáticamente a un 401 de autenticación del navegador.
No hay en la evidencia aportada subtipo ConnectTimeout/ReadTimeout ni diagnóstico
DNS/TLS correlacionado. No se llamó a Jina ni se modificaron parámetros para
adivinar la causa. El SIN_EVIDENCIA temprano sin selección no ejecuta ese cliente:
no se explica esa abstención por un timeout de otro recorrido.

### Comprobación exacta en el navegador, sin compartir secretos

1. En cada contexto de navegador, mantener su sesión propia. Abrir Red/Network y
   «Mi perfil» → «Actualizar perfil», sin recargar la aplicación que guarda el token
   en memoria. En la nueva respuesta 200 de /api/v1/auth/me comprobar localmente
   id, rol, activo=true y debe_cambiar_password=false. Para el dueño comparar el
   UUID esperado; para el lector confirmar USUARIO. No copiar headers ni exportar HAR.
2. En esa misma pestaña abrir el formulario de consulta y seleccionar AUTO/RAG para
   provocar el GET /api/v1/ia/documentos; revisar únicamente Response y estado HTTP.
   Si ya está cargado, navegar por la interfaz fuera y volver al formulario para
   generar su lectura, sin pulsar Enviar ni crear un turno. Si la sesión expira,
   detenerse y usar el login normal, sin transferir tokens entre clientes.
3. Con el estado PRIVATE actual, el dueño debe ver el UUID autorizado y el usuario
   sin ACL no debe verlo. Catálogo 200 vacío difiere de 401, 403 o error técnico.
   Comprobar por separado si se usa ConversationPanel (AUTO sin documento enviado)
   o el formulario con selector; no asumir que comparten selección.
4. Para turnos ya ejecutados, comparar ruta, hora, solicitud_id y modo del POST
   usando solo metadata saneada. No repetir consultas que consuman proveedores
   bajo esta autorización. Comunicar coincidencias y estados, no perfiles completos,
   prompts privados, claves o cabeceras de autenticación.

La identidad de las sesiones reales sigue **NO VERIFICADA desde Codex**. Se detiene
cualquier comprobación dependiente de esa autenticación; no se suplanta al lector.

### Siguiente acción mínima recomendada, NO ejecutada

Confirmar /me y catálogo por separado en ambas sesiones. Para el lector sin ACL,
la abstención actual es correcta. Si el objetivo funcional sigue siendo compartir
con todos los usuarios activos, la acción mínima posterior es una publicación
explícita de la versión exacta por el endpoint oficial y la sesión real del ADMIN
propietario, después de validar precondiciones y contar con autorización operativa
vigente para ese acto. No corresponde relajar ACL, cambiar solo visibilidad,
duplicar vectores o alterar el umbral para resolver una falta de publicación.
El timeout debe analizarse separadamente con correlación y evidencia de su etapa.

No se ejecutaron INSERT/UPDATE/DELETE, migraciones, publicación/revocación,
cambios de permisos/código/configuración, reinicios ni llamadas externas. No se
accedió a usuarios_test ni se imprimieron secretos. Único archivo actualizado:
docs/jina-cloud-10g-12d.md. Se finaliza el diagnóstico y se espera autorización
para cualquier modificación.


## Publicacion institucional controlada: detenida en autenticacion

12 de noviembre de 2026. MISMO Sprint 10G12D.
**PUBLICACION DETENIDA.** Se recibio autorizacion para una unica publicacion por
el endpoint oficial, condicionada a prevalidacion y sesion real del propietario.
No se solicita otra autorizacion para ese acto; falta el contexto autenticado.

### Prevalidacion READ ONLY

Muestra SQL: **21:47:04 UTC (18:47:04, Buenos Aires)**. Destino confirmado
usuarios_dev, 127.0.0.1:5434, transaction_read_only=on, connect_timeout=5,
statement_timeout=10000. Solo SELECT, cierre con rollback.

| Condicion | Resultado |
|---|---|
| Alembic | 0007_institutional_publication, unica fila |
| Documento | 8ac0c745-1307-5bb4-9d56-93dfbee0b3b8; PRIVATE, no archivado |
| Version activa | 7cb4e79c-747d-574a-8abb-0ebcb2e07636; LISTA |
| Propietario | 32eabde4-7d17-4029-a47a-60e2e38faf05; ADMIN activo |
| Espacio | 1f048209-4b55-31fc-5d34-06985eb3ba0e; activo e ingesta VALIDADA |
| Publicaciones del documento, totales / no revocadas | 0 / 0 |
| Backend | OpenAPI HTTP 200; POST de publicacion con seguridad declarada |
| Respaldo previamente validado | Disponible; 5.173.323 bytes y hash coincidente |

Se verifico el mismo usuarios_dev.dump del paso 4, en la carpeta privada
10g12d-0007-4f42adbf6ad14adb8d5d4c1fcc6873c7, sin generar otro respaldo.
SHA-256: 58bf705e1e66c9835c321fb3434b212138b52de30d6bc35bb0e7941255121acb.
La lectura elevada autorizada no cambio permisos; no se repitio la restauracion.

El verificador inicial de OpenAPI busco {documento_id} y produjo KeyError: el
contrato usa {document}. La lectura posterior confirmo el POST autenticado en
/api/v1/ia/documentos/{document}/publicacion. No fue un fallo del endpoint ni se
invoco el POST para comprobarlo. Una preparacion inicial del informe fallo antes
de escribir por busqueda textual; se corrigio sin cambios operativos.

### Autenticacion: condicion pendiente

No existe un contexto de sesion real del navegador utilizable por este ejecutor.
No se verifico /auth/me con la sesion del propietario. Su rol ADMIN en SQL no
prueba la identidad del solicitante HTTP. No se extrajeron tokens, cookies o
memoria del navegador ni se fabricaron sesiones.

Se solicita al operador iniciar sesion normalmente con el ADMIN propietario.
En esa misma pesta?a, abrir Red/Network y Mi perfil, pulsar Actualizar perfil y
revisar solamente la nueva respuesta de GET /api/v1/auth/me: HTTP 200,
id=32eabde4-7d17-4029-a47a-60e2e38faf05, rol=ADMIN, activo=true y
debe_cambiar_password=false. No recargar la aplicacion que conserva el token en
memoria. Comunicar solo coincidencia de controles y estado HTTP, sin perfiles
completos, cabeceras, JWT, contrase?as, HAR ni Copy as cURL.

El login del operador no conecta automaticamente su sesion con este ejecutor.
Continuar requiere un contexto autorizado capaz de verificar /auth/me y enviar
el POST con ESA misma sesion real; una confirmacion verbal no suministra dicha
capacidad. No se solicita transferir tokens ni contrase?as.

### Estado real y privacidad

Publicacion institucional **INACTIVA**. No se intento el POST; no hay actor
publicador ni resultado ambiguo que verificar. Etapas 3 y 4 pendientes. El ultimo
diagnostico ACL excluia a los tres USUARIO activos sin concesion individual y
permitia al propietario; no se declara lectura institucional concedida ni acceso
E2E probado en navegador.

No hubo escrituras sobre usuarios_dev, cambios de visibilidad, ACL individuales,
otros documentos, conversaciones o embeddings. No se recalcularon huellas
vectoriales ni se presenta validacion posterior a una publicacion inexistente.
No se conecto usuarios_test; su contenido no se certifica mediante lectura nueva.
No hubo migraciones, cambios de codigo/configuracion, reinicios, revocaciones ni
llamadas a Jina/OpenRouter. Solo se actualizo docs/jina-cloud-10g-12d.md.

Se detiene antes del POST por la condicion expresa de autenticacion. Revalidar
precondiciones al disponer del contexto autenticado utilizable. No se avanza con
pruebas E2E React/RAG.


## Revalidacion de publicacion controlada: 20:54, 12 de noviembre

**PUBLICACION DETENIDA en etapa 2.** La autorizacion del pedido reiterado permite
un unico POST oficial para el documento y version exactos, exclusivamente con
sesion real vigente del ADMIN propietario, verificada previamente por /auth/me.
No se ejecuto ese POST ni se sustituyo esta condicion por el registro SQL del due?o.

Nueva muestra READ ONLY: **2026-11-12 23:54:05 UTC (20:54:05, Buenos Aires)**.
Destino exigido y confirmado usuarios_dev, 127.0.0.1:5434; transaction_read_only=on,
connect_timeout=5, statement_timeout=10000, consultas SELECT y rollback final.

- Revision unica 0007_institutional_publication.
- Documento 8ac0c745-1307-5bb4-9d56-93dfbee0b3b8 PRIVATE, no archivado.
- Version activa 7cb4e79c-747d-574a-8abb-0ebcb2e07636 LISTA.
- Propietario 32eabde4-7d17-4029-a47a-60e2e38faf05 ADMIN activo.
- Espacio 1f048209-4b55-31fc-5d34-06985eb3ba0e activo e ingesta VALIDADA.
- Cero registros de publicacion del documento: publicacion institucional INACTIVA.
- OpenAPI local HTTP 200, POST de publicacion presente con seguridad declarada.
- Respaldo del paso 4 disponible: 5.173.323 bytes, SHA-256 coincidente con
  58bf705e1e66c9835c321fb3434b212138b52de30d6bc35bb0e7941255121acb.
  Lectura elevada autorizada; sin nuevo dump, restauracion o cambio de permisos.

Las herramientas disponibles no ofrecen un contexto de navegador autenticado
utilizable para /auth/me y el POST. No se accedio a tokens, cookies o memoria de
sesiones ni se fabricaron credenciales. No se atribuye un 401 a la sesion del
operador: en esta revalidacion no se invoco /auth/me sin credenciales para inferir
su identidad. Las precondiciones de etapa 1 fueron satisfactorias; el bloqueo es
la disponibilidad del contexto autenticado requerido en etapa 2.

Se solicita al operador iniciar sesion por el procedimiento normal con el due?o.
En la misma pesta?a: Mi perfil, Actualizar perfil, respuesta nueva de /auth/me en
Red/Network; comprobar HTTP 200, UUID propietario indicado arriba, ADMIN,
activo=true y debe_cambiar_password=false. No compartir perfiles completos,
Authorization, JWT, cookies, contrase?as o HAR. El login no conecta por si mismo
la sesion del navegador con este ejecutor: continuar exige un contexto autorizado
que pueda ejecutar ambas solicitudes con esa misma sesion, sin transferir secretos.

Etapas 3 y 4 no ejecutadas; no hay publicador efectivo ni acceso institucional
nuevo que certificar. No se declaran aprobadas pruebas E2E ni la lectura real de
los tres USUARIO. No hubo escrituras de base, modificaciones de ACL individuales,
otros documentos, conversaciones o embeddings, migraciones, cambios de codigo o
configuracion, reinicios, revocaciones ni llamadas a Jina/OpenRouter. No se conecto
usuarios_test. No se recalcularon huellas de embeddings ni se presenta la evidencia
historica como una comprobacion nueva de integridad posterior a publicar.
Solo se actualizo este informe. Se detiene aqui sin avanzar a pruebas React/RAG.

## Cierre de publicación: persistencia y permisos verificados READ ONLY

12 de noviembre de 2026, Buenos Aires. MISMO Sprint 10G12D.
**PUBLICACIÓN INSTITUCIONAL VALIDADA en base y política de autorización.**
Esta sección sustituye el estado anterior de publicación detenida. El operador
informó la ejecución desde Chrome con su sesión ADMIN y respuesta PUBLICADA.
Codex no ejecutó ni repitió ese POST; verificó independientemente su persistencia.

Muestra SQL: **2026-11-13 00:17:24 UTC (12 de noviembre, 21:17:24 Buenos Aires)**.
Destino exigido y confirmado usuarios_dev, 127.0.0.1:5434; lectura forzada mediante
default_transaction_read_only=on, connect_timeout=5 y statement_timeout=15000.
SELECT de current_database() y transaction_read_only comprobados; rollback final.

| Control | Resultado actual |
|---|---|
| Alembic | 0007_institutional_publication, única fila |
| Documento | 8ac0c745-1307-5bb4-9d56-93dfbee0b3b8; AUTHENTICATED, no archivado |
| Versión activa | 7cb4e79c-747d-574a-8abb-0ebcb2e07636; LISTA |
| Publicaciones del documento / activas de versión exacta | 1 / 1 |
| Actor publicado_por | 32eabde4-7d17-4029-a47a-60e2e38faf05; propietario ADMIN activo |
| Fecha persistida de publicación | 2026-11-13 00:15:29.801512 UTC; 12 de noviembre, 21:15:29 Buenos Aires |
| Revocación | revocado_at y revocado_por nulos |
| Espacio Jina | 1f048209-4b55-31fc-5d34-06985eb3ba0e; puntero activo e ingesta VALIDADA |
| USUARIO activos distintos del propietario | 3; los tres con lectura efectiva |
| ADMIN propietario | Conserva lectura por propiedad y condición administrativa |
| ACL individuales del documento | 0 filas, 0 concesiones |
| Otros documentos existentes | 0; no hay otros documentos cuya privacidad evaluar |
| Otras publicaciones activas | 0 |
| Embeddings cloud del espacio y versión | 432; dimensión 768, norma dentro de ±0,01, hash_entrada igual a hash_texto |
| Embeddings históricos | 864 |

Se evaluó en SELECT la expresión ACL productiva de postgres.py para cada usuario
activo, agrupando únicamente rol y condición de propietario. No se fabricaron
sesiones ni se ejecutó el agente bajo una identidad sustituida. La publicación
no exige ACL individual: AUTHENTICATED y el registro vigente de versión exacta
habilitan esa rama institucional, junto con actividad, versión y estado cloud.

La guarda administrativa revisada exige ADMIN activo y propietario; los tres
USUARIO no satisfacen esa condición. No se les conceden publicación, ingesta,
validación o activación por la nueva rama de lectura. Esto es comprobación de
política y datos, no intentos HTTP de escritura con cuentas reales. La publicación
no modifica las guardas de propiedad de conversaciones ni la revalidación de citas;
no se ejecutaron pruebas cruzadas de historial o conversaciones en este cierre.

### Conservación comparada con la restauración validada

Se compararon las cinco tablas completas siguientes entre usuarios_dev y el
destino aislado del paso 4, contenedor rag-recovery-12d-b9a9204365a8, base
rag_restore_12d_b9a9204365a84a7a9bc2c86c3380ba87. Ambas conexiones se forzaron a
READ ONLY, zona UTC y statement_timeout=30000; no se restauró ni modificó nada.
El acceso Docker requirió elevación autorizada. La autenticación existente se
utilizó internamente sin imprimir ni copiar sus valores al informe o al chat.

| Tabla | Filas actuales | Comparación completa con restauración |
|---|---:|---|
| rag_documento_permisos | 0 | Idéntica |
| rag_cloud_embeddings | 432 | Idéntica |
| rag_embeddings | 864 | Idéntica |
| rag_cloud_activos | 1 | Idéntica |
| rag_cloud_ingestas | 1 | Idéntica |

Por tabla se compararon cantidad y MD5 del agregado ordenado de MD5 de filas JSONB,
incluyendo todas las columnas y vectores; las huellas se procesaron en memoria,
sin imprimirlas ni mostrar filas. Todos los resultados coinciden. Es evidencia
operacional de conservación frente al respaldo restaurado, no una certificación
forense ante colisiones deliberadas ni una auditoría de modificaciones transitorias.
Además de conservar cantidades, esta comparación descarta cambios persistidos
observables en los vectores y ACL individuales de esas tablas respecto de esa base.

### Alcance del cierre y pendientes

No hay condición de persistencia o autorización detectada que impida cerrar la
operación de publicación. La identidad de la sesión Chrome fue informada por el
operador; el actor persistido coincide con el propietario esperado. Codex no
inspeccionó retrospectivamente esa sesión ni certifica su /auth/me por SQL.

**Pendiente la aceptación funcional de lectores desde navegador y RAG real.**
La lectura institucional de los tres usuarios queda verificada por base/código,
no por sesiones HTTP propias ni E2E. No se declara éxito funcional integral del
RAG o prueba de aislamiento E2E sin ejecutarlas; requieren la autorización posterior
prevista. La ausencia actual de otros documentos no prueba mediante un caso real
la denegación de un segundo documento privado; la política conserva esa restricción.

usuarios_test no recibió conexiones ni operaciones de este ejecutor. No se leyó
su contenido para afirmar una comparación antes/después: su protección en esta
intervención procede de restringir el destino a usuarios_dev y al entorno aislado
de restauración conocido. No se certifican actuaciones ajenas a este ejecutor.

No se ejecutaron migraciones, escrituras de base, publicaciones adicionales,
revocaciones, reinicios, cambios de código/configuración ni llamadas a proveedores.
Solo se actualizó docs/jina-cloud-10g-12d.md. Se detiene aquí sin pruebas E2E.
