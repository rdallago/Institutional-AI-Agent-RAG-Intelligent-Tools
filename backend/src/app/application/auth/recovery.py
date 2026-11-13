"""Recuperacion por operador local autorizado; no expuesta por HTTP."""
from dataclasses import replace

from app.application.auth.service import validate_password, utc_now
from app.application.auth.exceptions import PasswordReutilizada
from app.domain.usuarios.email import Email
from app.domain.usuarios.rol import Rol


class LocalAdminRecovery:
    def __init__(self,uow_factory,hasher,*,clock=utc_now):
        self.uow_factory,self.hasher,self.clock=uow_factory,hasher,clock

    def _target(self,uow,user_id,email):
        user=uow.usuarios.obtener_por_id(user_id)
        credential=uow.credential(user_id)
        if (user is None or not user.activo or user.rol is not Rol.ADMIN
                or str(user.email)!=email or credential is None):
            raise ValueError('Cuenta no apta para recuperacion.')
        return credential

    def reset(self,user_id,email,password):
        normalized=str(Email(email))
        validate_password(password)
        with self.uow_factory() as uow:
            original=self._target(uow,user_id,normalized)
        if self.hasher.verify(original.password_hash,password) or (
                original.password_inicial_hash is not None
                and self.hasher.verify(original.password_inicial_hash,password)):
            raise PasswordReutilizada()
        encoded=self.hasher.hash(password)
        # Hash fuera del lock; CAS y revocacion en la misma transaccion de seguridad.
        with self.uow_factory() as uow:
            current=self._target(uow,user_id,normalized)
            if current!=original:
                raise ValueError('La credencial cambio durante la recuperacion.')
            now=self.clock()
            uow.put_credential(replace(current,password_hash=encoded,actualizada_at=now,
                                       debe_cambiar_password=False))
            uow.revoke(user_id,now)
