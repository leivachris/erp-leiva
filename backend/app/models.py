"""Modelos SQLAlchemy del ERP LEIVA - version multi-tenant.

ARQUITECTURA:
  - Una BD (SQLite por instalacion, PostgreSQL en SaaS).
  - Multi-tenant por columna: TODAS las tablas operativas tienen `empresa_id`.
  - Cada Empresa tiene un Plan (basico/pro/empresa) que limita features.
  - El usuario pertenece a una Empresa. Un usuario NO ve datos de otra empresa.
  - Instalable: una sola empresa. SaaS: muchas empresas en una sola BD.

Entidades:
  - Empresas, Planes, Suscripciones, Licencias
  - Usuarios (por empresa)
  - Catalogo: Familias, Productos, Ubicaciones, Stocks, Tarifas
  - Terceros: Proveedores/Clientes
  - Operaciones: PedidosCompra, AlbaranesEntrada, AlbaranesSalida
  - Facturacion: FacturasProveedor, FacturasCliente
  - Tesoreria: CuentasBancarias, MovimientosTesoreria
  - Trazabilidad: MovimientosStock
  - Auditoria: AuditLog
"""
from datetime import datetime, date
from sqlalchemy import (
    Column, Integer, String, Float, DateTime, Date, Boolean, ForeignKey,
    Text, Numeric, Enum, UniqueConstraint, Index, JSON
)
from sqlalchemy.orm import relationship
import enum

from .database import Base


# ============================== ENUMS ==============================
class UnidadEnum(str, enum.Enum):
    UNIDAD = "ud"
    KILO = "kg"
    GRAMO = "g"
    LITRO = "l"
    METRO = "m"
    METRO_CUADRADO = "m2"
    METRO_CUBICO = "m3"
    PALET = "palet"
    BIG_BAG = "bigbag"
    SACO = "saco"
    BOLSA = "bolsa"
    ROLLO = "rollo"
    CAJA = "caja"
    TONELADA = "t"


class TipoIva(str, enum.Enum):
    GENERAL = "21"
    REDUCIDO = "10"
    SUPERREDUCIDO = "4"
    EXENTO = "0"


class EstadoPedido(str, enum.Enum):
    BORRADOR = "borrador"
    ENVIADO = "enviado"
    PARCIAL = "parcial"
    RECIBIDO = "recibido"
    CANCELADO = "cancelado"


class EstadoAlbaran(str, enum.Enum):
    BORRADOR = "borrador"
    CONFIRMADO = "confirmado"
    FACTURADO = "facturado"
    ANULADO = "anulado"


class EstadoFactura(str, enum.Enum):
    BORRADOR = "borrador"
    EMITIDA = "emitida"
    PAGADA_PARCIAL = "pagada_parcial"
    PAGADA = "pagada"
    VENCIDA = "vencida"
    ANULADA = "anulada"


class EstadoObra(str, enum.Enum):
    PLANIFICADA = "planificada"
    ACTIVA = "activa"
    PAUSADA = "pausada"
    FINALIZADA = "finalizada"
    CANCELADA = "cancelada"


class TipoMovimiento(str, enum.Enum):
    ENTRADA_COMPRA = "entrada_compra"
    SALIDA_VENTA = "salida_venta"
    AJUSTE_POSITIVO = "ajuste_positivo"
    AJUSTE_NEGATIVO = "ajuste_negativo"
    TRASPASO = "traspaso"
    INVENTARIO = "inventario"


class EstadoSuscripcion(str, enum.Enum):
    ACTIVA = "activa"
    VENCIDA = "vencida"
    CANCELADA = "cancelada"
    PRUEBA = "prueba"


# ============================== PLANES ==============================
class Plan(Base):
    """Plan comercial del producto. features es dict {clave: bool}."""
    __tablename__ = "planes"
    id = Column(Integer, primary_key=True)
    codigo = Column(String(20), unique=True, nullable=False)  # basico, pro, empresa
    nombre = Column(String(100), nullable=False)
    descripcion = Column(Text, nullable=True)
    precio_mensual = Column(Numeric(10, 2), default=0)
    precio_anual = Column(Numeric(10, 2), default=0)
    moneda = Column(String(3), default="EUR")
    max_usuarios = Column(Integer, default=1)
    max_productos = Column(Integer, default=500)
    max_documentos_mes = Column(Integer, default=200)
    max_almacenes = Column(Integer, default=1)
    max_cuentas_bancarias = Column(Integer, default=1)
    features = Column(JSON, default=dict)  # {"compras": true, "facturacion": true, ...}
    activo = Column(Boolean, default=True)
    destacado = Column(Boolean, default=False)
    orden = Column(Integer, default=0)


# ============================== EMPRESAS ==============================
class Empresa(Base):
    """Cada cliente del SaaS / instalacion es una Empresa."""
    __tablename__ = "empresas"
    id = Column(Integer, primary_key=True)
    slug = Column(String(60), unique=True, nullable=False, index=True)
    nombre = Column(String(200), nullable=False)
    nombre_comercial = Column(String(200), nullable=True)
    cif = Column(String(20), nullable=True)
    direccion = Column(String(255), nullable=True)
    cp = Column(String(10), nullable=True)
    poblacion = Column(String(100), nullable=True)
    provincia = Column(String(100), nullable=True)
    pais = Column(String(60), default="España")
    telefono = Column(String(30), nullable=True)
    email = Column(String(120), nullable=True)
    web = Column(String(200), nullable=True)
    logo_url = Column(String(500), nullable=True)
    color_primario = Column(String(7), default="#2563eb")  # para tema del frontend
    color_secundario = Column(String(7), default="#1e40af")
    plan_id = Column(Integer, ForeignKey("planes.id"), nullable=True)
    modo = Column(String(20), default="instalable")  # instalable | saas
    activa = Column(Boolean, default=True)
    fecha_alta = Column(DateTime, default=datetime.utcnow)
    fecha_baja = Column(DateTime, nullable=True)
    notas = Column(Text, nullable=True)

    plan = relationship("Plan")
    usuarios = relationship("Usuario", back_populates="empresa")
    suscripcion = relationship("Suscripcion", back_populates="empresa", uselist=False)


class Suscripcion(Base):
    """Suscripcion activa de la empresa a un plan."""
    __tablename__ = "suscripciones"
    id = Column(Integer, primary_key=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"), unique=True, nullable=False)
    plan_id = Column(Integer, ForeignKey("planes.id"), nullable=False)
    estado = Column(String(20), default="prueba")  # activa, prueba, vencida, cancelada
    periodicidad = Column(String(10), default="mensual")  # mensual, anual
    fecha_inicio = Column(DateTime, default=datetime.utcnow)
    fecha_fin = Column(DateTime, nullable=True)
    fecha_proxima_renovacion = Column(Date, nullable=True)
    metodo_pago = Column(String(50), nullable=True)
    referencia_pago = Column(String(100), nullable=True)
    notas = Column(Text, nullable=True)

    empresa = relationship("Empresa", back_populates="suscripcion")
    plan = relationship("Plan")


class Licencia(Base):
    """Clave de activacion para modo instalable. SaaS no usa licencia."""
    __tablename__ = "licencias"
    id = Column(Integer, primary_key=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=False, index=True)
    clave = Column(String(60), unique=True, nullable=False, index=True)
    max_instalaciones = Column(Integer, default=1)
    instalaciones_activas = Column(Integer, default=0)
    fecha_emision = Column(DateTime, default=datetime.utcnow)
    fecha_expiracion = Column(Date, nullable=True)
    activa = Column(Boolean, default=True)
    notas = Column(Text, nullable=True)

    empresa = relationship("Empresa")


# ============================== USUARIOS ==============================
class Usuario(Base):
    __tablename__ = "usuarios"
    id = Column(Integer, primary_key=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=False, index=True)
    username = Column(String(50), nullable=False, index=True)
    nombre = Column(String(100), nullable=False)
    email = Column(String(120), nullable=True)
    password_hash = Column(String(255), nullable=False)
    rol = Column(String(20), default="operario")  # admin, jefe, operario
    activo = Column(Boolean, default=True)
    ultimo_acceso = Column(DateTime, nullable=True)
    creado_en = Column(DateTime, default=datetime.utcnow)

    empresa = relationship("Empresa", back_populates="usuarios")

    __table_args__ = (
        UniqueConstraint("empresa_id", "username", name="uq_usuario_empresa_username"),
    )


# ============================== CATALOGO ==============================
class Familia(Base):
    __tablename__ = "familias"
    id = Column(Integer, primary_key=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=False, index=True)
    codigo = Column(String(20), nullable=False, index=True)
    nombre = Column(String(100), nullable=False)
    descripcion = Column(Text, nullable=True)

    productos = relationship("Producto", back_populates="familia")

    __table_args__ = (
        UniqueConstraint("empresa_id", "codigo", name="uq_familia_empresa_codigo"),
    )


class Producto(Base):
    """Producto/SKU del almacen."""
    __tablename__ = "productos"
    id = Column(Integer, primary_key=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=False, index=True)
    sku = Column(String(50), nullable=False, index=True)
    codigo_barras = Column(String(50), nullable=True, index=True)  # EAN-13, Code128...
    codigo_proveedor = Column(String(50), nullable=True, index=True)  # ref. del proveedor
    nombre = Column(String(200), nullable=False, index=True)
    descripcion = Column(Text, nullable=True)
    familia_id = Column(Integer, ForeignKey("familias.id"), nullable=True)
    marca = Column(String(100), nullable=True, index=True)
    modelo = Column(String(100), nullable=True)

    unidad_stock = Column(String(10), default="ud", nullable=False)
    unidad_compra = Column(String(10), default="ud", nullable=False)
    unidad_venta = Column(String(10), default="ud", nullable=False)
    factor_compra = Column(Float, default=1.0)
    factor_venta = Column(Float, default=1.0)

    # Pesos y volumen (para cálculo de portes)
    peso_kg = Column(Float, default=0)  # por unidad_stock
    volumen_m3 = Column(Float, default=0)  # por unidad_stock

    precio_compra = Column(Numeric(12, 4), default=0)
    precio_venta = Column(Numeric(12, 4), default=0)
    iva = Column(String(4), default="21", nullable=False)

    stock_minimo = Column(Float, default=0)
    stock_maximo = Column(Float, default=0)
    stock_actual = Column(Float, default=0)

    # Proveedor por defecto (para pedidos rápidos)
    proveedor_id = Column(Integer, ForeignKey("terceros.id"), nullable=True)

    activo = Column(Boolean, default=True)
    notas = Column(Text, nullable=True)
    creado_en = Column(DateTime, default=datetime.utcnow)
    actualizado_en = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    familia = relationship("Familia", back_populates="productos")
    movimientos = relationship("MovimientoStock", back_populates="producto")

    __table_args__ = (
        UniqueConstraint("empresa_id", "sku", name="uq_producto_empresa_sku"),
        Index("ix_producto_empresa_nombre", "empresa_id", "nombre"),
    )


class Ubicacion(Base):
    """Pasillo-Estanteria-Hueco-Nivel."""
    __tablename__ = "ubicaciones"
    id = Column(Integer, primary_key=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=False, index=True)
    almacen_id = Column(Integer, ForeignKey("almacenes.id"), nullable=True, index=True)
    codigo = Column(String(30), nullable=False, index=True)
    pasillo = Column(String(10), nullable=False)
    estanteria = Column(String(10), nullable=False)
    hueco = Column(String(10), nullable=False)
    nivel = Column(String(10), default="0")
    capacidad_kg = Column(Float, default=0)
    capacidad_m3 = Column(Float, default=0)
    notas = Column(Text, nullable=True)
    activo = Column(Boolean, default=True)

    stocks = relationship("Stock", back_populates="ubicacion")
    almacen = relationship("Almacen", back_populates="ubicaciones")

    __table_args__ = (
        UniqueConstraint("empresa_id", "codigo", name="uq_ubicacion_empresa_codigo"),
    )


class Stock(Base):
    """Stock de un producto en una ubicacion."""
    __tablename__ = "stocks"
    __table_args__ = (
        UniqueConstraint("empresa_id", "producto_id", "ubicacion_id",
                         name="uq_stock_empresa_producto_ubicacion"),
    )
    id = Column(Integer, primary_key=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=False, index=True)
    producto_id = Column(Integer, ForeignKey("productos.id"), nullable=False, index=True)
    ubicacion_id = Column(Integer, ForeignKey("ubicaciones.id"), nullable=False, index=True)
    cantidad = Column(Float, default=0, nullable=False)
    actualizado_en = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    producto = relationship("Producto")
    ubicacion = relationship("Ubicacion", back_populates="stocks")


# ============================== TERCEROS ==============================
class Tercero(Base):
    """Proveedor y/o cliente unificados."""
    __tablename__ = "terceros"
    id = Column(Integer, primary_key=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=False, index=True)
    tipo = Column(String(10), default="cliente", nullable=False)
    codigo = Column(String(20), nullable=False, index=True)
    nombre = Column(String(200), nullable=False, index=True)
    nombre_comercial = Column(String(200), nullable=True)
    cif_nif = Column(String(20), nullable=True)
    direccion = Column(String(255), nullable=True)
    cp = Column(String(10), nullable=True)
    poblacion = Column(String(100), nullable=True)
    provincia = Column(String(100), nullable=True)
    pais = Column(String(60), default="España")
    telefono = Column(String(30), nullable=True)
    email = Column(String(120), nullable=True)
    contacto = Column(String(120), nullable=True)
    web = Column(String(200), nullable=True)
    iban = Column(String(34), nullable=True)
    banco = Column(String(100), nullable=True)
    forma_pago = Column(String(100), nullable=True)
    dias_pago = Column(Integer, default=30)
    dia_pago_1 = Column(Integer, nullable=True)  # ej: 5 para "el dia 5 de cada mes"
    dia_pago_2 = Column(Integer, nullable=True)  # ej: 20 para "el 5 y el 20"
    tarifa_id = Column(Integer, ForeignKey("tarifas.id"), nullable=True)
    limite_credito = Column(Numeric(12, 2), default=0)
    # Campos BigTech
    regimen_iva = Column(String(20), default="general")  # general, recargo_equivalencia, simplificado, exento
    aplica_irpf = Column(Boolean, default=False)
    irpf_porcentaje = Column(Float, default=0)  # ej: 15.0 para profesionales
    recargo_equivalencia = Column(Boolean, default=False)
    notas = Column(Text, nullable=True)
    activo = Column(Boolean, default=True)
    creado_en = Column(DateTime, default=datetime.utcnow)
    actualizado_en = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    tarifa = relationship("Tarifa")
    obras = relationship("Obra", back_populates="cliente")

    __table_args__ = (
        UniqueConstraint("empresa_id", "codigo", name="uq_tercero_empresa_codigo"),
        Index("ix_tercero_empresa_nombre", "empresa_id", "nombre"),
    )


class Tarifa(Base):
    __tablename__ = "tarifas"
    id = Column(Integer, primary_key=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=False, index=True)
    nombre = Column(String(100), nullable=False)
    descripcion = Column(Text, nullable=True)
    activo = Column(Boolean, default=True)

    lineas = relationship("TarifaLinea", back_populates="tarifa", cascade="all, delete-orphan")


class TarifaLinea(Base):
    __tablename__ = "tarifa_lineas"
    id = Column(Integer, primary_key=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=False, index=True)
    tarifa_id = Column(Integer, ForeignKey("tarifas.id"), nullable=False, index=True)
    producto_id = Column(Integer, ForeignKey("productos.id"), nullable=False, index=True)
    precio = Column(Numeric(12, 4), nullable=False)
    descuento = Column(Float, default=0)

    tarifa = relationship("Tarifa", back_populates="lineas")
    producto = relationship("Producto")


# ============================== OBRAS ==============================
class Obra(Base):
    __tablename__ = "obras"
    id = Column(Integer, primary_key=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=False, index=True)
    codigo = Column(String(30), nullable=False, index=True)
    nombre = Column(String(200), nullable=False)
    descripcion = Column(Text, nullable=True)
    cliente_id = Column(Integer, ForeignKey("terceros.id"), nullable=True)
    direccion = Column(String(255), nullable=True)
    poblacion = Column(String(100), nullable=True)
    cp = Column(String(10), nullable=True)
    fecha_inicio = Column(Date, nullable=True)
    fecha_fin_prevista = Column(Date, nullable=True)
    fecha_fin_real = Column(Date, nullable=True)
    presupuesto = Column(Numeric(14, 2), default=0)
    estado = Column(String(20), default="planificada")
    notas = Column(Text, nullable=True)
    creado_en = Column(DateTime, default=datetime.utcnow)
    actualizado_en = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    cliente = relationship("Tercero", back_populates="obras")
    albaranes = relationship("AlbaranSalida", back_populates="obra")

    __table_args__ = (
        UniqueConstraint("empresa_id", "codigo", name="uq_obra_empresa_codigo"),
    )


# ============================== PEDIDOS COMPRA ==============================
class PedidoCompra(Base):
    __tablename__ = "pedidos_compra"
    id = Column(Integer, primary_key=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=False, index=True)
    numero = Column(String(30), nullable=False, index=True)
    proveedor_id = Column(Integer, ForeignKey("terceros.id"), nullable=False)
    fecha = Column(Date, default=date.today, nullable=False)
    fecha_prevista = Column(Date, nullable=True)
    estado = Column(String(20), default="borrador")
    notas = Column(Text, nullable=True)
    subtotal = Column(Numeric(14, 2), default=0)
    total_iva = Column(Numeric(14, 2), default=0)
    total = Column(Numeric(14, 2), default=0)
    creado_por_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    creado_en = Column(DateTime, default=datetime.utcnow)
    actualizado_en = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    proveedor = relationship("Tercero")
    lineas = relationship("PedidoCompraLinea", back_populates="pedido", cascade="all, delete-orphan")
    creado_por = relationship("Usuario")

    __table_args__ = (
        UniqueConstraint("empresa_id", "numero", name="uq_pedido_empresa_numero"),
    )


class PedidoCompraLinea(Base):
    __tablename__ = "pedidos_compra_lineas"
    id = Column(Integer, primary_key=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=False, index=True)
    pedido_id = Column(Integer, ForeignKey("pedidos_compra.id"), nullable=False, index=True)
    producto_id = Column(Integer, ForeignKey("productos.id"), nullable=False)
    cantidad = Column(Float, nullable=False)
    cantidad_recibida = Column(Float, default=0)
    precio = Column(Numeric(12, 4), nullable=False)
    descuento = Column(Float, default=0)
    iva = Column(String(4), default="21")
    subtotal = Column(Numeric(14, 2), default=0)

    pedido = relationship("PedidoCompra", back_populates="lineas")
    producto = relationship("Producto")


# ============================== ALBARANES ENTRADA ==============================
class AlbaranEntrada(Base):
    __tablename__ = "albaranes_entrada"
    id = Column(Integer, primary_key=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=False, index=True)
    numero = Column(String(30), nullable=False, index=True)
    serie = Column(String(10), default="AE")
    proveedor_id = Column(Integer, ForeignKey("terceros.id"), nullable=False)
    pedido_id = Column(Integer, ForeignKey("pedidos_compra.id"), nullable=True)
    fecha = Column(Date, default=date.today, nullable=False)
    numero_proveedor = Column(String(50), nullable=True)
    estado = Column(String(20), default="confirmado")
    notas = Column(Text, nullable=True)
    creado_por_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    creado_en = Column(DateTime, default=datetime.utcnow)

    proveedor = relationship("Tercero")
    pedido = relationship("PedidoCompra")
    lineas = relationship("AlbaranEntradaLinea", back_populates="albaran", cascade="all, delete-orphan")
    creado_por = relationship("Usuario")

    __table_args__ = (
        UniqueConstraint("empresa_id", "numero", name="uq_alb_entrada_empresa_numero"),
    )


class AlbaranEntradaLinea(Base):
    __tablename__ = "albaranes_entrada_lineas"
    id = Column(Integer, primary_key=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=False, index=True)
    albaran_id = Column(Integer, ForeignKey("albaranes_entrada.id"), nullable=False, index=True)
    producto_id = Column(Integer, ForeignKey("productos.id"), nullable=False)
    cantidad = Column(Float, nullable=False)
    ubicacion_id = Column(Integer, ForeignKey("ubicaciones.id"), nullable=True)
    precio = Column(Numeric(12, 4), default=0)
    iva = Column(String(4), default="21")
    lote = Column(String(50), nullable=True)
    caducidad = Column(Date, nullable=True)

    albaran = relationship("AlbaranEntrada", back_populates="lineas")
    producto = relationship("Producto")
    ubicacion = relationship("Ubicacion")


# ============================== ALBARANES SALIDA ==============================
class AlbaranSalida(Base):
    __tablename__ = "albaranes_salida"
    id = Column(Integer, primary_key=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=False, index=True)
    numero = Column(String(30), nullable=False, index=True)
    serie = Column(String(10), default="AS")
    cliente_id = Column(Integer, ForeignKey("terceros.id"), nullable=False)
    obra_id = Column(Integer, ForeignKey("obras.id"), nullable=True)
    fecha = Column(Date, default=date.today, nullable=False)
    estado = Column(String(20), default="confirmado")
    transportista = Column(String(100), nullable=True)
    matricula = Column(String(20), nullable=True)
    notas = Column(Text, nullable=True)
    subtotal = Column(Numeric(14, 2), default=0)
    total_iva = Column(Numeric(14, 2), default=0)
    total = Column(Numeric(14, 2), default=0)
    creado_por_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    creado_en = Column(DateTime, default=datetime.utcnow)

    cliente = relationship("Tercero")
    obra = relationship("Obra", back_populates="albaranes")
    lineas = relationship("AlbaranSalidaLinea", back_populates="albaran", cascade="all, delete-orphan")
    creado_por = relationship("Usuario")

    __table_args__ = (
        UniqueConstraint("empresa_id", "numero", name="uq_alb_salida_empresa_numero"),
    )


class AlbaranSalidaLinea(Base):
    __tablename__ = "albaranes_salida_lineas"
    id = Column(Integer, primary_key=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=False, index=True)
    albaran_id = Column(Integer, ForeignKey("albaranes_salida.id"), nullable=False, index=True)
    producto_id = Column(Integer, ForeignKey("productos.id"), nullable=False)
    cantidad = Column(Float, nullable=False)
    precio = Column(Numeric(12, 4), default=0)
    descuento = Column(Float, default=0)
    iva = Column(String(4), default="21")
    subtotal = Column(Numeric(14, 2), default=0)

    albaran = relationship("AlbaranSalida", back_populates="lineas")
    producto = relationship("Producto")


# ============================== FACTURAS PROVEEDOR ==============================
class FacturaProveedor(Base):
    __tablename__ = "facturas_proveedor"
    id = Column(Integer, primary_key=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=False, index=True)
    numero = Column(String(30), nullable=False, index=True)
    serie = Column(String(10), default="FP")
    proveedor_id = Column(Integer, ForeignKey("terceros.id"), nullable=False)
    fecha = Column(Date, default=date.today, nullable=False)
    fecha_vencimiento = Column(Date, nullable=True)
    numero_proveedor = Column(String(50), nullable=True)
    estado = Column(String(20), default="emitida")
    subtotal = Column(Numeric(14, 2), default=0)
    total_iva = Column(Numeric(14, 2), default=0)
    # IRPF soportado (facturas con retención)
    irpf_porcentaje = Column(Float, default=0)
    importe_irpf = Column(Numeric(14, 2), default=0)
    total = Column(Numeric(14, 2), default=0)
    pagado = Column(Numeric(14, 2), default=0)
    notas = Column(Text, nullable=True)
    creado_en = Column(DateTime, default=datetime.utcnow)

    proveedor = relationship("Tercero")
    lineas = relationship("FacturaProveedorLinea", back_populates="factura", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("empresa_id", "numero", name="uq_factura_prov_empresa_numero"),
    )


class FacturaProveedorLinea(Base):
    __tablename__ = "facturas_proveedor_lineas"
    id = Column(Integer, primary_key=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=False, index=True)
    factura_id = Column(Integer, ForeignKey("facturas_proveedor.id"), nullable=False, index=True)
    producto_id = Column(Integer, ForeignKey("productos.id"), nullable=True)
    descripcion = Column(String(255), nullable=False)
    cantidad = Column(Float, default=1)
    precio = Column(Numeric(12, 4), nullable=False)
    descuento = Column(Float, default=0)
    iva = Column(String(4), default="21")
    subtotal = Column(Numeric(14, 2), default=0)

    factura = relationship("FacturaProveedor", back_populates="lineas")
    producto = relationship("Producto")


# ============================== FACTURAS CLIENTE ==============================
class FacturaCliente(Base):
    __tablename__ = "facturas_cliente"
    id = Column(Integer, primary_key=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=False, index=True)
    numero = Column(String(30), nullable=False, index=True)
    serie = Column(String(10), default="FC")
    cliente_id = Column(Integer, ForeignKey("terceros.id"), nullable=False)
    fecha = Column(Date, default=date.today, nullable=False)
    fecha_vencimiento = Column(Date, nullable=True)
    estado = Column(String(20), default="emitida")
    subtotal = Column(Numeric(14, 2), default=0)
    total_iva = Column(Numeric(14, 2), default=0)
    # Campos BigTech: IRPF
    irpf_porcentaje = Column(Float, default=0)  # 15, 7, 0
    importe_irpf = Column(Numeric(14, 2), default=0)
    recargo_equivalencia = Column(Float, default=0)  # % RE
    total_recargo = Column(Numeric(14, 2), default=0)
    total = Column(Numeric(14, 2), default=0)
    cobrado = Column(Numeric(14, 2), default=0)
    notas = Column(Text, nullable=True)
    creado_en = Column(DateTime, default=datetime.utcnow)

    cliente = relationship("Tercero")
    lineas = relationship("FacturaClienteLinea", back_populates="factura", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("empresa_id", "numero", name="uq_factura_cli_empresa_numero"),
    )


class FacturaClienteLinea(Base):
    __tablename__ = "facturas_cliente_lineas"
    id = Column(Integer, primary_key=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=False, index=True)
    factura_id = Column(Integer, ForeignKey("facturas_cliente.id"), nullable=False, index=True)
    producto_id = Column(Integer, ForeignKey("productos.id"), nullable=True)
    albaran_salida_id = Column(Integer, ForeignKey("albaranes_salida.id"), nullable=True)
    descripcion = Column(String(255), nullable=False)
    cantidad = Column(Float, default=1)
    precio = Column(Numeric(12, 4), nullable=False)
    descuento = Column(Float, default=0)
    iva = Column(String(4), default="21")
    subtotal = Column(Numeric(14, 2), default=0)

    factura = relationship("FacturaCliente", back_populates="lineas")
    producto = relationship("Producto")
    albaran = relationship("AlbaranSalida")


# ============================== TESORERIA ==============================
class CuentaBancaria(Base):
    __tablename__ = "cuentas_bancarias"
    id = Column(Integer, primary_key=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=False, index=True)
    nombre = Column(String(100), nullable=False)
    iban = Column(String(34), nullable=True)
    banco = Column(String(100), nullable=True)
    saldo_inicial = Column(Numeric(14, 2), default=0)
    saldo_actual = Column(Numeric(14, 2), default=0)
    activo = Column(Boolean, default=True)


class MovimientoTesoreria(Base):
    __tablename__ = "movimientos_tesoreria"
    id = Column(Integer, primary_key=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=False, index=True)
    fecha = Column(Date, default=date.today, nullable=False, index=True)
    tipo = Column(String(20), nullable=False)  # cobro, pago, traspaso, comision, ajuste
    cuenta_id = Column(Integer, ForeignKey("cuentas_bancarias.id"), nullable=False, index=True)
    importe = Column(Numeric(14, 2), nullable=False)
    concepto = Column(String(255), nullable=True)
    factura_cliente_id = Column(Integer, ForeignKey("facturas_cliente.id"), nullable=True)
    factura_proveedor_id = Column(Integer, ForeignKey("facturas_proveedor.id"), nullable=True)
    tercero_id = Column(Integer, ForeignKey("terceros.id"), nullable=True)
    conciliado = Column(Boolean, default=False)
    notas = Column(Text, nullable=True)
    creado_en = Column(DateTime, default=datetime.utcnow)

    cuenta = relationship("CuentaBancaria")
    factura_cliente = relationship("FacturaCliente")
    factura_proveedor = relationship("FacturaProveedor")
    tercero = relationship("Tercero")


# ============================== TRAZABILIDAD STOCK ==============================
class MovimientoStock(Base):
    """Cada entrada/salida/ajuste deja un movimiento. fuente de verdad del stock."""
    __tablename__ = "movimientos_stock"
    id = Column(Integer, primary_key=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=False, index=True)
    fecha = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    tipo = Column(String(30), nullable=False)
    producto_id = Column(Integer, ForeignKey("productos.id"), nullable=False, index=True)
    cantidad = Column(Float, nullable=False)  # + entrada, - salida
    ubicacion_origen_id = Column(Integer, ForeignKey("ubicaciones.id"), nullable=True)
    ubicacion_destino_id = Column(Integer, ForeignKey("ubicaciones.id"), nullable=True)
    albaran_entrada_id = Column(Integer, ForeignKey("albaranes_entrada.id"), nullable=True)
    albaran_salida_id = Column(Integer, ForeignKey("albaranes_salida.id"), nullable=True)
    pedido_compra_id = Column(Integer, ForeignKey("pedidos_compra.id"), nullable=True)
    obra_id = Column(Integer, ForeignKey("obras.id"), nullable=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    notas = Column(Text, nullable=True)

    producto = relationship("Producto", back_populates="movimientos")
    ubicacion_origen = relationship("Ubicacion", foreign_keys=[ubicacion_origen_id])
    ubicacion_destino = relationship("Ubicacion", foreign_keys=[ubicacion_destino_id])
    usuario = relationship("Usuario")
    obra = relationship("Obra")


# ============================== AUDITORIA ==============================
class AuditLog(Base):
    __tablename__ = "audit_log"
    id = Column(Integer, primary_key=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=True, index=True)
    fecha = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    accion = Column(String(50), nullable=False)
    entidad = Column(String(50), nullable=False)
    entidad_id = Column(Integer, nullable=True)
    detalle = Column(Text, nullable=True)

    usuario = relationship("Usuario")


# ============================== TPV / PUNTO DE VENTA ==============================
class SesionCaja(Base):
    """Apertura/cierre de caja TPV."""
    __tablename__ = "sesiones_caja"
    id = Column(Integer, primary_key=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=False, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    fecha_apertura = Column(DateTime, default=datetime.utcnow)
    fecha_cierre = Column(DateTime, nullable=True)
    saldo_inicial = Column(Numeric(14, 2), default=0)
    saldo_final_teorico = Column(Numeric(14, 2), default=0)
    saldo_final_real = Column(Numeric(14, 2), nullable=True)
    diferencia = Column(Numeric(14, 2), nullable=True)
    notas = Column(Text, nullable=True)
    cerrada = Column(Boolean, default=False)

    __table_args__ = (
        Index("ix_sesion_caja_empresa_usuario", "empresa_id", "usuario_id"),
    )


class TicketTPV(Base):
    """Venta rápida tipo ticket (TPV)."""
    __tablename__ = "tickets_tpv"
    id = Column(Integer, primary_key=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=False, index=True)
    sesion_caja_id = Column(Integer, ForeignKey("sesiones_caja.id"), nullable=True)
    numero = Column(String(30), nullable=False, index=True)
    fecha = Column(DateTime, default=datetime.utcnow)
    cliente_id = Column(Integer, ForeignKey("terceros.id"), nullable=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    subtotal = Column(Numeric(14, 2), default=0)
    total_iva = Column(Numeric(14, 2), default=0)
    total = Column(Numeric(14, 2), default=0)
    forma_pago = Column(String(30), default="efectivo")  # efectivo, tarjeta, mixto
    entregado = Column(Numeric(14, 2), default=0)  # efectivo entregado por el cliente
    cambio = Column(Numeric(14, 2), default=0)
    notas = Column(Text, nullable=True)

    lineas = relationship("TicketTPVLinea", back_populates="ticket", cascade="all, delete-orphan")
    cliente = relationship("Tercero")
    usuario = relationship("Usuario")
    sesion = relationship("SesionCaja")

    __table_args__ = (
        UniqueConstraint("empresa_id", "numero", name="uq_ticket_empresa_numero"),
    )


class TicketTPVLinea(Base):
    __tablename__ = "tickets_tpv_lineas"
    id = Column(Integer, primary_key=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=False, index=True)
    ticket_id = Column(Integer, ForeignKey("tickets_tpv.id"), nullable=False, index=True)
    producto_id = Column(Integer, ForeignKey("productos.id"), nullable=False)
    cantidad = Column(Float, nullable=False)
    precio = Column(Numeric(12, 4), nullable=False)
    iva = Column(String(4), default="21")
    subtotal = Column(Numeric(14, 2), default=0)

    ticket = relationship("TicketTPV", back_populates="lineas")
    producto = relationship("Producto")


# ============================== TRASPASOS ENTRE UBICACIONES ==============================
class TraspasoStock(Base):
    """Movimiento de stock entre dos ubicaciones (no compra/venta)."""
    __tablename__ = "traspasos_stock"
    id = Column(Integer, primary_key=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=False, index=True)
    numero = Column(String(30), nullable=False, index=True)
    fecha = Column(DateTime, default=datetime.utcnow)
    motivo = Column(String(255), nullable=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    notas = Column(Text, nullable=True)

    lineas = relationship("TraspasoStockLinea", back_populates="traspaso", cascade="all, delete-orphan")
    usuario = relationship("Usuario")

    __table_args__ = (
        UniqueConstraint("empresa_id", "numero", name="uq_traspaso_empresa_numero"),
    )


class TraspasoStockLinea(Base):
    __tablename__ = "traspasos_stock_lineas"
    id = Column(Integer, primary_key=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=False, index=True)
    traspaso_id = Column(Integer, ForeignKey("traspasos_stock.id"), nullable=False, index=True)
    producto_id = Column(Integer, ForeignKey("productos.id"), nullable=False)
    cantidad = Column(Float, nullable=False)
    ubicacion_origen_id = Column(Integer, ForeignKey("ubicaciones.id"), nullable=False)
    ubicacion_destino_id = Column(Integer, ForeignKey("ubicaciones.id"), nullable=False)

    traspaso = relationship("TraspasoStock", back_populates="lineas")
    producto = relationship("Producto")
    ubicacion_origen = relationship("Ubicacion", foreign_keys=[ubicacion_origen_id])
    ubicacion_destino = relationship("Ubicacion", foreign_keys=[ubicacion_destino_id])


# ============================== ALMACENES ==============================
class Almacen(Base):
    """Almacen fisico. Puede contener muchas ubicaciones (pasillo/estanteria/hueco)."""
    __tablename__ = "almacenes"
    id = Column(Integer, primary_key=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=False, index=True)
    codigo = Column(String(20), nullable=False, index=True)
    nombre = Column(String(150), nullable=False)
    direccion = Column(String(255), nullable=True)
    cp = Column(String(10), nullable=True)
    poblacion = Column(String(100), nullable=True)
    provincia = Column(String(100), nullable=True)
    telefono = Column(String(30), nullable=True)
    email = Column(String(120), nullable=True)
    contacto = Column(String(120), nullable=True)
    es_principal = Column(Boolean, default=False)  # almacen por defecto para entradas
    notas = Column(Text, nullable=True)
    activo = Column(Boolean, default=True)
    creado_en = Column(DateTime, default=datetime.utcnow)

    ubicaciones = relationship("Ubicacion", back_populates="almacen")

    __table_args__ = (
        UniqueConstraint("empresa_id", "codigo", name="uq_almacen_empresa_codigo"),
    )


# ============================== TRANSITOS ==============================
class Transito(Base):
    """Mercancia en camino entre dos almacenes.
    Cuando se crea: se decrementa stock del almacen origen.
    Cuando se recibe: se incrementa stock del almacen destino.
    """
    __tablename__ = "transitos"
    id = Column(Integer, primary_key=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=False, index=True)
    numero = Column(String(30), nullable=False, index=True)
    fecha_envio = Column(DateTime, default=datetime.utcnow)
    fecha_recepcion_prevista = Column(DateTime, nullable=True)
    fecha_recepcion_real = Column(DateTime, nullable=True)
    almacen_origen_id = Column(Integer, ForeignKey("almacenes.id"), nullable=False, index=True)
    almacen_destino_id = Column(Integer, ForeignKey("almacenes.id"), nullable=False, index=True)
    transportista = Column(String(150), nullable=True)
    matricula = Column(String(20), nullable=True)
    bultos = Column(Integer, default=0)
    peso_kg = Column(Float, default=0)
    estado = Column(String(20), default="en_transito")  # en_transito, recibido, parcial, cancelado
    motivo = Column(String(255), nullable=True)
    notas = Column(Text, nullable=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)

    almacen_origen = relationship("Almacen", foreign_keys=[almacen_origen_id])
    almacen_destino = relationship("Almacen", foreign_keys=[almacen_destino_id])
    lineas = relationship("TransitoLinea", back_populates="transito", cascade="all, delete-orphan")
    usuario = relationship("Usuario")

    __table_args__ = (
        UniqueConstraint("empresa_id", "numero", name="uq_transito_empresa_numero"),
    )


class TransitoLinea(Base):
    __tablename__ = "transitos_lineas"
    id = Column(Integer, primary_key=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=False, index=True)
    transito_id = Column(Integer, ForeignKey("transitos.id"), nullable=False, index=True)
    producto_id = Column(Integer, ForeignKey("productos.id"), nullable=False)
    cantidad_enviada = Column(Float, nullable=False)
    cantidad_recibida = Column(Float, default=0)
    ubicacion_destino_id = Column(Integer, ForeignKey("ubicaciones.id"), nullable=True)

    transito = relationship("Transito", back_populates="lineas")
    producto = relationship("Producto")
    ubicacion_destino = relationship("Ubicacion")


# ============================== HOJAS DE CARGA Y EXPEDICIONES ==============================
class HojaCarga(Base):
    """Documento de agrupacion para una ruta de expedicion.
    Contiene varias expediciones (cada una = un albaran de salida).
    """
    __tablename__ = "hojas_carga"
    id = Column(Integer, primary_key=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=False, index=True)
    numero = Column(String(30), nullable=False, index=True)
    fecha = Column(Date, default=date.today)
    hora_salida = Column(DateTime, nullable=True)
    transportista = Column(String(150), nullable=True)
    matricula = Column(String(20), nullable=True)
    conductor = Column(String(120), nullable=True)
    ruta = Column(String(255), nullable=True)  # descripcion libre de la ruta
    almacen_origen_id = Column(Integer, ForeignKey("almacenes.id"), nullable=True)
    bultos_total = Column(Integer, default=0)
    peso_kg_total = Column(Float, default=0)
    estado = Column(String(20), default="planificada")  # planificada, en_curso, completada, cancelada
    fecha_completada = Column(DateTime, nullable=True)
    notas = Column(Text, nullable=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)

    almacen = relationship("Almacen")
    expediciones = relationship("Expedicion", back_populates="hoja", cascade="all, delete-orphan")
    usuario = relationship("Usuario")

    __table_args__ = (
        UniqueConstraint("empresa_id", "numero", name="uq_hoja_empresa_numero"),
    )


class Expedicion(Base):
    """Linea de una hoja de carga = un albaran de salida asociado a un orden/cliente.
    """
    __tablename__ = "expediciones"
    id = Column(Integer, primary_key=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=False, index=True)
    hoja_id = Column(Integer, ForeignKey("hojas_carga.id"), nullable=False, index=True)
    albaran_salida_id = Column(Integer, ForeignKey("albaranes_salida.id"), nullable=True)
    orden = Column(Integer, default=0)  # orden de entrega en la ruta
    cliente_id = Column(Integer, ForeignKey("terceros.id"), nullable=True)
    obra_id = Column(Integer, ForeignKey("obras.id"), nullable=True)
    direccion_entrega = Column(String(255), nullable=True)
    poblacion_entrega = Column(String(100), nullable=True)
    cp_entrega = Column(String(10), nullable=True)
    ventana_horaria = Column(String(100), nullable=True)  # "10:00-12:00"
    bultos = Column(Integer, default=0)
    peso_kg = Column(Float, default=0)
    estado = Column(String(20), default="pendiente")  # pendiente, entregado, parcial, incidencia, devuelto
    fecha_entrega = Column(DateTime, nullable=True)
    incidencia = Column(Text, nullable=True)
    notas = Column(Text, nullable=True)

    hoja = relationship("HojaCarga", back_populates="expediciones")
    albaran = relationship("AlbaranSalida")
    cliente = relationship("Tercero")
    obra = relationship("Obra")


# ============================== REGULARIZACION INVENTARIO ==============================
class InventarioFisico(Base):
    """Recuento físico para ajustar stock."""
    __tablename__ = "inventarios_fisicos"
    id = Column(Integer, primary_key=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=False, index=True)
    nombre = Column(String(100), nullable=False)
    fecha = Column(Date, default=date.today)
    estado = Column(String(20), default="abierto")  # abierto, cerrado
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    notas = Column(Text, nullable=True)

    lineas = relationship("InventarioFisicoLinea", back_populates="inventario", cascade="all, delete-orphan")
    usuario = relationship("Usuario")


class InventarioFisicoLinea(Base):
    __tablename__ = "inventarios_fisicos_lineas"
    id = Column(Integer, primary_key=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=False, index=True)
    inventario_id = Column(Integer, ForeignKey("inventarios_fisicos.id"), nullable=False, index=True)
    producto_id = Column(Integer, ForeignKey("productos.id"), nullable=False)
    ubicacion_id = Column(Integer, ForeignKey("ubicaciones.id"), nullable=True)
    cantidad_sistema = Column(Float, default=0)
    cantidad_contada = Column(Float, default=0)
    diferencia = Column(Float, default=0)

    inventario = relationship("InventarioFisico", back_populates="lineas")
    producto = relationship("Producto")
    ubicacion = relationship("Ubicacion")