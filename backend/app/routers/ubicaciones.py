"""Endpoints de ubicaciones y stock (multi-tenant)."""
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from ..database import get_db
from ..models import Ubicacion, Stock, Producto, MovimientoStock
from ..schemas import UbicacionBase, UbicacionOut, StockOut
from ..security import get_current_user, audit
from ..models import Usuario
from ..tenancy import require_empresa
from ..models import Empresa

router = APIRouter(prefix="/api/ubicaciones", tags=["ubicaciones"])


@router.get("", response_model=List[UbicacionOut])
def listar_ubicaciones(
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
    empresa: Empresa = Depends(require_empresa),
):
    return (
        db.query(Ubicacion)
        .filter(Ubicacion.empresa_id == empresa.id, Ubicacion.activo == True)
        .order_by(Ubicacion.codigo).all()
    )


@router.post("", response_model=UbicacionOut)
def crear_ubicacion(
    u: UbicacionBase, db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
    empresa: Empresa = Depends(require_empresa),
):
    if db.query(Ubicacion).filter(
        Ubicacion.empresa_id == empresa.id, Ubicacion.codigo == u.codigo
    ).first():
        raise HTTPException(400, f"Ubicación {u.codigo} ya existe")
    ub = Ubicacion(empresa_id=empresa.id, **u.model_dump())
    db.add(ub); db.commit(); db.refresh(ub)
    audit(db, user, "crear", "ubicacion", ub.id, ub.codigo, empresa_id=empresa.id)
    return ub


@router.patch("/{ubi_id}", response_model=UbicacionOut)
def actualizar_ubicacion(
    ubi_id: int, cambios: dict,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
    empresa: Empresa = Depends(require_empresa),
):
    u = db.query(Ubicacion).filter(
        Ubicacion.id == ubi_id, Ubicacion.empresa_id == empresa.id
    ).first()
    if not u: raise HTTPException(404, "Ubicación no encontrada")
    for k, v in cambios.items():
        if k in ("codigo", "pasillo", "estanteria", "hueco", "nivel",
                 "capacidad_kg", "capacidad_m3", "notas", "activo"):
            setattr(u, k, v)
    db.commit(); db.refresh(u)
    audit(db, user, "actualizar", "ubicacion", u.id, u.codigo, empresa_id=empresa.id)
    return u


@router.delete("/{ubi_id}")
def borrar_ubicacion(
    ubi_id: int, db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
    empresa: Empresa = Depends(require_empresa),
):
    u = db.query(Ubicacion).filter(
        Ubicacion.id == ubi_id, Ubicacion.empresa_id == empresa.id
    ).first()
    if not u: raise HTTPException(404, "Ubicación no encontrada")
    if u.stocks and any(s.cantidad > 0 for s in u.stocks):
        raise HTTPException(400, "Ubicación con stock; traspasa primero")
    u.activo = False
    db.commit()
    audit(db, user, "borrar", "ubicacion", ubi_id, None, empresa_id=empresa.id)
    return {"ok": True}


# ============ STOCK ============
@router.get("/stock/total", response_model=List[StockOut])
def stock_total(
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
    empresa: Empresa = Depends(require_empresa),
):
    rows = (
        db.query(Stock)
        .options(joinedload(Stock.producto), joinedload(Stock.ubicacion))
        .filter(Stock.empresa_id == empresa.id, Stock.cantidad > 0)
        .order_by(Stock.producto_id, Stock.ubicacion_id)
        .all()
    )
    return [
        StockOut(
            id=s.id, producto_id=s.producto_id, ubicacion_id=s.ubicacion_id,
            cantidad=s.cantidad,
            producto_nombre=s.producto.nombre, producto_sku=s.producto.sku,
            ubicacion_codigo=s.ubicacion.codigo,
        ) for s in rows
    ]


@router.post("/stock/ajuste")
def ajuste_stock(
    payload: dict, db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
    empresa: Empresa = Depends(require_empresa),
):
    pid = payload.get("producto_id")
    uid = payload.get("ubicacion_id")
    cant = float(payload.get("cantidad", 0))
    motivo = payload.get("motivo", "")
    if not pid or not uid or cant == 0:
        raise HTTPException(400, "Faltan campos: producto_id, ubicacion_id, cantidad")
    p = db.query(Producto).filter(
        Producto.id == pid, Producto.empresa_id == empresa.id
    ).first()
    u = db.query(Ubicacion).filter(
        Ubicacion.id == uid, Ubicacion.empresa_id == empresa.id
    ).first()
    if not p or not u: raise HTTPException(404, "Producto o ubicación no encontrado")

    stock = db.query(Stock).filter_by(
        empresa_id=empresa.id, producto_id=pid, ubicacion_id=uid
    ).first()
    if not stock:
        stock = Stock(empresa_id=empresa.id, producto_id=pid, ubicacion_id=uid, cantidad=0)
        db.add(stock)
    stock.cantidad += cant
    if stock.cantidad < 0:
        raise HTTPException(400, "Stock no puede ser negativo")
    p.stock_actual = (p.stock_actual or 0) + cant

    tipo = "ajuste_positivo" if cant > 0 else "ajuste_negativo"
    mov = MovimientoStock(
        empresa_id=empresa.id, tipo=tipo, producto_id=pid,
        cantidad=cant, ubicacion_destino_id=uid if cant > 0 else None,
        ubicacion_origen_id=uid if cant < 0 else None,
        usuario_id=user.id, notas=motivo,
    )
    db.add(mov); db.commit()
    audit(db, user, "ajuste_stock", "stock", pid,
          f"{p.sku} {cant:+g} {u.codigo} ({motivo})", empresa_id=empresa.id)
    return {"ok": True, "stock_actual": stock.cantidad, "producto_stock": p.stock_actual}