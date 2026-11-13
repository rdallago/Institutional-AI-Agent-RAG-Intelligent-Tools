# Sprint 10G.5–10G.6 — Preparación operativa; ejecución bloqueada

10 de noviembre de 2026. **NO-GO para indexación real.** El pedido adjunto declara
expresamente que NO autoriza 432 solicitudes externas. No se habilitó exportación.

## Preflight real READ ONLY

Configuración validada: usuarios_dev, 127.0.0.1:5434; conexión con
default_transaction_read_only=on, connect_timeout=10, statement_timeout=10000,
comprobación de modo READ ONLY y rollback. No se registró texto documental.

| Propiedad | Resultado |
|---|---|
| Revisión | 0006_cloud_embeddings |
| Documento | 8ac0c745-1307-5bb4-9d56-93dfbee0b3b8, reglamento-academico |
| Versión activa autorizable | 7cb4e79c-747d-574a-8abb-0ebcb2e07636 |
| Fragmentos | 432; hashes de fragmentos/páginas y slices/offsets comprobados |
| Propietario | 32eabde4-7d17-4029-a47a-60e2e38faf05, ADMIN activo |
| Visibilidad documental SQL | PRIVATE; no se cambió |
| Embeddings históricos | 864 conservados por conteo; auditoría completa previa en 10G.4 |
| Cuatro tablas cloud | Vacías |
| Pendientes | 432, sin checkpoints previos |
| Otras transacciones de usuarios_dev | 0 al comprobar |
| Configuración embeddings | jina / jina-embeddings-v3 / 768 |
| JINA_API_KEY en el proceso actual | AUSENTE, comprobación booleana únicamente |

Fingerprint previsto:
`1f0482094b5531fc5d3406985eb3ba0ec870af28871c4b2b7c4c6f12b6c37ed1`.
El flujo CLI usa retrieval.passage, hasta 10 fragmentos por ejecución y UN POST por
fragmento. Previsto máximo 432 POST en una ejecución completa sin fallos; no hay
llamadas OpenRouter en ese recorrido, ni fallback generativo/local. No se ejecutó.

## Revisión de contenido y permisos

El usuario declara que el reglamento es público. La ACL SQL PRIVATE es una
clasificación operativa distinta; no se convierte a AUTHENTICATED por esa declaración.
El propietario ADMIN es quien puede indexar según el guard existente.
Análisis local limitado del texto: sin marcadores de email, etiqueta DNI o secreto
etiquetado password/api-key/bearer. **No certifica ausencia de datos personales:**
nombres, firmas o identificadores en OCR pueden no coincidir con esos patrones.
La revisión documental humana/confirmación de contenido exportable sigue pendiente;
no se debe afirmar que el simple carácter público elimina esa revisión.

## Credenciales y uso gratuito: motivo de parada

La clave no está en este proceso. No se inspeccionaron claves de otros procesos
ni se pidieron por chat. El usuario declara créditos gratuitos y ausencia de
compras/medios de pago. El saldo previamente comunicado fue 9.999.541 tokens:
no es saldo actual verificado en esta ejecución. No se consultó la cuenta ni API.
No se puede certificar aquí vigencia/licencia, retención aplicable o imposibilidad
de cargos solo con esos datos. Conforme al punto 7 del pedido, se detiene la
preparación ejecutable para solicitar intervención del titular.

Intervención mínima: cargar la clave en la memoria de la terminal ejecutora mediante
Read-Host -AsSecureString según 10G.2/10G.4, sin compartir su valor. Confirmar desde
el panel/soporte saldo vigente suficiente, condiciones del paquete para este uso,
ausencia de cargos automáticos y tratamiento/retención aceptados. No adjuntar
capturas sensibles, claves o medios de pago al informe. Si esa información no
puede verificarse, permanece pendiente; no se presume garantía de consumo gratuito.

## Protección de alcance: cambio necesario, NO aplicado

DOCUMENT_EXPORT_APPROVED=False sigue intacto. Cambiarlo globalmente a True sería
insuficiente: no restringe por versión o por proceso. No se propone ese bypass.
Antes de habilitar, implementar y probar una autorización explícita que vincule
documento y versión exactos, fingerprint, propietario y hashes de fragmentos
permitidos al proceso CLI autorizado. Debe negar otros documentos/versiones,
uso desde FastAPI y activación; el adaptador público de documentos debe continuar
negando envíos sin ese contexto. La CLI conservará ACL, integridad y checkpoints.
Ese cambio de alcance está solicitado por el adjunto, pero NO se implementó aún
por la parada obligatoria ante clave/condiciones de cuenta no verificadas.
No usar monkeypatch operativo, llamadas privadas o SQL manual para eludirlo.

## Autorización a solicitar antes de ejecutar

Una vez resueltos los pendientes y preparado/probado el control anterior, solicitar
aprobación concreta de exportar SOLO documento/versión indicados, hasta 432 POST
retrieval.passage y sus escrituras de espacio, ingesta y checkpoints en usuarios_dev,
sin activación. Lotes secuenciales de hasta 10, una llamada a la vez y sin pedir
confirmación por cada lote después de esa aprobación global. Ante HTTP/cuota/red,
timeout incierto, SQL, integridad o recursos inválidos: detener sin reintentar.
Revisar checkpoint antes de una reanudación específicamente autorizada.

La validación oficial final también escribe estado VALIDADA: debe incluirse en
la autorización solicitada. Previamente comprobar 432 vectores finitos/normalizados
de 768 dimensiones, cero pendientes, hashes/offsets/modelo/tareas y conservación
de históricos. No ejecutar activate ni crear puntero. La publicación necesita
permiso independiente incluso si toda la indexación aprueba.

## Resultado de esta intervención

| Métrica | Resultado |
|---|---:|
| Fragmentos enviados/procesados realmente | 0 |
| POST reales a Jina/OpenRouter | 0 / 0 |
| Checkpoints nuevos | 0 |
| Errores/reanudaciones de indexación | No iniciada |
| Validación oficial de 432 Jina | No ejecutada, no existen vectores Jina |
| Activación | No ejecutada, cero punteros |

No se repitieron tests de 10G.4: no hubo cambios de código. Sus 60 mocks aprobados
siguen siendo evidencia sintética previa, no aceptación de exportación acotada
nueva. Único archivo incorporado: este informe. Sin escrituras de base, cambios
.env, modelos, guardas o secretos, APIs, migraciones, reinicios o borrados.

Preparación React: los comandos existentes están en 10G.3; solo después de una
publicación autorizada arrancar/reiniciar servicios con autorización y consultar
artículos 24 y 52 de forma secuencial, registrando citas y cobertura. No ejecutar
esas pruebas ahora: sin índice activo el RAG permanece indisponible.

**NO-GO para indexar, activar o probar React real.** Próximo paso es la intervención
del titular sobre clave/cuenta/contenido y luego completar la protección de alcance,
antes de pedir autorización final de las llamadas y escrituras concretas.
