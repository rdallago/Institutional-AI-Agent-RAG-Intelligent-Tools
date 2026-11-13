# Sprint 9.2.5A: diagnóstico de preparación para piloto Ollama

Fecha: **2 de noviembre de 2026**, mediciones alrededor de las **11:16 -03:00**.
Alcance: inspección de lectura y propuesta. **NO APTO en el estado actual** para
iniciar la primera inferencia. No se habilitó IA ni se realizó 9.2.5B.

## 1. Dictamen

El modelo candidato existe y Ollama responde en loopback. El código en disco
incluye las capas de IA aprobadas, pero hay tres bloqueos para el piloto:

1. Memoria física disponible entre **829 MiB y 1,031 GiB** en dos muestras:
   margen reducido para cargar el modelo junto al resto de aplicaciones.
2. El lanzador local existente no proporciona **LocalLLMContext**. Habilitar
   solamente LLM_ENABLED haría fallar la validación de arranque del código actual.
3. El backend actualmente servido responde, pero **no publica el endpoint IA en
   OpenAPI**. Es necesario preparar y autorizar un arranque con la composición nueva.

No se recomienda intentar generación para averiguar si alcanza la memoria.
La aprobación de pruebas aisladas no acredita disponibilidad operativa ni rendimiento.
El dictamen puede revisarse después de resolver estos controles; no requiere
descargar otro modelo ni desactivar protecciones.

## 2. Recursos medidos

| Recurso | Observación actual |
| --- | --- |
| RAM física total visible | **7,851 GiB** |
| RAM física disponible, primera muestra | **829,1 MiB**, carga de memoria 89 % |
| RAM física disponible, segunda muestra | **1,031 GiB**, variable |
| Memoria comprometida global, segunda muestra | **20,646 GiB** |
| Límite de compromiso global | **29,015 GiB** |
| Pico de compromiso informado por Windows | **26,161 GiB**, no atribuido a esta inspección |
| C: libre / capacidad | **44,47 / 155,43 GiB** |
| D: libre / capacidad | **111,40 / 309,59 GiB** |

Se usaron GlobalMemoryStatusEx y GetPerformanceInfo mediante ctypes del Python
existente, y shutil.disk_usage. El compromiso incluye memoria respaldada por
memoria virtual: **no equivale a RAM física libre**. Espacio de disco o margen de
compromiso no compensan automáticamente el coste de paginación de una inferencia.
Son muestras puntuales, sin benchmark ni medición de latencia o CPU bajo inferencia.

Procesos con mayor working set en la muestra, sin inspeccionar títulos de ventana,
documentos, argumentos completos o contenido de usuario:

| PID | Proceso | Working set MiB | Private bytes MiB |
| --- | --- | ---: | ---: |
| 9100 | chrome | 501,5 | 677,0 |
| 12776 | vmmem | 463,5 | 3999,0 |
| 1736 | Code | 459,0 | 689,3 |
| 16040 | Code | 376,8 | 502,3 |
| 33016 | chrome | 278,8 | 379,7 |
| 1924 | chrome | 226,9 | 229,5 |
| 24644 | chrome | 223,0 | 259,6 |
| 10684 | chrome | 202,9 | 260,2 |
| 6068 | MsMpEng | 196,2 | 355,5 |
| 10324 | chrome | 173,3 | 384,7 |
| 3528 | Code | 144,3 | 792,0 |
| 11592 | chrome | 139,7 | 188,5 |

Working set puede incluir páginas compartidas; sumar esta tabla no da la RAM
exclusiva consumida. Private bytes tampoco representa exclusivamente memoria residente.
No se detuvo ninguno de estos procesos; no se recomienda terminar vmmem, Docker,
PostgreSQL o protección del sistema para forzar el piloto.

### Limitaciones de inspección

Las consultas WMI/CIM de sistema, memoria y discos devolvieron **Acceso denegado**.
Sus resultados vacíos/cero se descartaron; las cifras anteriores proceden de las
APIs nativas de lectura alternativas. No se solicitó elevación, modificaron permisos
ni instalaron herramientas. No se obtuvo una revalidación actual de líneas de
comando o relación padre/hijo mediante CIM. Los antecedentes documentales no
sustituyen esa comprobación antes de intervenir sobre un proceso.

## 3. Ollama y modelos

Ejecutable localizado en la instalación convencional del usuario y PATH.
Los campos FileVersion/ProductVersion del archivo no aportaron versión; el servicio
existente informó **0.40.7** mediante GET `/api/version`.

Se hicieron exclusivamente GET de metadatos `/api/version`, `/api/tags` y `/api/ps`
contra **http://127.0.0.1:11434**, sin proxies del entorno, con timeout de 3 s.
No se invocaron generate/chat, run, pull, load/unload ni operaciones administrativas.

| Modelo local | Tamaño en disco observado |
| --- | ---: |
| qwen2.5:1.5b | **986061892 bytes**, aproximadamente 940 MiB |
| qwen3:1.7b | 1359293444 bytes |
| nomic-embed-text:latest | 274302450 bytes |

Digest observado del candidato:
`65ec06548149b04c096a120e4a6da9d4017ea809c91734ea5631e89f96ddc57b`.
Es un identificador público del modelo, no un hash de credenciales.
El modelo configurado coincide exactamente con el tag instalado.
GET `/api/ps` devolvió **cero modelos cargados**. No se midió su coste de ejecución,
tokenización o done_reason; existencia en disco no demuestra inferencia compatible.

## 4. Puertos, procesos y aplicación servida

Inventario TCP mediante netstat, sin peticiones autenticadas:

| Puerto | Listener observado | PID / identidad básica |
| --- | --- | --- |
| 11434 | **127.0.0.1** | **228**, ollama; inicio 27/10/2026 17:52:24 local |
| 8000 | **127.0.0.1** | **25604**, python; inicio 01/11/2026 18:47:44 local |
| 8001 | Sin listener observado | No se presume instancia de pruebas |
| 5173 | **127.0.0.1** | **12376**, node; inicio 01/11/2026 16:32:00 local |

También se observó Python **31616**, misma hora de inicio que 25604, cuyo ejecutable
pertenece a `backend/.venv/Scripts/python.exe` del workspace. El ejecutable de 25604
es `C:/Python314/python.exe`; Node corresponde a su instalación general.
El informe 8.6D registra el lanzador local con opt-in de aprovisionamiento para
estos procesos. **No se certificaron nuevamente sus argumentos ni parentesco**;
esa atribución detallada es antecedente, no una lectura actual de memoria del proceso.

GET `http://127.0.0.1:8000/openapi.json`: **200**, sin POST
`/api/v1/ia/consultas` en el documento servido. Solo se imprimieron estado y un
booleano de presencia, nunca el documento completo. Esto verifica que la API
servida aún no anuncia la integración actual; no se probó POST a una ruta ausente.

GET `http://127.0.0.1:5173/login`: **200**, entrada HTML con raíz React.
No equivale a un recorrido de navegador autenticado o prueba de generación.
No se efectuaron login, auth/me, consultas de usuarios o peticiones a PostgreSQL.

## 5. Arquitectura y configuración verificadas por lectura

- `configuration/llm.py`: LLM_ENABLED acepta true/false estrictos; false por
  defecto. LLM_ENVIRONMENT selecciona local-development; habilitación operativa
  en production/test inapropiados se rechaza. Carga `.env` y overrides LLM_* de
  proceso sin interpolación; TEST_LLM_* queda separado.
- Carga actual mediante `load_llm_config()`, sin abrir red: configuración válida,
  **enabled=false, environment=disabled**, modelo qwen2.5:1.5b, URL literal
  http://127.0.0.1:11434, timeout 60 s. Solo se mostraron campos LLM permitidos;
  no se imprimió `.env`, JWT, claves ni valores de autenticación. Describe un
  proceso nuevo de inspección; no demuestra el entorno privado del servidor activo.
- `configuration/llm_local.py`: LocalLLMContext debe contener el socket real y
  workers=1; exige AF_INET, dirección exactamente 127.0.0.1 y SO_ACCEPTCONN=1.
  WEB_CONCURRENCY debe estar ausente o ser exactamente 1. En el proceso de
  inspección está ausente, sin inferir su valor dentro de otro proceso.
- `bootstrap.py`: valida ese contexto antes de componer persistencia, abre un
  único ollama_runtime mediante AsyncExitStack en lifespan y comparte proveedor,
  admisión y caso de uso en app.state. Cierra runtime y dispone engine al salir.
  Deshabilitada usa DisabledLLMProvider sin cliente Ollama.
- `presentation/cli/local_server.py`: crea socket loopback, lo pasa a Uvicorn,
  desactiva proxy_headers/access_log y no configura reload o workers adicionales.
  **No construye ni pasa llm_local_context a create_app**. La opción
  --environment actual corresponde al lanzador/aprovisionamiento; no reemplaza
  automáticamente LLM_ENVIRONMENT.
- No se encontró otro llamador operativo que proporcione LocalLLMContext en
  backend/src. La validación de workers/contexto protege la composición, pero
  no constituye una exclusión global de otros procesos/clientes Ollama del equipo.
- React usa el transporte autenticado existente y `/api/v1/ia/consultas`.
  `vite.development.config.ts` compone el proxy `/api` a **127.0.0.1:8000**;
  `vite.config.ts` conserva **8001** para aislamiento. Ambos fijan host loopback y
  puerto estricto 5173. Se verificó código en disco, no argumentos efectivos de
  Node; no se alteró el proxy ni se afirmó una cadena autenticada ya comprobada.

Los resultados previos **665 backend / 162 PostgreSQL omitidas** y **189 frontend**
son antecedentes aprobados; no se ejecutaron tests, build ni suites en 9.2.5A.

## 6. Seguridad y memoria

El adaptador solo envía prompt, instrucción fija, modelo y presupuestos a la URL
literal loopback. No transmite Principal, JWT, roles o perfiles. HTTPX ignora
proxies de entorno, rechaza redirecciones y elimina Authorization/Cookie upstream.
React no llama directamente a Ollama. No se requieren CORS abiertos ni exposición
LAN, túneles, firewall nuevo o servidor público.

El endpoint y el caso de uso conservan autorización normal antes y después de
generar; sesiones pendientes no acceden. Admisión compartida: **1 concurrente,
5 por usuario/minuto y 15 globales/minuto**, contadores acotados a 1024 usuarios,
sin espera de cupo, con enfriamiento de 30 s por timeout. Son controles por proceso,
no distribuidos. Mantener un worker real y evitar otros clientes generando a la vez.

Presupuestos: contexto 4096, salida 256 tokens, deadline backend 60 s, espera UI
70 s, cuerpo upstream limitado a 64 KiB. No hay tools, comandos, datos privados
como contexto, conversaciones persistentes o persistencia de prompts/respuestas.
La UI trata salida como texto y limpia al salir. No se afirma haber auditado todos
los logs/retención de Ollama o del sistema; revisar su configuración sin registrar
contenido antes del piloto. No habilitar trazas HTTP ni logs de cuerpos para medirlo.

Con menos de 1,1 GiB disponible y memoria comprometida muy superior a la física,
existe riesgo de paginación, latencia alta, timeout o presión sobre servicios ya
abiertos. Los 940 MiB del archivo no representan memoria total de ejecución:
se añaden contexto, runtime y otras asignaciones. No se certificó aceleración GPU.

Alternativas no destructivas, a decidir por el responsable: guardar trabajo y
cerrar manualmente pestañas/aplicaciones no esenciales que reconozca, elegir una
ventana de menor carga o posponer a un equipo con más margen. Repetir mediciones
con FastAPI/PostgreSQL/React presentes. Como control inicial conservador, recuperar
al menos **2 GiB físicos disponibles**, criterio propuesto en 9.1 y sujeto a
medición; no garantiza suficiencia. No vaciar cachés, cambiar pagefile, cerrar
servicios del sistema ni sustituir/descargar modelos sin otra decisión.

## 7. Propuesta 9.2.5B — NO ejecutada

### Observaciones previas de lectura

1. Repetir RAM física/compromiso, top de procesos, discos, listeners e identidad
   de procesos. Resolver la limitación para revalidar argumentos/padres antes de
   detener algo; nunca actuar únicamente por PID histórico o puerto.
2. Confirmar Ollama loopback, versión, digest/tag y cero generaciones de otros
   clientes. Si no responde, registrar y pedir al responsable su inicio local
   únicamente dentro del alcance operativo aprobado; no autoarrancarlo desde IA.
3. Revisar configuración de logs, presupuesto, modelo y estado de servicios.
   No consultar contenido personal ni extraer credenciales para probar autenticación.

### Intervención operativa y cambio mínimo sujetos a autorización

4. Implementar/revisar una composición local explícita que entregue a create_app
   `LocalLLMContext(listener=el_mismo_socket_servido, workers=1)` y LLMConfig
   habilitada local-development. **Hace falta un cambio de código del lanzador o
   composición confiable; no basta modificar configuración.** Probarlo aislado
   antes de reiniciar. No fabricar sockets de prueba como prueba del servidor real,
   omitir require_local_runtime o habilitar automáticamente aprovisionamiento.
5. Preferir opt-in explícito por proceso y configuración inmutable inyectada;
   conservar el arranque normal deshabilitado y no editar persistentemente `.env`
   como atajo. Si se aprueba el mecanismo LLM_* por proceso, limitarlo a la nueva
   instancia y validar LLM_ENVIRONMENT=local-development. Elegir un mecanismo
   revisado, no dejar overrides permanentes o herencia accidental a tests.
6. Coordinar mantenimiento; revalidar identidad y detener solo backend propio
   autorizado, iniciar un único servidor en 127.0.0.1:8000 sin reload, workers
   adicionales, proxy externo o cabeceras confiadas. Mantener React si su proxy
   efectivo es el correcto. Confirmar socket real, worker y OpenAPI IA nuevo.
   Las verificaciones de destino/revisión de desarrollo para ese arranque deben
   quedar expresamente cubiertas: este diagnóstico no accedió a PostgreSQL.
7. Usar Ollama ya presente. Si está detenido, su arranque manual local requiere
   autorización; no descargar modelos, alterar OLLAMA_HOST o servicios por inercia.

### Primera inferencia, medición y cadena completa

8. Con margen de RAM recuperado, aprobar una sola consulta sintética, por ejemplo
   «Explicá en dos frases qué es una API REST», sin datos de usuarios. Definir antes
   cómo observar únicamente metadatos de protocolo de esa generación: status,
   done y done_reason, duración y tamaños, sin volcar prompt/respuesta/cabeceras.
   La API pública devuelve finalizacion, no done_reason: inferir el campo upstream
   solo desde la pantalla no basta. Preparar un observador opt-in revisado, sin
   logging de cuerpos ni endpoint diagnóstico público.
9. Verificar stop → completa y length → limite. Ausente/desconocido mantiene el
   rechazo 502 actual; documentar y parar, no introducir un default o relajar
   validación sobre la marcha. Si se aprueba una sonda directa aislada antes de
   React, tratarla como una inferencia adicional explícita, nunca automática.
10. Registrar reloj monotónico de inicio/fin, latencia total/fría, RAM disponible,
    compromiso y working set de Ollama/proceso de modelo antes, durante y después;
    anotar timeout, presión de memoria y descarga posterior, sin guardar contenido.
    No prometer que keep_alive=0 borra memoria de forma segura. Detener el piloto
    ante paginación intensa, pérdida de margen o degradación de los otros servicios.
11. Responsable introduce personalmente credenciales en React; probar `/ia` y
    React → FastAPI → Ollama con consulta no sensible, resultado/finalización y
    estados HTTP. No compartir JWT/credenciales ni extraer sesión del navegador.
    Logout y rutas protegidas deben conservar comportamiento. No crear usuarios
    para esta prueba ni mezclar un proveedor falso con evidencia de inferencia real.
12. Evaluar cancelación con autorización separada para esa llamada adicional;
    cerrar HTTP no garantiza detener cómputo. No reintentar automáticamente tras
    timeout o resultado incierto; si el cálculo persiste, detener nuevas admisiones
    del piloto y revisar supervisión antes de ampliar uso.

### Reversión y condiciones de parada

13. Revalidar y detener solo la instancia IA propia; reiniciar mediante arranque
    normal con configuración IA deshabilitada, sin opt-in de IA. Retirar solo
    overrides temporales acordados y confirmar configuración/no cliente Ollama.
    Mantener intactas JWT, bases, roles y barrera de aprovisionamiento; su estado
    no se cambia como parte de la habilitación o reversión de IA.
14. Deshabilitar IA en FastAPI no obliga a detener Ollama existente: no terminarlo
    si pertenece a otros usos. Cualquier apagado del servicio debe estar autorizado
    y con identidad revalidada. No descargar modelos, borrar datos o hacer downgrade.
15. Parar ante destino/socket/worker incorrectos, modelo/digest inesperado, falta
    de RAM, reconexiones/otros generadores, errores de arranque, protocolo inválido
    o fuga en logs. Conservar evidencia saneada y diagnosticar antes de modificar.

## 8. Alcance efectivamente cumplido y detención

Único archivo creado: este informe. Se hicieron lecturas de código/configuración
LLM, inventarios de recursos/puertos/procesos y GET de metadatos/HTML/OpenAPI.
Las comprobaciones no precisaron DB ni autenticación; no se accedió a usuarios_dev,
usuarios_test, tablas, hashes, perfiles, sesiones o secretos JWT.

No se instalaron paquetes, modificaron backend/React/configuración operativa,
reiniciaron o detuvieron servicios, cambiaron permisos/firewall/pagefile, ejecutaron
tests/migraciones, descargaron/cargaron modelos ni enviaron consultas al LLM.
La inspección de configuración procesó el archivo local en memoria sin imprimir
sus demás valores. El listener Ollama y los servicios existentes se conservaron.

**Diagnóstico finalizado: NO APTO actualmente.** Resolver memoria y composición
local confiable y revalidar los procesos antes del piloto. Se espera revisión y
autorización expresa de **9.2.5B**; no se habilita IA ni se realiza inferencia.
