"""Schemas Pydantic para request/response."""
from datetime import datetime, date
from typing import Optional, List
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field


# =========== COMUN ===========
class OrmModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# =========== INSTALACION ===========
class SetupIn(BaseModel):
    empresa: dict  # nombre, slug, cif, direccion, etc.
    admin: dict    # username, nombre, email, password
    plan_codigo: str = "basico"  # basico, pro, empresa
    licencia: Optional[str] = None  # clave de activacion (modo instalable)


class SetupOut(BaseModel):
    empresa_id: int
    empresa_slug: str
    admin_username: str
    plan: str
    mensaje: str


# =========== USUARIOS ===========
class UsuarioOut(OrmModel):
    id: int
    empresa_id: int
    username: str
    nombre: str
    email: Optional[str] = None
    rol: str
    activo: bool


class LoginIn(BaseModel):
    username: str
    password: str


class LoginOut(BaseModel):
    id: int
    username: str
    nombre: str
    rol: str
    empresa_id: int
    empresa_nombre: str
    empresa_slug: str
    plan: Optional[str] = None
    features: dict = {}


class UsuarioCreate(BaseModel):
    username: str
    nombre: str
    email: Optional[str] = None
    password: str
    rol: str = "operario"


class UsuarioUpdate(BaseModel):
    nombre: Optional[str] = None
    email: Optional[str] = None
    rol: Optional[str] = None
    activo: Optional[bool] = None
    password: Optional[str] = None


# =========== EMPRESA ===========
class EmpresaOut(OrmModel):
    id: int
    slug: str
    nombre: str
    nombre_comercial: Optional[str] = None
    cif: Optional[str] = None
    direccion: Optional[str] = None
    cp: Optional[str] = None
    poblacion: Optional[str] = None
    provincia: Optional[str] = None
    telefono: Optional[str] = None
    email: Optional[str] = None
    web: Optional[str] = None
    logo_url: Optional[str] = None
    color_primario: Optional[str] = None
    plan_id: Optional[int] = None
    modo: str


class EmpresaUpdate(BaseModel):
    nombre: Optional[str] = None
    nombre_comercial: Optional[str] = None
    cif: Optional[str] = None
    direccion: Optional[str] = None
    cp: Optional[str] = None
    poblacion: Optional[str] = None
    provincia: Optional[str] = None
    telefono: Optional[str] = None
    email: Optional[str] = None
    web: Optional[str] = None
    logo_url: Optional[str] = None
    color_primario: Optional[str] = None
    color_secundario: Optional[str] = None


# =========== PLANES ===========
class PlanOut(OrmModel):
    id: int
    codigo: str
    nombre: str
    descripcion: Optional[str] = None
    precio_mensual: Decimal
    precio_anual: Decimal
    max_usuarios: int
    max_productos: int
    max_documentos_mes: int
    max_almacenes: int
    features: dict = {}


# =========== FAMILIAS ===========
class FamiliaBase(BaseModel):
    codigo: str
    nombre: str
    descripcion: Optional[str] = None


class FamiliaOut(FamiliaBase, OrmModel):
    id: int


# =========== PRODUCTOS (con campos BigTech) ===========
class ProductoBase(BaseModel):
    sku: str
    nombre: str
    descripcion: Optional[str] = None
    familia_id: Optional[int] = None
    codigo_barras: Optional[str] = None
    codigo_proveedor: Optional[str] = None
    marca: Optional[str] = None
    modelo: Optional[str] = None
    unidad_stock: str = "ud"
    unidad_compra: str = "ud"
    unidad_venta: str = "ud"
    factor_compra: float = 1.0
    factor_venta: float = 1.0
    peso_kg: float = 0
    volumen_m3: float = 0
    precio_compra: Decimal = Decimal("0")
    precio_venta: Decimal = Decimal("0")
    iva: str = "21"
    stock_minimo: float = 0
    stock_maximo: float = 0
    proveedor_id: Optional[int] = None
    notas: Optional[str] = None


class ProductoCreate(ProductoBase):
    pass


class ProductoUpdate(BaseModel):
    nombre: Optional[str] = None
    descripcion: Optional[str] = None
    familia_id: Optional[int] = None
    codigo_barras: Optional[str] = None
    codigo_proveedor: Optional[str] = None
    marca: Optional[str] = None
    modelo: Optional[str] = None
    unidad_stock: Optional[str] = None
    unidad_compra: Optional[str] = None
    unidad_venta: Optional[str] = None
    factor_compra: Optional[float] = None
    factor_venta: Optional[float] = None
    peso_kg: Optional[float] = None
    volumen_m3: Optional[float] = None
    precio_compra: Optional[Decimal] = None
    precio_venta: Optional[Decimal] = None
    iva: Optional[str] = None
    stock_minimo: Optional[float] = None
    stock_maximo: Optional[float] = None
    proveedor_id: Optional[int] = None
    notas: Optional[str] = None
    activo: Optional[bool] = None


class ProductoOut(ProductoBase, OrmModel):
    id: int
    stock_actual: float
    activo: bool
    familia_nombre: Optional[str] = None


# =========== UBICACIONES ===========
class UbicacionBase(BaseModel):
    codigo: str
    pasillo: str
    estanteria: str
    hueco: str
    nivel: str = "0"
    capacidad_kg: float = 0
    capacidad_m3: float = 0
    notas: Optional[str] = None


class UbicacionOut(UbicacionBase, OrmModel):
    id: int
    activo: bool


class StockOut(OrmModel):
    id: int
    producto_id: int
    ubicacion_id: int
    cantidad: float
    producto_nombre: str
    producto_sku: str
    ubicacion_codigo: str


# =========== TERCEROS (con campos BigTech) ===========
class TerceroBase(BaseModel):
    tipo: str = "cliente"
    codigo: str
    nombre: str
    nombre_comercial: Optional[str] = None
    cif_nif: Optional[str] = None
    direccion: Optional[str] = None
    cp: Optional[str] = None
    poblacion: Optional[str] = None
    provincia: Optional[str] = None
    pais: str = "España"
    telefono: Optional[str] = None
    email: Optional[str] = None
    contacto: Optional[str] = None
    web: Optional[str] = None
    iban: Optional[str] = None
    banco: Optional[str] = None
    forma_pago: Optional[str] = None
    dias_pago: int = 30
    dia_pago_1: Optional[int] = None
    dia_pago_2: Optional[int] = None
    tarifa_id: Optional[int] = None
    limite_credito: Decimal = Decimal("0")
    regimen_iva: str = "general"
    aplica_irpf: bool = False
    irpf_porcentaje: float = 0
    recargo_equivalencia: bool = False
    notas: Optional[str] = None


class TerceroCreate(TerceroBase):
    pass


class TerceroUpdate(BaseModel):
    tipo: Optional[str] = None
    codigo: Optional[str] = None
    nombre: Optional[str] = None
    nombre_comercial: Optional[str] = None
    cif_nif: Optional[str] = None
    direccion: Optional[str] = None
    cp: Optional[str] = None
    poblacion: Optional[str] = None
    provincia: Optional[str] = None
    telefono: Optional[str] = None
    email: Optional[str] = None
    contacto: Optional[str] = None
    web: Optional[str] = None
    iban: Optional[str] = None
    banco: Optional[str] = None
    forma_pago: Optional[str] = None
    dias_pago: Optional[int] = None
    dia_pago_1: Optional[int] = None
    dia_pago_2: Optional[int] = None
    tarifa_id: Optional[int] = None
    limite_credito: Optional[Decimal] = None
    regimen_iva: Optional[str] = None
    aplica_irpf: Optional[bool] = None
    irpf_porcentaje: Optional[float] = None
    recargo_equivalencia: Optional[bool] = None
    notas: Optional[str] = None
    activo: Optional[bool] = None


class TerceroOut(TerceroBase, OrmModel):
    id: int
    activo: bool


# =========== OBRAS ===========
class ObraBase(BaseModel):
    codigo: str
    nombre: str
    descripcion: Optional[str] = None
    cliente_id: Optional[int] = None
    direccion: Optional[str] = None
    poblacion: Optional[str] = None
    cp: Optional[str] = None
    fecha_inicio: Optional[date] = None
    fecha_fin_prevista: Optional[date] = None
    fecha_fin_real: Optional[date] = None
    presupuesto: Decimal = Decimal("0")
    notas: Optional[str] = None


class ObraCreate(ObraBase):
    estado: str = "planificada"


class ObraUpdate(ObraBase):
    estado: Optional[str] = None


class ObraOut(ObraBase, OrmModel):
    id: int
    estado: str
    cliente_nombre: Optional[str] = None


# =========== ALBARANES ===========
class AlbaranEntradaLineaIn(BaseModel):
    producto_id: int
    cantidad: float
    ubicacion_id: Optional[int] = None
    precio: Decimal = Decimal("0")
    iva: str = "21"
    lote: Optional[str] = None
    caducidad: Optional[date] = None


class AlbaranEntradaCreate(BaseModel):
    numero: Optional[str] = None
    serie: str = "AE"
    proveedor_id: int
    pedido_id: Optional[int] = None
    fecha: date = Field(default_factory=date.today)
    numero_proveedor: Optional[str] = None
    notas: Optional[str] = None
    lineas: List[AlbaranEntradaLineaIn]


class AlbaranEntradaOut(OrmModel):
    id: int
    numero: str
    serie: str
    proveedor_id: int
    proveedor_nombre: str
    pedido_id: Optional[int] = None
    fecha: date
    numero_proveedor: Optional[str] = None
    estado: str
    notas: Optional[str] = None
    creado_en: datetime


class AlbaranSalidaLineaIn(BaseModel):
    producto_id: int
    cantidad: float
    precio: Decimal = Decimal("0")
    descuento: float = 0
    iva: str = "21"


class AlbaranSalidaCreate(BaseModel):
    numero: Optional[str] = None
    serie: str = "AS"
    cliente_id: int
    obra_id: Optional[int] = None
    fecha: date = Field(default_factory=date.today)
    transportista: Optional[str] = None
    matricula: Optional[str] = None
    notas: Optional[str] = None
    lineas: List[AlbaranSalidaLineaIn]


class AlbaranSalidaOut(OrmModel):
    id: int
    numero: str
    serie: str
    cliente_id: int
    cliente_nombre: str
    obra_id: Optional[int] = None
    obra_nombre: Optional[str] = None
    fecha: date
    estado: str
    total: Decimal
    creado_en: datetime


# =========== FACTURAS ===========
class FacturaProveedorCreate(BaseModel):
    numero: Optional[str] = None
    serie: str = "FP"
    proveedor_id: int
    fecha: date = Field(default_factory=date.today)
    fecha_vencimiento: Optional[date] = None
    numero_proveedor: Optional[str] = None
    irpf_porcentaje: float = 0
    notas: Optional[str] = None
    lineas: List[dict]


class FacturaClienteCreate(BaseModel):
    numero: Optional[str] = None
    serie: str = "FC"
    cliente_id: int
    fecha: date = Field(default_factory=date.today)
    fecha_vencimiento: Optional[date] = None
    irpf_porcentaje: float = 0
    recargo_equivalencia: float = 0
    notas: Optional[str] = None
    lineas: List[dict]


# =========== TESORERIA ===========
class MovimientoTesoreriaCreate(BaseModel):
    fecha: date = Field(default_factory=date.today)
    tipo: str
    cuenta_id: int
    importe: Decimal
    concepto: Optional[str] = None
    factura_cliente_id: Optional[int] = None
    factura_proveedor_id: Optional[int] = None
    tercero_id: Optional[int] = None
    notas: Optional[str] = None


class MovimientoTesoreriaOut(OrmModel):
    id: int
    fecha: date
    tipo: str
    cuenta_id: int
    importe: Decimal
    concepto: Optional[str] = None
    conciliado: bool


# =========== TPV ===========
class SesionCajaAbrir(BaseModel):
    saldo_inicial: Decimal = Decimal("0")


class SesionCajaCerrar(BaseModel):
    saldo_final_real: Decimal
    notas: Optional[str] = None


class TicketTPVLineaIn(BaseModel):
    producto_id: int
    cantidad: float
    precio: Optional[Decimal] = None  # si None, usa precio_venta del producto
    iva: str = "21"


class TicketTPVCreate(BaseModel):
    cliente_id: Optional[int] = None
    forma_pago: str = "efectivo"  # efectivo, tarjeta, mixto
    entregado: Decimal = Decimal("0")
    lineas: List[TicketTPVLineaIn]


# =========== TRASPASOS ===========
class TraspasoLineaIn(BaseModel):
    producto_id: int
    cantidad: float
    ubicacion_origen_id: int
    ubicacion_destino_id: int


class TraspasoCreate(BaseModel):
    motivo: Optional[str] = None
    notas: Optional[str] = None
    lineas: List[TraspasoLineaIn]


# =========== INVENTARIO FISICO ===========
class InventarioLineaIn(BaseModel):
    producto_id: int
    ubicacion_id: Optional[int] = None
    cantidad_sistema: float = 0
    cantidad_contada: float = 0


class InventarioCreate(BaseModel):
    nombre: str
    fecha: date = Field(default_factory=date.today)
    notas: Optional[str] = None
    lineas: List[InventarioLineaIn]


# =========== DASHBOARD ===========
class DashboardKPIs(BaseModel):
    productos_total: int
    productos_bajo_minimo: int
    stock_valor_compra: Decimal
    proveedores_total: int
    clientes_total: int
    obras_activas: int
    albaranes_pendientes_facturar: int
    facturas_cliente_pendientes: Decimal
    facturas_proveedor_pendientes: Decimal
    ventas_mes: Decimal
    compras_mes: Decimal


# =========== IMPORTACION CSV ===========
class ImportResult(BaseModel):
    total: int
    creados: int
    actualizados: int
    errores: List[str] = []