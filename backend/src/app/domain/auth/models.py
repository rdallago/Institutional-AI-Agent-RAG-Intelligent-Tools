from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class Credencial:
    usuario_id: UUID
    password_hash: str = field(repr=False)
    creada_at: datetime
    actualizada_at: datetime
    debe_cambiar_password: bool = field(kw_only=True)
    password_inicial_hash: str | None = field(repr=False, kw_only=True)

    def __post_init__(self):
        if type(self.debe_cambiar_password) is not bool:
            raise ValueError("El estado de la credencial debe ser booleano.")
        if self.debe_cambiar_password and self.password_inicial_hash is None:
            raise ValueError("La credencial pendiente requiere un hash inicial.")


@dataclass(frozen=True, slots=True)
class Sesion:
    id: UUID
    usuario_id: UUID
    creada_at: datetime
    expira_at: datetime
    revocada_at: datetime | None = None
    restringida: bool = field(kw_only=True)

    def __post_init__(self):
        if type(self.restringida) is not bool:
            raise ValueError("El alcance de la sesion debe ser booleano.")
