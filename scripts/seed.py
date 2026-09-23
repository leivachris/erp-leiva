"""Seed inicial: crea planes predefinidos y datos demo para una empresa demo.

Uso:
  python scripts/seed.py
o desde run.py con --seed

Crea:
  - 3 planes (Basico, Pro, Empresa) si no existen
  - Si no hay empresa, NO crea ninguna (lo hara el usuario via /api/instalacion/setup)
  - Si existe empresa y esta vacia, añade datos demo
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
# Tambien el subdir backend por si se ejecuta con `python scripts/seed.py`
sys.path.insert(0, str(ROOT / "backend"))


def seed_inicial(verbose: bool = False):
    from backend.app.database import init_db, SessionLocal
    from backend.app.models import (
        Plan, Empresa, Usuario, Familia, Producto, Tercero,
        Ubicacion, Stock, CuentaBancaria,
    )
    from backend.app.security import hash_password
    from backend.app.plans import planes_default

    init_db()
    db = SessionLocal()
    try:
        # 1. Planes
        for p in planes_default():
            existe = db.query(Plan).filter(Plan.codigo == p["codigo"]).first()
            if not existe:
                db.add(Plan(**p))
                if verbose: print(f"  + Plan {p['codigo']}: {p['nombre']}")
        db.commit()

        # 2. Si no hay empresa, parar
        empresa = db.query(Empresa).first()
        if not empresa:
            if verbose:
                print("No hay empresa. El usuario debe completar /api/instalacion/setup primero.")
            return

        # 3. Datos demo (solo si la empresa esta vacia)
        if db.query(Producto).filter(Producto.empresa_id == empresa.id).count() > 0:
            if verbose: print("Empresa ya tiene productos; no se hace seed demo.")
            return

        # Familias
        fams = [
            ("CEM", "Cementos y morteros"),
            ("LAD", "Ladrillos y bloques"),
            ("ACE", "Acero y ferralla"),
            ("SAN", "Sanitarios y fontanaria"),
            ("PIN", "Pinturas y disolventes"),
            ("MAD", "Maderas"),
            ("AIS", "Aislamientos"),
            ("HER", "Herramientas"),
        ]
        fams_db = {}
        for cod, nom in fams:
            f = Familia(empresa_id=empresa.id, codigo=cod, nombre=nom)
            db.add(f); db.flush()
            fams_db[cod] = f.id

        # Productos demo (orientado a almacen de obra)
        productos_demo = [
            ("CEM001", "Cemento Portland CEM II 32.5", "CEM", 8.50, 12.00, "21", 100, 500, "ud", 25),
            ("CEM002", "Mortero de agarre M-7.5", "CEM", 6.20, 9.50, "21", 50, 300, "saco", 25),
            ("CEM003", "Yeso manual", "CEM", 4.10, 7.00, "21", 30, 200, "saco", 17),
            ("LAD001", "Ladrillo hueco doble 24x11.5x9", "LAD", 0.18, 0.28, "21", 5000, 20000, "ud", 1.8),
            ("LAD002", "Bloque hormigon 40x20x20", "LAD", 0.85, 1.35, "21", 500, 3000, "ud", 16),
            ("LAD003", "Tabique ceramico 30x19", "LAD", 0.72, 1.10, "21", 800, 5000, "ud", 8.5),
            ("ACE001", "Corrugado B 500 S diam. 12 mm", "ACE", 1.45, 2.20, "21", 200, 1000, "kg", 1),
            ("ACE002", "Malla electrosoldada 15x15 diam. 6", "ACE", 2.80, 4.50, "21", 50, 200, "m2", 4.2),
            ("ACE003", "Vigueta pretensada T-18", "ACE", 18.50, 26.00, "21", 100, 500, "m", 22),
            ("SAN001", "Inodoro tanque bajo", "SAN", 95.00, 145.00, "21", 5, 20, "ud", 22),
            ("SAN002", "Lavabo pedestal 60cm", "SAN", 62.00, 95.00, "21", 5, 20, "ud", 18),
            ("SAN003", "Plato ducha 80x80", "SAN", 78.00, 119.00, "21", 5, 15, "ud", 25),
            ("PIN001", "Pintura plastica blanca 15L", "PIN", 38.00, 58.00, "21", 10, 50, "ud", 22),
            ("PIN002", "Esmalte sintetico brillante 4L", "PIN", 22.50, 34.00, "21", 15, 60, "ud", 5),
            ("MAD001", "Tablero contrachapado 244x122x18", "MAD", 32.00, 48.00, "21", 20, 80, "ud", 28),
            ("MAD002", "Liston pino 50x25x2400mm", "MAD", 1.80, 2.85, "21", 100, 500, "ud", 0.8),
            ("AIS001", "Poliestireno expandido 1m2 40mm", "AIS", 3.20, 4.90, "21", 50, 200, "m2", 1.2),
            ("AIS002", "Lana de roca 1.20x0.60 50mm", "AIS", 4.80, 7.30, "21", 40, 150, "m2", 1.8),
            ("HER001", "Martillo carpintero 500g", "HER", 11.50, 18.00, "21", 10, 50, "ud", 0.7),
            ("HER002", "Saco escombros rafia 100L", "HER", 0.85, 1.30, "21", 200, 1000, "ud", 0.4),
        ]
        for sku, nombre, fam, pc, pv, iva, smin, smax, unidad, peso in productos_demo:
            p = Producto(
                empresa_id=empresa.id, sku=sku, nombre=nombre,
                familia_id=fams_db.get(fam), unidad_stock=unidad,
                unidad_compra=unidad, unidad_venta=unidad,
                precio_compra=pc, precio_venta=pv, iva=iva,
                stock_minimo=smin, stock_maximo=smax,
                peso_kg=peso,
                # Stock inicial aleatorio entre min y max/2
                stock_actual=smin + ((smax - smin) // 3),
            )
            db.add(p)
            if verbose: print(f"  + Producto {sku}: {nombre}")

        # Ubicaciones
        ubicaciones_demo = [
            ("A-01-01", "A", "01", "01", "0", 1000, 5),
            ("A-01-02", "A", "01", "02", "0", 1000, 5),
            ("A-02-01", "A", "02", "01", "0", 1000, 5),
            ("A-02-02", "A", "02", "02", "0", 1000, 5),
            ("B-01-01", "B", "01", "01", "0", 2000, 10),
            ("B-01-02", "B", "01", "02", "0", 2000, 10),
            ("C-01-01", "C", "01", "01", "0", 500, 2),
            ("EXP-01", "EXP", "01", "01", "0", 0, 50),
        ]
        for cod, p, e, h, n, kg, m3 in ubicaciones_demo:
            db.add(Ubicacion(
                empresa_id=empresa.id, codigo=cod, pasillo=p,
                estanteria=e, hueco=h, nivel=n,
                capacidad_kg=kg, capacidad_m3=m3,
            ))
            if verbose: print(f"  + Ubicación {cod}")

        # Terceros demo
        provs = [
            ("P001", "Cementos del Sur S.L.", "B12345678", "Pol. Ind. Calonge, C/ Hierro 12", "41010", "Sevilla", "954123456", "compras@cemdelsur.es", "transferencia", 30),
            ("P002", "Cerámica Andaluza S.A.", "A41234567", "Ctra. Sevilla-Huelva km 8", "21010", "Huelva", "959654321", "pedidos@ceramicandaluza.es", "transferencia", 60),
            ("P003", "Hierros La Roda", "B23456789", "Pol. Ind. La Roda, nave 5", "02006", "Albacete", "967432109", "ventas@hierroslaroda.es", "talón", 0),
            ("P004", "Fontanería García", "12345678Z", "Av. Andalucía 45", "29006", "Málaga", "952765432", "", "contado", 0),
        ]
        for cod, nom, cif, dir, cp, pob, tel, email, fp, dias in provs:
            t = Tercero(
                empresa_id=empresa.id, tipo="proveedor", codigo=cod, nombre=nom,
                cif_nif=cif, direccion=dir, cp=cp, poblacion=pob, telefono=tel,
                email=email, forma_pago=fp, dias_pago=dias,
            )
            db.add(t)
            if verbose: print(f"  + Proveedor {cod}: {nom}")

        clientes = [
            ("C001", "Construcciones Pérez S.L.", "B91234567", "C/ Mayor 23", "28013", "Madrid", "912345678", "info@construperez.es", "transferencia", 60, True, 15.0),
            ("C002", "Reformas García Hnos.", "B56789123", "C/ Sol 8", "41001", "Sevilla", "954321987", "reformas@garciahnos.com", "transferencia", 30, False, 0),
            ("C003", "Particular - Juan López", "45678912X", "Av. Andalucía 102 3A", "29006", "Málaga", "952111222", "", "contado", 0, False, 0),
            ("C004", "Promociones del Sur S.A.", "A12345678", "Ctra. Nacional IV km 532", "41300", "San José de la Rinconada", "955666777", "administracion@promosur.es", "transferencia", 90, True, 15.0),
        ]
        for cod, nom, cif, dir, cp, pob, tel, email, fp, dias, irpf, irpf_pct in clientes:
            t = Tercero(
                empresa_id=empresa.id, tipo="cliente", codigo=cod, nombre=nom,
                cif_nif=cif, direccion=dir, cp=cp, poblacion=pob, telefono=tel,
                email=email, forma_pago=fp, dias_pago=dias,
                aplica_irpf=irpf, irpf_porcentaje=irpf_pct,
            )
            db.add(t)
            if verbose: print(f"  + Cliente {cod}: {nom}")

        # Cuentas bancarias
        cuentas = [
            ("Caja", "ES0000000000000000000000", 0),
            ("Banco Santander", "ES9121000418450200051332", 0),
        ]
        for nombre, iban, saldo in cuentas:
            c = CuentaBancaria(
                empresa_id=empresa.id, nombre=nombre, iban=iban,
                banco=nombre, saldo_inicial=saldo, saldo_actual=saldo,
            )
            db.add(c)
            if verbose: print(f"  + Cuenta {nombre}")

        db.commit()
        if verbose: print("Seed demo completado.")
    finally:
        db.close()


if __name__ == "__main__":
    seed_inicial(verbose=True)