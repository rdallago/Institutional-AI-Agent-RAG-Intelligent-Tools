# Diagnóstico privado de generación RAG

Requiere reiniciar FastAPI para cargar la instrumentación. No cambia validación,
contexto, generación ni el contrato HTTP. No reconstruye ejecuciones anteriores.

En el entorno del proceso, configurar `AGENT_PRIVATE_DIAGNOSTIC_DIR` con un
directorio privado existente. En Windows debe tener herencia deshabilitada y
permisos únicamente para su propietario y SYSTEM; en POSIX, propietario actual
y modo 0700. No se modifican permisos automáticamente.

Para conservar además el JSON literal, habilitar explícitamente
`AGENT_PRIVATE_CAPTURE_RAG_JSON=true` en ese proceso. Sin esta variable no se
guarda contenido generado. Nunca se incluye el literal en el buffer ni en logs.

Buscar en `agent-private-*.json` el `request_id` de la próxima solicitud real.
Los eventos `rag_validation` se correlacionan también por `trace`:

- `generation`: validez del contrato, cantidad de afirmaciones (null si inválido),
  identificadores, versión, páginas, offsets y SHA-256 UTF-8 de cada fuente enviada;
  `literal_json` solo con captura habilitada.
- `claims`: cantidades y resultados por índice, referencias y comparación léxica/
  polaridad de unidades rechazadas, sin duplicar textos de afirmaciones o fuentes.
- `publication`: model_abstention, all_claims_rejected, partial_grounded,
  grounded o final_support_rejected. La aceptación individual no garantiza
  aceptación final: se conserva la comprobación global existente.

JSON inválido conserva su excepción; no alcanza validación de afirmaciones.
El diagnóstico no repara contratos ni agrega referencias.

Límites: 64 eventos en memoria, 64 archivos compartidos con los diagnósticos
existentes, 12 KB de metadatos por evento, literal hasta 16 KiB y archivo hasta
32 KiB. Creación exclusiva; no sobrescribe ni elimina archivos. Un directorio
lleno, permisos insuficientes o error de escritura impiden la exportación sin
alterar el resultado funcional. Comprobar que aparecieron los archivos antes de
considerar conservada la evidencia. Los términos faltantes también son privados.
