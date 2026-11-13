# Sprint 9.2.5E: preflight operativo del piloto local Qwen3

Fecha: **3 de noviembre de 2026**, muestras de recursos **06:46:06–06:46:09
-03:00**. **Resultado: BLOQUEADO.** Infraestructura parcialmente verificada;
el piloto real no se ejecutó ni se considera autorizado por este informe.

## 1. Dictamen

WSL y Docker responden, ambos contenedores PostgreSQL del proyecto figuran
saludables y Ollama ofrece el modelo previsto. Sin embargo:

1. RAM física disponible **0,786 / 0,689 GiB** en dos muestras, antes de abrir
   FastAPI y React: margen muy reducido para sumar la aplicación y el modelo.
2. No hay backend ni Vite escuchando en los puertos previstos; no existe una
   cadena React → FastAPI actualmente verificada.
3. No se comprobó identidad/revisión ni integridad efectiva de usuarios_dev
   después de reinstalar WSL. No se permite deducirlas de salud, volumen o informes.
4. think=false, done_reason, latencia y consumo reales siguen sin probarse.

Está preparado el código para solicitar una **siguiente etapa condicionada de
preparación operativa**, pero no una ejecución inmediata del piloto. Resolver
recursos y autorizar explícitamente los controles DB y arranque antes de la
única generación. No se recomienda cargar el modelo para averiguar si alcanza RAM.

## 2. WSL y Docker

Inspección efectivamente realizada: wsl --status, wsl --list --verbose,
docker version, docker ps -a, docker volume ls e inspect limitado a salud,
montajes y puertos de los dos contenedores propios. No se ejecutó docker exec,
compose up/down, start/stop, restore, prune o comandos de administración.

| Elemento | Observado |
| --- | --- |
| Distribución predeterminada / versión | Debian / WSL 2 |
| Debian | Running, versión 2 |
| docker-desktop | Running, versión 2 |
| Docker Desktop | **4.93.0 (240920)** |
| Engine / API | **29.8.1 / 1.56**, linux/amd64 |
| Kernel informado por motor | 6.18.54.1-microsoft-standard-WSL2 |

Los primeros comandos restringidos devolvieron E_ACCESSDENIED en WSL y acceso
denegado al pipe/config de Docker. La revisión automática permitió repetir
exclusivamente las lecturas fuera de esa restricción; no fue necesario cambiar
permisos o reiniciar servicios. No se interpretó el error inicial como motor caído.
Una plantilla inspect con claves entrecomilladas falló al parsearse en PowerShell;
se simplificó a los metadatos requeridos y la lectura posterior aprobó, sin mutación.

Contenedores existentes del proyecto:

| Contenedor / ID abreviado | Imagen | Estado | Publicación |
| --- | --- | --- | --- |
| api-usuarios-clean-postgres-1 / ce41dbdca5f0 | postgres:18 | running, healthy | **127.0.0.1:5434 → 5432** |
| api-usuarios-clean-tests-postgres-1 / 80172da97281 | postgres:18 | running, healthy | **127.0.0.1:5435 → 5432** |

En el inventario aparecieron además seis contenedores ajenos ya detenidos:
takehome_app, takehome_postgres, challange-backend, challange, mysql-1 y
welcome-to-docker. No se intervinieron ni inspeccionaron sus datos/configuración.

Volúmenes existentes: **api-usuarios-clean_postgres_data**, los dos volúmenes
nombrados take-home-challange_postgres_data y challange-ejercicio_postgres_data,
y uno anónimo. Solo se revisó el montaje del proyecto: el volumen de desarrollo
está montado en **/var/lib/postgresql**, lectura/escritura. Existencia/montaje no
prueban que sus datos históricos o Alembic hayan sobrevivido intactos.

El contenedor de pruebas no muestra montajes persistentes en Mounts; compose.test.yaml
declara tmpfs en /var/lib/postgresql. No se verificó su contenido, estado interno
de base o conservación tras reinicios. Este preflight no lo utilizó para tests.

## 3. PostgreSQL sin acceso a datos

Se leyeron compose.yaml, compose.test.yaml y el cargador de configuración. Se
invocó load_database_config() sin construir engine ni abrir conexión; se imprimió
solo la identificación no secreta: **usuarios_dev / 127.0.0.1:5434** coincide.
No se imprimieron usuario, contraseña, URL o archivo .env. La carga procesa valores
solo en memoria; no los modifica. No se cargó configuración de pruebas.

El healthcheck existente usa pg_isready dentro del contenedor; se observó su estado
reportado por Docker, **no se invocó** manualmente. Salud y listener acreditan
señales de disponibilidad, no autenticación correcta, revisión 0003, tablas,
integridad o datos previos. No se consultó ningún catálogo/tablas/conteos ni se
ejecutó Alembic, SQL, backup o restauración.

En una siguiente etapa expresamente autorizada, antes del arranque, comprobar por
conexión forzada a lectura destino/usuario efectivos y revisión única 0003, junto
con los metadatos mínimos necesarios. Sin leer perfiles, hashes o tokens; detener
ante revisión/destino inesperados, sin migrar automáticamente. El lanzador sin
aprovisionamiento no verifica por sí solo la revisión. No se afirma disponibilidad
funcional de autenticación basándose solo en Docker recuperado.

## 4. Ollama y recursos

GET /api/version, /api/tags y /api/ps a **127.0.0.1:11434**, con proxies ignorados,
timeout de 3 s y salida reducida a metadatos: todos **200**.

| Control | Observado |
| --- | --- |
| Versión Ollama actual | **0.40.13**; el antecedente era 0.40.7, no se actualizó aquí |
| Modelo candidato instalado | **qwen3:1.7b**, 1359293444 bytes en disco |
| Digest | `8f68893c685c3ddff2aa3fffce2aa60a30bb2da65ca488b61fff134a4d1730e7` |
| Otros tags presentes | qwen2.5:1.5b, nomic-embed-text:latest; no se usan como fallback |
| Modelos cargados | **Ninguno**, según /api/ps en esta muestra |
| Proceso | ollama.exe **13416**, padre **11792**, inicio 03/11/2026 06:35:01 local |
| Ejecutable | Instalación local de Ollama del usuario; sin línea de comando completa en salida |

No se realizaron solicitudes /generate, /chat, /show, run, load/unload o pull.
No se cargó deliberadamente ningún modelo. Presencia en disco y respuesta de
metadatos no acreditan que la versión/tag respete think=false o el protocolo
estricto bajo generación. No se probó aceleración GPU.

| Recurso | Muestra 1 | Muestra 2, 3 s después |
| --- | ---: | ---: |
| RAM física total | 7,851 GiB | 7,851 GiB |
| Disponible | **0,786 GiB** | **0,689 GiB** |
| Compromiso global | **13,308 GiB** | **13,323 GiB** |
| Límite de compromiso | 25,851 GiB | 25,851 GiB |

Medición actual mediante GetPerformanceInfo. Ocupación física aproximada 90–91 %;
el compromiso no equivale a RAM residente. No se midió tasa de paginación, por lo
que no se certifica su intensidad, pero existe riesgo de presión adicional y
congelamiento. El margen virtual no garantiza fluidez durante carga del modelo.

Working sets principales de otra muestra cercana: vmmem PID 6064 **597 MiB**;
Chrome 12036 **507,4**; Code 7608 **403,2**; Chrome 11364 **377,7**;
MsMpEng 5968 **286,8**; Code 5780 **231**; Chrome 1648 **212,1**;
Code 28096 **189,3 MiB**. No sumar como memoria exclusiva por páginas compartidas.
Docker backend PIDs 7920/8732 mostraron 28,9/89,6 MiB; Ollama 17,8 MiB sin modelo.

La experiencia favorable previa con Qwen3 comunicada por el responsable sigue
siendo relevante, pero no prueba esta combinación de carga, contexto y versión.
FastAPI/Vite aún no están abiertos: su coste y el del modelo se añadirán.
Proponer únicamente al responsable guardar trabajo y cerrar voluntariamente
pestañas/aplicaciones no necesarias que reconozca, elegir otra ventana o posponer.
No cerrar servicios, modificar pagefile o vaciar cachés. Repetir mediciones con la
pila necesaria antes de autorizar generación; la referencia previa de 2 GiB libres
no es una garantía automática de suficiencia.

## 5. Backend, frontend y observador

| Puerto | Observación actual |
| --- | --- |
| 8000 | Sin listener |
| 8001 | Sin listener |
| 5173 | Sin listener |
| 11434 | 127.0.0.1, PID 13416, Ollama |
| 5434 / 5435 | 127.0.0.1, PID 8732 com.docker.backend, publicaciones Docker separadas |

El inventario CIM de Python/Node/Ollama, con lectura permitida fuera de restricción,
mostró únicamente Ollama al consultar: sin Uvicorn, lanzador local o Vite activo.
Se clasificaron argumentos sin imprimirlos. Los Python efímeros usados por los
comandos/pruebas no son servidores operativos. Los PIDs históricos del 2 de
noviembre ya no describen el estado actual y no deben usarse para detener nada.
No se hicieron solicitudes desde React ni se inició un servidor para comprobarlo.

Código revisado, sin modificar:

- local-development y host exactamente 127.0.0.1 obligatorios para el lanzador.
- --enable-llm habilita solo la instancia explícita; sin flag, LLMConfig inyectada
  queda deshabilitada, sin heredar LLM_* o TEST_LLM_* del entorno.
- --observe-llm requiere --enable-llm y no activa aprovisionamiento. El observador
  no se activa por variables heredadas ni endpoint público.
- Mismo socket IPv4 real escuchando entregado a LocalLLMContext y Uvicorn;
  workers=1, reload=false, proxy_headers=false y access_log=false.
- Modelo único qwen3:1.7b, URL literal loopback, think=false, stream=false,
  keep_alive=0; contexto **4096**, salida **256 tokens**, deadline **60 s**.
- Admisión compartida: **1 generación**, 5 solicitudes/usuario/minuto, 15 globales,
  1024 usuarios como máximo y enfriamiento de 30 s tras timeout. No es distribuida.
- Cuerpo upstream máximo 64 KiB, request IA 16 KiB; done=true y done_reason
  stop/length estrictos, salida validada. Sin tools, ejecución o historial.
- Ocho metadatos del observador intactos; sin prompt/response/thinking/JWT/headers
  ni identidad. Emisión en finally de la misma llamada; no hace una segunda
  solicitud y no altera el contrato público. Silencio por defecto.

Estas propiedades y pruebas acreditan preparación de código, no compatibilidad
real del modelo o activación operativa actual. No hay ahora una instancia que
certifique OpenAPI IA, login o proxy servido. El proxy de desarrollo en disco
apunta a 8000; la configuración aislada mantiene 8001. No se modificó React.

## 6. Seguridad del futuro recorrido

Omitir --enable-initial-provisioning y mantener el gate normal cerrado. No crear
usuarios ni cambiar perfiles/roles para probar IA. El caso de uso revalida acceso
normal antes/después y no envía identidad al modelo. La consulta IA no tiene un
caso de uso que modifique usuarios o sesiones, pero **login/logout sí escriben
sesiones/intentos**: si el responsable debe autenticarse para el piloto, ese efecto
normal debe quedar explícitamente autorizado; no prometer cero escrituras para
todo el recorrido ni copiar/reutilizar JWT para eludirlo.

Este preflight no hizo login, auth/me o SQL. El piloto futuro tampoco ejecutará
Alembic automáticamente. Proteger el destino de stdout con solo metadatos y no
habilitar trazas HTTP, cuerpos o captura de variables. No se auditó toda retención
de Ollama u otros componentes: la privacidad del observador no certifica sus logs.
Solo credenciales ficticias de fixtures aisladas en tests; el responsable
introducirá personalmente las de práctica en interfaz bajo permiso posterior.

## 7. Pruebas aisladas actuales

Ejecutadas desde backend, sin --run-postgres, con clientes MockTransport/ASGI,
AuthService de memoria y servidor doblado en pruebas de lanzador. Los sockets
efímeros comprueban metadatos; no levantan servicios persistentes. Las fixtures
de datos reales de PostgreSQL no se ejecutaron.

```powershell
.\.venv\Scripts\python.exe -B -m pytest -q tests/ia -p no:cacheprovider --basetemp=.pytest-tmp-925e-ia --tb=short
.\.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider --basetemp=.pytest-tmp-925e-full --tb=short
```

| Verificación | Resultado |
| --- | --- |
| Suite IA dirigida | **305 aprobadas**, **5,72 s** |
| Regresión backend sin PostgreSQL | **738 aprobadas, 162 omitidas**, **12,66 s**, sin fallos |
| Observador/configuración/lanzamiento/contrato/auth | Incluidos en esas suites, sin cambiar implementación |
| PostgreSQL, frontend y generación real | No ejecutados |

No se suman repeticiones. Las 162 omisiones son intencionales, no aprobaciones.
Permanece el aviso previo Starlette/TestClient sobre httpx; no se instalaron
dependencias para ocultarlo. Artefactos temporales de pytest quedan en sus rutas
ignoradas; ningún archivo de aplicación o prueba se modificó.

## 8. Próxima autorización y detención

Recomendación: siguiente etapa para resolver recursos y verificar de manera
autorizada destino/revisión efectiva DB, seguida de arranque local de la aplicación
y comprobaciones sin inferencia. El responsable debe acordar después la única
consulta real con observador y monitorización de RAM/latencia. No acumular esos
permisos a partir de este diagnóstico. No hay necesidad de recrear contenedores,
borrar volúmenes o reinstalar modelos por los resultados observados.

Comando preparado para **futura autorización operativa, NO EJECUTADO** desde backend:

```powershell
.\.venv\Scripts\python.exe -B -m app.presentation.cli.local_server --environment local-development --enable-llm --observe-llm --host 127.0.0.1 --port 8000
```

La ruta React necesita su inicio local expresamente autorizado con configuración
de desarrollo y proxy verificado; no se deduce disponibilidad por existencia de
node_modules/build. Antes de cualquier cambio repetir estado y PIDs actuales.

Único entregable creado: este informe. No se modificaron archivos de aplicación,
observador, .env, contratos, roles o JWT; no hubo inferencia, descargas, instalaciones,
conexiones DB, migraciones, restauraciones, contenedores/volúmenes alterados,
inicio/detención/reinicio de servicios o solicitudes desde React.
Las lecturas de estado Docker no equivalen a acceder a datos PostgreSQL.

**BLOQUEADO para piloto inmediato. Informe entregado; se detiene y espera revisión.**
