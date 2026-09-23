"""Endpoints de dashboard y busqueda global (multi-tenant)."""
from decimal import Decimal
from datetime import date, datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, or_

from ..database import get_db
from ..models import (
    Producto, Tercero, Obra, AlbaranSalida, AlbaranEntrada,
    FacturaCliente, FacturaProveedor, MovimientoStock, Empresa,
)
from ..schemas import DashboardKPIs
from ..security import get_current_user
from ..models import Usuario
from ..tenancy import require_empresa

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/kpis", response_model=DashboardKPIs)
def kpis(
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
    empresa: Empresa = Depends(require_empresa),
):
    productos_total = db.query(func.count(Producto.id)).filter(
        Producto.empresa_id == empresa.id, Producto.activo == True
    ).scalar() or 0
    productos_bajo_minimo = db.query(func.count(Producto.id)).filter(
        Producto.empresa_id == empresa.id, Producto.activo == True,
        Producto.stock_minimo > 0, Producto.stock_actual <= Producto.stock_minimo
    ).scalar() or 0
    stock_valor = db.query(
        func.coalesce(func.sum(Producto.stock_actual * Producto.precio_compra), 0)
    ).filter(Producto.empresa_id == empresa.id, Producto.activo == True).scalar() or 0
    proveedores_total = db.query(func.count(Tercero.id)).filter(
        Tercero.empresa_id == empresa.id, Tercero.activo == True,
        Tercero.tipo.in_(["proveedor", "ambos"])
    ).scalar() or 0
    clientes_total = db.query(func.count(Tercero.id)).filter(
        Tercero.empresa_id == empresa.id, Tercero.activo == True,
        Tercero.tipo.in_(["cliente", "ambos"])
    ).scalar() or 0
    obras_activas = db.query(func.count(Obra.id)).filter(
        Obra.empresa_id == empresa.id, Obra.estado == "activa"
    ).scalar() or 0
    alb_pend = db.query(func.count(AlbaranSalida.id)).filter(
        AlbaranSalida.empresa_id == empresa.id, AlbaranSalida.estado == "confirmado"
    ).scalar() or 0

    pend_cobro = db.query(
        func.coalesce(func.sum(FacturaCliente.total - FacturaCliente.cobrado), 0)
    ).filter(
        FacturaCliente.empresa_id == empresa.id,
        FacturaCliente.estado.in_(["emitida", "pagada_parcial", "vencida"])
    ).scalar() or 0
    pend_pago = db.query(
        func.coalesce(func.sum(FacturaProveedor.total - FacturaProveedor.pagado), 0)
    ).filter(
        FacturaProveedor.empresa_id == empresa.id,
        FacturaProveedor.estado.in_(["emitida", "pagada_parcial", "vencida"])
    ).scalar() or 0

    primer_dia_mes = date.today().replace(day=1)
    ventas_mes = db.query(
        func.coalesce(func.sum(AlbaranSalida.total), 0)
    ).filter(
        AlbaranSalida.empresa_id == empresa.id,
        AlbaranSalida.fecha >= primer_dia_mes
    ).scalar() or 0
    compras_mes = db.query(
        func.coalesce(func.sum(MovimientoStock.cantidad * Producto.precio_compra), 0)
    ).join(Producto, Producto.id == MovimientoStock.producto_id).filter(
        MovimientoStock.empresa_id == empresa.id,
        MovimientoStock.tipo == "entrada_compra",
        MovimientoStock.fecha >= datetime.combine(primer_dia_mes, datetime.min.time()),
    ).scalar() or 0

    return DashboardKPIs(
        productos_total=productos_total,
        productos_bajo_minimo=productos_bajo_minimo,
        stock_valor_compra=Decimal(str(stock_valor)),
        proveedores_total=proveedores_total,
        clientes_total=clientes_total,
        obras_activas=obras_activas,
        albaranes_pendientes_facturar=alb_pend,
        facturas_cliente_pendientes=Decimal(str(pend_cobro)),
        facturas_proveedor_pendientes=Decimal(str(pend_pago)),
        ventas_mes=Decimal(str(ventas_mes)),
        compras_mes=Decimal(str(compras_mes)),
    )


@router.get("/alertas")
def alertas(
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
    empresa: Empresa = Depends(require_empresa),
):
    out = {}

    bajo = db.query(Producto).filter(
        Producto.empresa_id == empresa.id, Producto.activo == True,
        Producto.stock_minimo > 0, Producto.stock_actual <= Producto.stock_minimo,
    ).limit(20).all()
    out["bajo_stock"] = [
        {
            "id": p.id, "sku": p.sku, "nombre": p.nombre,
            "stock_actual": p.stock_actual, "stock_minimo": p.stock_minimo,
        } for p in bajo
    ]

    hace_15 = date.today() - timedelta(days=15)
    alb_sin_fact = db.query(AlbaranSalida).options(
        joinedload(AlbaranSalida.cliente),
    ).filter(
        AlbaranSalida.empresa_id == empresa.id,
        AlbaranSalida.estado == "confirmado",
        AlbaranSalida.fecha <= hace_15,
    ).limit(20).all()
    out["albaranes_sin_facturar"] = [
        {
            "id": a.id, "numero": a.numero, "fecha": a.fecha.isoformat(),
            "cliente_nombre": a.cliente.nombre if a.cliente else "",
            "total": float(a.total),
        } for a in alb_sin_fact
    ]

    return out


@router.get("/buscar")
def buscar(
    q: str, db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
    empresa: Empresa = Depends(require_empresa),
):
    if len(q) < 2:
        return {"productos": [], "terceros": [], "obras": []}
    like = f"%{q}%"
    prods = db.query(Producto).filter(
        Producto.empresa_id == empresa.id, Producto.activo == True,
        or_(Producto.sku.ilike(like), Producto.nombre.ilike(like),
            Producto.codigo_barras == q)
    ).limit(15).all()
    ters = db.query(Tercero).filter(
        Tercero.empresa_id == empresa.id, Tercero.activo == True,
        or_(Tercero.codigo.ilike(like), Tercero.nombre.ilike(like),
            Tercero.cif_nif.ilike(like))
    ).limit(15).all()
    obras = db.query(Obra).filter(
        Obra.empresa_id == empresa.id,
        Obra.codigo.ilike(like) | Obra.nombre.ilike(like)
    ).limit(15).all()
    return {
        "productos": [{"id": p.id, "sku": p.sku, "nombre": p.nombre,
                       "stock": p.stock_actual} for p in prods],
        "terceros": [{"id": t.id, "codigo": t.codigo, "nombre": t.nombre,
                      "tipo": t.tipo} for t in ters],
        "obras": [{"id": o.id, "codigo": o.codigo, "nombre": o.nombre,
                   "estado": o.estado} for o in obras],
    }