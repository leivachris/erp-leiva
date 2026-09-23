"""Promote leiva to rol=root (super-admin)."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.app.database import SessionLocal
from backend.app.models import Usuario

db = SessionLocal()
try:
    u = db.query(Usuario).filter(Usuario.username == 'leiva').first()
    if not u:
        print('ERROR: usuario leiva no existe')
        sys.exit(1)
    u.rol = 'root'
    db.commit()
    print(f'OK: usuario {u.username} ahora tiene rol = {u.rol}')
finally:
    db.close()