# Preparación final con Dots3-Note

Estado: APTO PARA ACEPTACIÓN AUTOMATIZADA LOCAL; aceptación funcional real PENDIENTE.

Modelo solicitado: `dots-studio/dots-3-note-preview:free`. El sufijo se conserva
para cumplir el contrato gratuito; el identificador devuelto puede omitirlo.
Proveedor restringido: `atlas-cloud`, sin fallback. Catálogo y POST mantienen
precio cero, parámetros obligatorios y `data_collection=deny`. La comprobación
del catálogo exige que el endpoint compatible pertenezca a AtlasCloud.

Pruebas locales: 116 aprobadas; un aviso preexistente Starlette/TestClient.
Incluyen transporte OpenRouter, esquemas operativos del planificador y RAG,
contratos defectuosos, fuentes desconocidas, soporte documental, memoria,
diagnóstico privado y cliente de aceptación. Sin inferencias reales.

El único cambio persistente de configuración selecciona OpenRouter y Dots3-Note.
La clave sigue viniendo del entorno del proceso, nunca del informe. No cambia
la guarda, Nomic, su espacio, los 432 embeddings ni PostgreSQL. Ollama queda
necesario exclusivamente para embeddings; ningún error remoto activa generación local.

## Preparación operativa pendiente

No se iniciaron ni reiniciaron servicios. FastAPI necesita un reinicio controlado
para cargar el cambio. Su arranque debe mostrar OpenRouter y el modelo gratuito.
Reutilizar el lanzador existente, con `--environment local-development --enable-llm
--observe-llm --host 127.0.0.1 --port 8000`. La clave debe estar en esa terminal.
Configurar en ese proceso el directorio privado restringido existente y
`AGENT_PRIVATE_CAPTURE_RAG_JSON=true`; no usar directorios públicos ni relajar ACL.

Antes de la batería comprobar PostgreSQL usuarios_dev, versión activa
7cb4e79c-747d-574a-8abb-0ebcb2e07636, 432 embeddings, Ollama con Nomic instalado
y sin modelos cargados. El cliente verifica estos requisitos y recursos.
No se ha comprobado aquí el estado vivo de esos servicios.

## Comando de aceptación (no ejecutado)

Desde PowerShell interactivo, con los servicios preparados y el directorio
coincidente con el del servidor:

```powershell
Set-Location 'D:\Downloads\proyectos\api-usuarios-clean'
$env:AGENT_LLM_PROVIDER='openrouter'
$env:OPENROUTER_MODEL='dots-studio/dots-3-note-preview:free'
& '.\backend\.venv\Scripts\python.exe' -B '.\infra\acceptance_agent.py' --diagnostic-dir 'D:\Downloads\api-usuarios-clean-backups\93e-20261103\agent-final-20261107-113501-255e2678'
```

El directorio es el documentado previamente: debe seguir existiendo, ser privado
y corresponder al proceso actual. No se creó ni validó de nuevo en esta intervención.
El cliente solicita credenciales ocultas, ejecuta los 15 escenarios secuencialmente
y genera un informe privado. No reutilizar un checkpoint antiguo de otro proveedor
sin revisar sus solicitudes enviadas; un inicio nuevo crea conversaciones nuevas.

La ejecución real crea conversaciones y mensajes mediante los endpoints normales:
no se realizó durante esta preparación. El reinicio de FastAPI durante la fase
de persistencia es manual y verificado. No detener PostgreSQL.

Para reanudar esta misma batería, añadir `--resume` con su informe.json; nunca
reenviar solicitudes fallidas o inciertas automáticamente.

## Límites de aceptación

HTTP 200 con esquema mínimo no certifica los esquemas completos, calidad semántica
ni cobertura. Revisar artículos 24/52, memoria, clima, general, alternancia,
aislamiento y persistencia. La cobertura RAG puede ser parcial y debe declararse.
La privacidad efectiva depende también del routing y ajustes de la cuenta;
un rechazo de política se conserva, sin relajar deny. AtlasCloud no se presenta
como retención cero. Capacidad gratuita y red pueden bloquear la batería.

No declarar aceptación integral aprobada hasta ejecutar y revisar el informe real.
