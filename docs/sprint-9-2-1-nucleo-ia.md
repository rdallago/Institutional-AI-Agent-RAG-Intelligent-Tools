# Sprint 9.2.1: núcleo de aplicación IA y pruebas aisladas

Fecha: **1 de noviembre de 2026**. Estado: **implementado y verificado en aislamiento**.
Diseño 9.1 aprobado por el responsable para
implementación incremental. Alcance: puertos, DTO, caso de uso, autorización y
admisión en memoria. No se inicia 9.2.2 ni se conecta Ollama.

## 1. Arquitectura implementada y archivos

Application coordina el flujo mediante protocolos y datos inmutables. No importa
FastAPI, HTTPX, Ollama, SQLAlchemy o infraestructura. No se añadió una entidad de
dominio ni se modifica persistencia. Los dos adaptadores implementados no hacen
red: admisión local y puente asíncrono hacia AuthService.

Archivos nuevos de Application:

- `backend/src/app/application/ia/__init__.py`.
- `backend/src/app/application/ia/dto.py`.
- `backend/src/app/application/ia/ports.py`.
- `backend/src/app/application/ia/exceptions.py`.
- `backend/src/app/application/ia/use_cases/__init__.py`.
- `backend/src/app/application/ia/use_cases/generar_respuesta.py`.

Adaptadores nuevos:

- `backend/src/app/infrastructure/llm/__init__.py`.
- `backend/src/app/infrastructure/llm/admission.py`.
- `backend/src/app/infrastructure/llm/authorization.py`.

Pruebas nuevas:

- `backend/tests/ia_support.py`: proveedor falso, autorizador y reloj controlados.
- `backend/tests/ia/test_generation.py`.
- `backend/tests/ia/test_admission.py`.
- `backend/tests/ia/test_auth_integration.py`.

Único archivo funcional existente modificado:
`backend/src/app/application/auth/service.py`, que añade el método público
`require_normal_access(principal)`. Reutiliza `_normal` dentro de una UoW corta;
no cambia authenticate, JWT, permisos, alcance de sesiones ni aprovisionamiento.
Se crea también este informe.

No se conectó IA al composition root, router, lifespan, configuración operativa o
servicios que están funcionando. No se modificaron React, dependencias, modelos,
migraciones ni esquemas. No se reinició ningún servicio.

## 2. Contratos y límites

| Contrato | Responsabilidad |
| --- | --- |
| `ConsultaDatos(*, prompt)` | Entrada del usuario; solo prompt, sin parámetros internos |
| `GeneracionEntrada(*, prompt)` | Entrada al proveedor con límites fijos de 256 tokens de salida y 4096 de contexto, no elegibles en constructor |
| `GeneracionSalida(*, respuesta, finalizacion)` | Resultado con terminación completa o limite |
| `LLMProvider.generate(input)` | Protocolo async independiente del proveedor |
| `NormalAccessAuthorizer.require_normal(principal)` | Protocolo async para revalidación de acceso normal |
| `GenerationAdmission.try_acquire(principal)` | Adquirir cupo y consumir ambas cuotas atómicamente, sin espera ni I/O |
| `GenerationLease.release(timed_out=False)` | Liberación síncrona, idempotente; timeout activa enfriamiento |

DTO frozen/slots y campos nominales. Prompt, respuesta y terminación quedan fuera
de repr; los DTO no registran ni imprimen contenido. El núcleo no es un mecanismo
de borrado seguro de memoria ni impide que un consumidor serialice explícitamente
un DTO: los futuros adaptadores deberán respetar la política de no logging.

El caso de uso valida la entrada **después de autorizar y antes de admitir**:
string requerido, no vacío ni solo espacios, máximo 1000 puntos Unicode y 3000
bytes UTF-8, sin NUL ni surrogates aislados. No normaliza, recorta o trunca el texto
válido. Una entrada inválida no consume cuota ni llama al proveedor.

El constructor de ConsultaDatos no acepta modelo, URL, herramientas o límites;
los tipos se verifican al ejecutar el caso. La salida del proveedor se vuelve a
validar en el límite: DTO esperado, texto no vacío, Unicode sin NUL, máximo 4096
puntos/16384 bytes y finalización en `completa|limite`. Un objeto inesperado se rechaza.

**Separación de transporte:** no hay todavía límite HTTP de 16 KiB, parsing JSON,
413, endpoint, códigos HTTP o respuesta no-store. Son trabajo de **9.2.3**.
La lectura upstream limitada a 64 KiB, JSON/Ollama, tokenización y validación de
done/modelo/terminación del protocolo corresponden al adaptador de **9.2.2**.

## 3. Autorización y transacciones

Secuencia de `GenerarRespuesta.ejecutar`:

1. Esperar autorización normal del Principal mediante el puerto.
2. Validar el prompt.
3. Adquirir concesión y consumir cuotas en una sola operación de admisión.
4. Invocar al proveedor async bajo deadline total de generación.
5. Validar su salida y volver a autorizar al mismo Principal.
6. Devolver únicamente si el acceso sigue válido.
7. Liberar la concesión en finally ante éxito, error, autorización final fallida
   o cancelación.

`AuthServiceNormalAccessAuthorizer` llama al método público mediante
`asyncio.to_thread`. La UoW abre y cierra en ese hilo antes de continuar; no se
llaman métodos privados desde IA ni se abre una transacción alrededor del proveedor.
Las pruebas rastrean UoW y comprueban que no hay ninguna abierta al generar.
Otra prueba bloquea deliberadamente la comprobación síncrona con eventos y
demuestra que el event loop sigue ejecutándose en otro hilo.

ADMIN y USUARIO normales tienen acceso. Se conservan los errores actuales de
sesión revocada/vencida, usuario inactivo, credencial ausente y cambio pendiente.
La sesión restringida con credencial definitiva tampoco se promueve. Una revocación,
baja u obligación que aparezca durante la generación impide entregar el resultado.
No se modifica la sesión para autorizar ni se envía Principal/JWT/rol al proveedor.

Cancelar el await de to_thread no mata una operación síncrona ya iniciada; su UoW
termina normalmente en el worker. Nunca se mantiene ese worker esperando al LLM.
No se promete eliminar la pequeña carrera posterior a la comprobación final y
anterior a la entrega, ya explicitada en el diseño.

## 4. Admisión, cuotas y carreras

`MemoryGenerationAdmission` usa un lock de hilo breve. No contiene awaits ni I/O.
Dentro del mismo lock comprueba enfriamiento, ocupación, ventana/cuotas/capacidad,
crea la concesión y aumenta ambas cuotas. Solo una concesión queda activa.

- Máximo **una generación simultánea**, sin cola ni espera de cupo.
- **5 admisiones por usuario y 15 globales por minuto** en ventanas fijas de
  reloj monotónico. Diferentes sesiones del mismo UUID comparten cuota.
- Ocupación, enfriamiento, cuota o registro lleno no consumen parcialmente ninguna
  cuota. Validación/autorización previas fallidas tampoco consumen.
- Una solicitud admitida conserva su consumo aunque falle el proveedor, se cancele
  o se rechace la autorización final. El éxito tampoco reinicia contadores.
- Registro limitado a **1024 UUID** como máximo, sin prompts o respuestas.
  Puede reducirse la capacidad para pruebas, no aumentarla sobre ese techo.
- Al entrar en una ventana nueva se recuperan los registros vencidos; no hay
  limpieza en segundo plano. Si está lleno en la ventana vigente, rechaza sin
  expulsar la cuota de otro usuario. El espacio permanece acotado incluso inactivo.
- En timeout, release establece **30 segundos** de enfriamiento global. Retry-After
  se expresa como entero positivo redondeado hacia arriba en las excepciones.

Cada concesión tiene un token de identidad opaco. Doble liberación no descuenta
cuotas, no extiende enfriamiento ni libera una concesión posterior. Una prueba con
ocho hilos demuestra una sola admisión ganadora y ausencia de consumo parcial;
se verifica también liberación repetida concurrente.

El adaptador se deberá componer como **una instancia compartida por proceso** en
9.2.2/9.2.3. Crear dos instancias independientes crearía dos presupuestos; por eso
no constituye un limitador distribuido ni permite múltiples workers sin otro diseño.
Reiniciar pierde cuotas y enfriamiento. Las ventanas fijas admiten ráfagas en el
borde temporal; no se presentan como ventanas deslizantes.

Es independiente de LoginLimiter y auth_intentos. Las pruebas con AuthService real
de memoria comparan sus intentos antes/después de consultas y agotamiento de IA:
permanecen iguales. No se agregan tablas o contadores de autenticación.

## 5. Errores, timeout y cancelación

Errores propios: PromptInvalido, IANoDisponible, IATiempoAgotado,
IARespuestaInvalida, IAOcupada e IALimiteIntentos. Mensajes constantes sin contenido
del usuario/proveedor; los rechazos de admisión solo añaden retry_after numérico.
No hay todavía traducción HTTP.

El caso de uso aplica `asyncio.timeout` con **60 s por defecto**, techo de 60 s y
valores finitos/positivos. Se permite un deadline menor para pruebas controladas,
sin exponerlo en ConsultaDatos. TimeoutError o IATiempoAgotado del proveedor se
traducen al error propio saneado y activan enfriamiento.

Los errores conocidos del proveedor se reconstruyen sin sus mensajes originales;
los inesperados se convierten en IARespuestaInvalida sin cadena pública de causa.
Se prueban incluso excepciones con argumentos contaminados por un centinela ficticio,
comprobando mensajes, repr, traceback formateado y logs capturados. Los errores de
autorización existentes conservan su significado y no se disfrazan como fallo LLM.

CancelledError se propaga; no se convierte en una respuesta exitosa ni se reintenta.
La liberación es síncrona y no requiere otro await cancelable. La cancelación externa
libera el cupo sin el enfriamiento específico de timeout, según el diseño aprobado.
Si llega durante la autorización final, también se libera.

El proveedor debe cooperar con cancelación y no bloquear el event loop. Este núcleo
no puede detener una coroutine que ignore cancelación ni garantizar la terminación
de un cómputo externo. El adaptador futuro deberá cerrar transporte en finally;
las limitaciones de cancelación real de Ollama siguen pendientes del piloto.

## 6. Pruebas y resultados

Todas las pruebas nuevas son aisladas: proveedor falso determinista, eventos,
relojes y AuthService/UoW de memoria. El falso permite éxito, indisponibilidad,
timeout, salida inválida, fallo inesperado, bloqueo, cancelación y cambios de sesión
durante la generación. No se llama a Ollama ni se lee configuración operativa.
No se necesitaron pruebas PostgreSQL ni consultas a ninguna base.

Cobertura nueva:

- Vacío/tipos/espacios, límites exactos Unicode/bytes, NUL y surrogates; conservación
  exacta de espacios y secuencias Unicode válidas.
- ADMIN/USUARIO, pendiente/restringida, revocación, expiración, inactividad,
  credencial ausente y restricción anómala; proveedor no llamado ante rechazo inicial.
- Cambios de acceso durante inferencia, incluida revocación mientras el falso espera.
- Respuesta inválida, límites de salida, éxito y terminación por presupuesto.
- Cuotas por usuario entre sesiones, global, registro acotado, recuperación por reloj,
  fallo de proveedor que consume cuota y ausencia de consumo parcial.
- Concurrencia async y entre hilos, cancelación externa/del proveedor/en autorización
  final, liberación idempotente y enfriamiento sin esperas reales de 30 s.
- Deadline real de 10 ms con proveedor bloqueado cooperativo; sin sleeps largos.
- DTO ocultos/inmutables y rechazo de opciones internas del usuario.
- Trabajo de autorización en worker, ninguna UoW durante generación y separación
  de intentos de autenticación.

Comandos desde backend:

```powershell
.\.venv\Scripts\python.exe -B -m pytest -q tests/ia tests/unit/infrastructure/test_database_configuration.py -p no:cacheprovider --basetemp=.pytest-tmp-921-targeted-20261101 --tb=short
.\.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider --basetemp=.pytest-tmp-921-final-20261101 --tb=short
```

| Verificación | Resultado |
| --- | --- |
| Dirigida, IA y configuración previa | **89 aprobadas**, 1,57 s: 81 nuevas de IA y 8 existentes |
| Regresión backend final sin PostgreSQL | **514 aprobadas, 162 omitidas**, sin fallos, 14,55 s; 433 anteriores y 81 nuevas |
| Inspección AST de Application IA | 6 módulos válidos, sin imports de infraestructura/frameworks/proveedores |
| PostgreSQL / Ollama / frontend | No ejecutados en este incremento |

La primera ejecución dirigida obtuvo 79 aprobadas y una aserción de prueba
incorrecta al intentar añadir un atributo a una dataclass frozen/slots. Se corrigió
para comprobar la inmutabilidad de un campo existente. Se añadió después un caso
de fallos consecutivos que consumen cuota. La primera regresión obtuvo 512
aprobadas, 162 omitidas y dos errores de preparación por permisos de basetemp
dentro de .pytest_cache. La dirigida posterior pasó con una ruta nueva en backend;
la regresión final aprobó con esa misma estrategia. No se tocaron permisos globales ni
se eliminaron directorios ajenos.

Permanece únicamente el aviso previo Starlette/TestClient sobre httpx; no se
actualizaron dependencias para ocultarlo.

Las omisiones de PostgreSQL son intencionales al no usar --run-postgres; no se
afirman como aprobaciones. Los resultados de integración/backend/frontend de los
sprints previos siguen siendo antecedentes, no ejecuciones de esta intervención.

## 7. Límites y preparación de 9.2.2

No se conectó a usuarios_dev ni usuarios_test. No se cambiaron roles, sesiones,
JWT, claves, barrera, dependencias o servicios operativos. Las modificaciones de
estado en pruebas solo afectan fixtures ficticias en memoria. No se ejecutaron
migraciones, limpiezas reales, inferencia o descargas.

Para 9.2.2 quedan el adaptador Ollama y su configuración, HTTPX runtime declarado
con aprobación, ciclo de vida del cliente, protocolo y tamaño upstream, cierre
de transporte y pruebas MockTransport. Más adelante vendrán endpoint/límite de
cuerpo/no-store y React; no se anticiparon. La disponibilidad de RAM observada en
9.1 no se volvió a medir ni se asume resuelta.

Se entrega exclusivamente **9.2.1** y se espera revisión antes de continuar.
