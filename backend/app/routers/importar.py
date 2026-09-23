"""Importador CSV/Excel desde el ERP antiguo u otras fuentes.

Soporta:
  - Productos (sku, nombre, familia, precio_compra, precio_venta, iva, stock_actual, ...)
  - Clientes (codigo, nombre, cif, direccion, ...)
  - Proveedores (igual que clientes, tipo=proveedor)

El usuario sube el fichero desde el frontend; este endpoint lo lee,
compara por SKU/codigo y crea o actualiza.
"""
import csv
import io
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Producto, Tercero, Familia, Empresa
from ..schemas import ImportResult
from ..security import get_current_user, audit
from ..models import Usuario
from ..tenancy import require_empresa

router = APIRouter(prefix="/api/importar", tags=["importar"])


def _leer_csv(contenido: bytes, delimitador: str = ";") -> list[dict]:
    """Lee bytes y devuelve lista de dicts."""
    texto = contenido.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(texto), delimiter=delimitador)
    return [row for row in reader]


def _norm(v):
    if v is None: return None
    v = v.strip()
    return v if v else None


def _to_float(v, default=0):
    try:
        return float(v.replace(",", ".")) if isinstance(v, str) else float(v)
    except (ValueError, AttributeError):
        return default


@router.post("/productos", response_model=ImportResult)
async def importar_productos(
    file: UploadFile = File(...),
    delimitador: str = ";",
    actualizar: bool = True,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
    empresa: Empresa = Depends(require_empresa),
):
    contenido = await file.read()
    try:
        filas = _leer_csv(contenido, delimitador)
    except Exception as e:
        raise HTTPException(400, f"Error leyendo CSV: {e}")
    if not filas:
        raise HTTPException(400, "CSV vacío")

    creados = actualizados = 0
    errores = []
    familias_cache = {}

    def familia_por_nombre(nombre: str) -> Optional[int]:
        if not nombre:
            return None
        if nombre in familias_cache:
            return familias_cache[nombre]
        codigo = nombre[:20].upper().replace(" ", "")
        fam = db.query(Familia).filter(
            Familia.empresa_id == empresa.id, Familia.codigo == codigo
        ).first()
        if not fam:
            fam = Familia(empresa_id=empresa.id, codigo=codigo, nombre=nombre[:100])
            db.add(fam); db.flush()
        familias_cache[nombre] = fam.id
        return fam.id

    for i, row in enumerate(filas, start=2):
        try:
            sku = _norm(row.get("sku") or row.get("SKU") or row.get("codigo"))
            if not sku:
                errores.append(f"Línea {i}: falta SKU")
                continue
            prod = db.query(Producto).filter(
                Producto.empresa_id == empresa.id, Producto.sku == sku
            ).first()
            data = {
                "sku": sku,
                "nombre": _norm(row.get("nombre") or row.get("descripcion")) or sku,
                "descripcion": _norm(row.get("descripcion")),
                "familia_id": familia_por_nombre(_norm(row.get("familia") or "")),
                "unidad_stock": _norm(row.get("unidad_stock") or row.get("unidad")) or "ud",
                "precio_compra": _to_float(row.get("precio_compra") or row.get("coste"), 0),
                "precio_venta": _to_float(row.get("precio_venta") or row.get("pvp"), 0),
                "iva": str(_norm(row.get("iva") or row.get("IVA")) or "21"),
                "stock_minimo": _to_float(row.get("stock_minimo") or row.get("minimo"), 0),
                "stock_actual": _to_float(row.get("stock_actual") or row.get("stock"), 0),
                "codigo_barras": _norm(row.get("codigo_barras") or row.get("ean")),
                "marca": _norm(row.get("marca")),
                "modelo": _norm(row.get("modelo")),
                "peso_kg": _to_float(row.get("peso_kg") or row.get("peso"), 0),
            }
            if prod:
                if actualizar:
                    for k, v in data.items():
                        setattr(prod, k, v)
                    actualizados += 1
            else:
                prod = Producto(empresa_id=empresa.id, **data)
                db.add(prod)
                creados += 1
        except Exception as e:
            errores.append(f"Línea {i}: {e}")

    db.commit()
    audit(db, user, "importar", "producto", None,
          f"{creados}+{actualizados}", empresa_id=empresa.id)
    return ImportResult(
        total=len(filas), creados=creados, actualizados=actualizados, errores=errores[:50],
    )


@router.post("/terceros", response_model=ImportResult)
async def importar_terceros(
    file: UploadFile = File(...),
    tipo: str = "cliente",  # cliente o proveedor
    delimitador: str = ";",
    actualizar: bool = True,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
    empresa: Empresa = Depends(require_empresa),
):
    contenido = await file.read()
    try:
        filas = _leer_csv(contenido, delimitador)
    except Exception as e:
        raise HTTPException(400, f"Error leyendo CSV: {e}")

    creados = actualizados = 0
    errores = []

    for i, row in enumerate(filas, start=2):
        try:
            codigo = _norm(row.get("codigo")) or _norm(row.get("id"))
            nombre = _norm(row.get("nombre")) or _norm(row.get("razon_social"))
            if not nombre:
                errores.append(f"Línea {i}: falta nombre")
                continue
            t = None
            if codigo:
                t = db.query(Tercero).filter(
                    Tercero.empresa_id == empresa.id, Tercero.codigo == codigo
                ).first()
            data = {
                "tipo": tipo,
                "codigo": codigo or nombre[:20].upper(),
                "nombre": nombre,
                "nombre_comercial": _norm(row.get("nombre_comercial")),
                "cif_nif": _norm(row.get("cif") or row.get("cif_nif") or row.get("nif")),
                "direccion": _norm(row.get("direccion")),
                "cp": _norm(row.get("cp") or row.get("codigo_postal")),
                "poblacion": _norm(row.get("poblacion") or row.get("ciudad")),
                "provincia": _norm(row.get("provincia")),
                "telefono": _norm(row.get("telefono") or row.get("tel")),
                "email": _norm(row.get("email")),
                "contacto": _norm(row.get("contacto")),
                "iban": _norm(row.get("iban") or row.get("ccc")),
                "forma_pago": _norm(row.get("forma_pago")),
                "dias_pago": int(_to_float(row.get("dias_pago"), 30)),
                "limite_credito": _to_float(row.get("limite_credito"), 0),
            }
            if t:
                if actualizar:
                    for k, v in data.items():
                        setattr(t, k, v)
                    actualizados += 1
            else:
                t = Tercero(empresa_id=empresa.id, **data)
                db.add(t)
                creados += 1
        except Exception as e:
            errores.append(f"Línea {i}: {e}")

    db.commit()
    audit(db, user, "importar", "tercero", None,
          f"{creados}+{actualizados} ({tipo})", empresa_id=empresa.id)
    return ImportResult(
        total=len(filas), creados=creados, actualizados=actualizados, errores=errores[:50],
    )