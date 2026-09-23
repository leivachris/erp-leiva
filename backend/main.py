"""FastAPI app principal del ERP LEIVA.

Entry point: uvicorn backend.main:app
"""
import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .config import HOST, PORT, LOG_LEVEL, EMPRESA_NOMBRE
from .database import init_db
from .routers import (
    auth, productos, ubicaciones, terceros, albaranes,
    facturacion, tesoreria, dashboard, instalacion, empresas,
    tpv, traspasos, inventario, importar,
)

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("erp")


# ============ APP ============
app = FastAPI(
    title="ERP LEIVA",
    description="ERP para almacenes y construcción. Multi-tenant, instalable o cloud.",
    version="0.1.0",
    docs_url="/api/docs" if __import__("os").environ.get("ERP_ENV") != "production" else None,
    redoc_url=None,
)


# CORS para LAN y desarrollo
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # en produccion restringir
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============ EXCEPTION HANDLERS ============
@app.exception_handler(401)
async def unauthorized(request: Request, exc):
    if request.url.path.startswith("/api/"):
        return JSONResponse({"detail": exc.detail}, status_code=401)
    # Para rutas no-API, servir el frontend (SPA fallback)
    return FileResponse(_frontend_index())


@app.exception_handler(403)
async def forbidden(request: Request, exc):
    return JSONResponse({"detail": exc.detail}, status_code=403)


@app.exception_handler(404)
async def not_found(request: Request, exc):
    if request.url.path.startswith("/api/"):
        return JSONResponse({"detail": exc.detail}, status_code=404)
    return FileResponse(_frontend_index())


def _frontend_index():
    root = Path(__file__).resolve().parents[1]
    return root / "frontend" / "index.html"


# ============ ROUTERS ============
app.include_router(auth.router)
app.include_router(instalacion.router)
app.include_router(empresas.router)
app.include_router(productos.router)
app.include_router(ubicaciones.router)
app.include_router(terceros.router)
app.include_router(albaranes.router)
app.include_router(facturacion.router)
app.include_router(tesoreria.router)
app.include_router(dashboard.router)
app.include_router(tpv.router)
app.include_router(traspasos.router)
app.include_router(inventario.router)
app.include_router(importar.router)


# ============ STARTUP ============
@app.on_event("startup")
def startup_event():
    init_db()
    log.info(f"ERP LEIVA arrancando en http://{HOST}:{PORT}")
    log.info(f"Empresa por defecto: {EMPRESA_NOMBRE}")


@app.get("/api/health")
def health():
    return {"status": "ok", "version": app.version}


# ============ STATIC + SPA ============
_FRONTEND = Path(__file__).resolve().parents[1] / "frontend"
if _FRONTEND.exists():
    app.mount("/static", StaticFiles(directory=_FRONTEND / "static"), name="static")

    @app.get("/")
    def root():
        return FileResponse(_FRONTEND / "index.html")

    @app.get("/{full_path:path}")
    def spa(full_path: str):
        # Primero intentar servir un fichero estático
        target = _FRONTEND / full_path
        if target.is_file():
            return FileResponse(target)
        # SPA fallback al index
        return FileResponse(_FRONTEND / "index.html")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host=HOST, port=PORT, reload=False)