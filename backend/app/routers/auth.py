"""Endpoints de autenticacion (multi-tenant)."""
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Usuario, Empresa, Plan
from ..schemas import LoginIn, LoginOut, UsuarioOut
from ..security import (
    verify_password, create_session, clear_session,
    get_current_user, audit,
)
from ..plans import features_del_plan

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=LoginOut)
def login(payload: LoginIn, response: Response, db: Session = Depends(get_db)):
    # Buscar por (username, empresa) requiere saber la empresa primero.
    # Estrategia: username es unico DENTRO de empresa. Si hay colision,
    # permitimos login con username@slug.
    user = None
    if "@" in payload.username:
        username, slug = payload.username.split("@", 1)
        empresa = db.query(Empresa).filter(Empresa.slug == slug, Empresa.activa == True).first()
        if empresa:
            user = db.query(Usuario).filter(
                Usuario.empresa_id == empresa.id, Usuario.username == username
            ).first()
    else:
        # buscar primero usuario con ese username en cualquier empresa activa
        user = db.query(Usuario).filter(
            Usuario.username == payload.username, Usuario.activo == True
        ).first()

    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Usuario o contraseña incorrectos")

    empresa = db.query(Empresa).get(user.empresa_id)
    if not empresa or not empresa.activa:
        raise HTTPException(403, "Empresa inactiva")

    plan = db.query(Plan).get(empresa.plan_id) if empresa.plan_id else None
    features_set = features_del_plan(plan)
    features = {f: True for f in features_set}

    create_session(response, user.id)
    audit(db, user, "login", "usuario", user.id, empresa_id=empresa.id)
    return LoginOut(
        id=user.id, username=user.username, nombre=user.nombre, rol=user.rol,
        empresa_id=empresa.id, empresa_nombre=empresa.nombre, empresa_slug=empresa.slug,
        plan=plan.codigo if plan else None, features=features,
    )


@router.post("/logout")
def logout(response: Response, user: Usuario = Depends(get_current_user)):
    clear_session(response)
    return {"ok": True}


@router.get("/me", response_model=LoginOut)
def me(user: Usuario = Depends(get_current_user), db: Session = Depends(get_db)):
    empresa = db.query(Empresa).get(user.empresa_id)
    plan = db.query(Plan).get(empresa.plan_id) if empresa and empresa.plan_id else None
    features_set = features_del_plan(plan)
    features = {f: True for f in features_set}
    return LoginOut(
        id=user.id, username=user.username, nombre=user.nombre, rol=user.rol,
        empresa_id=empresa.id, empresa_nombre=empresa.nombre, empresa_slug=empresa.slug,
        plan=plan.codigo if plan else None, features=features,
    )