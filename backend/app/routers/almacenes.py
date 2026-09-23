"""Endpoints de almacenes: CRUD + traspasos entre almacenes."""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func

from ..database import get_db
from ..models import (
    Almacen, Ubicacion, Stock, Producto, Tercero, MovimientoStock, Empresa,
)
from ..schemas import UbicacionBase, UbicacionOut
from ..security import get_current_user, audit
from ..models import Usuario
from ..tenancy import require_empresa

router = APIRouter(prefix="/api/almacenes", tags=["almacenes"])


@router.get("")
def listar_almacenes(
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
    empresa: Empresa = Depends(require_empresa),
):
    rows = db.query(Almacen).filter(
        Almacen.empresa_id == empresa.id, Almacen.activo == True
    ).order_by(Almacen.codigo).all()
    out = []
    for a in rows:
        n_ubicaciones = db.query(func.count(Ubicacion.id)).filter(
            Ubicacion.almacen_id == a.id, Ubicacion.activo == True
        ).scalar() or 0
        # stock total: suma de stocks en ubicaciones de este almacen
        stock_valor = db.query(
            func.coalesce(func.sum(Stock.cantidad * Producto.precio_compra), 0)
        ).join(Ubicacion, Ubicacion.id == Stock.ubicacion_id).join(
            Producto, Producto.id == Stock.producto_id
        ).filter(
            Stock.empresa_id == empresa.id,
            Ubicacion.almacen_id == a.id,
        ).scalar() or 0
        out.append({
            "id": a.id, "codigo": a.codigo, "nombre": a.nombre,
            "direccion": a.direccion, "poblacion": a.poblacion,
            "telefono": a.telefono, "contacto": a.contacto,
            "es_principal": a.es_principal,
            "ubicaciones_count": n_ubicaciones,
            "stock_valor": float(stock_valor),
        })
    return out


@router.post("")
def crear_almacen(
    payload: dict, db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
    empresa: Empresa = Depends(require_empresa),
):
    if not payload.get("codigo") or not payload.get("nombre"):
        raise HTTPException(400, "Faltan codigo o nombre")
    if db.query(Almacen).filter(
        Almacen.empresa_id == empresa.id, Almacen.codigo == payload["codigo"]
    ).first():
        raise HTTPException(400, f"Ya existe almacen con codigo {payload['codigo']}")

    a = Almacen(
        empresa_id=empresa.id,
        codigo=payload["codigo"],
        nombre=payload["nombre"],
        direccion=payload.get("direccion"),
        cp=payload.get("cp"),
        poblacion=payload.get("poblacion"),
        provincia=payload.get("provincia"),
        telefono=payload.get("telefono"),
        email=payload.get("email"),
        contacto=payload.get("contacto"),
        es_principal=payload.get("es_principal", False),
        notas=payload.get("notas"),
        activo=True,
    )
    db.add(a); db.commit(); db.refresh(a)
    audit(db, user, "crear", "almacen", a.id, a.codigo, empresa_id=empresa.id)
    return {"id": a.id, "codigo": a.codigo, "nombre": a.nombre}


@router.patch("/{aid}")
def actualizar_almacen(
    aid: int, cambios: dict,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
    empresa: Empresa = Depends(require_empresa),
):
    a = db.query(Almacen).filter(
        Almacen.id == aid, Almacen.empresa_id == empresa.id
    ).first()
    if not a: raise HTTPException(404, "Almacen no encontrado")
    for k, v in cambios.items():
        if k in ("nombre", "direccion", "cp", "poblacion", "provincia",
                 "telefono", "email", "contacto", "es_principal", "activo", "notas"):
            setattr(a, k, v)
    db.commit(); db.refresh(a)
    audit(db, user, "actualizar", "almacen", aid, a.codigo, empresa_id=empresa.id)
    return {"id": a.id, "codigo": a.codigo, "nombre": a.nombre}


@router.delete("/{aid}")
def borrar_almacen(
    aid: int, db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
    empresa: Empresa = Depends(require_empresa),
):
    a = db.query(Almacen).filter(
        Almacen.id == aid, Almacen.empresa_id == empresa.id
    ).first()
    if not a: raise HTTPException(404, "Almacen no encontrado")
    # comprobar que no tenga stock
    stock_count = db.query(func.count(Stock.id)).join(
        Ubicacion, Ubicacion.id == Stock.ubicacion_id
    ).filter(
        Stock.empresa_id == empresa.id,
        Ubicacion.almacen_id == aid,
        Stock.cantidad > 0
    ).scalar() or 0
    if stock_count > 0:
        raise HTTPException(400, f"Tiene {stock_count} ubicaciones con stock. Traslada primero")
    a.activo = False
    db.commit()
    audit(db, user, "borrar", "almacen", aid, a.codigo, empresa_id=empresa.id)
    return {"ok": True}


# ============ UBICACIONES DE UN ALMACEN ============
@router.get("/{aid}/ubicaciones")
def ubicaciones_de_almacen(
    aid: int, db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
    empresa: Empresa = Depends(require_empresa),
):
    rows = db.query(Ubicacion).filter(
        Ubicacion.empresa_id == empresa.id,
        Ubicacion.almacen_id == aid,
        Ubicacion.activo == True,
    ).order_by(Ubicacion.codigo).all()
    out = []
    for u in rows:
        cant = db.query(func.coalesce(func.sum(Stock.cantidad), 0)).filter(
            Stock.empresa_id == empresa.id, Stock.ubicacion_id == u.id
        ).scalar() or 0
        out.append({
            "id": u.id, "codigo": u.codigo,
            "pasillo": u.pasillo, "estanteria": u.estanteria, "hueco": u.hueco,
            "nivel": u.nivel, "capacidad_kg": u.capacidad_kg, "capacidad_m3": u.capacidad_m3,
            "stock_total": float(cant),
        })
    return out


@router.post("/{aid}/ubicaciones")
def crear_ubicacion_en_almacen(
    aid: int, u: UbicacionBase,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
    empresa: Empresa = Depends(require_empresa),
):
    almacen = db.query(Almacen).filter(
        Almacen.id == aid, Almacen.empresa_id == empresa.id
    ).first()
    if not almacen: raise HTTPException(404, "Almacen no existe")
    if db.query(Ubicacion).filter(
        Ubicacion.empresa_id == empresa.id, Ubicacion.codigo == u.codigo
    ).first():
        raise HTTPException(400, f"Ya existe ubicacion {u.codigo}")
    ub = Ubicacion(empresa_id=empresa.id, almacen_id=aid, **u.model_dump())
    db.add(ub); db.commit(); db.refresh(ub)
    audit(db, user, "crear", "ubicacion", ub.id, ub.codigo, empresa_id=empresa.id)
    return {"id": ub.id, "codigo": ub.codigo}