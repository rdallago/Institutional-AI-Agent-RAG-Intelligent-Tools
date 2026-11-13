# Sprint 10G.12C — Desambiguación normativa y continuidad

11 de noviembre de 2026, America/Buenos_Aires.
**Implementado y verificado sin APIs externas. GO para probar manualmente la
aclaración y los artículos 24 desambiguados; artículo 52 completo recuperado,
con generación bloqueada por el presupuesto actual de contexto.**

## Evidencia documental real

Consultas exclusivamente READ ONLY en usuarios_dev, 127.0.0.1:5434, versión
7cb4e79c-747d-574a-8abb-0ebcb2e07636 del documento autorizado. Conexiones con
default_transaction_read_only=on, connect_timeout=10, statement_timeout=5000;
consultas directas terminadas con rollback. Solo se imprimieron encabezados
normativos, conteos y metadatos de ubicación, no cuerpos completos ni datos personales.
Las lecturas del repositorio también usaron conexión forzada READ ONLY.

| Artículo | Encabezados normativos comprobados | Página / offset / ordinal del fragmento |
|---|---|---|
| 24, primera aparición | REGLAMENTO ORG.ANICO MARCO / TITULO III. GOBIERNO INSTITUCIONAL | 11 / 2062 / 64 |
| 24, segunda aparición | ANEXO I REGIMEN ACADEMICO MARCO / Capitulo 3 TRAYECTORIA FORMATIVA | 58 / 686 / 346 |
| 52 | Marco orgánico, bajo TITULO IV. GESTION | 32 / 1327 / 196 |
| 53, prueba del cierre del 52 | Encabezado siguiente del mismo recorrido | 35 / 110 / 212 |

Se conservan los nombres extraídos literalmente; no se corrigió OCR en PostgreSQL.
La normalización de comparación elimina tildes, diferencias de caja, espacios y
puntos interiores de palabra (ORG.ANICO); no reescribe la evidencia.

Ambos artículos 24 son ocurrencias en cuerpos normativos diferentes, con reinicio
de numeración y textos distintos, no una repetición idéntica de extracción. El
primero abarca slices de páginas 11–12 (281 y 350 caracteres); el segundo es un
slice de página 58 (684 caracteres), cerrado por el siguiente artículo.
La presencia de un índice de contenidos en página 1 no se usa como sección del
primer cuerpo: un nuevo título normativo reinicia la jerarquía anterior.

El artículo 52 continúa por páginas 32, 33, 34 y los primeros 110 caracteres de
página 35, antes del artículo 53. Longitudes exactas de slices: 738, 1810, 2144,
110, total **4802 caracteres**. La ventana anterior terminaba en página 34;
no era un defecto de embeddings ni ausencia del artículo.

## Cambios implementados

- Nuevo resolver puro articles.py: recorre páginas verificadas en orden, detecta
  artículos y encabezados de anexo/norma/título/capítulo/sección, conserva todas las
  ocurrencias y produce ArticleResolution(chunks, alternatives, reason).
- La selección de homónimos exige una frase explícita de sección identificadora y
  coincidencia única. Sin ella devuelve alternativas con sección, página y offset;
  no escoge la primera ni deduplica automáticamente cuerpos repetidos.
- Límites: máximo 100 páginas y un millón de caracteres. Se rechazan huecos de
  páginas. El cierre se demuestra por siguiente artículo, cambio explícito de
  sección o fin del documento únicamente si el repositorio comprueba todas las
  páginas contra v.paginas. Sin prueba, razón unproven_end; no se usa una ventana
  fija como cierre. No se incluyen encabezados del siguiente artículo/sección.
- PostgresRAG.resolve_article conserva ACL SQL, documento y versión activa, hashes
  SHA-256 y require_active antes/después. CloudPostgresRAG hereda el recorrido y su
  comprobación de espacio Jina VALIDADA/activo. explicit_article sigue disponible
  como wrapper compatible. La recuperación estructurada no consulta Nomic.
- Cada slice conserva página, offsets y texto exacto, con identificador derivado de
  versión/página/offsets, igual que las expansiones transitorias previas. No se
  reemplazan ni modifican fragmentos persistidos. ArticleLink vincula los slices
  al mismo artículo, sección, scope, grupo, primera página y cierre demostrado.
- ResponderConDocumento convierte alternativas en RAGResult ACLARACION, revalida
  autorización y versión y no llama al generador ni a embeddings. El contrato API
  existente admite ACLARACION; React muestra el texto de alternativas en historial.
- El validador permite unidades de continuación solo con ArticleLink del scope y
  número solicitados, cierre válido y página no anterior al artículo. Mezclar
  enlaces de artículos distintos invalida el soporte de la respuesta. El LLM no
  recibe control sobre esa metadata interna. Las afirmaciones siguen requiriendo
  soporte léxico y polaridad de las fuentes citadas.
- El contexto debe contener TODOS los slices; de lo contrario se registra
  article_context_budget y se informa que el artículo localizado no cabe completo.
  No se generan respuestas a partir de un truncamiento silencioso. Las preguntas
  semánticas generales y sus umbrales permanecen intactos.

## Comprobación READ ONLY con el repositorio modificado

| Solicitud local, sin generación | Resultado |
|---|---|
| Artículo 24 sin sección | ambiguous: dos alternativas, páginas 11 y 58 |
| Artículo 24 del Reglamento Orgánico Marco | next_article, páginas 11–12, contexto completo disponible |
| Artículo 24 del Régimen Académico Marco | next_article, página 58, contexto completo disponible |
| Artículo 52 | next_article, páginas 32–35, recuperación completa |

build_context con ConservativeCounter comprobó que el 52 NO cabe completo: además
del tamaño total hay cuatro slices y el contrato actual permite tres fuentes.
No se amplió globalmente el contexto ni se fusionaron páginas perdiendo citas.
El bloqueo de cierre está resuelto; **la generación integral del 52 sigue limitada
por presupuesto/contrato**, y se abstiene con razón precisa. No debe interpretarse
como recuperación vacía ni probarse repetidamente con consumo de API.
Los chequeos de contexto locales no llamaron a ningún proveedor.

## Pruebas y alcance

Comando backend final desde backend:

```powershell
& '.\.venv\Scripts\python.exe' -B -m pytest tests/rag/test_normative_articles.py tests/rag/test_explicit_articles.py tests/rag/test_article_continuity.py tests/rag/test_jina_cloud.py tests/rag/test_core.py tests/ia/test_http_ia.py -q -p no:cacheprovider --basetemp=.pytest-tmp-10g12c-final --tb=short
```

**148 aprobadas, 0 fallidas, 5,21 s**, aviso previo Starlette/HTTPX.
Incluye homónimos, sección explícita, ambigüedad, duplicación de extracción que
conserva aclaración, cierre por artículo/sección/fin documentado, límites/gaps,
ACL/versión, continuidad enlazada y citas de página, contexto insuficiente sin
LLM y contratos HTTP. La vinculación de continuación de versión distinta se rechaza.

Frontend desde frontend:

```powershell
& 'C:\Program Files\nodejs\node.exe' node_modules/vitest/vitest.mjs run src/features/ia/ia.test.tsx --maxWorkers=1 -t 'articulos homonimos'
```

**1 aprobada, 55 omitidas por filtro**, 6,09 s total. Prueba React/MSW del panel
real mostrando las alternativas ACLARACION mediante el contrato conversacional
existente. No se ejecutó toda la suite frontend ni una E2E contra FastAPI real.
El primer fixture frontend devolvía historial vacío después del envío: se corrigió
el mock para reproducir la persistencia y recarga normales; no cambió producción React.

La ejecución ampliada previa que incluyó test_relevance.py dio **157 aprobadas y
1 fallida**, 6,09 s. El fallo es test_academic_evidence_and_real_page: su fixture
produce “Norma ficticia [F1].” mientras su evidencia exige asistencia. La pregunta
no menciona número de artículo y el doble no implementa resolución estructurada;
no recorre estas ramas nuevas. La respuesta carece de soporte y se rechaza
correctamente. El fallo ya estaba documentado en 10B/12B. No se modificó el test,
su expectativa ni el validador para ocultarlo; no se declara aprobada toda la suite.

## Archivos modificados/incorporados

1. backend/src/app/application/rag/articles.py (nuevo).
2. backend/src/app/application/rag/dto.py.
3. backend/src/app/application/rag/use_cases.py.
4. backend/src/app/application/rag/relevance.py.
5. backend/src/app/infrastructure/rag/postgres.py.
6. backend/tests/rag/test_normative_articles.py (nuevo).
7. frontend/src/features/ia/ia.test.tsx (solo prueba).
8. docs/jina-cloud-10g-12c.md (este informe).

## Repetición manual posterior y decisión

No se reinició el backend. Para cargar cambios, reiniciar manualmente solo la
instancia del proyecto desde la terminal privada que ya tiene ambas claves:

```powershell
Set-Location 'D:\Downloads\proyectos\api-usuarios-clean\backend'
$env:PYTHONPATH=(Join-Path (Get-Location) 'src')
& '.\.venv\Scripts\python.exe' -B -m app.presentation.cli.local_server --environment local-development --enable-llm --observe-llm --host 127.0.0.1 --port 8000
```

Detener antes la instancia propia con Ctrl+C; no iniciar otra en un puerto ocupado.
En http://127.0.0.1:5173/ia, cuenta autorizada, nueva conversación:

1. «¿Qué establece el artículo 24 del reglamento académico?» Debe pedir sección
   y mostrar ambas alternativas con páginas; no debe generar evidencia ambigua.
2. Repetir como pregunta completa: «¿Qué establece el artículo 24 del reglamento
   académico, en el Régimen Académico Marco?» Para el otro cuerpo, sustituir la
   sección por «Reglamento Orgánico Marco». Incluir el título del catálogo mantiene
   inequívoca la selección documental del agente; el resolver distingue la sección.
3. Comprobar citas/páginas y soporte en la respuesta real; no declararlo aprobado
   solo por estas pruebas locales. No asumir resolución de referencias elípticas
   como “el primero” sin repetir sección y artículo.

**GO técnico para comprobar aclaración y artículos 24 desambiguados desde React.**
**NO-GO para afirmar generación completa del artículo 52 con el presupuesto actual.**
La recuperación multipágina está resuelta y probada; sigue protegido el rechazo a
contexto parcial. No hubo llamadas externas, consumo de créditos, escrituras SQL,
reindexación, migraciones, cambios de ACL/.env/proveedor, fallback local, reinicios
automáticos o cambios a DOCUMENT_EXPORT_APPROVED=False. No se modificaron vectores.
