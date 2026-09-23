"""Endpoints de instalacion inicial y gestion de planes.

Una sola vez al instalar el ERP:
  1. POST /api/instalacion/setup  -> crea empresa + plan + admin + suscripcion prueba
  2. POST /api/instalacion/activar -> activa una licencia (modo instalable)

Tambien:
  - GET /api/instalacion/estado -> sabe si ya esta instalado
  - GET /api/planes -> lista planes disponibles
"""
import secrets
import string
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db, SessionLocal
from ..models import (
    Empresa, Plan, Suscripcion, Licencia, Usuario,
)
from ..schemas import SetupIn, SetupOut, PlanOut
from ..security import hash_password, audit
from ..plans import planes_default

router = APIRouter(tags=["instalacion"])


@router.get("/instalacion/estado")
def estado_instalacion(db: Session = Depends(get_db)):
    """Dice si la instalacion ya esta configurada."""
    hay_empresa = db.query(Empresa).count() > 0
    return {
        "instalado": hay_empresa,
        "mensaje": "Instalado" if hay_empresa else "Pendiente de configuración inicial",
    }


@router.post("/instalacion/setup", response_model=SetupOut)
def setup(payload: SetupIn, db: Session = Depends(get_db)):
    """Crea la primera empresa + admin + suscripcion de prueba.

    Solo funciona si NO hay empresas creadas aun.
    """
    if db.query(Empresa).count() > 0:
        raise HTTPException(400, "La instalación ya está configurada")

    # 1. Crear/asegurar planes predefinidos
    planes = {}
    for p in planes_default():
        plan = db.query(Plan).filter(Plan.codigo == p["codigo"]).first()
        if not plan:
            plan = Plan(**p)
            db.add(plan); db.flush()
        planes[p["codigo"]] = plan

    # 2. Plan elegido
    plan_elegido = planes.get(payload.plan_codigo, planes["basico"])

    # 3. Empresa
    empresa_data = payload.empresa
    slug = empresa_data.get("slug") or _slugify(empresa_data["nombre"])
    if db.query(Empresa).filter(Empresa.slug == slug).first():
        raise HTTPException(400, f"Slug '{slug}' ya existe. Elige otro.")
    empresa = Empresa(
        slug=slug,
        nombre=empresa_data.get("nombre", "Mi Empresa"),
        nombre_comercial=empresa_data.get("nombre_comercial"),
        cif=empresa_data.get("cif"),
        direccion=empresa_data.get("direccion"),
        cp=empresa_data.get("cp"),
        poblacion=empresa_data.get("poblacion"),
        provincia=empresa_data.get("provincia"),
        telefono=empresa_data.get("telefono"),
        email=empresa_data.get("email"),
        web=empresa_data.get("web"),
        plan_id=plan_elegido.id,
        modo="instalable",
        activa=True,
        color_primario="#2563eb",
    )
    db.add(empresa); db.flush()

    # 4. Suscripcion (30 dias de prueba)
    susc = Suscripcion(
        empresa_id=empresa.id, plan_id=plan_elegido.id,
        estado="prueba", periodicidad="mensual",
        fecha_inicio=datetime.utcnow(),
        fecha_fin=datetime.utcnow() + timedelta(days=30),
    )
    db.add(susc); db.flush()

    # 5. Licencia (modo instalable)
    if payload.licencia:
        lic = Licencia(
            empresa_id=empresa.id, clave=payload.licencia,
            max_instalaciones=1, fecha_emision=datetime.utcnow(),
            fecha_expiracion=datetime.utcnow() + timedelta(days=365),
            activa=True,
        )
        db.add(lic)

    # 6. Usuario admin
    admin_data = payload.admin
    if not admin_data.get("username") or not admin_data.get("password"):
        raise HTTPException(400, "Faltan username o password del admin")
    if db.query(Usuario).filter(
        Usuario.empresa_id == empresa.id, Usuario.username == admin_data["username"]
    ).first():
        raise HTTPException(400, f"Usuario '{admin_data['username']}' ya existe")

    admin = Usuario(
        empresa_id=empresa.id,
        username=admin_data["username"],
        nombre=admin_data.get("nombre", admin_data["username"]),
        email=admin_data.get("email"),
        password_hash=hash_password(admin_data["password"]),
        rol="admin",
        activo=True,
    )
    db.add(admin); db.commit()

    audit(db, admin, "instalar", "empresa", empresa.id, slug)

    return SetupOut(
        empresa_id=empresa.id,
        empresa_slug=empresa.slug,
        admin_username=admin.username,
        plan=plan_elegido.codigo,
        mensaje="Instalación completada. Inicia sesión con tu usuario admin.",
    )


@router.post("/instalacion/activar")
def activar_licencia(payload: dict, db: Session = Depends(get_db)):
    """Activa una licencia para la primera empresa (modo instalable)."""
    empresa = db.query(Empresa).first()
    if not empresa:
        raise HTTPException(400, "No hay empresa instalada")
    clave = payload.get("clave", "").strip().upper()
    if not clave:
        raise HTTPException(400, "Clave vacía")

    lic = db.query(Licencia).filter(
        Licencia.clave == clave, Licencia.activa == True
    ).first()
    if not lic:
        raise HTTPException(404, "Licencia inválida o ya usada")
    if lic.empresa_id != empresa.id:
        raise HTTPException(403, "Esta licencia no corresponde a tu instalación")

    return {
        "ok": True,
        "empresa": empresa.nombre,
        "plan": empresa.plan.nombre if empresa.plan else None,
        "expiracion": lic.fecha_expiracion.isoformat() if lic.fecha_expiracion else None,
    }


@router.get("/planes", response_model=list[PlanOut])
def listar_planes(db: Session = Depends(get_db)):
    return db.query(Plan).filter(Plan.activo == True).order_by(Plan.orden).all()


@router.get("/planes/empresa")
def plan_empresa_actual(
    db: Session = Depends(get_db),
    user = None,
):
    """Devuelve info del plan actual (sin auth para onboarding)."""
    e = db.query(Empresa).first()
    if not e:
        return {"instalado": False}
    plan = db.query(Plan).get(e.plan_id) if e.plan_id else None
    return {
        "instalado": True,
        "empresa": {"nombre": e.nombre, "slug": e.slug},
        "plan": {"codigo": plan.codigo, "nombre": plan.nombre} if plan else None,
    }


def _slugify(s: str) -> str:
    s = s.lower().strip()
    # Reemplazar caracteres no alfanumericos por guion
    out = []
    for c in s:
        if c.isalnum():
            out.append(c)
        elif c in " -_":
            out.append("-")
    slug = "".join(out).strip("-")
    return slug or "empresa"