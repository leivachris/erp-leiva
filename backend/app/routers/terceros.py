"""Endpoints de terceros y obras (multi-tenant)."""
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Tercero, Obra
from ..schemas import TerceroCreate, TerceroUpdate, TerceroOut, ObraCreate, ObraUpdate, ObraOut
from ..security import get_current_user, audit
from ..models import Usuario
from ..tenancy import require_empresa
from ..models import Empresa

router = APIRouter(prefix="/api/terceros", tags=["terceros"])


@router.get("", response_model=List[TerceroOut])
def listar_terceros(
    tipo: Optional[str] = Query(None),
    q: Optional[str] = None,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
    empresa: Empresa = Depends(require_empresa),
):
    qry = db.query(Tercero).filter(
        Tercero.empresa_id == empresa.id, Tercero.activo == True
    )
    if tipo:
        qry = qry.filter((Tercero.tipo == tipo) | (Tercero.tipo == "ambos"))
    if q:
        like = f"%{q}%"
        qry = qry.filter(
            (Tercero.codigo.ilike(like)) |
            (Tercero.nombre.ilike(like)) |
            (Tercero.cif_nif.ilike(like))
        )
    return qry.order_by(Tercero.codigo).limit(500).all()


@router.post("", response_model=TerceroOut)
def crear_tercero(
    t: TerceroCreate, db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
    empresa: Empresa = Depends(require_empresa),
):
    if db.query(Tercero).filter(
        Tercero.empresa_id == empresa.id, Tercero.codigo == t.codigo
    ).first():
        raise HTTPException(400, f"Código {t.codigo} ya existe")
    obj = Tercero(empresa_id=empresa.id, **t.model_dump())
    db.add(obj); db.commit(); db.refresh(obj)
    audit(db, user, "crear", "tercero", obj.id, obj.codigo, empresa_id=empresa.id)
    return obj


@router.get("/{tid}", response_model=TerceroOut)
def obtener_tercero(
    tid: int, db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
    empresa: Empresa = Depends(require_empresa),
):
    t = db.query(Tercero).filter(
        Tercero.id == tid, Tercero.empresa_id == empresa.id
    ).first()
    if not t: raise HTTPException(404, "Tercero no encontrado")
    return t


@router.patch("/{tid}", response_model=TerceroOut)
def actualizar_tercero(
    tid: int, cambios: TerceroUpdate,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
    empresa: Empresa = Depends(require_empresa),
):
    t = db.query(Tercero).filter(
        Tercero.id == tid, Tercero.empresa_id == empresa.id
    ).first()
    if not t: raise HTTPException(404, "Tercero no encontrado")
    for k, v in cambios.model_dump(exclude_unset=True).items():
        setattr(t, k, v)
    db.commit(); db.refresh(t)
    audit(db, user, "actualizar", "tercero", tid, t.codigo, empresa_id=empresa.id)
    return t


@router.delete("/{tid}")
def borrar_tercero(
    tid: int, db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
    empresa: Empresa = Depends(require_empresa),
):
    if user.rol not in ("admin", "jefe"):
        raise HTTPException(403, "Requiere rol jefe/admin")
    t = db.query(Tercero).filter(
        Tercero.id == tid, Tercero.empresa_id == empresa.id
    ).first()
    if not t: raise HTTPException(404, "Tercero no encontrado")
    if t.obras:
        raise HTTPException(400, f"Tiene {len(t.obras)} obras asociadas")
    t.activo = False
    db.commit()
    audit(db, user, "borrar", "tercero", tid, t.codigo, empresa_id=empresa.id)
    return {"ok": True}


# ============== OBRAS ==============
@router.get("/obras/all", response_model=List[ObraOut])
def listar_obras(
    estado: Optional[str] = None,
    cliente_id: Optional[int] = None,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
    empresa: Empresa = Depends(require_empresa),
):
    qry = db.query(Obra).filter(Obra.empresa_id == empresa.id)
    if estado: qry = qry.filter(Obra.estado == estado)
    if cliente_id: qry = qry.filter(Obra.cliente_id == cliente_id)
    res = qry.order_by(Obra.codigo).all()
    out = []
    for o in res:
        x = ObraOut.model_validate(o)
        x.cliente_nombre = o.cliente.nombre if o.cliente else None
        out.append(x)
    return out


@router.post("/obras/all", response_model=ObraOut)
def crear_obra(
    o: ObraCreate, db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
    empresa: Empresa = Depends(require_empresa),
):
    if db.query(Obra).filter(
        Obra.empresa_id == empresa.id, Obra.codigo == o.codigo
    ).first():
        raise HTTPException(400, f"Obra {o.codigo} ya existe")
    obj = Obra(empresa_id=empresa.id, **o.model_dump())
    db.add(obj); db.commit(); db.refresh(obj)
    audit(db, user, "crear", "obra", obj.id, obj.codigo, empresa_id=empresa.id)
    x = ObraOut.model_validate(obj)
    x.cliente_nombre = obj.cliente.nombre if obj.cliente else None
    return x


@router.patch("/obras/{oid}", response_model=ObraOut)
def actualizar_obra(
    oid: int, cambios: ObraUpdate,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
    empresa: Empresa = Depends(require_empresa),
):
    o = db.query(Obra).filter(
        Obra.id == oid, Obra.empresa_id == empresa.id
    ).first()
    if not o: raise HTTPException(404, "Obra no encontrada")
    for k, v in cambios.model_dump(exclude_unset=True).items():
        setattr(o, k, v)
    db.commit(); db.refresh(o)
    audit(db, user, "actualizar", "obra", oid, o.codigo, empresa_id=empresa.id)
    x = ObraOut.model_validate(o)
    x.cliente_nombre = o.cliente.nombre if o.cliente else None
    return x


@router.delete("/obras/{oid}")
def borrar_obra(
    oid: int, db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
    empresa: Empresa = Depends(require_empresa),
):
    if user.rol not in ("admin", "jefe"):
        raise HTTPException(403, "Requiere rol jefe/admin")
    o = db.query(Obra).filter(
        Obra.id == oid, Obra.empresa_id == empresa.id
    ).first()
    if not o: raise HTTPException(404, "Obra no encontrada")
    if o.albaranes:
        raise HTTPException(400, f"Tiene {len(o.albaranes)} albaranes; anúlalos primero")
    db.delete(o); db.commit()
    audit(db, user, "borrar", "obra", oid, o.codigo, empresa_id=empresa.id)
    return {"ok": True}