"""Endpoints de albaranes (multi-tenant)."""
from typing import List, Optional
from decimal import Decimal
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from ..database import get_db
from ..models import (
    AlbaranEntrada, AlbaranEntradaLinea,
    AlbaranSalida, AlbaranSalidaLinea,
    Producto, Tercero, Obra, Stock, MovimientoStock,
    PedidoCompra, PedidoCompraLinea, Empresa,
)
from ..schemas import (
    AlbaranEntradaCreate, AlbaranEntradaOut,
    AlbaranSalidaCreate, AlbaranSalidaOut,
)
from ..security import get_current_user, audit, check_feature
from ..models import Usuario
from ..tenancy import require_empresa
from ..services.numeracion import generar_numero
from ..services.totales import calcular_linea, calcular_totales_documento

router = APIRouter(prefix="/api/albaranes", tags=["albaranes"])


# ====================== ALBARANES DE ENTRADA ======================
@router.get("/entrada", response_model=List[AlbaranEntradaOut])
def listar_albaranes_entrada(
    proveedor_id: Optional[int] = None,
    estado: Optional[str] = None,
    limit: int = Query(50, le=500),
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
    empresa: Empresa = Depends(require_empresa),
):
    q = db.query(AlbaranEntrada).options(joinedload(AlbaranEntrada.proveedor)).filter(
        AlbaranEntrada.empresa_id == empresa.id
    )
    if proveedor_id: q = q.filter(AlbaranEntrada.proveedor_id == proveedor_id)
    if estado: q = q.filter(AlbaranEntrada.estado == estado)
    res = q.order_by(AlbaranEntrada.fecha.desc(), AlbaranEntrada.id.desc()).limit(limit).all()
    out = []
    for a in res:
        x = AlbaranEntradaOut.model_validate(a)
        x.proveedor_nombre = a.proveedor.nombre if a.proveedor else ""
        out.append(x)
    return out


@router.post("/entrada", response_model=AlbaranEntradaOut)
def crear_albaran_entrada(
    p: AlbaranEntradaCreate, db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
    empresa: Empresa = Depends(require_empresa),
):
    check_feature(user, "inventario", db)
    if not p.lineas:
        raise HTTPException(400, "Albarán sin líneas")
    if not db.query(Tercero).filter(
        Tercero.id == p.proveedor_id, Tercero.empresa_id == empresa.id
    ).first():
        raise HTTPException(404, "Proveedor no existe en tu empresa")

    numero = p.numero or generar_numero(db, AlbaranEntrada, serie=p.serie, empresa_id=empresa.id)

    alb = AlbaranEntrada(
        empresa_id=empresa.id, numero=numero, serie=p.serie,
        proveedor_id=p.proveedor_id, pedido_id=p.pedido_id,
        fecha=p.fecha, numero_proveedor=p.numero_proveedor,
        estado="confirmado", notas=p.notas, creado_por_id=user.id,
    )
    db.add(alb); db.flush()

    for ln in p.lineas:
        prod = db.query(Producto).filter(
            Producto.id == ln.producto_id, Producto.empresa_id == empresa.id
        ).first()
        if not prod: raise HTTPException(404, f"Producto {ln.producto_id} no existe")

        db.add(AlbaranEntradaLinea(
            empresa_id=empresa.id, albaran_id=alb.id,
            producto_id=ln.producto_id, cantidad=ln.cantidad,
            ubicacion_id=ln.ubicacion_id, precio=ln.precio,
            iva=ln.iva, lote=ln.lote, caducidad=ln.caducidad,
        ))

        if ln.ubicacion_id:
            stock = db.query(Stock).filter_by(
                empresa_id=empresa.id,
                producto_id=ln.producto_id, ubicacion_id=ln.ubicacion_id
            ).first()
            if not stock:
                stock = Stock(
                    empresa_id=empresa.id,
                    producto_id=ln.producto_id, ubicacion_id=ln.ubicacion_id, cantidad=0
                )
                db.add(stock)
            stock.cantidad += ln.cantidad

        prod.stock_actual = (prod.stock_actual or 0) + ln.cantidad

        db.add(MovimientoStock(
            empresa_id=empresa.id, tipo="entrada_compra",
            producto_id=ln.producto_id, cantidad=ln.cantidad,
            ubicacion_destino_id=ln.ubicacion_id,
            albaran_entrada_id=alb.id, pedido_compra_id=p.pedido_id,
            usuario_id=user.id,
        ))

        if p.pedido_id:
            pline = db.query(PedidoCompraLinea).filter_by(
                empresa_id=empresa.id,
                pedido_id=p.pedido_id, producto_id=ln.producto_id
            ).first()
            if pline:
                pline.cantidad_recibida = (pline.cantidad_recibida or 0) + ln.cantidad

    db.commit()
    audit(db, user, "crear", "albaran_entrada", alb.id, alb.numero, empresa_id=empresa.id)
    db.refresh(alb)
    out = AlbaranEntradaOut.model_validate(alb)
    out.proveedor_nombre = alb.proveedor.nombre if alb.proveedor else ""
    return out


# ====================== ALBARANES DE SALIDA ======================
@router.get("/salida", response_model=List[AlbaranSalidaOut])
def listar_albaranes_salida(
    cliente_id: Optional[int] = None,
    obra_id: Optional[int] = None,
    estado: Optional[str] = None,
    limit: int = Query(50, le=500),
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
    empresa: Empresa = Depends(require_empresa),
):
    q = db.query(AlbaranSalida).options(
        joinedload(AlbaranSalida.cliente), joinedload(AlbaranSalida.obra),
    ).filter(AlbaranSalida.empresa_id == empresa.id)
    if cliente_id: q = q.filter(AlbaranSalida.cliente_id == cliente_id)
    if obra_id: q = q.filter(AlbaranSalida.obra_id == obra_id)
    if estado: q = q.filter(AlbaranSalida.estado == estado)
    res = q.order_by(AlbaranSalida.fecha.desc(), AlbaranSalida.id.desc()).limit(limit).all()
    out = []
    for a in res:
        x = AlbaranSalidaOut.model_validate(a)
        x.cliente_nombre = a.cliente.nombre if a.cliente else ""
        x.obra_nombre = a.obra.nombre if a.obra else None
        out.append(x)
    return out


@router.post("/salida", response_model=AlbaranSalidaOut)
def crear_albaran_salida(
    p: AlbaranSalidaCreate, db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
    empresa: Empresa = Depends(require_empresa),
):
    check_feature(user, "ventas", db)
    if not p.lineas:
        raise HTTPException(400, "Albarán sin líneas")
    if not db.query(Tercero).filter(
        Tercero.id == p.cliente_id, Tercero.empresa_id == empresa.id
    ).first():
        raise HTTPException(404, "Cliente no existe")
    if p.obra_id and not db.query(Obra).filter(
        Obra.id == p.obra_id, Obra.empresa_id == empresa.id
    ).first():
        raise HTTPException(404, "Obra no existe")

    lineas_calc = []
    for ln in p.lineas:
        sub = calcular_linea(ln.cantidad, ln.precio, ln.descuento)
        lineas_calc.append({"subtotal": sub, "iva": ln.iva})
    totales = calcular_totales_documento(lineas_calc)

    numero = p.numero or generar_numero(db, AlbaranSalida, serie=p.serie, empresa_id=empresa.id)

    alb = AlbaranSalida(
        empresa_id=empresa.id, numero=numero, serie=p.serie,
        cliente_id=p.cliente_id, obra_id=p.obra_id, fecha=p.fecha,
        transportista=p.transportista, matricula=p.matricula,
        estado="confirmado", notas=p.notas,
        subtotal=totales["subtotal"], total_iva=totales["total_iva"],
        total=totales["total"], creado_por_id=user.id,
    )
    db.add(alb); db.flush()

    for ln in p.lineas:
        prod = db.query(Producto).filter(
            Producto.id == ln.producto_id, Producto.empresa_id == empresa.id
        ).first()
        if not prod: raise HTTPException(404, f"Producto {ln.producto_id} no existe")
        if (prod.stock_actual or 0) < ln.cantidad:
            raise HTTPException(
                400,
                f"Stock insuficiente para {prod.sku}: tiene {prod.stock_actual}, "
                f"necesita {ln.cantidad}"
            )
        sub = calcular_linea(ln.cantidad, ln.precio, ln.descuento)
        db.add(AlbaranSalidaLinea(
            empresa_id=empresa.id, albaran_id=alb.id,
            producto_id=ln.producto_id, cantidad=ln.cantidad,
            precio=ln.precio, descuento=ln.descuento,
            iva=ln.iva, subtotal=sub,
        ))
        prod.stock_actual = (prod.stock_actual or 0) - ln.cantidad

        restante = ln.cantidad
        for stock in (
            db.query(Stock)
            .filter(Stock.empresa_id == empresa.id,
                    Stock.producto_id == ln.producto_id,
                    Stock.cantidad > 0)
            .order_by(Stock.cantidad.desc()).all()
        ):
            if restante <= 0: break
            tomado = min(stock.cantidad, restante)
            stock.cantidad -= tomado
            restante -= tomado

        db.add(MovimientoStock(
            empresa_id=empresa.id, tipo="salida_venta",
            producto_id=ln.producto_id, cantidad=-ln.cantidad,
            albaran_salida_id=alb.id, obra_id=p.obra_id, usuario_id=user.id,
        ))

    db.commit()
    audit(db, user, "crear", "albaran_salida", alb.id, alb.numero, empresa_id=empresa.id)
    db.refresh(alb)
    out = AlbaranSalidaOut.model_validate(alb)
    out.cliente_nombre = alb.cliente.nombre if alb.cliente else ""
    out.obra_nombre = alb.obra.nombre if alb.obra else None
    return out