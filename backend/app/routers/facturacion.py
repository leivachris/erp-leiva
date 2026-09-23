"""Endpoints de facturacion (multi-tenant, con IRPF y recargo equivalencia)."""
from typing import List, Optional
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from ..database import get_db
from ..models import (
    FacturaCliente, FacturaClienteLinea,
    FacturaProveedor, FacturaProveedorLinea,
    Tercero, Producto, MovimientoTesoreria, CuentaBancaria, Empresa,
)
from ..schemas import FacturaClienteCreate, FacturaProveedorCreate
from ..security import get_current_user, audit, check_feature
from ..models import Usuario
from ..tenancy import require_empresa
from ..services.numeracion import generar_numero
from ..services.totales import calcular_linea, calcular_totales_documento

router = APIRouter(prefix="/api/facturacion", tags=["facturacion"])


def _aplicar_irpf_y_total(base_imponible: float, total_iva: float,
                          irpf_pct: float, recargo_pct: float = 0):
    """Calcula IRPF, recargo equivalencia y total final."""
    irpf_imp = round(base_imponible * irpf_pct / 100, 2)
    recargo_imp = round(base_imponible * recargo_pct / 100, 2)
    total = base_imponible + total_iva + recargo_imp - irpf_imp
    return irpf_imp, recargo_imp, total


# =================== FACTURAS CLIENTE ===================
@router.get("/cliente")
def listar_facturas_cliente(
    cliente_id: Optional[int] = None,
    estado: Optional[str] = None,
    limit: int = Query(100, le=500),
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
    empresa: Empresa = Depends(require_empresa),
):
    q = db.query(FacturaCliente).options(joinedload(FacturaCliente.cliente)).filter(
        FacturaCliente.empresa_id == empresa.id
    )
    if cliente_id: q = q.filter(FacturaCliente.cliente_id == cliente_id)
    if estado: q = q.filter(FacturaCliente.estado == estado)
    res = q.order_by(FacturaCliente.fecha.desc()).limit(limit).all()
    return [
        {
            "id": f.id, "numero": f.numero, "serie": f.serie,
            "cliente_id": f.cliente_id,
            "cliente_nombre": f.cliente.nombre if f.cliente else "",
            "fecha": f.fecha.isoformat(),
            "fecha_vencimiento": f.fecha_vencimiento.isoformat() if f.fecha_vencimiento else None,
            "estado": f.estado,
            "total": float(f.total), "cobrado": float(f.cobrado),
            "irpf_porcentaje": f.irpf_porcentaje or 0,
            "importe_irpf": float(f.importe_irpf or 0),
            "pendiente": float(f.total - f.cobrado),
        } for f in res
    ]


@router.post("/cliente")
def crear_factura_cliente(
    p: FacturaClienteCreate, db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
    empresa: Empresa = Depends(require_empresa),
):
    check_feature(user, "facturacion", db)
    if not p.lineas:
        raise HTTPException(400, "Factura sin líneas")
    cli = db.query(Tercero).filter(
        Tercero.id == p.cliente_id, Tercero.empresa_id == empresa.id
    ).first()
    if not cli: raise HTTPException(404, "Cliente no existe")

    # IRPF por defecto del cliente si no se especifica
    irpf_pct = p.irpf_porcentaje or (cli.irpf_porcentaje if cli.aplica_irpf else 0)
    recargo_pct = p.recargo_equivalencia or (5.2 if cli.recargo_equivalencia else 0)

    lineas_calc = []
    for ln in p.lineas:
        sub = calcular_linea(ln.get("cantidad", 1), ln["precio"], ln.get("descuento", 0))
        lineas_calc.append({"subtotal": sub, "iva": str(ln.get("iva", "21"))})
    totales = calcular_totales_documento(lineas_calc)

    # aplicar IRPF y recargo
    irpf_imp, recargo_imp, total = _aplicar_irpf_y_total(
        float(totales["subtotal"]), float(totales["total_iva"]),
        irpf_pct, recargo_pct
    )

    numero = p.numero or generar_numero(db, FacturaCliente, serie=p.serie, empresa_id=empresa.id)

    fac = FacturaCliente(
        empresa_id=empresa.id, numero=numero, serie=p.serie,
        cliente_id=p.cliente_id, fecha=p.fecha,
        fecha_vencimiento=p.fecha_vencimiento, estado="emitida",
        notas=p.notas, subtotal=totales["subtotal"], total_iva=totales["total_iva"],
        irpf_porcentaje=irpf_pct, importe_irpf=irpf_imp,
        recargo_equivalencia=recargo_pct, total_recargo=recargo_imp,
        total=total, cobrado=0,
    )
    db.add(fac); db.flush()

    for ln in p.lineas:
        sub = calcular_linea(ln.get("cantidad", 1), ln["precio"], ln.get("descuento", 0))
        db.add(FacturaClienteLinea(
            empresa_id=empresa.id, factura_id=fac.id,
            producto_id=ln.get("producto_id"),
            albaran_salida_id=ln.get("albaran_salida_id"),
            descripcion=ln["descripcion"], cantidad=ln.get("cantidad", 1),
            precio=ln["precio"], descuento=ln.get("descuento", 0),
            iva=str(ln.get("iva", "21")), subtotal=sub,
        ))

    db.commit()
    audit(db, user, "crear", "factura_cliente", fac.id, fac.numero, empresa_id=empresa.id)
    return {
        "ok": True, "id": fac.id, "numero": fac.numero,
        "subtotal": float(fac.subtotal), "total_iva": float(fac.total_iva),
        "irpf": irpf_imp, "recargo": recargo_imp, "total": float(fac.total),
    }


@router.post("/cliente/{fac_id}/cobrar")
def registrar_cobro(
    fac_id: int, payload: dict, db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
    empresa: Empresa = Depends(require_empresa),
):
    fac = db.query(FacturaCliente).filter(
        FacturaCliente.id == fac_id, FacturaCliente.empresa_id == empresa.id
    ).first()
    if not fac: raise HTTPException(404, "Factura no encontrada")
    pendiente = float(fac.total - fac.cobrado)
    importe = float(payload.get("importe", 0))
    if importe <= 0 or importe > pendiente + 0.01:
        raise HTTPException(400, f"Importe debe estar entre 0 y {pendiente:.2f}")

    cuenta_id = payload.get("cuenta_id")
    cuenta = db.query(CuentaBancaria).filter(
        CuentaBancaria.id == cuenta_id, CuentaBancaria.empresa_id == empresa.id
    ).first()
    if not cuenta: raise HTTPException(400, "Cuenta bancaria inválida")

    db.add(MovimientoTesoreria(
        empresa_id=empresa.id,
        fecha=payload.get("fecha") or date.today(),
        tipo="cobro", cuenta_id=cuenta_id,
        importe=importe, concepto=payload.get("concepto", f"Cobro {fac.numero}"),
        factura_cliente_id=fac.id, tercero_id=fac.cliente_id,
    ))
    fac.cobrado = float(fac.cobrado) + importe
    fac.estado = "pagada" if abs(fac.cobrado - float(fac.total)) < 0.01 else "pagada_parcial"
    cuenta.saldo_actual = float(cuenta.saldo_actual) + importe

    db.commit()
    audit(db, user, "cobrar", "factura_cliente", fac.id,
          f"{importe:.2f}€ {cuenta.nombre}", empresa_id=empresa.id)
    return {"ok": True, "cobrado": fac.cobrado,
            "pendiente": float(fac.total - fac.cobrado), "estado": fac.estado}


# =================== FACTURAS PROVEEDOR ===================
@router.get("/proveedor")
def listar_facturas_proveedor(
    proveedor_id: Optional[int] = None,
    estado: Optional[str] = None,
    limit: int = Query(100, le=500),
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
    empresa: Empresa = Depends(require_empresa),
):
    q = db.query(FacturaProveedor).options(joinedload(FacturaProveedor.proveedor)).filter(
        FacturaProveedor.empresa_id == empresa.id
    )
    if proveedor_id: q = q.filter(FacturaProveedor.proveedor_id == proveedor_id)
    if estado: q = q.filter(FacturaProveedor.estado == estado)
    res = q.order_by(FacturaProveedor.fecha.desc()).limit(limit).all()
    return [
        {
            "id": f.id, "numero": f.numero, "serie": f.serie,
            "proveedor_id": f.proveedor_id,
            "proveedor_nombre": f.proveedor.nombre if f.proveedor else "",
            "fecha": f.fecha.isoformat(),
            "fecha_vencimiento": f.fecha_vencimiento.isoformat() if f.fecha_vencimiento else None,
            "numero_proveedor": f.numero_proveedor,
            "estado": f.estado,
            "total": float(f.total), "pagado": float(f.pagado),
            "irpf_porcentaje": f.irpf_porcentaje or 0,
            "importe_irpf": float(f.importe_irpf or 0),
            "pendiente": float(f.total - f.pagado),
        } for f in res
    ]


@router.post("/proveedor")
def crear_factura_proveedor(
    p: FacturaProveedorCreate, db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
    empresa: Empresa = Depends(require_empresa),
):
    check_feature(user, "compras", db)
    check_feature(user, "facturacion", db)
    if not p.lineas:
        raise HTTPException(400, "Factura sin líneas")
    if not db.query(Tercero).filter(
        Tercero.id == p.proveedor_id, Tercero.empresa_id == empresa.id
    ).first():
        raise HTTPException(404, "Proveedor no existe")

    lineas_calc = []
    for ln in p.lineas:
        cant = ln.get("cantidad", 1)
        sub = calcular_linea(cant, ln["precio"], ln.get("descuento", 0))
        lineas_calc.append({"subtotal": sub, "iva": str(ln.get("iva", "21"))})
    totales = calcular_totales_documento(lineas_calc)

    # IRPF soportado en compras (profesionales)
    irpf_imp = round(float(totales["subtotal"]) * p.irpf_porcentaje / 100, 2)
    total = float(totales["subtotal"]) + float(totales["total_iva"]) - irpf_imp

    numero = p.numero or generar_numero(db, FacturaProveedor, serie=p.serie, empresa_id=empresa.id)

    fac = FacturaProveedor(
        empresa_id=empresa.id, numero=numero, serie=p.serie,
        proveedor_id=p.proveedor_id, fecha=p.fecha,
        fecha_vencimiento=p.fecha_vencimiento,
        numero_proveedor=p.numero_proveedor, estado="emitida",
        notas=p.notas, subtotal=totales["subtotal"],
        total_iva=totales["total_iva"], irpf_porcentaje=p.irpf_porcentaje,
        importe_irpf=irpf_imp, total=total, pagado=0,
    )
    db.add(fac); db.flush()

    for ln in p.lineas:
        cant = ln.get("cantidad", 1)
        sub = calcular_linea(cant, ln["precio"], ln.get("descuento", 0))
        db.add(FacturaProveedorLinea(
            empresa_id=empresa.id, factura_id=fac.id,
            producto_id=ln.get("producto_id"),
            descripcion=ln["descripcion"], cantidad=cant,
            precio=ln["precio"], descuento=ln.get("descuento", 0),
            iva=str(ln.get("iva", "21")), subtotal=sub,
        ))

    db.commit()
    audit(db, user, "crear", "factura_proveedor", fac.id, fac.numero, empresa_id=empresa.id)
    return {"ok": True, "id": fac.id, "numero": fac.numero,
            "subtotal": float(fac.subtotal), "total_iva": float(fac.total_iva),
            "irpf": irpf_imp, "total": float(fac.total)}


@router.post("/proveedor/{fac_id}/pagar")
def registrar_pago(
    fac_id: int, payload: dict, db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
    empresa: Empresa = Depends(require_empresa),
):
    fac = db.query(FacturaProveedor).filter(
        FacturaProveedor.id == fac_id, FacturaProveedor.empresa_id == empresa.id
    ).first()
    if not fac: raise HTTPException(404, "Factura no encontrada")
    pendiente = float(fac.total - fac.pagado)
    importe = float(payload.get("importe", 0))
    if importe <= 0 or importe > pendiente + 0.01:
        raise HTTPException(400, f"Importe debe estar entre 0 y {pendiente:.2f}")

    cuenta_id = payload.get("cuenta_id")
    cuenta = db.query(CuentaBancaria).filter(
        CuentaBancaria.id == cuenta_id, CuentaBancaria.empresa_id == empresa.id
    ).first()
    if not cuenta: raise HTTPException(400, "Cuenta bancaria inválida")

    db.add(MovimientoTesoreria(
        empresa_id=empresa.id,
        fecha=payload.get("fecha") or date.today(),
        tipo="pago", cuenta_id=cuenta_id,
        importe=-importe, concepto=payload.get("concepto", f"Pago {fac.numero}"),
        factura_proveedor_id=fac.id, tercero_id=fac.proveedor_id,
    ))
    fac.pagado = float(fac.pagado) + importe
    fac.estado = "pagada" if abs(fac.pagado - float(fac.total)) < 0.01 else "pagada_parcial"
    cuenta.saldo_actual = float(cuenta.saldo_actual) - importe

    db.commit()
    audit(db, user, "pagar", "factura_proveedor", fac.id,
          f"{importe:.2f}€ {cuenta.nombre}", empresa_id=empresa.id)
    return {"ok": True, "pagado": fac.pagado,
            "pendiente": float(fac.total - fac.pagado), "estado": fac.estado}