"""Script de arranque del ERP LEIVA.

Uso:
  python run.py                 # arranca en 0.0.0.0:8000
  python run.py --port 9000     # puerto custom
  python run.py --host 127.0.0.1 # solo localhost
  python run.py --seed          # instala planes y datos demo
  python run.py --reset         # borra BD antes de arrancar
"""
import argparse
import sys
from pathlib import Path

# Raiz del proyecto: anade para que `backend` sea importable como paquete
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser(description="ERP LEIVA - servidor")
    parser.add_argument("--host", default="0.0.0.0", help="Host (default 0.0.0.0 para LAN)")
    parser.add_argument("--port", type=int, default=8000, help="Puerto (default 8000)")
    parser.add_argument("--seed", action="store_true", help="Cargar planes y datos demo")
    parser.add_argument("--reset", action="store_true", help="Borrar BD y empezar de cero")
    parser.add_argument("--reload", action="store_true", help="Hot-reload (desarrollo)")
    args = parser.parse_args()

    if args.reset:
        from backend.app.config import DATA_DIR
        bd = DATA_DIR / "erp.db"
        if bd.exists():
            bd.unlink()
            print(f"BD borrada: {bd}")

    if args.seed:
        from scripts.seed import seed_inicial
        seed_inicial(verbose=True)
        print("Seed cargado: planes y datos demo.")
        if "--seed" in sys.argv and len(sys.argv) <= 3:
            return

    import uvicorn
    from backend.app.config import EMPRESA_NOMBRE
    print(f"""
+----------------------------------------------------------+
|                  ERP LEIVA v0.1.0                        |
+----------------------------------------------------------+
|  Servidor:    http://{args.host}:{args.port}
|  Frontend:    http://{args.host}:{args.port}/
|  API docs:    http://{args.host}:{args.port}/api/docs
|  Empresa:     {EMPRESA_NOMBRE}
+----------------------------------------------------------+
Primera vez? Abre el frontend y completa la instalacion.
""")
    # Pasar el objeto app directamente (evita problemas de import string)
    from backend.app.main import app as fastapi_app
    uvicorn.run(
        fastapi_app,
        host=args.host, port=args.port,
        reload=args.reload,
        log_level="info",
    )


if __name__ == "__main__":
    main()