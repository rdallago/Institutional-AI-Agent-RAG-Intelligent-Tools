# Sprint 10G.3 — Preparación React / FastAPI / RAG cloud

10 de noviembre de 2026. **NO-GO para una consulta RAG real desde React:** falta
indexar y publicar Jina; configuración de integración preparada sin llamadas reales.

## Arquitectura y archivos reales

`/ia` usa frontend/src/features/ia/pages/ConsultaIAPage.tsx y ConversationPanel.tsx.
El panel usa api/conversationsApi.ts y el cliente frontend/src/api/httpClient.ts.
El navegador solo admite base `/api/v1`; no contiene claves ni clientes Jina/OpenRouter.
vite.development.config.ts compone el proxy `/api` → http://127.0.0.1:8000.
La configuración Vite base apunta al entorno aislado 8001: usar explícitamente
el archivo development para desarrollo real. No se requiere CORS en este recorrido
del mismo origen mediante proxy; no se encontró middleware CORS que autorice
un navegador a acceder directamente entre 5173 y 8000. No habilitarlo por defecto.

Endpoints reales en backend/src/app/presentation/http/ia/conversaciones.py:

- POST /api/v1/ia/conversaciones: creación autenticada.
- GET /api/v1/ia/conversaciones: listado del propietario.
- GET /api/v1/ia/conversaciones/{UUID}/mensajes: historial autorizado.
- POST /api/v1/ia/conversaciones/{UUID}/mensajes: turno con prompt, modo,
  solicitud_id y documento_id opcional; devuelve identidad de solicitud/conversación,
  herramienta y resultado. React verifica estrictamente ese contrato.

El panel normal usa esas rutas; el modo diagnóstico sin historial también dispone
de POST /api/v1/ia/consultas. No confundir ambos recorridos al correlacionar evidencia.
El cliente añade Bearer de la sesión en memoria; las rutas dependen de get_current_user.
Conversations valida usuario, propietario de conversación, entrada y secretos,
recupera últimos ocho mensajes y revalida permisos documentales del historial.
El agente selecciona ruta; RAG exige versión/espacio autorizado, genera consulta
con Jina retrieval.query, busca por coseno en CloudPostgresRAG con ACL y entrega
contexto a OpenRouter/Dots3-Note. Las afirmaciones/citas se validan antes de publicar.
React muestra respuesta y fuentes/páginas recibidas; no construye evidencias nuevas.

## Estado READ ONLY y ausencia de índice

Se confirmó usuarios_dev/127.0.0.1:5434, transaction_read_only=on, revisión
0006_cloud_embeddings y cero filas en las cuatro tablas cloud. Rollback al terminar.
Configuración efectiva de proceso nuevo: jina, jina-embeddings-v3, 768; clave ausente
en este proceso. No se inspeccionaron mensajes/usuarios privados. El proceso actual
de FastAPI no fue reiniciado: no se afirma que ya cargó la nueva configuración.

CloudPostgresRAG.require_active exige puntero al espacio configurado e ingesta
VALIDADA; sin ello lanza IANoDisponible antes de la consulta embedding en ese
recorrido. No cae a Nomic/Ollama. La capa HTTP lo representa como 503,
IA_NO_DISPONIBLE. El panel de conversaciones muestra:
«El proveedor o servicio no está disponible. No se inventaron datos.»
Es genérico: no identifica específicamente ausencia de índice. Tampoco debe
presentarse como HTTP 200/SIN_EVIDENCIA o fallo de citas.

Además, abrir un historial RAG anterior revalida sus documentos usando el espacio
operativo actual. Mientras no haya activo Jina puede fallar la carga y mostrar
«No pudimos recuperar el historial autorizado». No implica pérdida de PostgreSQL.
No usar historiales antiguos para diagnosticar generación antes de publicar Jina.

## Pruebas y alcance

Backend, sin servicios ni inferencia real:

```powershell
Set-Location 'D:\Downloads\proyectos\api-usuarios-clean\backend'
& '.\.venv\Scripts\python.exe' -B -m pytest tests/rag/test_jina_cloud.py tests/rag/test_jina_10c_storage.py tests/ia/test_dots_openrouter.py tests/ia/test_http_ia.py -q -p no:cacheprovider --basetemp=.pytest-tmp-10g3 --tb=short
```

**104 aprobadas, 0 fallidas, 5,94 s**, advertencia Starlette/HTTPX. Incluye Jina y
OpenRouter con MockTransport, ausencia de índice fail-closed, composición sin
cliente embeddings Ollama y contrato HTTP FastAPI con autenticación simulada.
Los tests HTTP usan dependencias de prueba, no una base real ni cuentas existentes.

Frontend: comando local preparado/ejecutado con MSW, sin servicios externos:

```powershell
Set-Location 'D:\Downloads\proyectos\api-usuarios-clean\frontend'
& 'C:\Program Files\nodejs\node.exe' node_modules/vitest/vitest.mjs run src/features/ia/ia.test.tsx src/api/httpClient.test.ts --maxWorkers=1
```

Resultado frontend: **58 aprobadas, 0 fallidas, 2 archivos, 90,00 s**, exit code 0.
La suite cubre respuestas RAG/citas, contratos inválidos,
401/403, red, 503, sesión y ausencia de reintentos automáticos. MSW sustituye el
servidor: no es React conectado a FastAPI real. Las capas verificadas por separado
NO constituyen una prueba E2E conjunta ni prueba de servicios cloud reales.

No se identificó un defecto demostrado que requiera cambios productivos para
esta preparación. Existen textos heredados Qwen/Ollama en errores específicos del
panel; documentar esa limitación de presentación, sin confundirlos con proveedor
efectivamente invocado. No se modificaron mensajes o contratos en esta intervención.

## Arranque posterior desde terminales VS Code — NO ejecutado

Primero resolver indexación/publicación, credenciales privadas en memoria y
autorización de arranque. No iniciar una segunda instancia en puertos ocupados.
Introducir JINA_API_KEY y OPENROUTER_API_KEY mediante entrada privada siguiendo
10G.2, sin .env, setx, argumentos o transcripciones. No ejecutar peticiones al
arrancar. No detener el backend ya abierto sin autorización específica.

Terminal backend:

```powershell
Set-Location 'D:\Downloads\proyectos\api-usuarios-clean\backend'
$env:PYTHONPATH=(Join-Path (Get-Location) 'src')
& '.\.venv\Scripts\python.exe' -B -m app.presentation.cli.local_server --environment local-development --enable-llm --observe-llm --host 127.0.0.1 --port 8000
```

Terminal frontend:

```powershell
Set-Location 'D:\Downloads\proyectos\api-usuarios-clean\frontend'
& 'C:\Program Files\nodejs\node.exe' node_modules/vite/bin/vite.js --config vite.development.config.ts --host 127.0.0.1 --port 5173 --strictPort
```

URL: http://127.0.0.1:5173/ia. Iniciar sesión con cuenta autorizada; después de
la publicación crear una conversación de aceptación independiente. Preguntas
iniciales: funciones del Rectorado (artículo 24), requisitos de coordinación
(artículo 52), una por vez. Registrar request ID, versión/fuentes/páginas,
respuesta, soporte documental y cobertura por separado; no reenviar automáticamente.

## Plan documental previo — no ejecutar ahora

1. Resolver condiciones de retención/cuenta, derechos de exportación y uso permitido.
   El usuario declara documento público y 9.999.541 tokens gratuitos; no es una
   verificación contractual ni de facturación. No encontrar controles de recarga
   no prueba que estén deshabilitados. Ver límites/evidencias de 10G.1 y 10G.2.
2. Obtener permiso para levantar el bloqueo documental y enviar el primer fragmento
   público. Hoy DOCUMENT_EXPORT_APPROVED=False; no usar bypass. Confirmar clave
   del proceso sin imprimirla, saldo, fingerprint, base/versión y ausencia de ingesta.
3. Piloto mediante CLI existente, --action index --max-chunks 1, owner ADMIN
   propietario autorizado y versión 7cb4e79c-747d-574a-8abb-0ebcb2e07636. No se
   crea aquí comando con identidad supuesta. Una llamada HTTP y checkpoint SQL.
4. Revisar dimensión, finitud, norma, hashes y checkpoint del piloto; sin puntero
   activo. Autorizar continuación de hasta 9, luego lotes secuenciales de hasta 10.
   432 fragmentos significan 432 POST si no hay fallos, no 44 llamadas batch.
5. HTTP/red/cuota/RAM/SQL inválido: detener sin reintento, conservar confirmados.
   Una llamada incierta puede consumir cuota sin checkpoint. Reanudar solo tras
   revisar pendientes y autorización, sin cambiar modelo/identidad.
6. Validar 432 vectores con hashes de entradas/páginas, offsets y norma; cero
   faltantes/contradicciones, ACL correctas, versión activa y Nomic preservados.
   validate escribe VALIDADA pero no activa; requiere autorización.
7. Pedir publicación separada: activate repite validación bajo lock y cambia
   puntero cloud en la misma transacción. No indexar o activar mediante SQL manual.
8. Solo después, arranque aprobado, controles HTTP y prueba React autenticada
   real con recursos suficientes. No presentar mocks como aceptación funcional.

## Decisión

**NO-GO para RAG real desde React en el estado actual.** Tablas cloud vacías,
sin espacio activo y clave ausente en el proceso auditado. Persisten condiciones
de privacidad/facturación y autorización documental; no se solicita ejecutar una
consulta que todavía no puede funcionar. GO para revisar esta preparación y
resolver esos pendientes antes de autorizar un piloto.

No se cambió .env, código, migraciones, guardas o datos históricos. No se
reiniciaron servicios ni se hicieron llamadas reales, indexación o activación.
