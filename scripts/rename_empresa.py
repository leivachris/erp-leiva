"""Renombra la empresa en la BD."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.app.database import SessionLocal
from backend.app.models import Empresa

NUEVO_NOMBRE = "Centro Logístico de Almacenes"

db = SessionLocal()
try:
    e = db.query(Empresa).first()
    if not e:
        print('ERROR: no hay empresa')
        sys.exit(1)
    print(f'Antes: {e.nombre!r}')
    e.nombre = NUEVO_NOMBRE
    e.nombre_comercial = NUEVO_NOMBRE
    db.commit()
    print(f'Despues: {e.nombre!r}')
finally:
    db.close()