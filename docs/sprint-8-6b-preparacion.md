# Sprint 8.6B · primera etapa: correcciones y preparación

Fecha: **31 de octubre de 2026**. Preparación sin despliegue, sin acceso a
usuarios_dev y sin habilitación de aprovisionamiento. No se inicia la segunda
etapa de 8.6B ni Sprint 9.

## 1. Resultado y punto de control

Se corrigieron **A01 (foco), A03 (documentación) y A04 (login/limitador)**.
A02 fue evaluado: no se encontró una actualización dentro de los rangos declarados
que resuelva el aviso. Se mantiene pendiente de decisión, sin forzar una versión
mayor ni modificar dependencias.

**Recomendación: mantener bloqueada por ahora la puesta en funcionamiento.**
No se detectó un nuevo defecto crítico; se necesita resolver o aceptar expresamente
A02, completar los controles operativos y autorizar la segunda etapa. Este informe
no autoriza migrar, arrancar servicios operativos ni abrir la barrera.

## 2. A01: foco visible

El tema compartido conserva colores, distribución y elevación actuales. Añade un
contorno sólido oscuro de **3 px**, separado **3 px**, durante foco de teclado:

- MuiButtonBase cubre botones, iconos, enlaces MUI y controles derivados.
- MuiOutlinedInput cubre inputs y selects con foco de teclado dentro del control.
- En forced-colors se usa el color de sistema Highlight; esa regla se revisó en
  código, sin afirmar una auditoría completa del modo de alto contraste.

El arnés real comprueba estilo calculado de campo, icono mostrar/ocultar y botón
Ingresar con Tab: ancho 3 px y estilo solid. Comprueba además que el contorno del
botón cambia al perder foco. Se espera el siguiente render de MUI para medir blur,
porque la clase Mui-focusVisible no desaparece sincrónicamente con el evento.
Las capturas permiten revisar que el indicador resulta distinguible sin alterar
el diseño normal. No se declara certificación WCAG.

## 3. A03: documentación vigente

Se reemplazaron los README de entrada y se añadió una guía backend con requisitos,
configuración por entorno, preflight seguro y procedimiento aislado. Todos exigen
**0003 para el backend actual**, explican cambio obligatorio/voluntario y dejan
claro que bootstrap/alta/asignación permanecen bloqueados.

Se retiraron de las guías de entrada los arranques sobre esquemas antiguos y las
afirmaciones de aprovisionamiento disponible. Los documentos de etapas anteriores
conservan sus evidencias históricas, con un aviso destacado que remite a la guía
actual; sus comandos no son instrucciones operativas para este código.

Las suites eliminan fixtures: un servidor iniciado después de ellas no dispone
automáticamente de un administrador. No se recomienda SQL manual, credenciales
reales o excepciones de barrera para conseguir un login de prueba.
El estado actual de desarrollo no se afirma sin una nueva comprobación autorizada.

## 4. A04: corrección mínima de login

Antes, login confirmaba una sesión y luego liberaba la reserva de pareja; si esa
liberación fallaba, devolvía error con una sesión vigente sin token entregado.

Ahora el orden es:

1. Reservar cupos e identificar credencial/perfil, como antes.
2. Verificar contraseña, rechazar inactivos y preparar rehash cuando corresponda.
3. **Liberar únicamente la reserva propia de pareja antes de la UoW final**.
4. Releer y revalidar usuario/credencial bajo la transacción final.
5. Aplicar rehash si procede, crear sesión con alcance derivado del estado actual,
   firmar token y confirmar la transacción.
6. Devolver el mismo LoginResultado/contrato HTTP, sin otra operación del limitador
   que pueda fallar después del commit.

No se introduce un nuevo puerto, endpoint o contrato ni se captura genéricamente
una excepción para convertirla en éxito. Los fallos técnicos siguen llegando al
manejo saneado existente. Si la liberación falla antes o después de su propio
commit, la creación de sesión todavía no ocurrió. Si firma, escritura o commit
final fallan, se mantiene el rollback de la UoW.

No se anidan UoW esperando el advisory lock: la del limitador termina antes de la
final de seguridad. Las sesiones previas permanecen intactas y válidas, sin revocar
todas las sesiones de una persona para compensar el fallo de un login nuevo.
El cambio de contraseña y logout mantienen sus revocaciones existentes.

### Presupuesto de intentos y límites de atomicidad

La IP sigue consumida para solicitudes admitidas; credenciales incorrectas retienen
su reserva de pareja. Una contraseña verificada correctamente libera solo su propia
reserva, no borra fallos anteriores. Si después falla firma/commit o cambia la
credencial concurrentemente, esa liberación no se deshace: el secreto fue correcto
en la verificación inicial. La revalidación final sigue impidiendo emitir sesión
con una credencial anterior. Este tratamiento coincide con el orden ya utilizado
para cambio de contraseña y no amplía los límites 30/IP y 5/email+IP.

No se promete atomicidad distribuida entre HTTP y PostgreSQL: una respuesta perdida
o un resultado de commit incierto pueden seguir dejando al cliente sin confirmación.
La corrección elimina el fallo técnico posterior de liberación que originó A04;
no puede garantizar entrega de un token al navegador a través de cualquier fallo
de red. No se agregaron reintentos automáticos ni se debilitó la expiración de 900 s.

### Nuevas pruebas de inyección de fallos

`test_login_completion.py` agrega siete casos entre memoria y PostgreSQL:

- Fallo antes de liberar y después de liberar: 500 saneado, sin access_token,
  sin escritura de sesión ni modificación de credencial/sesión previa.
- Reintento explícito posterior funciona sin introducir un bypass del limitador.
- Liberación precede a firma y transacción final; si firma falla, no queda sesión.
- Fallo inyectado de commit PostgreSQL revierte la nueva sesión y conserva la previa.

La regresión conserva rehash, sesiones restringidas, cambios concurrentes, límites
compartidos, intentos repetidos y revocación. No se cambió la barrera.

## 5. A02: evaluación de dependencias

Consultas realizadas al registro oficial, con TLS activo y caché local del proyecto:

| Comprobación | Resultado |
| --- | --- |
| npm audit completo | 12 entradas moderadas propagadas por minimatch; 0 altas y 0 críticas |
| npm audit --omit=dev | 0 avisos en el árbol de producción consultado |
| minimatch instalado | 10.2.6, transitivo de ESLint/typescript-eslint |
| Última rama 10 consultada | 10.2.6, aún incluida en el aviso |
| ESLint consultado | 10.14.0 declara minimatch ^10.2.6; actualizar solo ESLint no resuelve |
| typescript-eslint / estree consultados | 8.72.1; estree declara minimatch ^10.2.2 |
| Versión corregida publicada | 11.0.1; engines 18, 20 o >=22 admite Node 24, pero eso no prueba compatibilidad de API con consumidores de rama 10 |

No se instaló ni actualizó ningún paquete. No se ejecutó audit fix --force, no se
aceptaron downgrades y package.json/package-lock.json se conservan.
El aviso es [GHSA-g3hv-75wg-m249](https://github.com/advisories/GHSA-g3hv-75wg-m249),
amplificación de patrones. No se demostró una ruta explotable desde la API/bundle;
afecta herramientas de desarrollo y su exposición a patrones no confiables.

Alternativas que requieren decisión:

1. Esperar versiones de los consumidores que declaren la rama corregida, o un
   backport publicado que quede fuera del rango vulnerable; volver a consultar.
2. Autorizar una evaluación aislada de override a 11.0.1, con revisión de API,
   lint y pruebas específicas además de la suite. No se aplicó: está fuera de
   los rangos declarados y no se puede presentar como actualización compatible
   ya demostrada.
3. Aceptar temporalmente el riesgo residual de herramientas, limitando entradas
   no confiables en CI y fijando una revisión posterior. No se presume aceptación.

Python: pip check aprobó; pip-audit sigue sin estar instalado. Se revisaron
pyproject.toml y herramientas existentes; no se instalaron analizadores ni se
afirma ausencia de CVE. Permanece el aviso de Starlette/TestClient sobre httpx.
Revisar su sustitución/compatibilidad con autorización separada, sin actualizar
dependencias para ocultar el aviso.

## 6. Archivos creados y modificados

Código y pruebas:

- `frontend/src/app/theme.ts`: foco compartido.
- `backend/src/app/application/auth/service.py`: orden de liberación en login.
- `backend/tests/security/test_login_completion.py` (nuevo): siete casos de fallo.
- `backend/tests/integration/postgresql/browser_quality_audit.mjs`: aserciones de
  foco, espera del render tras blur y reporte saneado también ante fallo del arnés.

Guías:

- `README.md` y `frontend/README.md`: guías actuales reemplazadas.
- `backend/README.md` (nuevo): requisitos, configuración y preflight de pruebas.
- `docs/arquitectura.md`, `docs/etapa-4-postgresql.md`,
  `docs/etapa-5-persistencia.md`, `docs/etapa-6-api-rest.md` y
  `docs/sprint-7-autenticacion.md`: avisos de antecedente histórico.
- `docs/sprint-8-6b-preparacion.md` (este informe).

Sin cambios de contratos HTTP, puertos de Application, modelos, migraciones,
Docker, secretos, dependencias o código de la barrera. Los avisos históricos no
reescriben resultados de pruebas anteriores como si fueran verificaciones actuales.

## 7. Verificaciones

Comandos principales desde backend, después de preflight:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/security/test_login_completion.py tests/security/test_transactions.py tests/security/test_password_changes.py -p no:cacheprovider --basetemp=.pytest_cache/86b-unit-temp --tb=short
.\.venv\Scripts\python.exe -m pytest -q --run-postgres -p no:cacheprovider --basetemp=.pytest_cache/86b-full-final-temp --tb=short
```

Desde frontend:

```powershell
npm.cmd run typecheck
npm.cmd run lint
npm.cmd test
npm.cmd run build
npm.cmd audit --json --cache node_modules/.cache/npm-audit-86b
npm.cmd audit --omit=dev --json --cache node_modules/.cache/npm-audit-86b
```

La ejecución dirigida intermedia obtuvo 58 aprobadas y 59 omitidas sin PostgreSQL,
antes de incorporar el último caso PostgreSQL de fallo de commit. Vitest obtuvo
**151 aprobadas en 8 archivos**, 175,59 s. Typecheck, lint y build aprobaron; build
944 módulos y mayor chunk 218,75 kB antes de gzip.

Los primeros casos de navegador detectaron que la medición inmediata de blur aún
leía la clase MUI de foco del render anterior. Se corrigió la espera manteniendo
las aserciones exigentes de contorno. Chrome aprobó después esa prueba dirigida.
Esas ejecuciones intermedias no se contabilizan como éxito final.

Resultados finales de esta intervención:

| Verificación | Resultado |
| --- | --- |
| Suite backend completa final | **568 aprobadas**, sin fallos, **203,79 s** |
| Regresión conservada | **561 casos anteriores**, incluidos los tres navegadores |
| Casos nuevos A04 | **7 aprobados** |
| Casos PostgreSQL / sin PostgreSQL | **160 / 408**, incluidos en el total |
| Chrome / Edge / Firefox | Tres recorridos reales aprobados con las nuevas aserciones de foco |
| Frontend | **151 aprobadas**, typecheck/lint/build correctos |
| Alembic check final | **No new upgrade operations detected.**, revisión **0003** |
| Barrera en proceso Python nuevo | **Cerrada**, AprovisionamientoNoHabilitado esperado |
| Estado final de fixtures | Tablas de aplicación vacías; listeners temporales cerrados |

La primera suite completa intermedia obtuvo 565 aprobadas y tres fallos de la
medición de blur del arnés. La suite completa se repitió después del ajuste y
obtuvo las 568 aprobaciones indicadas, sin ocultar los fallos ni contar repeticiones
como casos nuevos. No se cambiaron dependencias para suprimir el aviso de httpx.

Se revisaron visualmente las capturas de foco de los tres navegadores. Sus informes
confirman contorno 3 px/solid en campo, icono y botón, cambio al perder foco,
22 vistas por navegador sin desborde horizontal, foco de diálogo contenido y
restaurado, y ausencia de navegación/datos privados tras logout. Los artefactos
ficticios se guardaron en el directorio ignorado frontend/node_modules/.cache:

- `audit-86a-chrome-1793482170943`.
- `audit-86a-edge-1793482188820`.
- `audit-86a-firefox-1793482212084`.

El prefijo del arnés conserva su nombre de auditoría anterior; los archivos son
nuevos de esta ejecución. No contienen contraseñas visibles ni trazas HTTP.
No se probó lector de pantalla ni una matriz exhaustiva de tecnologías asistivas.

## 8. Riesgos residuales A05–A08

| Riesgo | Tratamiento en esta etapa |
| --- | --- |
| A05: mezcla de versiones | Checklist de mantenimiento y publicación coordinada; prohibido rolling mixto sin diseño adicional. No se desplegó |
| A06: política acotada | Se mantienen lista común interna acotada, sin TTL/reset y antecedente inicial protegido. No se amplía política ni historial |
| A07: herramientas/advertencias | pip check correcto, auditoría CVE Python pendiente sin herramientas nuevas, aviso httpx registrado; A02 requiere decisión |
| A08: capacidad/retención/edición | Lock global, sin purga nueva ni control optimista. Medición y política de retención futuras; no se borra información operativa |

Se mantienen los límites de recarga sin JWT persistido, credencial inicial conocida
por ADMIN hasta su cambio y necesidad de entrega segura. No se implementaron
reset, recuperación, roles, refresh o funcionalidades de IA.

## 9. Lista de verificación de despliegue futuro — NO ejecutada

Esta lista concreta los controles del procedimiento de la sección 8 de
[8.6A](sprint-8-6a-auditoria.md). **Todo sigue pendiente de autorización y ejecución**.
No es una orden de operación ni evidencia de que desarrollo haya sido revisado.

- [ ] Aprobar correcciones y resolver/aceptar A02; definir responsable y ventana.
- [ ] Identificar host, puerto, base y cuenta real sin imprimir URL o secretos.
      Destino esperado de desarrollo: usuarios_dev / 127.0.0.1:5434.
- [ ] Consultar revisión actual y verificar que sea 0002. Si ya es 0003, detener
      esta migración prevista y revisar el estado; no deducirlo de documentación.
- [ ] Confirmar que 0003 depende de 0002, revisar DDL, artefactos y checksums;
      detenerse ante revisiones adicionales o archivos inesperados.
- [ ] Preparar respaldo PostgreSQL consistente, fuera del repositorio, protegido
      y con checksum; no incluir contraseñas en comandos. Incluir por procedimiento
      separado configuración/roles que pg_dump de una base no respalda.
- [ ] Verificar archivo con pg_restore --list y restauración de ensayo en otra
      base aislada autorizada. Listar el backup no prueba restauración completa.
- [ ] Habilitar mantenimiento; impedir escrituras, detener workers/procesos
      antiguos y confirmar que no queda tráfico mezclado.
- [ ] Capturar en memoria conteos, valores completos de perfiles/credenciales/
      sesiones/fechas y objetos ajenos. No imprimir hashes. Congelar escrituras
      durante comparación; igualdad de conteos por sí sola no demuestra integridad.
- [ ] Aplicar únicamente 0003 mediante el mecanismo de autorización existente.
      Los comandos siguientes son propuestos, **no ejecutados**:

```powershell
# Desde backend, solo con otra autorización operativa y preflight satisfactorio:
.\.venv\Scripts\python.exe -m alembic -x allow-development=true current
.\.venv\Scripts\python.exe -m alembic -x allow-development=true upgrade 0003
.\.venv\Scripts\python.exe -m alembic -x allow-development=true current
.\.venv\Scripts\python.exe -m alembic -x allow-development=true check
```

- [ ] Comprobar 0003, check sin diferencias, columnas/CHECK/defaults/FK, datos
      previos iguales y backfill false/null/false, sin credenciales nuevas ni
      cambios a objetos ajenos. Parar ante cualquier discrepancia.
- [ ] Iniciar exclusivamente backend compatible con 0003; no iniciar el código
      actual sobre 0002 ni volver a un backend que ignore restricciones.
- [ ] Publicar frontend compatible y proxy del mismo origen. Vite dev/preview
      no son la publicación productiva; definir HTTPS/CSP si corresponde.
- [ ] Invalidar/revalidar HTML y cachés, verificar assets nuevos y tratar pestañas
      antiguas. No prometer expulsión universal del cliente sin protocolo adicional.
- [ ] Verificar login/me/roles/logout manualmente con autorización expresa y
      contraseña introducida personalmente en la interfaz; no usar pruebas
      automatizadas, fixtures, cuentas reales en scripts o limpieza en desarrollo.
- [ ] Mantener alta/asignación/bootstrap bloqueados. Evaluar su habilitación en
      otra decisión con cambio revisado; no agregar flags para sortear la barrera.
- [ ] Reabrir tráfico solo después de controles completos y aprobación del responsable.

### Parada y contingencia

Parar ante destino/revisión incorrectos, backup no verificable, fallo de migración,
diferencias de integridad, procesos antiguos, artefactos inconsistentes, controles
de permisos fallidos o apertura no autorizada de la barrera. Mantener mantenimiento;
no continuar con comandos siguientes tras un fallo.

Comprobar rollback real si falló la migración. Si 0003 quedó confirmada, preferir
corrección hacia adelante. No hacer downgrade: no revierte contraseñas cambiadas
y puede eliminar las restricciones de acceso. Una restauración exige autorización
separada, servicios detenidos, respaldo ensayado, artefactos/configuración coherentes
y aceptación de pérdida de datos posteriores. No improvisar pg_restore --clean
en desarrollo ni eliminar volúmenes. No se ejecutó ninguna de estas acciones.

## 10. Aislamiento y detención

Preflight: configuración exclusivamente de pruebas, require_test_database,
current_database/current_user y revisión **usuarios_test / usuarios_test_admin /
127.0.0.1:5435 / 0003**. Las fixtures mantienen sus guardas antes de escrituras,
migraciones de regresión o limpieza. No hay fallback a desarrollo.

**No se accedió a usuarios_dev, puerto 5434, datos reales o secretos de desarrollo.**
No se iniciaron servicios operativos, no se cambió una migración ni se instalaron
herramientas. Los servidores temporales de pruebas se limitan a loopback.
La función productiva de aprovisionamiento no se modificó y debe seguir denegando;
no hay nuevas variables, flags, cabeceras o caminos alternativos.
El control final independiente confirmó ese rechazo, revisión 0003 y destino de
pruebas, Alembic sin diferencias y cierre de puertos temporales. Las únicas
migraciones/reversiones ejecutadas fueron las de regresión en usuarios_test.

Se entrega la primera etapa 8.6B para revisión, con **A02 pendiente de decisión**.
La puesta en funcionamiento y la segunda etapa necesitan aprobación expresa.
