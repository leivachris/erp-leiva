"""Traspasos de stock entre ubicaciones."""
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import (
    TraspasoStock, TraspasoStockLinea,
    Stock, MovimientoStock, Producto, Ubicacion, Empresa,
)
from ..schemas import TraspasoCreate
from ..security import get_current_user, audit, check_feature
from ..models import Usuario
from ..tenancy import require_empresa
from ..services.numeracion import generar_numero

router = APIRouter(prefix="/api/traspasos", tags=["traspasos"])


@router.post("")
def crear_traspaso(
    p: TraspasoCreate,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
    empresa: Empresa = Depends(require_empresa),
):
    check_feature(user, "inventario", db)
    if not p.lineas:
        raise HTTPException(400, "Traspaso sin líneas")

    numero = generar_numero(db, TraspasoStock, serie="TR", empresa_id=empresa.id)
    tras = TraspasoStock(
        empresa_id=empresa.id, numero=numero, motivo=p.motivo,
        notas=p.notas, usuario_id=user.id,
    )
    db.add(tras); db.flush()

    for ln in p.lineas:
        if ln.ubicacion_origen_id == ln.ubicacion_destino_id:
            raise HTTPException(400, "Origen y destino no pueden ser iguales")
        prod = db.query(Producto).filter(
            Producto.id == ln.producto_id, Producto.empresa_id == empresa.id
        ).first()
        ori = db.query(Ubicacion).filter(
            Ubicacion.id == ln.ubicacion_origen_id, Ubicacion.empresa_id == empresa.id
        ).first()
        dst = db.query(Ubicacion).filter(
            Ubicacion.id == ln.ubicacion_destino_id, Ubicacion.empresa_id == empresa.id
        ).first()
        if not (prod and ori and dst):
            raise HTTPException(404, "Producto o ubicación no encontrada")

        stock_ori = db.query(Stock).filter_by(
            empresa_id=empresa.id, producto_id=ln.producto_id, ubicacion_id=ln.ubicacion_origen_id
        ).first()
        if not stock_ori or stock_ori.cantidad < ln.cantidad:
            raise HTTPException(400, f"Stock insuficiente en origen ({ori.codigo})")

        stock_ori.cantidad -= ln.cantidad
        stock_dst = db.query(Stock).filter_by(
            empresa_id=empresa.id, producto_id=ln.producto_id, ubicacion_id=ln.ubicacion_destino_id
        ).first()
        if not stock_dst:
            stock_dst = Stock(
                empresa_id=empresa.id,
                producto_id=ln.producto_id, ubicacion_id=ln.ubicacion_destino_id, cantidad=0
            )
            db.add(stock_dst)
        stock_dst.cantidad += ln.cantidad

        db.add(TraspasoStockLinea(
            empresa_id=empresa.id, traspaso_id=tras.id,
            producto_id=ln.producto_id, cantidad=ln.cantidad,
            ubicacion_origen_id=ln.ubicacion_origen_id,
            ubicacion_destino_id=ln.ubicacion_destino_id,
        ))
        db.add(MovimientoStock(
            empresa_id=empresa.id, tipo="traspaso",
            producto_id=ln.producto_id, cantidad=ln.cantidad,
            ubicacion_origen_id=ln.ubicacion_origen_id,
            ubicacion_destino_id=ln.ubicacion_destino_id,
            usuario_id=user.id, notas=f"Traspaso {numero}",
        ))

    db.commit()
    audit(db, user, "crear", "traspaso_stock", tras.id, numero, empresa_id=empresa.id)
    return {"ok": True, "id": tras.id, "numero": numero}


@router.get("")
def listar_traspasos(
    limit: int = 50,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
    empresa: Empresa = Depends(require_empresa),
):
    res = db.query(TraspasoStock).filter(
        TraspasoStock.empresa_id == empresa.id
    ).order_by(TraspasoStock.fecha.desc()).limit(limit).all()
    return [
        {
            "id": t.id, "numero": t.numero, "fecha": t.fecha.isoformat(),
            "motivo": t.motivo, "lineas_count": len(t.lineas),
        } for t in res
    ]