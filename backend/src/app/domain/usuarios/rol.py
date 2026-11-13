"""Roles admitidos; la autorización se implementará en etapas posteriores."""

from enum import StrEnum


class Rol(StrEnum):
    ADMIN = "ADMIN"
    USUARIO = "USUARIO"
