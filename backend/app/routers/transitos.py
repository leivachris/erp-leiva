"""Endpoints de transitos entre almacenes.

Estados:
  - en_transito: creado, stock descontado del almacen origen
  - recibido: recepcion completa, stock anadido al almacen destino
  - parcial: recepcion incompleta (faltan productos)
  - cancelado: anulado antes de enviar

Flujo:
  1. Crear transito -> decrementa stock origen (por ubicacion FIFO)
  2. Recibir transito -> incrementa stock destino (a la ubicacion indicada)
"""
from datetime import datetime, date
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func

from ..database import get_db
from ..models import (
    Transito, TransitoLinea, Almacen, Producto, Stock,
    MovimientoStock, Empresa, Ubicacion,
)
from ..security import get_current_user, audit, check_feature
from ..models import Usuario
from ..tenancy import require_empresa
from ..services.numeracion import generar_numero

router = APIRouter(prefix="/api/transitos", tags=["transitos"])


@router.get("")
def listar_transitos(
    estado: str = None,
    almacen_id: int = None,
    limit: int = 50,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
    empresa: Empresa = Depends(require_empresa),
):
    q = db.query(Transito).filter(Transito.empresa_id == empresa.id)
    if estado: q = q.filter(Transito.estado == estado)
    if almacen_id:
        q = q.filter(
            (Transito.almacen_origen_id == almacen_id) |
            (Transito.almacen_destino_id == almacen_id)
        )
    res = q.order_by(Transito.fecha_envio.desc()).limit(limit).all()
    return [
        {
            "id": t.id, "numero": t.numero,
            "fecha_envio": t.fecha_envio.isoformat() if t.fecha_envio else None,
            "fecha_recepcion_prevista": t.fecha_recepcion_prevista.isoformat() if t.fecha_recepcion_prevista else None,
            "fecha_recepcion_real": t.fecha_recepcion_real.isoformat() if t.fecha_recepcion_real else None,
            "almacen_origen_id": t.almacen_origen_id,
            "almacen_origen": t.almacen_origen.nombre if t.almacen_origen else "",
            "almacen_destino_id": t.almacen_destino_id,
            "almacen_destino": t.almacen_destino.nombre if t.almacen_destino else "",
            "transportista": t.transportista, "matricula": t.matricula,
            "bultos": t.bultos, "peso_kg": t.peso_kg,
            "estado": t.estado,
            "lineas_count": len(t.lineas),
        } for t in res
    ]


@router.post("")
def crear_transito(
    p: dict, db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
    empresa: Empresa = Depends(require_empresa),
):
    check_feature(user, "inventario", db)
    lineas = p.get("lineas", [])
    if not lineas:
        raise HTTPException(400, "Sin lineas")
    origen = db.query(Almacen).filter(
        Almacen.id == p["almacen_origen_id"], Almacen.empresa_id == empresa.id
    ).first()
    destino = db.query(Almacen).filter(
        Almacen.id == p["almacen_destino_id"], Almacen.empresa_id == empresa.id
    ).first()
    if not origen or not destino:
        raise HTTPException(404, "Almacen origen/destino no existe")
    if origen.id == destino.id:
        raise HTTPException(400, "Origen y destino no pueden ser iguales")

    numero = generar_numero(db, Transito, serie="T", empresa_id=empresa.id)
    transito = Transito(
        empresa_id=empresa.id, numero=numero,
        fecha_envio=datetime.utcnow(),
        fecha_recepcion_prevista=p.get("fecha_recepcion_prevista"),
        almacen_origen_id=origen.id, almacen_destino_id=destino.id,
        transportista=p.get("transportista"),
        matricula=p.get("matricula"),
        bultos=p.get("bultos", 0), peso_kg=p.get("peso_kg", 0),
        estado="en_transito",
        motivo=p.get("motivo"), notas=p.get("notas"),
        usuario_id=user.id,
    )
    db.add(transito); db.flush()

    for ln in lineas:
        pid = ln["producto_id"]
        cant = float(ln["cantidad"])
        prod = db.query(Producto).filter(
            Producto.id == pid, Producto.empresa_id == empresa.id
        ).first()
        if not prod: raise HTTPException(404, f"Producto {pid} no existe")
        # descontar stock del almacen origen (FIFO por ubicacion)
        restante = cant
        for stock in (
            db.query(Stock).join(Ubicacion, Ubicacion.id == Stock.ubicacion_id)
            .filter(
                Stock.empresa_id == empresa.id,
                Ubicacion.almacen_id == origen.id,
                Stock.producto_id == pid,
                Stock.cantidad > 0,
            ).order_by(Stock.cantidad.desc()).all()
        ):
            if restante <= 0: break
            tomado = min(stock.cantidad, restante)
            stock.cantidad -= tomado
            restante -= tomado

        if restante > 0.001:
            db.rollback()
            raise HTTPException(400, f"Stock insuficiente en origen para {prod.sku}: faltan {restante}")

        # descontar stock_actual del producto (es global)
        prod.stock_actual = (prod.stock_actual or 0) - cant

        db.add(TransitoLinea(
            empresa_id=empresa.id, transito_id=transito.id,
            producto_id=pid, cantidad_enviada=cant, cantidad_recibida=0,
        ))
        db.add(MovimientoStock(
            empresa_id=empresa.id, tipo="traspaso",
            producto_id=pid, cantidad=-cant,
            notas=f"Transito {numero} envio desde {origen.nombre}",
            usuario_id=user.id,
        ))

    db.commit()
    audit(db, user, "crear", "transito", transito.id, numero, empresa_id=empresa.id)
    return {"ok": True, "id": transito.id, "numero": numero}


@router.post("/{tid}/recibir")
def recibir_transito(
    tid: int, payload: dict,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
    empresa: Empresa = Depends(require_empresa),
):
    """Recibe un transito. Payload: {lineas: [{producto_id, cantidad_recibida, ubicacion_destino_id}]}
    Si no se envian lineas, se recibe todo completo en la primera ubicacion del almacen destino.
    """
    t = db.query(Transito).filter(
        Transito.id == tid, Transito.empresa_id == empresa.id
    ).first()
    if not t: raise HTTPException(404, "Transito no existe")
    if t.estado not in ("en_transito", "parcial"):
        raise HTTPException(400, f"Transito en estado {t.estado}")

    lineas_input = payload.get("lineas", [])
    if not lineas_input:
        # recepcion completa automatica
        lineas_input = [
            {"producto_id": ln.producto_id, "cantidad_recibida": ln.cantidad_enviada}
            for ln in t.lineas
        ]

    recibido_total = 0
    for inp in lineas_input:
        pid = inp["producto_id"]
        cant_rec = float(inp.get("cantidad_recibida", 0))
        if cant_rec <= 0: continue

        ln = db.query(TransitoLinea).filter(
            TransitoLinea.transito_id == t.id, TransitoLinea.producto_id == pid
        ).first()
        if not ln: continue
        pendiente = ln.cantidad_enviada - ln.cantidad_recibida
        cant_rec = min(cant_rec, pendiente)
        ln.cantidad_recibida += cant_rec

        # anadir stock al almacen destino
        prod = db.query(Producto).get(pid)
        ub_id = inp.get("ubicacion_destino_id")
        if not ub_id:
            # primera ubicacion del almacen destino
            ub = db.query(Ubicacion).filter(
                Ubicacion.almacen_id == t.almacen_destino_id,
                Ubicacion.activo == True,
            ).first()
            ub_id = ub.id if ub else None

        if ub_id:
            stock = db.query(Stock).filter_by(
                empresa_id=empresa.id, producto_id=pid, ubicacion_id=ub_id
            ).first()
            if not stock:
                stock = Stock(
                    empresa_id=empresa.id,
                    producto_id=pid, ubicacion_id=ub_id, cantidad=0
                )
                db.add(stock)
            stock.cantidad += cant_rec

        prod.stock_actual = (prod.stock_actual or 0) + cant_rec

        db.add(MovimientoStock(
            empresa_id=empresa.id, tipo="traspaso",
            producto_id=pid, cantidad=cant_rec,
            notas=f"Transito {t.numero} recepcion en {t.almacen_destino.nombre}",
            usuario_id=user.id,
        ))
        recibido_total += cant_rec

    # actualizar estado del transito
    todas_recibidas = all(
        ln.cantidad_recibida >= ln.cantidad_enviada - 0.001 for ln in t.lineas
    )
    alguna_recibida = any(ln.cantidad_recibida > 0 for ln in t.lineas)

    if todas_recibidas:
        t.estado = "recibido"
        t.fecha_recepcion_real = datetime.utcnow()
    elif alguna_recibida:
        t.estado = "parcial"
    db.commit()
    audit(db, user, "recibir", "transito", tid, t.numero, empresa_id=empresa.id)
    return {"ok": True, "estado": t.estado, "recibido_total": recibido_total}


@router.post("/{tid}/cancelar")
def cancelar_transito(
    tid: int, db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
    empresa: Empresa = Depends(require_empresa),
):
    t = db.query(Transito).filter(
        Transito.id == tid, Transito.empresa_id == empresa.id
    ).first()
    if not t: raise HTTPException(404, "Transito no existe")
    if t.estado == "recibido":
        raise HTTPException(400, "Ya fue recibido, no se puede cancelar")
    if t.estado == "cancelado":
        raise HTTPException(400, "Ya estaba cancelado")

    # devolver stock al origen
    for ln in t.lineas:
        pendiente = ln.cantidad_enviada - ln.cantidad_recibida
        if pendiente <= 0: continue
        prod = db.query(Producto).get(ln.producto_id)
        # anadir a primera ubicacion del origen
        ub = db.query(Ubicacion).filter(
            Ubicacion.almacen_id == t.almacen_origen_id, Ubicacion.activo == True
        ).first()
        if ub:
            stock = db.query(Stock).filter_by(
                empresa_id=empresa.id,
                producto_id=ln.producto_id, ubicacion_id=ub.id
            ).first()
            if not stock:
                stock = Stock(
                    empresa_id=empresa.id,
                    producto_id=ln.producto_id, ubicacion_id=ub.id, cantidad=0
                )
                db.add(stock)
            stock.cantidad += pendiente
        if prod:
            prod.stock_actual = (prod.stock_actual or 0) + pendiente
        db.add(MovimientoStock(
            empresa_id=empresa.id, tipo="traspaso",
            producto_id=ln.producto_id, cantidad=pendiente,
            notas=f"Cancelacion transito {t.numero}",
            usuario_id=user.id,
        ))
    t.estado = "cancelado"
    db.commit()
    audit(db, user, "cancelar", "transito", tid, t.numero, empresa_id=empresa.id)
    return {"ok": True, "estado": t.estado}