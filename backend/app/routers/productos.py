"""Endpoints de productos y familias (multi-tenant)."""
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from ..database import get_db
from ..models import Producto, Familia, Tercero
from ..schemas import (
    ProductoCreate, ProductoUpdate, ProductoOut,
    FamiliaBase, FamiliaOut,
)
from ..security import get_current_user, audit, check_feature
from ..models import Usuario
from ..tenancy import require_empresa, check_empresa_activa
from ..models import Empresa

router = APIRouter(prefix="/api/productos", tags=["productos"])


# ============ FAMILIAS ============
@router.get("/familias", response_model=List[FamiliaOut])
def listar_familias(
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
    empresa: Empresa = Depends(require_empresa),
):
    return (
        db.query(Familia)
        .filter(Familia.empresa_id == empresa.id)
        .order_by(Familia.codigo).all()
    )


@router.post("/familias", response_model=FamiliaOut)
def crear_familia(
    p: FamiliaBase, db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
    empresa: Empresa = Depends(require_empresa),
):
    check_empresa_activa(empresa, db)
    if db.query(Familia).filter(
        Familia.empresa_id == empresa.id, Familia.codigo == p.codigo
    ).first():
        raise HTTPException(400, f"Familia {p.codigo} ya existe")
    f = Familia(empresa_id=empresa.id, **p.model_dump())
    db.add(f); db.commit(); db.refresh(f)
    audit(db, user, "crear", "familia", f.id, p.codigo, empresa_id=empresa.id)
    return f


@router.delete("/familias/{fam_id}")
def borrar_familia(
    fam_id: int, db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
    empresa: Empresa = Depends(require_empresa),
):
    if user.rol not in ("admin", "jefe"):
        raise HTTPException(403, "Requiere rol jefe/admin")
    f = db.query(Familia).filter(
        Familia.id == fam_id, Familia.empresa_id == empresa.id
    ).first()
    if not f: raise HTTPException(404, "Familia no encontrada")
    if f.productos:
        raise HTTPException(400, f"Tiene {len(f.productos)} productos asignados")
    db.delete(f); db.commit()
    audit(db, user, "borrar", "familia", fam_id, None, empresa_id=empresa.id)
    return {"ok": True}


# ============ PRODUCTOS ============
@router.get("", response_model=List[ProductoOut])
def listar_productos(
    q: Optional[str] = Query(None),
    familia_id: Optional[int] = None,
    solo_activos: bool = True,
    bajo_minimo: bool = False,
    limit: int = Query(500, le=5000),
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
    empresa: Empresa = Depends(require_empresa),
):
    query = db.query(Producto).options(joinedload(Producto.familia)).filter(
        Producto.empresa_id == empresa.id
    )
    if solo_activos:
        query = query.filter(Producto.activo == True)
    if familia_id:
        query = query.filter(Producto.familia_id == familia_id)
    if q:
        like = f"%{q}%"
        query = query.filter(
            (Producto.sku.ilike(like)) |
            (Producto.nombre.ilike(like)) |
            (Producto.codigo_barras == q)
        )
    if bajo_minimo:
        query = query.filter(
            Producto.stock_minimo > 0,
            Producto.stock_actual <= Producto.stock_minimo
        )
    res = query.order_by(Producto.sku).limit(limit).all()
    out = []
    for p in res:
        o = ProductoOut.model_validate(p)
        o.familia_nombre = p.familia.nombre if p.familia else None
        out.append(o)
    return out


@router.post("", response_model=ProductoOut)
def crear_producto(
    p: ProductoCreate, db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
    empresa: Empresa = Depends(require_empresa),
):
    check_empresa_activa(empresa, db)
    check_feature(user, "inventario", db)
    if db.query(Producto).filter(
        Producto.empresa_id == empresa.id, Producto.sku == p.sku
    ).first():
        raise HTTPException(400, f"SKU {p.sku} ya existe")
    if p.proveedor_id and not db.query(Tercero).filter(
        Tercero.id == p.proveedor_id, Tercero.empresa_id == empresa.id
    ).first():
        raise HTTPException(400, "Proveedor no pertenece a tu empresa")
    prod = Producto(empresa_id=empresa.id, **p.model_dump())
    db.add(prod); db.commit(); db.refresh(prod)
    audit(db, user, "crear", "producto", prod.id, prod.sku, empresa_id=empresa.id)
    out = ProductoOut.model_validate(prod)
    out.familia_nombre = prod.familia.nombre if prod.familia else None
    return out


@router.get("/{prod_id}", response_model=ProductoOut)
def obtener_producto(
    prod_id: int, db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
    empresa: Empresa = Depends(require_empresa),
):
    p = db.query(Producto).options(joinedload(Producto.familia)).filter(
        Producto.id == prod_id, Producto.empresa_id == empresa.id
    ).first()
    if not p: raise HTTPException(404, "Producto no encontrado")
    out = ProductoOut.model_validate(p)
    out.familia_nombre = p.familia.nombre if p.familia else None
    return out


@router.patch("/{prod_id}", response_model=ProductoOut)
def actualizar_producto(
    prod_id: int, cambios: ProductoUpdate,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
    empresa: Empresa = Depends(require_empresa),
):
    p = db.query(Producto).filter(
        Producto.id == prod_id, Producto.empresa_id == empresa.id
    ).first()
    if not p: raise HTTPException(404, "Producto no encontrado")
    for k, v in cambios.model_dump(exclude_unset=True).items():
        setattr(p, k, v)
    db.commit(); db.refresh(p)
    audit(db, user, "actualizar", "producto", p.id, p.sku, empresa_id=empresa.id)
    out = ProductoOut.model_validate(p)
    out.familia_nombre = p.familia.nombre if p.familia else None
    return out


@router.delete("/{prod_id}")
def borrar_producto(
    prod_id: int, db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
    empresa: Empresa = Depends(require_empresa),
):
    if user.rol not in ("admin", "jefe"):
        raise HTTPException(403, "Requiere rol jefe/admin")
    p = db.query(Producto).filter(
        Producto.id == prod_id, Producto.empresa_id == empresa.id
    ).first()
    if not p: raise HTTPException(404, "Producto no encontrado")
    if p.stock_actual and p.stock_actual > 0:
        raise HTTPException(400, f"Tiene stock ({p.stock_actual}). Haz un ajuste primero.")
    p.activo = False
    db.commit()
    audit(db, user, "borrar", "producto", prod_id, p.sku, empresa_id=empresa.id)
    return {"ok": True}