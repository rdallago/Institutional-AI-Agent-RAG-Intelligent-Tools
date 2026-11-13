# Recuperación local del administrador existente

Preparado el 3 de noviembre de 2026. **No se ejecutó el restablecimiento real.**
La cuenta indicada por el responsable fue localizada por consulta READ ONLY:
rdallago@gmail.com, UUID `32eabde4-7d17-4029-a47a-60e2e38faf05`, ADMIN activo con
credencial existente, único administrador en esa lectura. Se vuelve a verificar
identidad/rol/estado al ejecutar; no se crean cuentas o credenciales inexistentes.

El flujo HTTP de cambio requiere conocer la contraseña anterior; bootstrap y
asignación inicial no reemplazan credenciales existentes. Se preparó por ello
una CLI separada de mantenimiento, sin endpoint público y sin abrir la barrera
de aprovisionamiento.

## Procedimiento, pendiente de confirmación expresa

1. Confirmar con el responsable que la cuenta es **rdallago@gmail.com** y que
   autoriza restablecer su contraseña y revocar sus sesiones.
2. En una terminal PowerShell propia, desde la raíz del proyecto, inspección opcional
   de solo lectura:

```powershell
.\backend\.venv\Scripts\python.exe -B -m app.presentation.cli.recover_admin --email rdallago@gmail.com
```

3. **Solo después de autorizar**, ejecutar desde esa terminal interactiva:

```powershell
.\backend\.venv\Scripts\python.exe -B -m app.presentation.cli.recover_admin --email rdallago@gmail.com --usuario-id 32eabde4-7d17-4029-a47a-60e2e38faf05 --allow-development --apply
```

4. Revisar la cuenta mostrada. La CLI exige escribir exactamente
   `RESTABLECER rdallago@gmail.com` antes de pedir el secreto. Introducir la nueva
   contraseña dos veces, con entrada oculta. No enviarla por chat, argumento,
   variable de entorno o archivo; no usar pipes o transcripción de terminal.
5. Se aplica la política existente: 15–128 puntos Unicode, máximo 512 bytes UTF-8,
   sin recortar/normalizar y rechazo de contraseñas comunes de la política. Debe
   diferir de la contraseña actual y de la inicial si se conserva ese hash.
6. Ante éxito, abrir http://127.0.0.1:5173/login e ingresar normalmente con el
   email y la nueva contraseña. Las sesiones previas quedarán inválidas; no es
   necesario extraer/borrar manualmente JWT. Login crea una nueva sesión mediante
   el flujo normal. No se realiza login automático desde la CLI.

## Controles implementados

Solo configuración operativa y destino exacto usuarios_dev / 127.0.0.1:5434,
incluyendo comprobación current_database. No hay selector de usuarios_test.
Es obligatoria selección por UUID para escritura, incluso si hubiera varios ADMIN.
El email y UUID deben resolver al mismo ADMIN activo con credencial preexistente.
La confirmación del terminal se suma a la autorización del responsable.

Se usa Argon2Hasher existente (Argon2id y parámetros normales), validate_password
y la misma SecurityUnitOfWork/advisory lock del backend. La contraseña se hashea
fuera de la transacción final. Allí se revalida usuario y credencial mediante CAS,
se actualiza el hash y se marcan revocadas las sesiones de esa cuenta mediante
uow.revoke, **sin eliminarlas**. Actualización/revocación son atómicas. No se
reutiliza la contraseña anterior, no se cambia JWT global y no se tocan otras cuentas.

La contraseña nueva es definitiva, elegida por el responsable; se deja acceso
normal, sin obligar a otro cambio inmediato. Se conserva el hash inicial previo
para la prevención de reutilización ya existente. No se limpian intentos de login:
si existe un límite temporal activo, esperar su vencimiento, sin saltarse cuotas.

La entrada requiere TTY y aborta si getpass no puede ocultar el eco. No se guardan
contraseñas o hashes en logs/archivos/argumentos. No se promete borrado seguro de
la memoria Python. No requiere reiniciar servicios, migraciones o tocar RAG,
volúmenes, documentos o embeddings. No ejecutar bajo depuradores que capturen secretos.

## Verificación aislada

Se añadieron tests de cuenta exacta, política/reutilización, revocación sin borrar,
login normal posterior, rollback ante fallo de revocación y rechazo de entrada
visible/no interactiva. Usan cuentas, secretos y almacenes ficticios de memoria;
no cambian la credencial real ni acceden a usuarios_test.

Resultado: **8 pruebas aprobadas**, sin fallos, 0,11 s. Permanece el aviso
preexistente Starlette/TestClient. Solo se comprobó además --help de la CLI;
no se ejecutó --apply sobre la cuenta real.
