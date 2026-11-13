"""Causas públicas fijas; nunca mensajes, cuerpos ni argumentos del proveedor."""
from app.application.ia.exceptions import IANoDisponible


class PlanificadorNoDisponible(IANoDisponible):
    mensaje = 'El planificador local no esta disponible.'


class MemoriaPlanificadorInsuficiente(PlanificadorNoDisponible):
    mensaje = 'No hay memoria suficiente para el planificador local.'


class ClimaNoDisponible(IANoDisponible):
    mensaje = 'El proveedor meteorologico no esta disponible.'
