# Sprint 9.3G: agente híbrido, AUTO y skill academic-rag

**3 de noviembre de 2026. IMPLEMENTADO y cargado localmente.** La orquestación,
la carga efectiva de instrucciones y los contratos están comprobados con pruebas
aisladas. La aceptación autenticada de la ampliación en el navegador real queda
pendiente del responsable; no se presenta MSW como una generación real de Qwen.

## 1. Arquitectura y archivos

Orquestador: **`backend/src/app/application/agent/agent.py`**, clase `Agent`.
Router: **`backend/src/app/application/agent/router.py`**, clase `AgentRouter`.
Contexto y resultado inmutables: `application/agent/context.py`.

Archivos nuevos de esta ampliación:

- `backend/src/app/application/agent/__init__.py`.
- `backend/src/app/application/agent/agent.py`.
- `backend/src/app/application/agent/router.py`.
- `backend/src/app/application/agent/context.py`.
- `backend/src/app/application/agent/skills/__init__.py`.
- `backend/src/app/application/agent/skills/registry.py`.
- `backend/src/app/application/agent/skills/academic-rag/SKILL.md`.
- `backend/src/app/infrastructure/rag/skills.py`.
- `backend/tests/rag/test_agent.py`.
- Este informe.

Archivos modificados en esta ampliación:

- `backend/src/app/bootstrap.py`: composición de `app.state.ia_agent`, dependencias
  compartidas y limpieza en lifespan.
- `backend/src/app/presentation/http/ia/respuestas.py`: delegación en Agent; AUTO
  predeterminado, con documento opcional para AUTO. RAG manual sigue requiriéndolo.
- `backend/src/app/application/rag/dto.py`, `core.py`, `use_cases.py`: instrucciones
  internas opcionales, contadas en el contexto y transferidas al proveedor.
- `backend/src/app/infrastructure/rag/ollama.py`: validación del render incluyendo
  esas instrucciones, conservando modelo, parser y presupuestos.
- `backend/src/app/application/rag/relevance.py`: términos funcionales de preguntas
  de duración y delegación del helper anterior al router único.
- `backend/pyproject.toml`: inclusión del SKILL.md como package-data; sin instalar
  dependencias ni modificar versiones.
- `backend/tests/rag/test_adapters.py`: integración HTTP con el agente compuesto.
- `frontend/src/features/ia/pages/ConsultaIAPage.tsx`: AUTO por defecto y explicación
  de su comportamiento, sin exigir documento para consultas generales.
- `frontend/src/features/ia/ia.test.tsx`, `frontend/src/test/mocks/handlers.ts`:
  pruebas y catálogo ficticio, sin llamadas a servicios reales.

La corrección previa del mismo sprint conserva `iaApi.ts`, las pruebas de
relevancia y el diagnóstico en `docs/sprint-9-3g-relevancia-auto.md`. El presente
informe describe la ampliación pedida en el adjunto y reemplaza su condición
anterior de que AUTO académico sin documento tuviera que devolver 422.

## 2. Orquestación y selección

Agent exige acceso normal y valida la pregunta. Delega en `GenerarRespuesta` o
`ResponderConDocumento`, sin copiar sus adaptadores, transacciones, cuotas o
validaciones. Usa la misma admisión del runtime y los mismos proveedores/gates.
Una respuesta directa o RAG consume una admisión en su caso de uso; la abstención
local por ambigüedad/falta de documento autorizado obtiene una sola admisión y
revalida autorización. No hay inferencia adicional de clasificación.

El router combina referencias normativas explícitas, relaciones entre acciones
y objetos académicos y contexto de documentos autorizados. No basta encontrar
una palabra aislada como «unidad»: unidad de almacenamiento es general; unidad
curricular es documental. Regularidad de una función matemática es general;
regularidad curricular es documental. Las preguntas institucionales reconocidas
nunca caen a directo por falta de fuentes.

Para AUTO documental sin selección se consulta únicamente el catálogo filtrado
por permisos. Si hay un documento autorizado, se elige; con varios se pide
selección, sin escoger arbitrariamente. Sin ninguno se devuelve RAG/SIN_EVIDENCIA.
Un documento explícito debe pasar require_active/ACL. Una pregunta ambigua como
«¿Cuánto tiempo dura?» pide precisar tema/documento, sin intentar adivinar con
otro modelo. No se conserva conversación ni se supone contexto de turnos previos.

Las decisiones son reglas conservadoras y comprobables, **no un clasificador
semántico universal**. Formulaciones institucionales no reconocidas o preguntas
mixtas pueden requerir modo manual; no se promete comprensión de cualquier texto.

## 3. Skill cargada y aplicada

Registro cerrado: `SkillRegistry`, con puerto `SkillLoader` en application.
Adaptador de lectura: `PackagedSkillLoader`, en infrastructure. Solo se permite
`academic-rag`, desde la ruta fija del paquete. No hay rutas, plugins o Markdown
proporcionados por HTTP, el usuario o el PDF. Se rechazan nombres desconocidos,
archivo inexistente/enlazado/excesivo, marcadores duplicados e instrucciones
vacías, con NUL o mayores a **512 bytes UTF-8**. Un fallo de carga es 503 técnico,
no SIN_EVIDENCIA. El registro cachea la skill; editarla exige recargar el proceso.

El SKILL.md documenta activación, alcance, herramientas, ACL, recuperación,
relevancia, páginas físicas, abstención y prohibiciones. El cargador extrae solo
el bloque entre `<!-- runtime -->` y `<!-- /runtime -->`, no todo el documento.
La selección llama a `Skill.execute`, que transmite ese bloque al caso RAG.
`build_context` lo incorpora al render y cuenta su tamaño con pregunta/fuentes.
GroundedProvider verifica el mismo render antes de enviar el prompt a Ollama.

Herramientas/casos utilizados por academic-rag:

- `ResponderConDocumento`: autorización antes/después, admisión y operación RAG.
- `DocumentRepository`/`VectorRepository`: versión LISTA, ACL y top-k coseno
  filtrado en SQL antes de LIMIT.
- `AcademicRelevance`, `build_context`, `resolve_citations`: pertinencia,
  presupuesto y fuentes canónicas con página física/offsets.
- Adaptadores existentes `Embeddings` y `GroundedProvider`: nomic-embed-text y
  qwen3:1.7b, secuenciales, sin modelos adicionales.

La skill **no reemplaza controles de código**. El PDF se mantiene como dato no
confiable; sus textos no se cargan como skill ni se ejecutan. No hay herramientas
de código/shell/red disponibles al modelo. El contexto mantiene 4096, salida 256
y reserva 512; no se aumentaron límites para incluir la skill.

## 4. Ausencia de evidencia y errores reales

Se reutiliza la corrección de pertinencia del mismo sprint: coseno >= 0,60 más
cobertura de conceptos específicos por fuente. La inspección previa real había
encontrado API REST con máximo **0,6409**, 12 candidatos sobre el umbral y **0**
pertinentes: prueba de que el umbral solo admite falsos positivos. La pregunta
académica previa conservaba cuatro candidatos en páginas 54/55. No se repitieron
esas llamadas de modelos para esta ampliación ni se recalcularon embeddings.

La reproducción aislada anterior confirma que una respuesta general sin citas
después de recuperar falsos positivos termina en IARespuestaInvalida. Los logs
históricos no permiten atribuir inequívocamente ese recorrido a un evento concreto.
Se conserva esa limitación y los diagnósticos seguros por etapa/categoría.

Sin evidencia pertinente: SIN_EVIDENCIA/fuentes vacías, sin generador o fallback.
Contrato inválido, cita inexistente, timeout, modelo indisponible, repositorio
fallido o skill no disponible siguen siendo errores técnicos. No se añadieron
catch que conviertan esos errores en una respuesta exitosa. Las equivalencias
léxicas son conservadoras: sinónimos no contemplados o evidencia distribuida
pueden causar abstención. Identificadores válidos no demuestran entailment de
todas las afirmaciones; su evaluación sigue siendo necesaria.

## 5. Evidencia de pruebas

| Verificación final | Resultado |
| --- | --- |
| RAG + IA + lifespan HTTP + autenticación/autorización aisladas | **461 aprobadas**, 6,28 s |
| React/AuthProvider/MSW, incluyendo AUTO predeterminado | **48 aprobadas**, 26,38 s |
| TypeScript | Aprobado |
| ESLint | Aprobado |

Las ejecuciones intermedias no se suman como casos distintos. Hay **29 casos
nuevos de agente/skill** dentro del resultado final. No se ejecutaron pruebas
PostgreSQL, usuarios_test, toda la regresión o un build redundante. Permanece el
aviso previo de Starlette/TestClient.

Comando backend desde backend:

```powershell
.\.venv\Scripts\python.exe -B -m pytest -q tests/rag tests/ia tests/http/test_lifespan.py tests/security/test_authentication.py tests/security/test_authorization.py -p no:cacheprovider --basetemp=.pytest-tmp-93g-agent-delivery --tb=short
```

Desde frontend: `npm.cmd run typecheck`, `npm.cmd run lint` y
`npm.cmd exec vitest run src/features/ia/ia.test.tsx`.

| Criterio | Evidencia aislada |
| --- | --- |
| A: AUTO/API REST | HTTP autenticado con auth de memoria; GENERADA/LLM_DIRECTO, sin catálogo/skill/modelo documental |
| B: AUTO/duración de regularidad | Pipeline RAG real con vectores/generador ficticios, skill real cargada; FUNDAMENTADA y página 7 de fixture |
| C: manual RAG/API REST | SIN_EVIDENCIA, sin fuentes ni llamada al generador |
| D: sin documento autorizado | Abstención local, sin llamadas de modelos ni fallback |
| E: documento privado ajeno | HTTP 403 antes de embeddings/generación |
| F: skill efectiva | Bloque real del SKILL.md presente en GroundedInput y en payload del adaptador HTTP MockTransport; presupuesto comprobado |
| G: compatibilidad | Suites de IA directa, RAG, auth, cuotas, contratos, cancelación y exclusión aprobadas |

Se prueban también precisión ante ambigüedad, catálogo múltiple, revocación durante
generación, allowlist de carga, instrucciones inválidas y rechazo de citas F999.
La página de fixture no se presenta como una página del reglamento real.

## 6. Estado local y restricciones

Se revalidó la instancia propia previa padre **29384**/hijo **18936**, ejecutables,
creación exacta, flags y listener único antes de reiniciarla. Nuevo padre **24088**,
arranque **21:17:06 -03:00**, mismo lanzador loopback con enable-llm/observe-llm,
sin aprovisionamiento. Logs técnicos protegidos con prefijo
`backend-93g-agent-20261103-211706` en el directorio de respaldo de 9.3E. No se
detuvo React, PostgreSQL, Docker u Ollama.

Verificación **21:17:26 -03:00**: FastAPI/OpenAPI **200** y modo por defecto AUTO,
React/login **200**, documentos anónimos **401**, Ollama/ps sin modelos cargados.
RAM disponible **1,584 GiB** antes y **1,579 GiB** después: muestras, no garantía
de rendimiento ni picos de modelos. Se mantienen guardas RAM y gate compartido.

Lectura controlada de usuarios_dev: **0004_rag, 432 embeddings y una versión
LISTA**. Destino forzado usuarios_dev/127.0.0.1:5434, transacción READ ONLY con
timeouts y rollback. No se modificaron datos/embeddings, usuarios_test, migraciones,
Docker/Compose, modelos, respaldos, volumen original o contraseñas. No se instalaron
dependencias, ejecutaron generaciones, extrajeron sesiones ni registraron secretos
o contenido sensible. No se inicia memoria conversacional.

## 7. Pasos desde React y pendientes

1. Recargar `http://127.0.0.1:5173/ia` e ingresar normalmente. AUTO debe estar
   seleccionado. No compartir credenciales/JWT ni usar la recuperación sin su
   autorización específica.
2. Preguntar «¿Qué es una API REST?» sin elegir documento: esperar
   **LLM_DIRECTO / GENERADA**, sin fuentes.
3. En AUTO preguntar «¿Cuánto tiempo dura la regularidad de una unidad curricular?»:
   con el único reglamento autorizado se selecciona automáticamente; esperar
   **RAG / FUNDAMENTADA**, contrastando las páginas físicas citadas con el PDF.
4. En manual RAG seleccionar Reglamento académico y preguntar sobre API REST:
   esperar **SIN_EVIDENCIA**, fuentes vacías, sin error de contrato.
5. Una cuenta sin documentos autorizados obtiene abstención para preguntas
   institucionales; no se crean usuarios o permisos para fingir esa evidencia.
   La denegación explícita y los fallos técnicos se verificaron con dobles sin
   provocar averías reales en los servicios.

Pendientes: confirmación del responsable de A/B/C en su sesión real con esta
ampliación; evaluación de sinónimos/preguntas mixtas y fundamentación semántica.
No se afirma una nueva respuesta Qwen visible o calidad validada solo por las
pruebas. **Software funcional implementado, integrado y servido; aceptación
autenticada real pendiente.**

## 8. Confirmación posterior del responsable

El responsable respondió «sí, sí devolvió bien» a la solicitud de probar desde
React los casos A/B/C: RAG manual con API REST, AUTO con API REST y AUTO con
requisitos de regularidad curricular. Se registra como **confirmación manual
favorable del recorrido solicitado**, no como observación automatizada del navegador.

No informó estrategia, estado o páginas por separado; no se inventan esos
metadatos ni se atribuye la confirmación a una llamada concreta de Ollama. Tampoco
se extiende a la variante de duración de regularidad ni a fallos/denegaciones
reales, cubiertos aisladamente. No se ejecutaron consultas adicionales para este
registro. Se cierra la espera de esa confirmación general; permanece pendiente
el contraste detallado de las citas y la evaluación semántica señalados arriba.
