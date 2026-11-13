"""Objeto de valor para emails ASCII: no verifica existencia ni propiedad."""

import re
from dataclasses import dataclass

from app.domain.usuarios.exceptions import EmailInvalido


_PARTE_LOCAL = re.compile(r"[a-z0-9!#$%&'*+/=?^_`{|}~.-]+", re.ASCII)
_ETIQUETA_DOMINIO = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", re.ASCII)


@dataclass(frozen=True, slots=True)
class Email:
    """Dirección normalizada e inmutable; su igualdad depende del valor."""

    valor: str

    def __post_init__(self) -> None:
        if not isinstance(self.valor, str):
            raise EmailInvalido("El email debe ser una cadena.")
        if not self.valor.isascii() or any(ord(c) < 32 or ord(c) == 127 for c in self.valor):
            raise EmailInvalido("El email debe ser ASCII y no contener caracteres de control.")
        normalizado = self.valor.strip(" ").lower()
        if len(normalizado) > 254 or normalizado.count("@") != 1:
            raise EmailInvalido("El email debe tener una @ y hasta 254 caracteres.")
        local, dominio = normalizado.split("@")
        if (
            not 1 <= len(local) <= 64
            or not _PARTE_LOCAL.fullmatch(local)
            or local.startswith(".")
            or local.endswith(".")
            or ".." in local
        ):
            raise EmailInvalido("La parte local del email no es válida.")
        etiquetas = dominio.split(".")
        if (
            not 1 <= len(dominio) <= 253
            or len(etiquetas) < 2
            or any(not _ETIQUETA_DOMINIO.fullmatch(etiqueta) for etiqueta in etiquetas)
        ):
            raise EmailInvalido("El dominio debe tener al menos dos etiquetas válidas.")
        object.__setattr__(self, "valor", normalizado)

    def __str__(self) -> str:
        return self.valor
