"""Sistema de planes: features gated segun plan contratado.

Sin imports problematicos: este modulo solo expone helpers que NO
importan tenancy.security para evitar ciclos.
"""
from typing import List, Optional
from fastapi import HTTPException

from .models import Plan


# Catálogo de features reconocidas por el sistema
FEATURES = {
    # Operaciones basicas
    "inventario": "Gestión de inventario y ubicaciones",
    "compras": "Compras y gestión de proveedores",
    "ventas": "Ventas, albaranes y gestión de clientes",
    "facturacion": "Facturación (cliente y proveedor)",
    "tesoreria": "Tesorería y conciliación bancaria",
    "obras": "Gestión de obras y subcontratas",
    # Avanzadas
    "multi_almacen": "Múltiples almacenes",
    "multi_usuario_avanzado": "Roles y permisos personalizados",
    "tarifas_avanzadas": "Tarifas por cliente con descuentos",
    "reportes_avanzados": "Informes y exportación avanzada",
    "api_externa": "API para integraciones",
    "soporte_prioritario": "Soporte prioritario",
    "marca_blanca": "Personalización de marca",
    # Modulos extra
    "tickets": "Tickets de soporte / SAT",
    "produccion": "Órdenes de producción",
    "punto_venta": "TPV / caja",
}


def features_del_plan(plan: Optional[Plan]) -> set:
    if not plan or not plan.features:
        return set()
    f = plan.features
    if isinstance(f, dict):
        return {k for k, v in f.items() if v}
    return set()


def assert_feature(plan: Optional[Plan], feature: str):
    """Lanza 403 si el plan no tiene la feature."""
    feats = features_del_plan(plan)
    if feature not in feats:
        nombre = FEATURES.get(feature, feature)
        raise HTTPException(
            403,
            f"Tu plan no incluye: {nombre}. "
            f"Mejora tu plan desde la sección de Suscripción.",
        )


def assert_limit(plan: Optional[Plan], limit_name: str, current_value: int):
    """Lanza 403 si current_value excede el limite del plan."""
    if not plan:
        return
    maximo = getattr(plan, f"max_{limit_name}", None)
    if maximo is None or maximo == 0:
        return
    if current_value >= maximo:
        raise HTTPException(
            403,
            f"Has alcanzado el límite de {limit_name} de tu plan ({maximo}). "
            f"Mejora tu plan para añadir más.",
        )


def planes_default() -> List[dict]:
    """Planes predefinidos que se crean al instalar."""
    return [
        {
            "codigo": "basico",
            "nombre": "Básico",
            "descripcion": "Para autónomos y micropymes. Inventario + ventas.",
            "precio_mensual": 29,
            "precio_anual": 290,
            "moneda": "EUR",
            "max_usuarios": 2,
            "max_productos": 500,
            "max_documentos_mes": 200,
            "max_almacenes": 1,
            "max_cuentas_bancarias": 1,
            "features": {
                "inventario": True,
                "ventas": True,
                "obras": True,
                "compras": False,
                "facturacion": False,
                "tesoreria": False,
                "multi_almacen": False,
                "multi_usuario_avanzado": False,
                "tarifas_avanzadas": False,
                "reportes_avanzados": False,
                "api_externa": False,
                "soporte_prioritario": False,
                "marca_blanca": False,
            },
            "destacado": False,
            "orden": 1,
        },
        {
            "codigo": "pro",
            "nombre": "Profesional",
            "descripcion": "Para pequeñas empresas. Incluye compras y facturación.",
            "precio_mensual": 59,
            "precio_anual": 590,
            "moneda": "EUR",
            "max_usuarios": 5,
            "max_productos": 5000,
            "max_documentos_mes": 2000,
            "max_almacenes": 3,
            "max_cuentas_bancarias": 3,
            "features": {
                "inventario": True,
                "ventas": True,
                "compras": True,
                "facturacion": True,
                "obras": True,
                "tesoreria": True,
                "multi_almacen": True,
                "multi_usuario_avanzado": False,
                "tarifas_avanzadas": True,
                "reportes_avanzados": False,
                "api_externa": False,
                "soporte_prioritario": False,
                "marca_blanca": False,
            },
            "destacado": True,
            "orden": 2,
        },
        {
            "codigo": "empresa",
            "nombre": "Empresa",
            "descripcion": "Sin límites. Multi-almacén, API, marca blanca, soporte prioritario.",
            "precio_mensual": 119,
            "precio_anual": 1190,
            "moneda": "EUR",
            "max_usuarios": 0,
            "max_productos": 0,
            "max_documentos_mes": 0,
            "max_almacenes": 0,
            "max_cuentas_bancarias": 0,
            "features": {
                "inventario": True,
                "ventas": True,
                "compras": True,
                "facturacion": True,
                "obras": True,
                "tesoreria": True,
                "multi_almacen": True,
                "multi_usuario_avanzado": True,
                "tarifas_avanzadas": True,
                "reportes_avanzados": True,
                "api_externa": True,
                "soporte_prioritario": True,
                "marca_blanca": True,
            },
            "destacado": False,
            "orden": 3,
        },
    ]