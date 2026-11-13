# Cliente local de aceptación del agente

El cliente es `infra/acceptance_agent.py`. Usa exclusivamente HTTP real a FastAPI
en 127.0.0.1:8000, comprobaciones de metadatos PostgreSQL READ ONLY y consultas
de estado de Ollama en 127.0.0.1:11434. No usa mocks al ejecutarse normalmente.
No cambia la implementación ni la configuración del proyecto.

## Antes de ejecutarlo

- Abrir PowerShell normal e interactivo en `D:\Downloads\proyectos\api-usuarios-clean`.
  No usar una consola compartida, transcripción de PowerShell, redirección de entrada
  ni grabación de pantalla para introducir credenciales.
- Dejar FastAPI iniciado con el lanzador local del proyecto, local-development,
  `--enable-llm --observe-llm`, modelo `qwen2.5:1.5b`, y las variables privadas
  ya preparadas. No cambia `.env` ni desactiva guardas.
- Mantener PostgreSQL usuarios_dev disponible en 127.0.0.1:5434. Se exige la versión
  `7cb4e79c-747d-574a-8abb-0ebcb2e07636`, LISTA, con 432 fragmentos/embeddings.
- Mantener Ollama iniciado y sin modelos cargados. El cliente no instala modelos ni
  fuerza su descarga de memoria. No usar simultáneamente React, otra batería o una ingesta.
- El directorio de diagnóstico debe ser el del proceso FastAPI y estar protegido
  para propietario y SYSTEM, con herencia deshabilitada. La captura RAG debe seguir
  habilitada. El cliente no modifica esos permisos ni variables del servidor.

## Ejecutar en Windows

Para verificar únicamente la creación de un directorio privado y su checkpoint,
sin autenticación, HTTP, PostgreSQL ni Ollama, agregar `--initialize-only` al comando.
Ese modo también funciona sin consola interactiva y conserva un informe con todas
las consultas NO EVALUADAS. Para usarlo después, reanudar ese informe con `--resume`.

En Windows los directorios nuevos se crean con `CreateDirectoryW` y una DACL
protegida explícita para el SID del usuario y SYSTEM, aplicada desde la creación.
No se usa `mkdir(mode=0700)` de Python, que puede agregar Administradores y OWNER
RIGHTS. Se ejecuta el mismo validador estricto después de crear. Si rechaza una ruta,
el mensaje identifica esa ruta y el motivo ACL; no muestra contenido de archivos.

```powershell
Set-Location 'D:\Downloads\proyectos\api-usuarios-clean'
& '.\backend\.venv\Scripts\python.exe' -B '.\infra\acceptance_agent.py' --diagnostic-dir 'D:\Downloads\api-usuarios-clean-backups\93e-20261103\agent-final-20261107-113501-255e2678'
```

Ingresar primero el email y la contraseña de ADMIN y luego los del usuario común.
**Ambos campos se solicitan con entrada oculta.** No pasarlos por argumentos,
archivos, chat ni variables de entorno. Si no existe entrada privada, se detiene.
`/auth/me` debe devolver el email, rol, estado activo e identidad esperados. Si se
requiere cambio de contraseña, se detiene sin modificarla. En una reanudación
exige los mismos UUID de usuario; no sustituye cuentas ni otorga permisos.

Se crearán cinco conversaciones de ADMIN y una del usuario común, como máximo,
mediante los endpoints existentes. Se identifican en el informe como
`ACEPTACION <run> <usuario>:<grupo>` y por UUID. El contrato no permite títulos:
no introduce mensajes de marcador ni modifica historiales previos para etiquetarlas.

La matriz incluye los artículos 24 y 52, memoria del Rectorado, clima actual/mañana,
API REST/ejemplo FastAPI y alternancia RAG → clima → general → RAG. Si el usuario
común no tiene el ROM en su catálogo autorizado, su prueba académica se marca
BLOQUEADA, sin cambiar permisos. Una prueba dependiente de un antecedente fallido
no se anuncia como ejecutada.

## Recursos y detención

- Una petición a la vez; mutex local impide dos clientes simultáneos.
- RAM física mínima de 1,5 GiB y Ollama idle antes de cada turno. La RAM vuelve a
  medirse inmediatamente antes del envío. Se mantienen las guardas del servidor.
- Espaciado preventivo de 13 segundos entre comienzos de turnos. No es un reintento
  ni cambia cuotas. Otros clientes pueden consumirlas: un 429 queda registrado.
- Timeout HTTP de 70 segundos; errores nunca se reenvían automáticamente.
- Ctrl+C conserva los checkpoints. No mata modelos ni otros servicios. El timeout
  del cliente no garantiza detener cómputo remoto: comprobar Ollama antes de continuar.

## Informe y reanudación

Al empezar muestra una ruta como:

```text
D:\Downloads\proyectos\api-usuarios-clean\.acceptance-private\run-<UUID>\informe.json
```

El subdirectorio se crea nuevo con ACL restringida; los checkpoints se reemplazan
atómicamente dentro de él. El informe es privado: contiene respuestas y preguntas
de esta batería, UUID, roles, HTTP, canales, citas, RAM, tiempos, estado y motivos.
No contiene emails, contraseñas, tokens o encabezados Authorization. Se omiten
patrones conocidos de secretos; no existe un detector universal de contenido sensible.
No compartir el informe completo sin revisarlo.

Para reanudar **la misma** ejecución, usar la ruta que mostró, no lanzar otra batería:

```powershell
& '.\backend\.venv\Scripts\python.exe' -B '.\infra\acceptance_agent.py' --resume '.\.acceptance-private\run-<UUID>\informe.json' --diagnostic-dir 'D:\Downloads\api-usuarios-clean-backups\93e-20261103\agent-final-20261107-113501-255e2678'
```

- UUID de conversación persistido antes de crearla; creación idempotente si se
  interrumpió esa operación. No duplica conversaciones al reanudar.
- Clave de solicitud persistida antes del POST del turno. Las solicitudes ya enviadas,
  completas o fallidas, **no se vuelven a enviar**.
- Un bloqueo por RAM antes de enviar puede continuar al reanudar. Un envío INFLIGHT
  o de resultado incierto requiere revisión de esa clave y no se repite. El cliente
  no modifica estados PENDIENTE/FALLIDA ni los resuelve por la fuerza.
- Los tokens no sobreviven al proceso. Se vuelve a autenticar interactivamente.
  Python no garantiza borrado criptográfico de cadenas en RAM; no se persisten.

El informe asocia diagnósticos mediante `request_id`; conserva ruta y metadatos,
sin duplicar el JSON literal privado. Directorio lleno (máximo existente: 64 archivos),
diagnósticos ausentes o ilegibles se informan como evidencia faltante. El cliente
no elimina archivos para hacer lugar. Si FastAPI cambia de directorio al reiniciarse,
usar ese nuevo destino en la siguiente reanudación.

## Logout/login y reinicio

Concluidos los turnos se recuperan por HTTP los historiales de las conversaciones
creadas y se guardan sus hashes y cantidades. Se verifica que ninguno aparezca en
el listado del otro usuario y que acceder a sus UUID devuelva **403**, en ambos
sentidos, incluido ADMIN intentando leer al usuario común. No se copian historiales
anteriores de los usuarios al informe.

Después se hace logout real, se solicitan otra vez las credenciales y se comparan
los historiales. PostgreSQL se consulta READ ONLY: propietario, mensajes y estados
COMPLETA/PENDIENTE/FALLIDA de las conversaciones de esta batería; no se leen hashes
de contraseñas ni sesiones de terceros. El conteo SQL debe coincidir con HTTP.

Finalmente pide reiniciar **manualmente solo FastAPI**. Usar Ctrl+C en su terminal
verificada y relanzar con el mismo lanzador, argumentos y entorno de diagnóstico.
No detener PostgreSQL ni cambiar configuración. Escribir `REINICIADO` en el cliente.
Se comprueba cambio de PID/fecha de inicio, pertenencia al proyecto y se recuperan
otra vez los historiales autenticados. Enter sin confirmación detiene conservando
el checkpoint. No envía señales a procesos automáticamente. Si la sesión vence,
reanudar: pide autenticación nueva sin repetir turnos.
Si FastAPI está en una consola oculta o no se puede comprobar su identidad, no
terminar procesos a ciegas: pulsar Enter, solicitar el reinicio exclusivo y reanudar.
El checkpoint conserva la identidad anterior para reconocer el reinicio ya realizado.

## Qué significa el resultado

`APROBADO` por fila significa que pasó el criterio **automático técnico**: contrato,
canal/estado esperado, referencias publicadas para RAG o recuerdo de Rectorado para
memoria. No demuestra por sí solo exhaustividad, exactitud de un ejemplo de código,
entailment semántico ni ausencia de llamadas internas innecesarias. Leer las respuestas
y los diagnósticos antes de cerrar la aceptación. El resumen conserva esa revisión pendiente.

El contrato HTTP no expone la decisión regla/Qwen, el nombre de la capacidad RAG,
ni el número de inferencias internas. Esos campos se declaran NO DETERMINABLES cuando
los diagnósticos no los prueban; no se inventan a partir de la estrategia final.
`herramienta` conserva el valor público real (clima o null). Los diagnósticos RAG
sí permiten comparar fuentes, hashes, afirmaciones y motivos por solicitud.

`FALLIDO`: respuesta/canal/contrato no satisface el criterio. `BLOQUEADO`: recursos,
sesión, permisos o dependencia impidieron la comprobación. `NO EVALUADO`: no se envió.
Un error de transporte puede haber completado en servidor: se identifica como incierto.

## Pruebas del cliente sin servicios

```powershell
Set-Location '.\backend'
& '.\.venv\Scripts\python.exe' -B -m pytest tests/acceptance/test_local_client.py -q -p no:cacheprovider
```

Estas pruebas usan únicamente dobles en memoria; no ejecutan la batería real,
no hacen login ni consultan PostgreSQL u Ollama.
