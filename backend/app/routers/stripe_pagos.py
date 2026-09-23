"""Endpoints de cobros con Stripe.

Flujo:
  1. Cliente elige plan en /config
  2. Frontend llama POST /api/stripe/checkout con {plan_codigo}
     -> crea Checkout Session en Stripe
     -> devuelve URL para redirigir al cliente
  3. Cliente paga en Stripe (tarjeta, etc.)
  4. Stripe redirige a /suscripcion/exito?session_id=...
  5. Stripe envia webhook a POST /api/stripe/webhook
     -> actualiza estado de la suscripcion en BD
"""
import os
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Empresa, Suscripcion, Plan, AuditLog
from ..security import get_current_user
from ..models import Usuario
from ..tenancy import require_empresa
from ..plans import planes_default

router = APIRouter(prefix="/api/stripe", tags=["stripe"])


STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
PUBLIC_URL = os.environ.get("PUBLIC_URL", "http://localhost:8000")


def get_stripe():
    """Devuelve modulo stripe si esta configurado, sino None."""
    if not STRIPE_SECRET_KEY:
        return None
    try:
        import stripe
        stripe.api_key = STRIPE_SECRET_KEY
        return stripe
    except ImportError:
        return None


# Mapeo plan_codigo -> price_id (configurable via env)
PRICE_IDS = {
    "basico": os.environ.get("STRIPE_PRICE_BASICO", "price_BASICO_PLACEHOLDER"),
    "pro": os.environ.get("STRIPE_PRICE_PRO", "price_PRO_PLACEHOLDER"),
    "empresa": os.environ.get("STRIPE_PRICE_EMPRESA", "price_EMPRESA_PLACEHOLDER"),
}


@router.get("/config")
def config_stripe(user: Usuario = Depends(get_current_user)):
    """Devuelve si Stripe esta configurado y los planes disponibles."""
    return {
        "configurado": bool(STRIPE_SECRET_KEY),
        "precio_mensual_url": f"{PUBLIC_URL}/suscripcion/exito",
        "precio_cancel_url": f"{PUBLIC_URL}/suscripcion/cancel",
        "planes": [
            {"codigo": p["codigo"], "nombre": p["nombre"], "precio_mensual": float(p["precio_mensual"])}
            for p in planes_default()
        ],
    }


@router.post("/checkout")
def crear_checkout_session(
    payload: dict,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
    empresa: Empresa = Depends(require_empresa),
):
    """Crea una sesion de Stripe Checkout para el plan elegido."""
    stripe = get_stripe()
    if not stripe:
        raise HTTPException(503, "Stripe no esta configurado en este servidor")

    plan_codigo = payload.get("plan_codigo")
    if plan_codigo not in PRICE_IDS:
        raise HTTPException(400, "Plan invalido")
    price_id = PRICE_IDS[plan_codigo]
    if "PLACEHOLDER" in price_id:
        raise HTTPException(503, f"Stripe price_id no configurado para plan {plan_codigo}")

    try:
        checkout = stripe.checkout.Session.create(
            mode="subscription",
            payment_method_types=["card"],
            line_items=[{"price": price_id, "quantity": 1}],
            customer_email=user.email or None,
            client_reference_id=str(empresa.id),
            metadata={
                "empresa_id": str(empresa.id),
                "plan_codigo": plan_codigo,
                "empresa_slug": empresa.slug,
            },
            success_url=f"{PUBLIC_URL}/suscripcion/exito?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{PUBLIC_URL}/suscripcion/cancel",
            allow_promotion_codes=True,
        )
        return {"url": checkout.url, "session_id": checkout.id}
    except Exception as e:
        raise HTTPException(500, f"Error creando checkout: {e}")


@router.post("/portal")
def crear_portal_gestion(
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
    empresa: Empresa = Depends(require_empresa),
):
    """Crea una sesion del portal de cliente de Stripe para gestionar su suscripcion."""
    stripe = get_stripe()
    if not stripe:
        raise HTTPException(503, "Stripe no configurado")
    s = db.query(Suscripcion).filter(Suscripcion.empresa_id == empresa.id).first()
    if not s or not s.referencia_pago:
        raise HTTPException(400, "No tienes suscripcion activa en Stripe")
    try:
        portal = stripe.billing_portal.Session.create(
            customer=s.referencia_pago,
            return_url=f"{PUBLIC_URL}/config",
        )
        return {"url": portal.url}
    except Exception as e:
        raise HTTPException(500, f"Error creando portal: {e}")


@router.post("/webhook")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    """Webhook de Stripe. Se ejecuta sin autenticacion (verificamos firma)."""
    stripe = get_stripe()
    if not stripe or not STRIPE_WEBHOOK_SECRET:
        raise HTTPException(503, "Stripe no configurado")

    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
    except Exception as e:
        raise HTTPException(400, f"Firma invalida: {e}")

    # Procesar evento
    if event["type"] in ("checkout.session.completed", "customer.subscription.updated",
                         "customer.subscription.created", "customer.subscription.deleted"):
        session = event["data"]["object"]
        empresa_id = None
        if session.get("client_reference_id"):
            empresa_id = int(session["client_reference_id"])
        elif session.get("metadata", {}).get("empresa_id"):
            empresa_id = int(session["metadata"]["empresa_id"])

        if not empresa_id:
            return {"ok": True}

        empresa = db.query(Empresa).get(empresa_id)
        if not empresa:
            return {"ok": True}

        s = db.query(Suscripcion).filter(Suscripcion.empresa_id == empresa_id).first()
        if not s:
            s = Suscripcion(empresa_id=empresa_id, plan_id=empresa.plan_id or 1)
            db.add(s)

        # Actualizar segun tipo de evento
        if event["type"] == "checkout.session.completed":
            plan_codigo = session.get("metadata", {}).get("plan_codigo")
            plan = db.query(Plan).filter(Plan.codigo == plan_codigo).first() if plan_codigo else None
            if plan:
                s.plan_id = plan.id
                empresa.plan_id = plan.id
            s.estado = "activa"
            s.referencia_pago = session.get("customer")
            s.fecha_inicio = datetime.utcnow()
            # renovar en 1 mes
            from datetime import timedelta
            s.fecha_fin = datetime.utcnow() + timedelta(days=30)
            s.fecha_proxima_renovacion = s.fecha_fin
        elif event["type"] == "customer.subscription.deleted":
            s.estado = "cancelada"
        elif event["type"] in ("customer.subscription.updated", "customer.subscription.created"):
            sub = event["data"]["object"]
            s.estado = "activa" if sub.get("status") == "active" else sub.get("status")
            s.fecha_proxima_renovacion = (
                datetime.fromtimestamp(sub["current_period_end"])
                if sub.get("current_period_end") else None
            )

        db.add(AuditLog(
            empresa_id=empresa_id,
            accion=f"stripe_{event['type']}",
            entidad="suscripcion",
            detalle=f"Plan: {session.get('metadata', {}).get('plan_codigo', '?')}"
        ))
        db.commit()

    return {"ok": True}


# ============ API publica para el frontend ============
@router.get("/planes-publicos")
def listar_planes_publicos(db: Session = Depends(get_db)):
    """Planes visibles sin autenticacion (para landing de venta)."""
    planes = db.query(Plan).filter(Plan.activo == True).order_by(Plan.orden).all()
    return [
        {
            "codigo": p.codigo,
            "nombre": p.nombre,
            "descripcion": p.descripcion,
            "precio_mensual": float(p.precio_mensual),
            "precio_anual": float(p.precio_anual),
            "max_usuarios": p.max_usuarios,
            "max_productos": p.max_productos,
            "features": p.features or {},
        } for p in planes
    ]