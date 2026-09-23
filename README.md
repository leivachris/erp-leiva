# ERP LEIVA

ERP multi-tenant para almacenes de construcción. **Inspirado en BigTech ERP**
(interfaz MDI, densa, con atajos de teclado).

Pensado para venderse en **dos modos**:
- **Instalable Windows** (cliente descarga un `.exe` con todo incluido)
- **SaaS en tu servidor** (clientes acceden por web, cobras suscripción mensual)

## Características principales

### Plan Básico (29 €/mes)
- Inventario + ubicaciones
- Ventas / albaranes
- Gestión de obras
- 2 usuarios, 500 productos, 1 almacén

### Plan Profesional (59 €/mes) — el más vendido
- Todo lo del Básico
- Compras + facturación (cliente y proveedor)
- Tesorería y conciliación
- IRPF + recargo de equivalencia
- Multi-almacén
- 5 usuarios, 5 000 productos, 2 000 docs/mes

### Plan Empresa (119 €/mes)
- Todo lo del Profesional
- Roles personalizados
- Marca blanca
- API externa
- Soporte prioritario
- Sin límites

## Stack técnico

| Capa | Tecnología |
|------|------------|
| Backend | Python 3.10+ / FastAPI |
| Base de datos | SQLite (incluida) o PostgreSQL (SaaS) |
| Frontend | HTML + CSS + JS vanilla (sin frameworks, sin build) |
| Auth | Cookie firmada con `itsdangerous` |
| Numeración | Serie+año+secuencia (estilo español: `FC26001`) |
| Despliegue | `python run.py` o PyInstaller para `.exe` |

## Estructura del proyecto

```
ERP LEIVA/
├── backend/
│   ├── app/
│   │   ├── main.py            # FastAPI app
│   │   ├── models.py          # SQLAlchemy (multi-tenant)
│   │   ├── schemas.py         # Pydantic
│   │   ├── security.py        # Auth + audit
│   │   ├── tenancy.py         # Multi-tenant helpers
│   │   ├── plans.py           # Features por plan
│   │   ├── database.py        # SQLAlchemy setup
│   │   ├── config.py          # Config (env vars)
│   │   ├── routers/
│   │   │   ├── auth.py
│   │   │   ├── instalacion.py
│   │   │   ├── empresas.py
│   │   │   ├── productos.py
│   │   │   ├── ubicaciones.py
│   │   │   ├── terceros.py
│   │   │   ├── albaranes.py
│   │   │   ├── facturacion.py
│   │   │   ├── tesoreria.py
│   │   │   ├── tpv.py
│   │   │   ├── traspasos.py
│   │   │   ├── inventario.py
│   │   │   ├── importar.py
│   │   │   └── dashboard.py
│   │   └── services/
│   │       ├── numeracion.py
│   │       └── totales.py
│   └── main.py
├── frontend/
│   ├── index.html
│   └── static/
│       ├── css/style.css      # Estilo BigTech (gris azulado, denso)
│       └── js/
│           ├── api.js
│           └── app.js
├── scripts/
│   └── seed.py                # Datos demo
├── data/
│   └── erp.db                 # BD SQLite (se crea al arrancar)
├── run.py                     # Script de arranque
├── requirements.txt
└── README.md
```

## Instalación rápida (desarrollo)

```bash
# 1. Instalar dependencias
pip install -r requirements.txt

# 2. Cargar planes predefinidos (sin empresa, solo planes)
python scripts/seed.py

# 3. Arrancar el servidor
python run.py

# 4. Abrir en el navegador
# http://localhost:8000
# Primera vez: te lleva a la pantalla de instalación.
```

Una vez completada la instalación, accedes con tu usuario admin.

## Primera vez — pantalla de instalación

1. Rellena datos de la empresa
2. Elige plan (Básico / Pro / Empresa)
3. Crea el usuario admin
4. El sistema crea la primera empresa + suscripción de prueba (30 días)

## Modo SaaS

Para desplegar en la nube:

```bash
# Detrás de nginx/cloudflare como proxy inverso
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --workers 4
```

Variables de entorno:

| Variable | Default | Descripción |
|----------|---------|-------------|
| `ERP_DATA_DIR` | `data/` | Carpeta de la BD |
| `ERP_DATABASE_URL` | `sqlite:///data/erp.db` | URL de conexión BD |
| `ERP_SECRET_KEY` | — | Clave de firma de cookies (CAMBIAR en prod) |
| `ERP_HOST` | `0.0.0.0` | Host del servidor |
| `ERP_PORT` | `8000` | Puerto |
| `ERP_EMPRESA_NOMBRE` | `Almacén LEIVA` | Nombre por defecto |

## Modo instalable Windows

Para empaquetar como `.exe`:

```bash
pip install pyinstaller
pyinstaller --onefile --windowed --add-data "frontend;frontend" --name "ERP-LEIVA" run.py
```

El `.exe` resultante en `dist/` lleva todo incluido (BD SQLite local).

## Atajos de teclado (estilo BigTech)

- **F2** = Editar seleccionado
- **F4** = Nuevo registro
- **F5** = Actualizar vista
- **F9** = Guardar formulario
- **Esc** = Cancelar / cerrar modal
- **Ctrl + B** = Búsqueda global

## Migración desde otro ERP

El módulo **Importar CSV** (en el menú lateral) permite cargar:
- Productos (columnas: `sku, nombre, familia, precio_compra, precio_venta, iva, ...`)
- Clientes / proveedores (columnas: `codigo, nombre, cif, direccion, ...`)

Codificación: UTF-8 con o sin BOM. Separador: `;` (configurable).

## Licencia

Copyright © 2026. Software propietario. Todos los derechos reservados.