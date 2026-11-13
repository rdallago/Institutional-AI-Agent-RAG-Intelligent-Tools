# Estabilización acotada del agente — 7 de noviembre de 2026

La memoria explícita de preguntas se resuelve por extracción de preguntas del
usuario dentro de los últimos ocho mensajes autorizados. No se invoca Qwen ni
se usan respuestas del asistente. Varios antecedentes distintos producen aclaración.

La continuidad mantiene comprobación de páginas, slices, pertenencia y límites
de artículos. La ventana administrativa de lectura pasa a dos páginas a cada
lado, con el mismo máximo de 64 fragmentos. Una sección `Requisitos del/de la`
con lista completa y siguiente encabezado explícito puede seleccionarse dentro
del artículo probado. Sus offsets y hashes son exactos; la respuesta se marca
parcial. Si la sección no cabe, se conserva la abstención, sin truncarla.

El diagnóstico privado de ubicación y propuestas JSON usa un buffer de 64 eventos,
de hasta 4096 bytes por evento. No se envía a logs operativos o endpoints HTTP.
La exportación es optativa mediante `AGENT_PRIVATE_DIAGNOSTIC_DIR`, apuntando a un
directorio privado existente; no se habilita ni cambia configuración automáticamente.
Se crean archivos exclusivos `agent-private-*.json`, hasta 64 por directorio;
al llegar al límite no se exportan más. El buffer sigue rotando. La exportación
usa los permisos heredados del directorio: el operador debe restringir su acceso.
Los fallos de exportación no alteran las herramientas; no hay garantía de registro
persistente si no se configuró un destino válido y escribible.

Se registra UUID de solicitud, traza efímera, argumentos meteorológicos acotados,
normalización, coincidencias y motivo. Del planificador se conserva tipo de acción,
campo permitido y regla de rechazo, nunca JSON original, inputs o mensajes de
excepciones. Valores con patrones de credenciales se redactan. No es un detector
universal de secretos; introducir secretos en ubicaciones sigue estando prohibido.

No cambian modelos, parámetros, guarda RAM, prompts, validación de afirmaciones,
embeddings, esquema, credenciales ni historiales. La extracción original del
artículo 52 conserva sus defectos OCR y cifras contradictorias; no se reparan.
Falta aceptación funcional desde React con recursos suficientes y una consulta
secuencial por caso; las pruebas automatizadas usan dobles y funciones puras.
