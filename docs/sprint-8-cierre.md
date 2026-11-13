# Cierre de Sprint 8: aplicación Full Stack local

Fecha: **1 de noviembre de 2026**. **Cierre funcional local confirmado por el
responsable**, sin autorización de publicación externa.

Se completaron frontend React/TypeScript, autenticación con JWT en memoria,
sesiones revocables, permisos ADMIN/USUARIO, inicial manual, acceso restringido,
cambio obligatorio y aprovisionamiento administrativo local controlado.
La migración 0003 de desarrollo y su integridad constan en
[8.6B, sección 9](sprint-8-6b-migracion.md#9-reanudación-final-sesiones-autorizadas-cerradas-y-migración-completada).

El responsable confirmó manualmente: login ADMIN, alta con inicial, logout ADMIN,
primer login restringido, cambio obligatorio, nuevo login definitivo, rechazo de
administración para USUARIO y logout con protección posterior de rutas.
Las ocho comprobaciones se registran en [8.6D, sección 11](sprint-8-6d-aprovisionamiento-local.md#11-cierre-funcional-confirmado-por-el-responsable).
**Son resultados comunicados por el responsable, no pruebas automatizadas
observadas por Codex.** No se recibieron ni registraron datos personales o secretos.

Como antecedentes independientes, 8.6D documenta una regresión de **592 casos
backend**, **27 casos dirigidos** —con repeticiones de los anteriores— y **151
frontend**, además de typecheck/lint/build aprobados. No se reejecutaron al cerrar.

La habilitación solo corresponde a la instancia local explícita; arranques normales
y CLI conservan cierre por defecto. Persisten A02 aceptado temporalmente para
práctica, revisión de dependencias antes de exposición externa, inicial sin TTL ni
reset, entrega segura manual, hash inicial adicional, JWT sin persistencia y
límites de capacidad ya documentados. No equivale a certificación de seguridad,
accesibilidad o preparación para producción.

Este cierre solo actualiza documentación: no accede a bases ni modifica servicios.
La siguiente etapa autorizada es [Sprint 9.1: diseño LLM](sprint-9-1-diseno-llm.md).
La implementación 9.2 requiere revisión y aprobación del diseño.
