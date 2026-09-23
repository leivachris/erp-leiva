"""Endpoints de tesoreria (multi-tenant)."""
from typing import Optional, List
from datetime import date, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from ..database import get_db
from ..models import (
    CuentaBancaria, MovimientoTesoreria,
    FacturaCliente, FacturaProveedor, Tercero, Empresa,
)
from ..schemas import MovimientoTesoreriaCreate
from ..security import get_current_user, audit
from ..models import Usuario
from ..tenancy import require_empresa

router = APIRouter(prefix="/api/tesoreria", tags=["tesoreria"])


# ============ CUENTAS ============
@router.get("/cuentas")
def listar_cuentas(
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
    empresa: Empresa = Depends(require_empresa),
):
    return [
        {
            "id": c.id, "nombre": c.nombre, "iban": c.iban, "banco": c.banco,
            "saldo_inicial": float(c.saldo_inicial),
            "saldo_actual": float(c.saldo_actual),
            "activo": c.activo,
        } for c in db.query(CuentaBancaria).filter(
            CuentaBancaria.empresa_id == empresa.id, CuentaBancaria.activo == True
        ).all()
    ]


@router.post("/cuentas")
def crear_cuenta(
    payload: dict, db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
    empresa: Empresa = Depends(require_empresa),
):
    c = CuentaBancaria(
        empresa_id=empresa.id,
        nombre=payload["nombre"],
        iban=payload.get("iban"),
        banco=payload.get("banco"),
        saldo_inicial=float(payload.get("saldo_inicial", 0)),
        saldo_actual=float(payload.get("saldo_inicial", 0)),
        activo=True,
    )
    db.add(c); db.commit(); db.refresh(c)
    audit(db, user, "crear", "cuenta_bancaria", c.id, c.nombre, empresa_id=empresa.id)
    return {"id": c.id, "nombre": c.nombre, "saldo_actual": c.saldo_actual}


@router.patch("/cuentas/{cid}")
def actualizar_cuenta(
    cid: int, cambios: dict,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
    empresa: Empresa = Depends(require_empresa),
):
    c = db.query(CuentaBancaria).filter(
        CuentaBancaria.id == cid, CuentaBancaria.empresa_id == empresa.id
    ).first()
    if not c: raise HTTPException(404, "Cuenta no encontrada")
    for k, v in cambios.items():
        if k in ("nombre", "iban", "banco", "saldo_inicial", "saldo_actual", "activo"):
            setattr(c, k, v)
    db.commit(); db.refresh(c)
    audit(db, user, "actualizar", "cuenta_bancaria", cid, c.nombre, empresa_id=empresa.id)
    return {"id": c.id, "nombre": c.nombre, "saldo_actual": c.saldo_actual}


# ============ MOVIMIENTOS ============
@router.get("/movimientos")
def listar_movimientos(
    cuenta_id: Optional[int] = None,
    tipo: Optional[str] = None,
    desde: Optional[date] = None,
    hasta: Optional[date] = None,
    limit: int = Query(100, le=500),
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
    empresa: Empresa = Depends(require_empresa),
):
    q = db.query(MovimientoTesoreria).options(
        joinedload(MovimientoTesoreria.cuenta)
    ).filter(MovimientoTesoreria.empresa_id == empresa.id)
    if cuenta_id: q = q.filter(MovimientoTesoreria.cuenta_id == cuenta_id)
    if tipo: q = q.filter(MovimientoTesoreria.tipo == tipo)
    if desde: q = q.filter(MovimientoTesoreria.fecha >= desde)
    if hasta: q = q.filter(MovimientoTesoreria.fecha <= hasta)
    res = q.order_by(MovimientoTesoreria.fecha.desc()).limit(limit).all()
    return [
        {
            "id": m.id, "fecha": m.fecha.isoformat(), "tipo": m.tipo,
            "cuenta_id": m.cuenta_id, "cuenta_nombre": m.cuenta.nombre if m.cuenta else "",
            "importe": float(m.importe), "concepto": m.concepto,
            "conciliado": m.conciliado,
        } for m in res
    ]


@router.post("/movimientos")
def crear_movimiento(
    p: MovimientoTesoreriaCreate, db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
    empresa: Empresa = Depends(require_empresa),
):
    c = db.query(CuentaBancaria).filter(
        CuentaBancaria.id == p.cuenta_id, CuentaBancaria.empresa_id == empresa.id
    ).first()
    if not c: raise HTTPException(404, "Cuenta no existe")
    mov = MovimientoTesoreria(empresa_id=empresa.id, **p.model_dump())
    db.add(mov)
    c.saldo_actual = float(c.saldo_actual) + float(p.importe)
    db.commit(); db.refresh(mov)
    audit(db, user, "crear", "movimiento_tesoreria", mov.id,
          f"{p.tipo} {p.importe}", empresa_id=empresa.id)
    return {"ok": True, "id": mov.id, "saldo_cuenta": c.saldo_actual}


# ============ VENCIMIENTOS ============
@router.get("/vencimientos")
def listar_vencimientos(
    dias: int = 30, db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
    empresa: Empresa = Depends(require_empresa),
):
    hoy = date.today()
    limite = hoy + timedelta(days=dias)

    cobros = []
    for f in db.query(FacturaCliente).options(joinedload(FacturaCliente.cliente)).filter(
        FacturaCliente.empresa_id == empresa.id,
        FacturaCliente.estado.in_(["emitida", "pagada_parcial", "vencida"]),
        FacturaCliente.fecha_vencimiento != None,
        FacturaCliente.fecha_vencimiento <= limite,
    ).all():
        pendiente = float(f.total - f.cobrado)
        cobros.append({
            "id": f.id, "tipo": "cobro",
            "numero": f.numero, "fecha": f.fecha.isoformat(),
            "vencimiento": f.fecha_vencimiento.isoformat(),
            "tercero_nombre": f.cliente.nombre if f.cliente else "",
            "importe": pendiente, "vencida": f.fecha_vencimiento < hoy,
        })

    pagos = []
    for f in db.query(FacturaProveedor).options(joinedload(FacturaProveedor.proveedor)).filter(
        FacturaProveedor.empresa_id == empresa.id,
        FacturaProveedor.estado.in_(["emitida", "pagada_parcial", "vencida"]),
        FacturaProveedor.fecha_vencimiento != None,
        FacturaProveedor.fecha_vencimiento <= limite,
    ).all():
        pendiente = float(f.total - f.pagado)
        pagos.append({
            "id": f.id, "tipo": "pago",
            "numero": f.numero, "fecha": f.fecha.isoformat(),
            "vencimiento": f.fecha_vencimiento.isoformat(),
            "tercero_nombre": f.proveedor.nombre if f.proveedor else "",
            "importe": pendiente, "vencida": f.fecha_vencimiento < hoy,
        })

    return {"cobros": cobros, "pagos": pagos}