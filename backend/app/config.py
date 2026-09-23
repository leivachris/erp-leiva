"""Configuracion central del ERP LEIVA.

Lee de variables de entorno con defaults sensatos para escritorio/LAN.
"""
from pathlib import Path
import os

# Raiz del proyecto (3 niveles arriba: backend/app/config.py -> backend/app -> backend -> raiz)
ROOT_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.environ.get("ERP_DATA_DIR", ROOT_DIR / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Base de datos SQLite (un solo fichero para backup facil)
DATABASE_URL = os.environ.get("ERP_DATABASE_URL", f"sqlite:///{DATA_DIR / 'erp.db'}")

# Secret para firmar cookies de sesion (CAMBIAR en produccion)
SECRET_KEY = os.environ.get("ERP_SECRET_KEY", "cambia-esto-en-produccion-leiva-2026")

# Host/puerto del servidor web
HOST = os.environ.get("ERP_HOST", "0.0.0.0")
PORT = int(os.environ.get("ERP_PORT", "8000"))

# Empresa
EMPRESA_NOMBRE = os.environ.get("ERP_EMPRESA_NOMBRE", "Centro Logístico de Almacenes")
EMPRESA_CIF = os.environ.get("ERP_EMPRESA_CIF", "")

# Sesion: duracion en segundos (8h)
SESSION_MAX_AGE = 8 * 3600

# Logging basico
LOG_LEVEL = os.environ.get("ERP_LOG_LEVEL", "INFO")