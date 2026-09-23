"""Endpoints de hojas de carga y expediciones."""
from datetime import datetime, date
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import (
    HojaCarga, Expedicion, AlbaranSalida, Tercero, Obra, Empresa,
)
from ..security import get_current_user, audit, check_feature
from ..models import Usuario
from ..tenancy import require_empresa
from ..services.numeracion import generar_numero

router = APIRouter(prefix="/api/expediciones", tags=["expediciones"])


# ============ HOJAS DE CARGA ============
@router.get("/hojas")
def listar_hojas(
    estado: str = None, db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
    empresa: Empresa = Depends(require_empresa),
):
    q = db.query(HojaCarga).filter(HojaCarga.empresa_id == empresa.id)
    if estado: q = q.filter(HojaCarga.estado == estado)
    res = q.order_by(HojaCarga.fecha.desc(), HojaCarga.id.desc()).limit(100).all()
    return [
        {
            "id": h.id, "numero": h.numero, "fecha": h.fecha.isoformat(),
            "transportista": h.transportista, "matricula": h.matricula,
            "conductor": h.conductor, "ruta": h.ruta,
            "almacen_nombre": h.almacen.nombre if h.almacen else "",
            "bultos_total": h.bultos_total, "peso_kg_total": h.peso_kg_total,
            "estado": h.estado,
            "expediciones_count": len(h.expediciones),
        } for h in res
    ]


@router.post("/hojas")
def crear_hoja(
    p: dict, db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
    empresa: Empresa = Depends(require_empresa),
):
    check_feature(user, "ventas", db)
    numero = generar_numero(db, HojaCarga, serie="HC", empresa_id=empresa.id)
    h = HojaCarga(
        empresa_id=empresa.id, numero=numero,
        fecha=p.get("fecha", date.today()),
        transportista=p.get("transportista"),
        matricula=p.get("matricula"),
        conductor=p.get("conductor"),
        ruta=p.get("ruta"),
        almacen_origen_id=p.get("almacen_origen_id"),
        estado="planificada",
        notas=p.get("notas"),
        usuario_id=user.id,
    )
    db.add(h); db.flush()

    # expediciones (lineas)
    for i, ex in enumerate(p.get("expediciones", [])):
        e = Expedicion(
            empresa_id=empresa.id, hoja_id=h.id,
            albaran_salida_id=ex.get("albaran_salida_id"),
            orden=ex.get("orden", i),
            cliente_id=ex.get("cliente_id"),
            obra_id=ex.get("obra_id"),
            direccion_entrega=ex.get("direccion_entrega"),
            poblacion_entrega=ex.get("poblacion_entrega"),
            cp_entrega=ex.get("cp_entrega"),
            ventana_horaria=ex.get("ventana_horaria"),
            bultos=ex.get("bultos", 0),
            peso_kg=ex.get("peso_kg", 0),
            estado="pendiente",
            notas=ex.get("notas"),
        )
        db.add(e)
        # acumular totales
        h.bultos_total += e.bultos
        h.peso_kg_total += e.peso_kg

    db.commit()
    audit(db, user, "crear", "hoja_carga", h.id, h.numero, empresa_id=empresa.id)
    return {"ok": True, "id": h.id, "numero": h.numero}


@router.get("/hojas/{hid}")
def obtener_hoja(
    hid: int, db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
    empresa: Empresa = Depends(require_empresa),
):
    h = db.query(HojaCarga).filter(
        HojaCarga.id == hid, HojaCarga.empresa_id == empresa.id
    ).first()
    if not h: raise HTTPException(404, "Hoja no encontrada")
    return {
        "id": h.id, "numero": h.numero, "fecha": h.fecha.isoformat(),
        "transportista": h.transportista, "matricula": h.matricula,
        "conductor": h.conductor, "ruta": h.ruta,
        "almacen_origen_id": h.almacen_origen_id,
        "almacen_nombre": h.almacen.nombre if h.almacen else "",
        "bultos_total": h.bultos_total, "peso_kg_total": h.peso_kg_total,
        "estado": h.estado, "notas": h.notas,
        "expediciones": [
            {
                "id": e.id, "orden": e.orden,
                "albaran_salida_id": e.albaran_salida_id,
                "albaran_numero": e.albaran.numero if e.albaran else None,
                "cliente_id": e.cliente_id,
                "cliente_nombre": e.cliente.nombre if e.cliente else "",
                "obra_id": e.obra_id,
                "obra_nombre": e.obra.nombre if e.obra else "",
                "direccion_entrega": e.direccion_entrega,
                "poblacion_entrega": e.poblacion_entrega,
                "cp_entrega": e.cp_entrega,
                "ventana_horaria": e.ventana_horaria,
                "bultos": e.bultos, "peso_kg": e.peso_kg,
                "estado": e.estado,
                "fecha_entrega": e.fecha_entrega.isoformat() if e.fecha_entrega else None,
                "incidencia": e.incidencia,
                "notas": e.notas,
            } for e in sorted(h.expediciones, key=lambda x: x.orden)
        ]
    }


@router.post("/hojas/{hid}/completar")
def completar_hoja(
    hid: int, db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
    empresa: Empresa = Depends(require_empresa),
):
    h = db.query(HojaCarga).filter(
        HojaCarga.id == hid, HojaCarga.empresa_id == empresa.id
    ).first()
    if not h: raise HTTPException(404, "Hoja no encontrada")
    h.estado = "completada"
    h.fecha_completada = datetime.utcnow()
    db.commit()
    audit(db, user, "completar", "hoja_carga", hid, h.numero, empresa_id=empresa.id)
    return {"ok": True}


@router.post("/hojas/{hid}/expediciones/{eid}/estado")
def actualizar_estado_expedicion(
    hid: int, eid: int, payload: dict,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
    empresa: Empresa = Depends(require_empresa),
):
    e = db.query(Expedicion).filter(
        Expedicion.id == eid, Expedicion.hoja_id == hid,
        Expedicion.empresa_id == empresa.id
    ).first()
    if not e: raise HTTPException(404, "Expedicion no encontrada")
    estado = payload.get("estado")
    if estado not in ("pendiente", "entregado", "parcial", "incidencia", "devuelto"):
        raise HTTPException(400, "Estado invalido")
    e.estado = estado
    if estado == "entregado":
        e.fecha_entrega = datetime.utcnow()
    if "incidencia" in payload:
        e.incidencia = payload["incidencia"]
    db.commit()
    audit(db, user, "actualizar_estado", "expedicion", eid, estado, empresa_id=empresa.id)
    return {"ok": True, "estado": e.estado}


# ============ ALBARANES PENDIENTES DE EXPEDIR ============
@router.get("/pendientes")
def albaranes_pendientes_expedir(
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
    empresa: Empresa = Depends(require_empresa),
):
    """Albaranes de salida en estado confirmado que aun no estan en ninguna hoja."""
    from sqlalchemy import not_
    sub = db.query(Expedicion.albaran_salida_id).filter(
        Expedicion.empresa_id == empresa.id,
        Expedicion.albaran_salida_id != None
    )
    res = db.query(AlbaranSalida).filter(
        AlbaranSalida.empresa_id == empresa.id,
        AlbaranSalida.estado == "confirmado",
        AlbaranSalida.id.notin_(sub),
    ).order_by(AlbaranSalida.fecha.desc()).limit(100).all()
    return [
        {
            "id": a.id, "numero": a.numero, "fecha": a.fecha.isoformat(),
            "cliente_nombre": a.cliente.nombre if a.cliente else "",
            "obra_nombre": a.obra.nombre if a.obra else "",
            "direccion": a.obra.direccion if a.obra and a.obra.direccion else
                         (a.cliente.direccion if a.cliente else ""),
            "poblacion": a.obra.poblacion if a.obra and a.obra.poblacion else
                         (a.cliente.poblacion if a.cliente else ""),
            "cp": a.obra.cp if a.obra and a.obra.cp else
                  (a.cliente.cp if a.cliente else ""),
            "total": float(a.total),
        } for a in res
    ]