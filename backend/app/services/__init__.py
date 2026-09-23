"""Servicios de logica de negocio."""
from .numeracion import generar_numero, siguiente_numero_serie
from .totales import calcular_linea, calcular_totales_documento

__all__ = [
    "generar_numero", "siguiente_numero_serie",
    "calcular_linea", "calcular_totales_documento",
]