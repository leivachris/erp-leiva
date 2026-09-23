"""Endpoints para gestionar la propia empresa (config, branding)."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Empresa, Usuario, Plan, Suscripcion
from ..schemas import EmpresaOut, EmpresaUpdate, UsuarioCreate, UsuarioUpdate, UsuarioOut
from ..security import get_current_user, audit, hash_password
from ..tenancy import require_empresa

router = APIRouter(prefix="/api/empresa", tags=["empresa"])


@router.get("", response_model=EmpresaOut)
def obtener_empresa(
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
    empresa=Depends(require_empresa),
):
    return empresa


@router.patch("", response_model=EmpresaOut)
def actualizar_empresa(
    cambios: EmpresaUpdate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
    empresa=Depends(require_empresa),
):
    if user.rol not in ("admin",):
        raise HTTPException(403, "Solo el admin puede modificar la empresa")
    for k, v in cambios.model_dump(exclude_unset=True).items():
        if v is not None:
            setattr(empresa, k, v)
    db.commit(); db.refresh(empresa)
    audit(db, user, "actualizar", "empresa", empresa.id, empresa.slug)
    return empresa


# ====== USUARIOS DE LA EMPRESA ======
@router.get("/usuarios", response_model=list[UsuarioOut])
def listar_usuarios(
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
    empresa=Depends(require_empresa),
):
    return db.query(Usuario).filter(
        Usuario.empresa_id == empresa.id, Usuario.activo == True
    ).order_by(Usuario.username).all()


@router.post("/usuarios", response_model=UsuarioOut)
def crear_usuario(
    p: UsuarioCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
    empresa=Depends(require_empresa),
):
    if user.rol not in ("admin", "jefe"):
        raise HTTPException(403, "Requiere rol admin/jefe")
    if db.query(Usuario).filter(
        Usuario.empresa_id == empresa.id, Usuario.username == p.username
    ).first():
        raise HTTPException(400, "Username ya existe en esta empresa")
    u = Usuario(
        empresa_id=empresa.id, username=p.username, nombre=p.nombre,
        email=p.email, rol=p.rol,
        password_hash=hash_password(p.password), activo=True,
    )
    db.add(u); db.commit(); db.refresh(u)
    audit(db, user, "crear", "usuario", u.id, u.username)
    return u


@router.patch("/usuarios/{uid}", response_model=UsuarioOut)
def actualizar_usuario(
    uid: int, cambios: UsuarioUpdate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
    empresa=Depends(require_empresa),
):
    if user.rol not in ("admin", "jefe"):
        raise HTTPException(403, "Requiere rol admin/jefe")
    u = db.query(Usuario).filter(
        Usuario.id == uid, Usuario.empresa_id == empresa.id
    ).first()
    if not u: raise HTTPException(404, "Usuario no encontrado")
    if cambios.password:
        u.password_hash = hash_password(cambios.password)
    for k, v in cambios.model_dump(exclude_unset=True).items():
        if k == "password": continue
        setattr(u, k, v)
    db.commit(); db.refresh(u)
    audit(db, user, "actualizar", "usuario", u.id, u.username)
    return u


# ====== SUSCRIPCION ACTUAL ======
@router.get("/suscripcion")
def mi_suscripcion(
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
    empresa=Depends(require_empresa),
):
    s = db.query(Suscripcion).filter(Suscripcion.empresa_id == empresa.id).first()
    if not s:
        return {"ok": False, "mensaje": "Sin suscripción"}
    plan = db.query(Plan).get(s.plan_id)
    return {
        "plan_codigo": plan.codigo if plan else None,
        "plan_nombre": plan.nombre if plan else None,
        "estado": s.estado,
        "periodicidad": s.periodicidad,
        "fecha_inicio": s.fecha_inicio.isoformat() if s.fecha_inicio else None,
        "fecha_fin": s.fecha_fin.isoformat() if s.fecha_fin else None,
        "fecha_proxima_renovacion": s.fecha_proxima_renovacion.isoformat() if s.fecha_proxima_renovacion else None,
    }