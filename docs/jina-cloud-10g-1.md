# Sprint 10G.1 — Preparación final de indexación Jina

Fecha: 10 de noviembre de 2026. **GO de almacenamiento; NO-GO para exportación
e indexación real mientras permanezcan los pendientes indicados al final.**
No se ejecutó la CLI de indexación ni se enviaron documentos o consultas a APIs.

## 1. Estado PostgreSQL comprobado READ ONLY

Destino validado: usuarios_dev, 127.0.0.1:5434. Auditoría con connect_timeout=10,
default_transaction_read_only=on, statement_timeout=10000, comprobación de modo
READ ONLY y rollback. No se aplicó Alembic ni ninguna escritura.

| Verificación | Resultado |
|---|---|
| Revisión | 0006_cloud_embeddings |
| Cuatro tablas cloud | Existen, todas con cero filas |
| Tipo embedding cloud | vector(768) |
| PK/FK/UNIQUE/CHECK/NOT NULL | Definiciones inspeccionadas; convalidated=true |
| Integridad histórica | 864 fragmentos y 864 vectores válidos |
| Hashes de páginas/fragmentos/entrada y offsets/slices | Sin errores |
| Versiones | Ambas LISTA, 72 páginas y 432 fragmentos cada una |
| Activa | 7cb4e79c-747d-574a-8abb-0ebcb2e07636 |
| Anterior conservada | 9cab30cd-9554-5679-a2d9-35d85dd5ab85 |
| Docker | Contenedor esperado healthy, 127.0.0.1:5434 publicado |
| RAM disponible | 2.052.608 KiB, aproximadamente 1,96 GiB |

Las restricciones corresponden al DDL 0006: espacios con fingerprint único y
dimensión 768; embeddings con PK(fragmento,espacio), FK a fragmento y espacio/dimensión;
ingestas con PK(version,espacio), FK a ambos y estado PREPARANDO/VALIDADA;
activos con FK a pareja de ingesta. La FK no exige VALIDADA/completitud por sí sola:
esa garantía depende además del procedimiento de aplicación, no de SQL manual.
No se imprimieron documentos, usuarios, conversaciones o vectores.

## 2. Configuración efectiva y prevista

El proceso de diagnóstico devuelve actualmente provider=ollama, aunque model sea
jina-embeddings-v3. El nombre del modelo NO selecciona el proveedor. No se
instanció ni invocó Ollama. El arranque cloud operativo exige Jina+OpenRouter.

**JINA_API_KEY no está presente en este proceso.** Esto no prueba que falte en
la terminal privada del usuario. Solo se comprobó su presencia booleana, sin
imprimirla, modificarla o transmitirla. El loader la lee exclusivamente del entorno
del proceso; no basta incorporarla a .env. No se validó autenticación/saldo por API.

Configuración prevista, NO aplicada:

```dotenv
EMBEDDING_PROVIDER=jina
EMBEDDING_MODEL=jina-embeddings-v3
EMBEDDING_DIMENSIONS=768
EMBEDDING_TIMEOUT_SECONDS=30
EMBEDDING_MAX_INPUT_BYTES=2048
EMBEDDING_MAX_RESPONSE_BYTES=65536
```

Documentos: retrieval.passage. Consultas: retrieval.query. normalized=true,
embedding_type=float. El fingerprint previsto con esos contratos es
`1f0482094b5531fc5d3406985eb3ba0ec870af28871c4b2b7c4c6f12b6c37ed1`.
Incluye tareas, normalización, modelo, dimensión y contrato UTF-8; no inventa un
digest inmutable del proveedor. No mezclarlo con Nomic ni cambiar identidad a mitad.
Mantener Dots3-Note/OpenRouter sin alteraciones y sin fallback local.

## 3. Revisión del adaptador y CLI

Archivos inspeccionados: infrastructure/rag/jina.py, cloud_postgres.py,
configuration/embeddings.py y presentation/cli/reindex_jina.py bajo backend/src/app.

- DOCUMENT_EXPORT_APPROVED=False se conserva. Bloquea la CLI antes de SQL/exportación
  y el método público embed_document antes del transporte. No existe flag/env de bypass.
- Cliente HTTPX: un solo envío a la vez, retries=0, sin redirecciones/fallback/proxy
  del entorno, límite de una conexión, TLS normal, sin cuerpos upstream en mensajes.
- Límite global asíncrono de 30 s por llamada, connect=3 s; no confundirlo con
  tiempo de todo un lote. Config admite hasta 55 s, no se cambió.
- Entrada UTF-8 exacta, sin NUL, máximo 2048 bytes, detección de secretos. Respuesta
  limitada a 65536 bytes, JSON con claves duplicadas/no finitos rechazados.
- Exige modelo exacto, un único elemento data, índice entero cero y vector de
  768 números finitos; norma unitaria con tolerancia 0,01. No repara ni renormaliza.
- 408/504 y timeouts se traducen a tiempo agotado; 401/402/403/429/5xx y errores
  de red a indisponibilidad; otros estados/contratos inválidos se rechazan.
  La CLI muestra un mensaje genérico: no permite distinguir allí saldo, cuota y
  autenticación. No sustituirlo por impresión del cuerpo del proveedor.
- Guarda de RAM de la llamada cloud: 0,25 GiB, intacta. Revalidar recursos para
  cada ejecución; la medición presente no garantiza estabilidad futura.
- La CLI exige destino dev exacto, revisión 0006 y ADMIN activo propietario de
  la versión textual activa LISTA. Usa mutex local de archivo, no modelo local.
- Cada fragmento valida SHA de página/fragmento y slice antes de HTTP. Tras la
  respuesta, checkpoint transaccional vuelve a validar integridad y actor.
- PK y ON CONFLICT impiden sobrescribir: duplicado idéntico es idempotente;
  contradicción de hash/vector provoca error/rollback. Pendientes excluyen filas
  ya confirmadas del mismo espacio. La respuesta remota y el commit SQL NO son
  una transacción distribuida: un corte entre ambos puede consumir cuota sin checkpoint.
- prepare_existing crea espacio e ingesta PREPARANDO, pero no duplica fragmentos.
  missing_cloud no valida por sí solo un checkpoint existente; validación final
  revisa todos. No usar una lectura de pendientes como certificado de integridad.
- validate verifica exactamente 432 elementos y marca VALIDADA, sin activar.
  activate vuelve a validar y actualiza puntero cloud dentro de la misma transacción
  con lock de documento. No cambia el UUID textual ni elimina Nomic.
  Consultas cloud requieren espacio activo VALIDADA y ACL; no hay fallback Nomic.

El mutex solo coordina procesos locales. No garantiza exclusión entre máquinas.
No se ejecutó ninguna de esas acciones: incluso validate realiza escrituras y
está fuera del alcance READ ONLY actual.

## 4. Número real de llamadas y consumo

La CLI admite 1–10 fragmentos por ejecución, pero llama embed_document por cada
uno con input=[texto]. **432 fragmentos = 432 POST**, si todos responden y no hay
fallos. No son 44 POST batch: serían 43 ejecuciones de diez y una de dos.
Validación y activación no llaman Jina. Las consultas posteriores sí requieren
llamadas retrieval.query adicionales, no incluidas en las 432.

Datos activos medidos: 159.779 bytes UTF-8 incluyendo solapamientos; mínimo 64,
máximo 400 por fragmento. Caben en 2048 bytes. sum(tokens_medidos)=159779 en
el almacenamiento histórico: es presupuesto conservador local, NO tokenización
Jina ni factura. Heurística previa de 2–4 bytes/token: 40.000–80.000 tokens.
Reservar orientativamente 200.000 tokens más consultas/verificación, y comprobar
saldo y uso real antes/después. No prometer precio cero para una cuenta no auditada.

Con timeout de 30 s, 432 llamadas podrían acumular 3 h 36 min de tiempo HTTP si
todas se acercaran al límite, más SQL/operación; no es una estimación de duración
típica ni una garantía. Una prueba sintética previa de 1,714 s no permite pronosticar
la ingesta completa. El primer error detiene, por lo que no se espera el total
si una llamada agota timeout. Respuestas fallidas/ambiguas pueden consumir cuota.

## 5. Privacidad, licencia y facturación — evidencia oficial consultada

Consultas de documentación pública únicamente, sin clave ni peticiones de embeddings:

- [FAQ de embeddings](https://jina.ai/embeddings/): el proveedor declara no utilizar
  solicitudes, entradas o salidas para entrenamiento. Es declaración del proveedor,
  no auditoría independiente ni garantía de retención cero.
- [Aviso legal](https://jina.ai/legal/): actualizado 4/5/2026, remite tras adquisición
  a términos de tratamiento de Elastic y advierte que textos antiguos pueden no
  reflejar prácticas actuales. Falta confirmar retención efectiva para esta cuenta.
- [Precios](https://jina.ai/api-dashboard/pricing/): publica mecanismo de recarga
  automática del medio guardado al caer saldo y límites gratuitos de embeddings
  de 100 RPM/100.000 TPM. Son límites publicados, no promesa de capacidad.
- El resultado oficial indexado de precios indica uso no comercial (CC-BY-NC),
  pero la representación pública directa no muestra todos los detalles de planes.
  **No está confirmado que el plan disponible del usuario permita uso comercial.**
  No confundir licencia de pesos/on-prem con condiciones del servicio hospedado.

No se accedió al panel autenticado: saldo, paquete, vigencia, medio de pago,
auto-recarga y acuerdo concreto siguen sin verificar. Confirmar con titular/
proveedor antes de exportar. No exigir información sensible en el chat.
La política pública no fija por sí sola un plazo comprobado de textos/vectores,
logs/backups para esta clave: confirmar región, subprocesadores, eliminación y
condiciones educativas/no comerciales. El saldo gratuito no autoriza uso documental.

Se enviarían exclusivamente los textos de los 432 fragmentos activos, con sus
solapamientos, tareas y configuración del modelo; no PDF ni registros de usuarios.
La revisión de derechos/permiso del reglamento y de posibles datos personales
incluidos en ese texto sigue siendo necesaria antes de aprobar la exportación.

## 6. Plan gradual propuesto, NO ejecutado

1. Resolver privacidad, derechos de exportación y condiciones de cuenta; confirmar
   saldo, vigencia y auto-recarga deshabilitada. Aportar clave solo a la memoria
   de la terminal ejecutora y comprobar presencia sin mostrarla.
2. Obtener autorización específica de configuración y levantamiento controlado
   del bloqueo documental. Hoy NO está concedida. No eludirlo mediante monkeypatch.
3. Revalidar base, versión, fingerprint, recursos, respaldo y exclusión local.
   Registrar baseline de tablas históricas; no reiniciar backend automáticamente.
4. Primera ejecución: 1 fragmento. Comprobar checkpoint, vector/hash y consumo;
   cero punteros activos. Detener para revisar el resultado real.
5. Después autorizar hasta 9 adicionales para llegar a 10 confirmados; revisar.
   Continuar con ejecuciones de hasta 10, secuenciales y supervisadas. El total
   sigue siendo 432 llamadas si no hay fallos; con piloto separado serán más
   ejecuciones CLI que en el plan estándar de 44.
6. Ante HTTP, RAM, red, integridad o SQL inválido: detener, conservar checkpoints;
   no reintentar automáticamente ni cambiar proveedor/modelo. Revisar pendientes
   y cualquier llamada incierta antes de autorizar reanudación; no garantizar
   idempotencia de consumo remoto. La CLI no tiene rate limiter propio: supervisar
   RPM/TPM y pausar entre ejecuciones si corresponde, sin reenviar fallos.
7. Al alcanzar 432: validar todos los hashes, offsets, dimensión, finitud, norma,
   correspondencia de fuentes y checkpoints. Revalidar conservación histórica.
   validate cambia estado pero no publica; requiere autorización de escritura.
8. Presentar evidencia y solicitar activación por separado. Solo después de ella
   autorizar búsquedas de artículos 24/52 y aceptación real. No activar automáticamente
   al completar un lote ni usar un índice incompleto.

## 7. Decisión

**Preparación técnica documentada; NO-GO para solicitar ejecución inmediata de
exportación/indexación.** Pendientes concretos:

1. Privacidad/retención y condiciones del plan para el uso previsto.
2. Confirmación del titular de saldo, vigencia, auto-recarga deshabilitada y derechos
   de exportación; sin claves, capturas sensibles o datos de pago en informes.
3. JINA_API_KEY en el proceso ejecutor (ausente aquí), sin modificarla ahora.
4. Selección explícita de Jina (actualmente ollama) y aprobación separada para
   levantar DOCUMENT_EXPORT_APPROVED=False; no se realizó ninguno de esos cambios.

Solo se creó este informe. No se ejecutaron tests repetidos, Alembic, indexación,
APIs de inferencia/embeddings, cambios .env, escrituras SQL, activación ni borrados.
Se conserva la evidencia histórica de tests con mocks y del ensayo SQL de 10C;
no se presenta como nueva validación real de 432 embeddings Jina.
