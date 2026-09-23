"""Autenticacion basica con cookies de sesion firmadas.

Multi-tenant: el usuario pertenece a una Empresa. La sesion no carga
directamente los datos sensibles; el caller debe usar `require_empresa`
para obtenerlos.
"""
from datetime import datetime
from typing import Optional

from fastapi import Depends, HTTPException, Request, Response, status
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from .config import SECRET_KEY, SESSION_MAX_AGE
from .database import get_db
from .models import Usuario, AuditLog
from .plans import assert_feature, features_del_plan

# Hashing: pbkdf2_sha256 (built-in, sin problemas con bcrypt 5.x)
# NOTA: passlib esta deprecado y rompe con bcrypt 5.x. pbkdf2_sha256 es
# nativo de hashlib, sin dependencias externas y suficiente para el ERP.
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

# Cookie
SESSION_COOKIE = "erp_session"


def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def _sign(payload: str) -> str:
    from itsdangerous import URLSafeSerializer
    s = URLSafeSerializer(SECRET_KEY, salt="erp-session")
    return s.dumps(payload)


def _unsign(token: str) -> Optional[str]:
    from itsdangerous import URLSafeSerializer, BadSignature
    s = URLSafeSerializer(SECRET_KEY, salt="erp-session")
    try:
        return s.loads(token)
    except BadSignature:
        return None


def create_session(response: Response, user_id: int):
    token = _sign(str(user_id))
    response.set_cookie(
        key=SESSION_COOKIE, value=token,
        max_age=SESSION_MAX_AGE, httponly=True, samesite="lax", path="/",
    )


def clear_session(response: Response):
    response.delete_cookie(SESSION_COOKIE, path="/")


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
) -> Usuario:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise HTTPException(status_code=401, detail="No autenticado")
    uid = _unsign(token)
    if not uid:
        raise HTTPException(status_code=401, detail="Sesion invalida")
    user = db.query(Usuario).filter(Usuario.id == int(uid), Usuario.activo == True).first()
    if not user:
        raise HTTPException(status_code=401, detail="Usuario inactivo")
    user.ultimo_acceso = datetime.utcnow()
    db.commit()
    return user


def require_role(*roles: str):
    def dep(user: Usuario = Depends(get_current_user)):
        # root = super-admin (passa tots els checks)
        # admin = admin (passa tots els checks habituals)
        if user.rol not in roles and user.rol not in ("admin", "root"):
            raise HTTPException(status_code=403, detail=f"Requiere rol: {roles}")
        return user
    return dep


def audit(db: Session, user: Optional[Usuario], accion: str, entidad: str,
          entidad_id: Optional[int] = None, detalle: Optional[str] = None,
          empresa_id: Optional[int] = None):
    try:
        log = AuditLog(
            empresa_id=empresa_id or (user.empresa_id if user else None),
            usuario_id=user.id if user else None,
            accion=accion, entidad=entidad, entidad_id=entidad_id,
            detalle=detalle, fecha=datetime.utcnow(),
        )
        db.add(log); db.commit()
    except Exception:
        db.rollback()
        pass


def check_feature(user: Usuario, feature: str, db: Session):
    """Verifica que el plan de la empresa del usuario tiene la feature."""
    # root bypassa comprovacions de plan
    if user.rol == "root":
        return
    from .models import Plan
    from .tenancy import empresa_de_usuario
    empresa = empresa_de_usuario(user, db)
    if not empresa.plan_id:
        raise HTTPException(403, "Empresa sin plan asignado")
    plan = db.query(Plan).get(empresa.plan_id)
    assert_feature(plan, feature)