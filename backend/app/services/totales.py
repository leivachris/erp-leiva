"""Calculo de totales y subtotales."""
from decimal import Decimal, ROUND_HALF_UP
from typing import List, Dict, Any


def _q(x):
    """Quantize a 2 decimales."""
    return Decimal(x).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def calcular_linea(cantidad: float, precio, descuento: float = 0) -> Decimal:
    """Subtotal de una linea: cant * precio * (1 - descuento/100)."""
    base = Decimal(str(cantidad)) * Decimal(str(precio))
    if descuento:
        base = base * (Decimal("100") - Decimal(str(descuento))) / Decimal("100")
    return _q(base)


def calcular_totales_documento(lineas: List[Dict[str, Any]]) -> Dict[str, Decimal]:
    """Calcula subtotal, total_iva y total de un documento.

    Cada linea debe tener 'subtotal' (Decimal/float) y 'iva' (str/int).
    """
    subtotal = Decimal("0")
    ivas: Dict[str, Decimal] = {}
    for ln in lineas:
        sub = ln.get("subtotal", 0)
        iva_pct = str(ln.get("iva", "21"))
        subtotal += Decimal(str(sub))
        iva_imp = Decimal(str(sub)) * Decimal(iva_pct) / Decimal("100")
        ivas[iva_pct] = ivas.get(iva_pct, Decimal("0")) + iva_imp
    total_iva = sum(ivas.values())
    total = subtotal + total_iva
    return {
        "subtotal": _q(subtotal),
        "total_iva": _q(total_iva),
        "total": _q(total),
        "iva_detalle": {k: _q(v) for k, v in ivas.items()},
    }