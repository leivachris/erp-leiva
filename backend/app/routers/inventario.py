"""Inventario fisico: recuento y ajuste."""
from datetime import date
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import (
    InventarioFisico, InventarioFisicoLinea,
    Producto, Stock, MovimientoStock, Empresa,
)
from ..schemas import InventarioCreate
from ..security import get_current_user, audit, check_feature
from ..models import Usuario
from ..tenancy import require_empresa

router = APIRouter(prefix="/api/inventario", tags=["inventario"])


@router.post("")
def crear_inventario(
    p: InventarioCreate,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
    empresa: Empresa = Depends(require_empresa),
):
    check_feature(user, "inventario", db)
    inv = InventarioFisico(
        empresa_id=empresa.id, nombre=p.nombre, fecha=p.fecha,
        notas=p.notas, usuario_id=user.id,
    )
    db.add(inv); db.flush()

    for ln in p.lineas:
        diff = ln.cantidad_contada - ln.cantidad_sistema
        db.add(InventarioFisicoLinea(
            empresa_id=empresa.id, inventario_id=inv.id,
            producto_id=ln.producto_id, ubicacion_id=ln.ubicacion_id,
            cantidad_sistema=ln.cantidad_sistema,
            cantidad_contada=ln.cantidad_contada,
            diferencia=diff,
        ))

    db.commit()
    audit(db, user, "crear", "inventario_fisico", inv.id, p.nombre, empresa_id=empresa.id)
    return {"ok": True, "id": inv.id}


@router.post("/{inv_id}/cerrar")
def cerrar_inventario(
    inv_id: int,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
    empresa: Empresa = Depends(require_empresa),
):
    inv = db.query(InventarioFisico).filter(
        InventarioFisico.id == inv_id, InventarioFisico.empresa_id == empresa.id
    ).first()
    if not inv: raise HTTPException(404, "Inventario no encontrado")
    if inv.estado == "cerrado":
        raise HTTPException(400, "Ya está cerrado")

    # Aplicar diferencias como movimientos de stock
    for ln in inv.lineas:
        if ln.diferencia == 0:
            continue
        prod = db.query(Producto).get(ln.producto_id)
        if not prod: continue
        prod.stock_actual = (prod.stock_actual or 0) + ln.diferencia

        if ln.ubicacion_id:
            stock = db.query(Stock).filter_by(
                empresa_id=empresa.id,
                producto_id=ln.producto_id, ubicacion_id=ln.ubicacion_id
            ).first()
            if not stock:
                stock = Stock(
                    empresa_id=empresa.id,
                    producto_id=ln.producto_id, ubicacion_id=ln.ubicacion_id,
                    cantidad=max(0, ln.diferencia)
                )
                db.add(stock)
            else:
                stock.cantidad = max(0, stock.cantidad + ln.diferencia)

        db.add(MovimientoStock(
            empresa_id=empresa.id,
            tipo="inventario",
            producto_id=ln.producto_id, cantidad=ln.diferencia,
            ubicacion_origen_id=ln.ubicacion_id if ln.diferencia < 0 else None,
            ubicacion_destino_id=ln.ubicacion_id if ln.diferencia > 0 else None,
            usuario_id=user.id, notas=f"Inventario {inv.nombre}",
        ))

    inv.estado = "cerrado"
    db.commit()
    audit(db, user, "cerrar", "inventario_fisico", inv.id, inv.nombre, empresa_id=empresa.id)
    return {"ok": True, "estado": inv.estado}


@router.get("")
def listar_inventarios(
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
    empresa: Empresa = Depends(require_empresa),
):
    res = db.query(InventarioFisico).filter(
        InventarioFisico.empresa_id == empresa.id
    ).order_by(InventarioFisico.fecha.desc()).limit(50).all()
    return [
        {
            "id": i.id, "nombre": i.nombre, "fecha": i.fecha.isoformat(),
            "estado": i.estado, "lineas": len(i.lineas),
        } for i in res
    ]