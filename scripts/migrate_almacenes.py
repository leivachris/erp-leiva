"""Migracion: crea tablas nuevas (almacenes, transitos, hojas_carga, expediciones)
y añade columna almacen_id a ubicaciones.

Idempotente: comprueba que cada cambio ya está hecho antes de aplicarlo.
"""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sqlalchemy import inspect, text
from backend.app.database import engine as db_engine, SessionLocal
from backend.app.models import (
    Base, Almacen, Transito, TransitoLinea, HojaCarga, Expedicion,
    Ubicacion,
)


def tiene_columna(tabla, columna):
    insp = inspect(db_engine)
    cols = [c['name'] for c in insp.get_columns(tabla)]
    return columna in cols


def tiene_tabla(tabla):
    insp = inspect(db_engine)
    return tabla in insp.get_table_names()


def main():
    print("=== Iniciando migracion ===")

    # 1. Crear tablas nuevas (las que no existan)
    tablas_nuevas = [Almacen, Transito, TransitoLinea, HojaCarga, Expedicion]
    for modelo in tablas_nuevas:
        nombre = modelo.__tablename__
        if tiene_tabla(nombre):
            print(f"  [skip] tabla '{nombre}' ya existe")
        else:
            print(f"  [+] creando tabla '{nombre}'")
            modelo.__table__.create(db_engine, checkfirst=True)

    # 2. Anadir columna almacen_id a ubicaciones (si no existe)
    if tiene_columna('ubicaciones', 'almacen_id'):
        print("  [skip] columna ubicaciones.almacen_id ya existe")
    else:
        print("  [+] anadiendo columna ubicaciones.almacen_id")
        with db_engine.begin() as conn:
            conn.execute(text("ALTER TABLE ubicaciones ADD COLUMN almacen_id INTEGER REFERENCES almacenes(id)"))
        # Crear almacen por defecto y asignarlo a todas las ubicaciones existentes
        db = SessionLocal()
        try:
            almacen_principal = db.query(Almacen).filter(
                Almacen.empresa_id == 1, Almacen.codigo == 'PRINCIPAL'
            ).first()
            if not almacen_principal:
                # leer primera empresa
                from backend.app.models import Empresa
                emp = db.query(Empresa).first()
                if emp:
                    almacen_principal = Almacen(
                        empresa_id=emp.id,
                        codigo='PRINCIPAL',
                        nombre='Almacen Principal',
                        es_principal=True,
                    )
                    db.add(almacen_principal)
                    db.commit()
                    print(f"  [+] creado almacen PRINCIPAL para empresa {emp.id}")

            if almacen_principal:
                with db_engine.begin() as conn:
                    conn.execute(text(
                        "UPDATE ubicaciones SET almacen_id = :aid WHERE almacen_id IS NULL"
                    ), {"aid": almacen_principal.id})
                print(f"  [+] ubicaciones existentes asignadas a almacen {almacen_principal.id}")
        finally:
            db.close()

    print("=== Migracion completada ===")


if __name__ == "__main__":
    main()