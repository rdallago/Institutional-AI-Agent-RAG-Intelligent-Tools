"""Barrera por defecto cerrada, incluida la CLI de aprovisionamiento.

El lanzador local autorizado inyecta una politica administrativa por instancia;
no modifica esta funcion ni habilita procesos normales o comandos bootstrap.
"""
from app.application.auth.exceptions import AprovisionamientoNoHabilitado


def require_initial_provisioning_enabled() -> None:
    raise AprovisionamientoNoHabilitado()
