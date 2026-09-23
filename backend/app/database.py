"""Setup de SQLAlchemy + sesion por request."""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import StaticPool

from .config import DATABASE_URL

# SQLite: check_same_thread=False para FastAPI; StaticPool para evitar problemas con hilos
engine_kwargs = {"connect_args": {"check_same_thread": False}, "poolclass": StaticPool}

engine = create_engine(DATABASE_URL, **engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """Generador de sesion para dependencia de FastAPI."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Crea todas las tablas. Llamar al arrancar."""
    # Importar modelos para que se registren en Base.metadata
    from . import models  # noqa: F401
    Base.metadata.create_all(bind=engine)