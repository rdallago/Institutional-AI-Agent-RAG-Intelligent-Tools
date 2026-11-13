# Sprint 9.3F: RAG integrado; indexación pausada por memoria

Fecha: **3 de noviembre de 2026**. **PARCIAL para el criterio real de extremo a
extremo**: software integrado y comprobado, PDF extraído y persistido, embeddings
e inferencia real pendientes por recursos. No se sustituye esa evidencia por
respuestas ficticias o pruebas aisladas.

## 1. Resultado concreto

| Entregable | Estado |
| --- | --- |
| Adaptadores PDF, embeddings, generación fundamentada y PostgreSQL | Implementados |
| POST /api/v1/ia/respuestas, modos LLM_DIRECTO/RAG | Registrado y disponible |
| POST /api/v1/ia/consultas | Conservado con su contrato anterior |
| React: modo, documento autorizado, estado, estrategia y páginas | Integrado y probado con MSW |
| PDF real | **72 páginas extraídas y persistidas** |
| Fragmentos reales preparados | **432**, con procedencia verificada |
| Embeddings reales generados/persistidos | **0 / 0** |
| Versión del reglamento | **PREPARANDO**, privada, sin versión activa publicada |
| Consulta real al reglamento | **NO EJECUTADA**: falta completar embeddings/publicación |
| RAM de comprobación posterior | **0,495 GiB disponibles** |
| Ollama posterior | GET /api/ps 200, **cero modelos cargados** |

La ingesta se detuvo **antes del primer embedding** por su control de memoria.
No hay un índice completo consultable todavía. React no lista la versión parcial;
muestra ausencia de documentos indexados disponibles, en lugar de inventar una
respuesta o presentar una preparación parcial como una consulta SIN_EVIDENCIA.
El backend integrado permanece funcionando. No se bloquearon las fases de código
y pruebas por la RAM; únicamente se pausó la ejecución real de modelos.

## 2. Archivos

Nuevos:

- `backend/src/app/infrastructure/rag/__init__.py`.
- `backend/src/app/infrastructure/rag/text.py`: extracción PDF y contador conservador.
- `backend/src/app/infrastructure/rag/ollama.py`: embeddings y GroundedProvider.
- `backend/src/app/infrastructure/rag/postgres.py`: repositorio SQLAlchemy/pgvector.
- `backend/src/app/infrastructure/rag/models.py`: exclusión local y proveedor directo coordinado.
- `backend/src/app/infrastructure/rag/resources.py`: guardas de RAM para ejecución local Windows.
- `backend/src/app/presentation/http/ia/respuestas.py`: esquemas y rutas nuevas.
- `backend/src/app/presentation/cli/ingest_academic.py`: comando administrativo explícito.
- `backend/tests/rag/test_adapters.py`: pruebas nuevas de adaptadores/HTTP/exclusión/PDF.
- `infra/pgvector/verify_rag_repository_93f.py`: integración real reversible del repositorio.
- Este informe.

Modificados:

- `backend/pyproject.toml`: dependencia **pypdf==6.21.4**.
- `.gitignore`: archivo técnico de bloqueo de modelos, sin contenido de usuarios.
- `backend/src/app/bootstrap.py`: composición y limpieza de adaptadores RAG/coordinador.
- `backend/src/app/infrastructure/llm/ollama.py`: transporte/parser interno reutilizable;
  la entrada directa sigue validándose por separado.
- `backend/src/app/application/ia/use_cases/generar_respuesta.py`: propaga ocupación
  saneada del coordinador sin convertirla en error de protocolo.
- `backend/src/app/application/rag/core.py`: abstención explícita solicitada al
  modelo y avance estricto del final de fragmentos con solape.
- `backend/src/app/application/rag/use_cases.py`: respuesta local ante el marcador
  exacto SIN_EVIDENCIA del generador.
- `backend/src/app/presentation/http/ia/middleware.py`: límite de lectura también
  para la ruta nueva.
- `backend/tests/rag/test_core.py`: abstención del generador y avance con solape.
- `frontend/src/features/ia/api/iaApi.ts`, `pages/ConsultaIAPage.tsx` e `ia.test.tsx`:
  contrato RAG, selección, fuentes, estados y verificaciones.

No se editaron Docker/Compose, migraciones, roles, credenciales o configuración
.env. Alembic continúa en **0004_rag**, sin repetir esa migración.

## 3. Extracción, fragmentación y tokens

Se añadió e instaló únicamente pypdf 6.21.4, biblioteca Python pura de extracción
ligera; no se instalaron frameworks de modelos, tokenizadores pesados o OCR. La
primera instalación desde sandbox falló por restricción de red; la instalación
autorizada con acceso revisado descargó el wheel de unos 410 kB y terminó bien.
No se descargaron modelos. La biblioteca permite extraer texto por página; el
adaptador no ejecuta OCR ni da por resueltas tablas complejas.
[Documentación pypdf](https://pypdf.readthedocs.io/en/stable/user/extract-text.html).

La CLI solo abre el archivo fijo
`backend/data/documents/reglamento_academico.pdf`, regular y sin enlace simbólico,
con límites de archivo/páginas/contenido. Extrae texto por página física numerada
desde 1 y rechaza páginas vacías, NUL o excesos. No imprime el texto. No existe
ruta pública de descarga ni carga automática al iniciar FastAPI.

Se reutilizan Page, Scope, Chunk y prepare_pages de 9.3B. Fragmentos dentro de una
página, offsets Unicode `[start,end)` sobre texto exacto, techo **400** y solape
**50** unidades conservadoras. La corrección del solape evita volver a emitir
fragmentos que terminen repetidamente en el mismo salto de párrafo. No se infieren
artículos o números impresos: las citas muestran **página física PDF**.

El contador mide bytes UTF-8 como cota conservadora, identificado y versionado
como `utf8-upper-bound-v1`; **no son tokens exactos**. El contexto incluye el render
completo y reserva 512 para plantilla/instrucción más 256 de salida, manteniendo
4096 de contexto. El adaptador contrasta prompt_eval_count con esa cota/reserva
y rechaza desbordes; embeddings usan su propia reserva pequeña y truncate=false.
No se trunca la pregunta ni una evidencia para hacerlas caber. Entradas Unicode
muy costosas pueden rechazarse conservadoramente aunque un tokenizador exacto
admitiera más texto. La columna tokens_medidos almacena esta cota identificada
por la política, no una medida exacta de tokens Qwen.

Los tests prueban el contraste de presupuestos con respuestas simuladas; **el
contraste empírico con los modelos locales sigue pendiente** por la pausa. No se
afirma que esta fase haya validado tokenización real del corpus bajo inferencia.

## 4. Modelos, transporte y exclusión

Embeddings fijados a nomic-embed-text y el digest aprobado en 9.3A, 768 dimensiones.
Antes de usarlos se comprueba identidad mediante /api/tags; la respuesta debe
identificar ese modelo/alias latest, contener un vector finito no nulo y dimensión
exacta, norma aproximadamente unitaria y prompt_eval_count acotado. No se mezclan
espacios solo por coincidir en dimensión.

Se usan `search_document: ` y `search_query: ` según la operación, conforme a la
[ficha oficial Nomic](https://huggingface.co/nomic-ai/nomic-embed-text-v1.5).
POST /api/embed recibe un solo texto, contexto 2048, truncate=false y keep_alive=0,
sin modelos/URL/opciones del cliente. El contrato está documentado por
[Ollama](https://docs.ollama.com/api/embed). No se ejecuta una llamada adicional
de embeddings para comprobar conectividad.

El generador fundamentado reutiliza transporte/parser estricto del adaptador
existente, pero recibe GroundedInput separado: qwen3:1.7b, think=false, stream=false,
salida 256, contexto 4096, keep_alive=0. Exige done=true y done_reason stop/length,
texto válido y presupuesto comprobable. Resuelve citas solo entre F1/F2/F3
efectivamente enviadas. Razones, referencias o contratos inválidos se rechazan;
no hay reintento automático, fallback directo o incremento de presupuesto.

Se comparte el gate entre IA directa y RAG en el proceso. Además, un bloqueo de
archivo no bloqueante coordina FastAPI y la CLI local del mismo workspace. Se
libera por finally/cierre del descriptor, también al cancelar; no es una cola ni
un registro de contenido. Los tests verifican exclusión entre instancias y leases
obsoletos. No sustituye las cuotas existentes ni coordina equipos/workspaces ajenos.

La ingesta mantiene el gate durante el lote; RAG lo mantiene durante su operación
completa. Se espera que /api/ps quede vacío después de embeddings y antes de
admitir otra generación; si no se libera en la ventana acotada se devuelve
indisponibilidad, sin iniciar otro modelo. El proveedor directo también usa esa
barrera en la composición operativa. No se termina Ollama para forzar descarga.

Guardas actuales: **1,0 GiB libre antes de embeddings** y **1,5 GiB antes de generar
RAG**. Son controles conservadores del piloto Windows, no garantías de suficiencia;
la memoria máxima real sigue pendiente. No hay portabilidad de esa guarda a otros
sistemas sin adaptar la lectura de recursos. No se modificó silenciosamente la
configuración del servidor ni se aumentaron presupuestos.

## 5. PostgreSQL definitivo, ACL e ingesta

El repositorio utiliza el engine SQLAlchemy existente con SQL parametrizado;
no requiere instalar un paquete cliente pgvector. Usa las nueve tablas definitivas
de 0004_rag y casts vector(768), sin tablas vectoriales temporales o almacenamiento
alternativo. Transacciones de metadatos/checkpoints/publicación separadas de la
espera de modelos; no se mantiene una transacción DB durante inferencia.

La búsqueda coseno exacta une documento, versión activa LISTA, espacio fijo y
usuario activo, y aplica propietario/ACL/visibilidad autorizada **en WHERE antes
de ORDER BY y LIMIT**. También exige que el texto recuperado corresponda al slice
de la página persistida. No se recupera globalmente para filtrar permisos después.
El caso de uso revalida acceso normal y ACL/versión antes de entregar.

La CLI es una operación administrativa local autorizada y explícita, no un acceso
HTTP con Principal inventado. Exige destino usuarios_dev/127.0.0.1:5434, revisión
0004_rag y selección inequívoca del único ADMIN activo con credencial normal.
Si no hay un único propietario admisible, falla cerrado. No cambia roles, claves
o sesiones para indexar. El documento queda **PRIVATE**; otros usuarios necesitan
permiso explícito y no reciben acceso por ser ADMIN automáticamente.

Huellas/IDs deterministas por propietario, PDF, pipeline y espacio permiten
repetir/reanudar sin duplicar versiones o fragmentos. Se consultan embeddings
faltantes y se inserta un checkpoint por fragmento; un vector conflictivo para
la misma clave no se reemplaza silenciosamente. El progreso solo informa conteos.

Publicar requiere cobertura completa, páginas y fragmentos esperados, vectores
768 no nulos y procedencia exacta; se realiza bajo lock del documento y transacción
atómica, pasando versión/ingesta a LISTA y apuntando la versión activa. Una
interrupción deja PREPARANDO/EMBEBIENDO y conserva checkpoints, sin mostrar contenido
parcial por HTTP. No se borran versiones anteriores.

No se añadió RLS ni se promete aislamiento de un superusuario DB frente a acceso
administrativo directo. El aislamiento de aplicación está en las consultas/servicios
y se verificó con un segundo usuario activo sintético.

## 6. FastAPI y React

Nuevo POST **/api/v1/ia/respuestas**, Bearer normal obligatorio:

```json
{"modo":"RAG","documento_id":"<UUID autorizado>","prompt":"<consulta>"}
```

Modo LLM_DIRECTO acepta solo modo/prompt, sin documento. Respuesta nueva:

```json
{
  "respuesta":"<texto>",
  "finalizacion":"completa",
  "estado":"FUNDAMENTADA",
  "estrategia":"RAG",
  "fuentes":[{"id":"F1","pagina":12}]
}
```

Ese ejemplo **es de contrato**, no una respuesta real del reglamento. SIN_EVIDENCIA
tiene finalizacion=null y fuentes=[]; puede provenir de recuperación insuficiente
o del marcador exacto de abstención del generador. No se llama al LLM cuando no
hay evidencia recuperada admisible. Una indisponibilidad/índice incompleto no se
oculta como una abstención exitosa.

GET **/api/v1/ia/documentos** devuelve solo ID/título de documentos activos LISTA
permitidos. No expone texto, rutas, propietarios, modelo o credenciales. Ambos
POST mantienen cuerpo máximo 16 KiB y pregunta máxima 1000 puntos/3000 bytes.
Toda respuesta IA usa no-store y errores saneados. RAG y directo comparten
admisión/cuotas/deadline; GET de documentos no consume generación.

React permite elegir LLM_DIRECTO/RAG y un documento autorizado; muestra estrategia,
estado, texto escapado y páginas físicas, sin HTML o Markdown ejecutable. Conserva
cancelación, deadline local 70 s, Retry-After y bloqueo de doble envío. SIN_EVIDENCIA
no se muestra como límite de generación. El modo directo de la pantalla conserva
su llamada antigua /ia/consultas; la ruta nueva también ofrece LLM_DIRECTO mediante
el mismo caso de uso. No cambió el contrato de /ia/consultas.

Se reinició exclusivamente FastAPI para cargar los adaptadores y las rutas:
instancia anterior padre 13384/hijo 30616 revalidada por creación, ejecutables y
listener; nuevo padre **5996**. Sin aprovisionamiento; se preservaron enable-llm y
observe-llm. Logs de inicio en el directorio protegido usado en 9.3E. No se reinició
React, Docker, PostgreSQL, WSL u Ollama. Vite sirve los cambios del frontend.

OpenAPI activo: consultas/respuestas/documentos presentes. GET anónimo de
documentos: **401**. React /login: **200**. No hubo autenticación automatizada o
extracción de sesión del navegador para fingir una prueba real autorizada.

## 7. Pruebas y ejecuciones

| Ejecución | Resultado |
| --- | --- |
| IA/RAG inicial, antes de casos nuevos | 359 aprobadas |
| Adaptadores/IA/RAG intermedia | 373 aprobadas, 14,41 s |
| Regresión backend sin PostgreSQL | **807 aprobadas, 162 omitidas**, 66,47 s; antes de dos casos finales |
| Dirigida IA/RAG final | **376 aprobadas**, 16,19 s |
| Dirigida de barrera/lifespan, incluida en cobertura final | 27 aprobadas, 7,25 s |
| Typecheck frontend | Aprobado |
| Lint frontend final | Aprobado |
| React/MSW IA | **41 aprobadas**, 66,45 s totales |
| Build frontend | Aprobado, 947 módulos; chunk IA 8,53 kB / 3,56 kB gzip |
| Repositorio contra usuarios_dev con fixtures y ROLLBACK | **Aprobado**, incluida repetición tras endurecer checkpoints/publicación |

Las ejecuciones no se suman como casos distintos. Las 162 pruebas PostgreSQL se
omitieron: no se conectó a usuarios_test. El aviso Starlette/TestClient permanece.
El primer lint detectó setState síncrono en un effect; se movió la limpieza al
evento de cambio de modo, sin deshabilitar la regla.

Mocks verifican payload/prefijos/modelos, dimensión/presupuesto, timeouts, cierre,
done_reason estricto, contratos HTTP, anonimato, referencias, no-store, cota de
cuerpo y exclusión. Un PDF sintético de dos páginas prueba el extractor real.
La integración SQL ejecuta staging repetido, checkpoints, publicación, coseno,
concesión/revocación y aislamiento entre dos usuarios activos sintéticos; todas
esas fixtures se revierten con ROLLBACK, sin alterar cuentas existentes.

Comandos principales desde backend:

```powershell
.\.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider --basetemp=.pytest-tmp-93f-regression --tb=short
.\.venv\Scripts\python.exe -B -m pytest -q tests/rag tests/ia -p no:cacheprovider --basetemp=.pytest-tmp-93f-delivery --tb=short
```

Desde la raíz, prueba SQL explícita y reversible:

```powershell
$env:PYTHONPATH='backend/src'
.\backend\.venv\Scripts\python.exe -B infra/pgvector/verify_rag_repository_93f.py
```

## 8. Ingesta real intentada y estado persistido

Se ejecutó desde backend:

```powershell
.\.venv\Scripts\python.exe -B -m app.presentation.cli.ingest_academic --confirm-local-administrative-ingest --max-chunks 10000
```

Salida técnica, sin texto ni identificadores personales:

```text
PREPARADO paginas=72 fragmentos=432 pendientes=432
PAUSADO_MEMORIA checkpoints_conservados=true
```

Lectura controlada posterior de usuarios_dev confirmó:

- 72 páginas y 432 fragmentos persistidos, **0 embeddings**.
- Estado PREPARANDO, visibilidad PRIVATE y puntero activo ausente.
- **Cero discrepancias** entre texto de fragmento, offsets, página y cota UTF-8
  persistida. No se inventaron páginas para construir referencias.
- Revisión 0004_rag conservada.
- RAM disponible **0,495 GiB**; /api/ps sin modelos cargados.

No se cargó Nomic para averiguar si alcanzaba la memoria y no se envió una pregunta
real a Qwen. No hubo errores de inferencia que se disimularan con un fake o con
una segunda llamada. Los checkpoints conservados en esta ejecución son las páginas,
fragmentos y estado de trabajo; **no hay checkpoints de vectores generados todavía**.

## 9. Pendientes para cerrar el criterio real

1. Recuperar recursos voluntariamente y reanudar el mismo comando por lotes,
   por ejemplo --max-chunks 10. Reutiliza la versión/fragmentos actuales y omite
   embeddings ya presentes; no repite migraciones o extracción al arrancar HTTP.
   La CLI sí vuelve a extraer/verificar el PDF cuando se ejecuta explícitamente.
2. Completar los **432 embeddings** y comprobar publicación LISTA. No eliminar ni
   rehacer infraestructura; no reemplazar PostgreSQL por otro almacenamiento.
3. Con margen para Qwen y sin ingesta simultánea, el responsable inicia sesión
   normalmente con la cuenta propietaria; recarga Consultar IA, elige RAG y el
   reglamento publicado. No compartir contraseñas/JWT ni crear usuarios para eludir
   permisos. Otros usuarios necesitan ACL explícita; no se habilitó acceso global.
4. Ejecutar una pregunta no sensible y contrastar afirmaciones/páginas con el PDF,
   y una negativa para evaluar abstención. La calidad española, umbral inicial
   coseno **0,60**, entailment y latencia siguen pendientes de evaluación real.
   La validez de un identificador de cita no garantiza por sí sola fundamentación.

No se anuncia éxito React → pgvector → Ollama real antes de esas comprobaciones.
No se ejecutaron nuevas migraciones, cambios Docker/Compose, descargas de modelos,
accesos a usuarios_test, limpieza de respaldos/volúmenes o modificaciones del volumen
original conservado. Los únicos datos duraderos nuevos son el staging documental
autorizado en la base definitiva. Prompts/respuestas/JWT no se persistieron o registraron.

**PARCIAL: implementación integrada y probada; indexación/inferencia real pausadas
por RAM, con avance conservado y servicios disponibles.**
