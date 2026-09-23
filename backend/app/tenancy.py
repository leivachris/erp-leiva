"""Gestion de tenancy: la empresa activa del request actual.

Patron:
  - El usuario logueado TIENE una empresa_id.
  - Toda query operativa debe filtrar por empresa_id.
  - En endpoints que reciben objetos desde la URL, validar que pertenecen a la empresa.

Importante: para evitar ciclos con security.py, importamos get_current_user
de forma perezosa (dentro de las funciones que lo usan).
"""
from typing import Optional
from fastapi import HTTPException, Depends
from sqlalchemy.orm import Session

from .models import Empresa, Usuario, Suscripcion
from .database import get_db
from .security import get_current_user  # OK: ya no hay ciclo (plans.py no importa tenancy)


def empresa_de_usuario(user: Usuario, db: Session) -> Empresa:
    """Carga la empresa del usuario. 404 si no existe o inactiva."""
    e = db.query(Empresa).get(user.empresa_id)
    if not e or not e.activa:
        raise HTTPException(403, "Empresa inactiva o no encontrada")
    return e


def require_empresa(
    user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Empresa:
    """Dependencia FastAPI: devuelve la empresa del usuario actual."""
    return empresa_de_usuario(user, db)


def empresa_suscripcion_activa(empresa: Empresa, db: Session) -> bool:
    """True si la suscripcion esta activa o en prueba no vencida."""
    from datetime import datetime, timedelta
    s = db.query(Suscripcion).filter(Suscripcion.empresa_id == empresa.id).first()
    if not s:
        return False
    if s.estado == "activa":
        return True
    if s.estado == "prueba":
        if s.fecha_inicio and (datetime.utcnow() - s.fecha_inicio) < timedelta(days=30):
            return True
    return False


def check_empresa_activa(empresa: Empresa, db: Session):
    """Bloquea si la suscripcion esta vencida."""
    if not empresa.activa:
        raise HTTPException(403, "Empresa desactivada. Contacta con soporte.")
    if not empresa_suscripcion_activa(empresa, db):
        raise HTTPException(
            402,
            "Suscripcion vencida. Renueva el plan para continuar.",
        )