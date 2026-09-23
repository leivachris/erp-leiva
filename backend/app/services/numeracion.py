"""Numeracion automatica estilo espanol.

Formatos soportados:
  - "corto":   FC26001      (serie + anio 2digit + seq 5)
  - "medio":   FC-26-001    (serie + anio 2digit + seq 3)
  - "largo":   FC-2026-00001 (serie + anio 4digit + seq 5)
  - "guion":   A/26001      (cualquier serie + anio + seq)

Default: "corto" (lo mas compacto y tipico de BigTech/A3/factura espanyola).
Se puede cambiar por empresa en configuracion.
"""
from datetime import date
from sqlalchemy.orm import Session
from sqlalchemy import func


# Formato por defecto: "FC26001" (serie 2-3 letras + anio 2cifras + seq 5cifras)
# Configurable por empresa mas adelante; por ahora fijo.
FORMATO_DEFAULT = "corto"


def _formatear(serie: str, year: int, seq: int, formato: str = FORMATO_DEFAULT) -> str:
    yy = year % 100
    if formato == "corto":
        return f"{serie}{yy:02d}{seq:05d}"
    if formato == "medio":
        return f"{serie}-{yy:02d}-{seq:03d}"
    if formato == "guion":
        return f"{serie}/{yy:02d}{seq:05d}"
    # largo
    return f"{serie}-{year}-{seq:05d}"


def generar_numero(db: Session, modelo, serie: str, empresa_id: int,
                   campo_serie: str = "serie", campo_numero: str = "numero",
                   formato: str = FORMATO_DEFAULT) -> str:
    """Siguiente numero para una serie en una empresa.

    Asume columnas `empresa_id` y `serie` y `numero` en el modelo.
    """
    year = date.today().year
    yy = year % 100
    patron_corto = f"{serie}{yy:02d}%"
    patron_largo = f"{serie}-{year}-%"

    q = (
        db.query(func.count(modelo.id))
        .filter(modelo.empresa_id == empresa_id)
        .filter(getattr(modelo, campo_serie) == serie)
        .filter(
            (getattr(modelo, campo_numero).like(patron_corto)) |
            (getattr(modelo, campo_numero).like(patron_largo))
        )
    )
    n = q.scalar() or 0
    return _formatear(serie, year, n + 1, formato)


def preview_numero(serie: str, year: int = None, seq: int = 99999,
                   formato: str = FORMATO_DEFAULT) -> str:
    """Solo para preview en el frontend."""
    return _formatear(serie, year or date.today().year, seq, formato)


def siguiente_numero_serie(serie: str) -> str:
    """Preview del siguiente numero sin tocar BD."""
    return _formatear(serie, date.today().year, 99999, FORMATO_DEFAULT)