"""Endpoints de TPV (punto de venta)."""
from decimal import Decimal
from datetime import datetime, date
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from ..database import get_db
from ..models import (
    SesionCaja, TicketTPV, TicketTPVLinea,
    Producto, Tercero, Stock, MovimientoStock, Empresa,
)
from ..schemas import (
    SesionCajaAbrir, SesionCajaCerrar, TicketTPVCreate,
)
from ..security import get_current_user, audit, check_feature
from ..models import Usuario
from ..tenancy import require_empresa
from ..services.numeracion import generar_numero

router = APIRouter(prefix="/api/tpv", tags=["tpv"])


# ============ SESION DE CAJA ============
@router.post("/sesion/abrir")
def abrir_sesion(
    p: SesionCajaAbrir,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
    empresa: Empresa = Depends(require_empresa),
):
    check_feature(user, "punto_venta", db)
    # Bloquear si ya hay una sesion abierta por este usuario
    abierta = db.query(SesionCaja).filter(
        SesionCaja.empresa_id == empresa.id, SesionCaja.usuario_id == user.id,
        SesionCaja.cerrada == False
    ).first()
    if abierta:
        raise HTTPException(400, "Ya tienes una sesión de caja abierta")
    s = SesionCaja(
        empresa_id=empresa.id, usuario_id=user.id,
        saldo_inicial=p.saldo_inicial,
        saldo_final_teorico=p.saldo_inicial,
    )
    db.add(s); db.commit(); db.refresh(s)
    audit(db, user, "abrir_caja", "sesion_caja", s.id, None, empresa_id=empresa.id)
    return {"id": s.id, "saldo_inicial": float(s.saldo_inicial)}


@router.post("/sesion/{sesion_id}/cerrar")
def cerrar_sesion(
    sesion_id: int, p: SesionCajaCerrar,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
    empresa: Empresa = Depends(require_empresa),
):
    s = db.query(SesionCaja).filter(
        SesionCaja.id == sesion_id, SesionCaja.empresa_id == empresa.id,
        SesionCaja.cerrada == False
    ).first()
    if not s: raise HTTPException(404, "Sesión no encontrada o ya cerrada")

    # Calcular saldo teorico: inicial + cobros en efectivo
    from sqlalchemy import func
    total_cobros = db.query(func.coalesce(func.sum(TicketTPV.total), 0)).filter(
        TicketTPV.empresa_id == empresa.id,
        TicketTPV.sesion_caja_id == sesion_id,
        TicketTPV.forma_pago == "efectivo"
    ).scalar() or 0
    s.saldo_final_teorico = float(s.saldo_inicial) + float(total_cobros)
    s.saldo_final_real = float(p.saldo_final_real)
    s.diferencia = s.saldo_final_real - s.saldo_final_teorico
    s.fecha_cierre = datetime.utcnow()
    s.cerrada = True
    s.notas = p.notas
    db.commit()
    audit(db, user, "cerrar_caja", "sesion_caja", s.id,
          f"diferencia {s.diferencia:.2f}", empresa_id=empresa.id)
    return {
        "saldo_teorico": s.saldo_final_teorico,
        "saldo_real": s.saldo_final_real,
        "diferencia": s.diferencia,
    }


@router.get("/sesion/actual")
def sesion_actual(
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
    empresa: Empresa = Depends(require_empresa),
):
    s = db.query(SesionCaja).filter(
        SesionCaja.empresa_id == empresa.id, SesionCaja.usuario_id == user.id,
        SesionCaja.cerrada == False
    ).first()
    if not s:
        return {"abierta": False}
    from sqlalchemy import func
    total_cobros = db.query(func.coalesce(func.sum(TicketTPV.total), 0)).filter(
        TicketTPV.empresa_id == empresa.id, TicketTPV.sesion_caja_id == s.id
    ).scalar() or 0
    return {
        "abierta": True,
        "id": s.id,
        "saldo_inicial": float(s.saldo_inicial),
        "saldo_teorico": float(s.saldo_inicial) + float(total_cobros),
        "tickets_count": db.query(func.count(TicketTPV.id)).filter(
            TicketTPV.sesion_caja_id == s.id
        ).scalar() or 0,
    }


# ============ TICKETS ============
@router.post("/ticket")
def crear_ticket(
    p: TicketTPVCreate,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
    empresa: Empresa = Depends(require_empresa),
):
    check_feature(user, "punto_venta", db)
    if not p.lineas:
        raise HTTPException(400, "Ticket sin líneas")

    sesion = db.query(SesionCaja).filter(
        SesionCaja.empresa_id == empresa.id, SesionCaja.usuario_id == user.id,
        SesionCaja.cerrada == False
    ).first()
    if not sesion:
        raise HTTPException(400, "No tienes sesión de caja abierta. Abre caja primero.")

    numero = generar_numero(db, TicketTPV, serie="T", empresa_id=empresa.id)

    # Calcular totales
    total = Decimal("0")
    lineas_data = []
    for ln in p.lineas:
        prod = db.query(Producto).filter(
            Producto.id == ln.producto_id, Producto.empresa_id == empresa.id
        ).first()
        if not prod: raise HTTPException(404, f"Producto {ln.producto_id} no existe")
        if (prod.stock_actual or 0) < ln.cantidad:
            raise HTTPException(400, f"Stock insuficiente: {prod.sku} tiene {prod.stock_actual}")
        precio = ln.precio if ln.precio is not None else prod.precio_venta
        sub = Decimal(str(ln.cantidad)) * Decimal(str(precio))
        total += sub
        lineas_data.append((ln, prod, sub, precio))

    # aplicar IVA simple (precio con IVA incluido) -> desglosar
    ivas: dict = {}
    subtotal_sin_iva = Decimal("0")
    for ln, prod, sub, precio in lineas_data:
        iva_pct = Decimal(ln.iva)
        base = sub / (Decimal("100") + iva_pct) * Decimal("100")
        iva_imp = sub - base
        ivas[iva_pct] = ivas.get(iva_pct, Decimal("0")) + iva_imp
        subtotal_sin_iva += base

    entregado = Decimal(str(p.entregado))
    cambio = max(Decimal("0"), entregado - total) if p.forma_pago == "efectivo" else Decimal("0")

    ticket = TicketTPV(
        empresa_id=empresa.id, sesion_caja_id=sesion.id,
        numero=numero, fecha=datetime.utcnow(),
        cliente_id=p.cliente_id, usuario_id=user.id,
        subtotal=float(subtotal_sin_iva),
        total_iva=float(sum(ivas.values())),
        total=float(total),
        forma_pago=p.forma_pago,
        entregado=float(entregado), cambio=float(cambio),
    )
    db.add(ticket); db.flush()

    for ln, prod, sub, precio in lineas_data:
        db.add(TicketTPVLinea(
            empresa_id=empresa.id, ticket_id=ticket.id,
            producto_id=ln.producto_id, cantidad=ln.cantidad,
            precio=precio, iva=ln.iva, subtotal=float(sub),
        ))
        prod.stock_actual = (prod.stock_actual or 0) - ln.cantidad
        # Decrementar stock primera ubicacion con cantidad
        stock = db.query(Stock).filter(
            Stock.empresa_id == empresa.id,
            Stock.producto_id == ln.producto_id, Stock.cantidad > 0
        ).order_by(Stock.cantidad.desc()).first()
        if stock:
            stock.cantidad = max(0, stock.cantidad - ln.cantidad)
        db.add(MovimientoStock(
            empresa_id=empresa.id, tipo="salida_venta",
            producto_id=ln.producto_id, cantidad=-ln.cantidad,
            usuario_id=user.id, notas=f"Ticket {numero}",
        ))

    db.commit()
    audit(db, user, "crear", "ticket_tpv", ticket.id, numero, empresa_id=empresa.id)
    return {
        "ok": True, "id": ticket.id, "numero": numero,
        "subtotal": float(subtotal_sin_iva),
        "total_iva": float(sum(ivas.values())),
        "total": float(total),
        "cambio": float(cambio),
    }