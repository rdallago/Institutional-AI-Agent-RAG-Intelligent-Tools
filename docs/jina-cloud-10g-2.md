# Sprint 10G.2 — Configuración segura de Jina

Fecha: 10 de noviembre de 2026. **Configuración preparada y pruebas locales
APROBADAS; sin autorización de exportación, indexación o activación.**

## Resultado efectivo

- usuarios_dev/127.0.0.1:5434 verificada READ ONLY: revisión 0006_cloud_embeddings.
  transaction_read_only=on, connect_timeout=10, statement_timeout=5000 y rollback.
- Único cambio de configuración: tres variables no secretas en .env raíz:
  EMBEDDING_PROVIDER=jina, EMBEDDING_MODEL=jina-embeddings-v3,
  EMBEDDING_DIMENSIONS=768. El loader confirmó esos valores para un proceso nuevo.
- AGENT_LLM_PROVIDER=openrouter y modelo Dots3-Note conservados. No se habilita
  fallback a Ollama; no se construyeron clientes locales operativos.
- Tareas del adaptador intactas: retrieval.query y retrieval.passage.
- JINA_API_KEY: ausente en este proceso. Se comprueba solo booleano; podría estar
  presente en otra terminal del usuario. No se creó, imprimió, transmitió o guardó.
  El loader utiliza os.environ para la clave, ignorando claves escritas en .env.
- DOCUMENT_EXPORT_APPROVED=False permanece intacto. No se reinició FastAPI:
  un proceso ya abierto no recibe este cambio hasta un arranque posterior aprobado.

## Pruebas locales, sin API real

Ejecutadas desde backend:

```powershell
& '.\.venv\Scripts\python.exe' -B -m pytest tests/rag/test_jina_cloud.py tests/rag/test_jina_10c_storage.py tests/ia/test_dots_openrouter.py -q -p no:cacheprovider --basetemp=.pytest-tmp-10g2-20261110 --tb=short
```

**60 aprobadas, 0 fallidas, 4,43 s.** Advertencia de deprecación Starlette/HTTPX.
Incluyen aislamiento de configuración/identidad, mocks query/passage, secretos y
vectores inválidos, composición cloud que rechaza construir embeddings Ollama,
bloqueo documental anterior a SQL y contratos de Dots3-Note. No es aceptación real
de Jina ni de los 432 fragmentos. No se modificó código productivo o tests.

## Clave y arranque posterior — NO ejecutados

Usar una terminal PowerShell privada sin transcripción. No usar argumentos,
archivos, setx ni imprimir configuración completa. Entrada privada de clave:

```powershell
$jinaSecure=Read-Host 'JINA_API_KEY' -AsSecureString
$jinaPtr=[Runtime.InteropServices.Marshal]::SecureStringToBSTR($jinaSecure)
try {
    $env:JINA_API_KEY=[Runtime.InteropServices.Marshal]::PtrToStringBSTR($jinaPtr)
} finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($jinaPtr)
    $jinaSecure.Dispose()
}
if ([string]::IsNullOrWhiteSpace($env:JINA_API_KEY)) { throw 'Falta JINA_API_KEY' }
Write-Host 'JINA_API_KEY presente en este proceso'
```

La clave queda en memoria del proceso y será heredada por sus hijos, no se
persiste en archivos. OPENROUTER_API_KEY también debe estar en la misma terminal,
mediante el mecanismo privado existente. Variables de proceso EMBEDDING_* pueden
sobrescribir .env: revisar únicamente nombres/valores no secretos antes de iniciar.

Solo tras autorización posterior de arranque, sin otro backend en el puerto:

```powershell
Set-Location 'D:\Downloads\proyectos\api-usuarios-clean\backend'
$env:PYTHONPATH=(Join-Path (Get-Location) 'src')
& '.\.venv\Scripts\python.exe' -B -m app.presentation.cli.local_server --environment local-development --enable-llm --observe-llm --host 127.0.0.1 --port 8000
# Después de terminar el servidor:
Remove-Item Env:JINA_API_KEY -ErrorAction SilentlyContinue
```

No ejecutar consultas reales por iniciar el servidor. El espacio cloud todavía
no está indexado/publicado: no esperar RAG operativo; el repositorio falla cerrado
si no hay activo VALIDADA. Un futuro arranque no autoriza indexación ni levantar
el bloqueo documental. No se solicita reiniciar servicios durante esta etapa.

## Cuenta, privacidad y facturación

El usuario declara reglamento público, uso exclusivo de créditos gratuitos y
9.999.541 tokens disponibles. Son datos comunicados por el titular, no saldo
verificado mediante API/panel por este proceso. Supera orientativamente la reserva
preliminar de 200.000 tokens, pero no demuestra condiciones de licencia/retención.

El titular no encuentra opciones de facturación/recarga; **no equivale a confirmar
ausencia de medio guardado o auto-recarga deshabilitada**. No se activó facturación
ni se compraron tokens. El adaptador se detiene ante errores sin reintentos, pero
no impone un tope monetario remoto ni verifica el plan/saldo antes de cada envío.
Por ello no garantiza por sí solo consumo exclusivo de créditos gratuitos.

La revisión oficial de 10G.1 documenta declaración de no entrenamiento, remisión
a términos Elastic, retención exacta pendiente y condiciones gratuitas/comerciales
sin confirmar para la cuenta. No se volvió a consultar documentación externa en
10G.2. Que el reglamento sea público no elimina la necesidad de aceptar condiciones
del proveedor ni acredita uso comercial permitido. Ver fuentes y límites en
[10G.1](jina-cloud-10g-1.md), sección 5.

## Decisión y alcance

**GO para configuración local preparada. NO-GO para exportar/indexar ahora.**
Pendientes: clave en el ejecutor, confirmación de condiciones aplicables de cuenta,
retención y uso gratuito sin cargos, y autorización específica antes de cualquier
llamada real. La indexación necesitará además aprobar explícitamente el cambio
del bloqueo documental; no se eludirá. La activación exige autorización separada.

Archivos modificados: .env (solo tres variables no secretas) y este informe.
No se modificaron datos, migraciones, modelos, prompts o seguridad; no hubo llamadas
reales, exportación, indexación, activación, arranque/reinicio ni claves guardadas.
