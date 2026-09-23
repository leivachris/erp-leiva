FROM python:3.11-slim

LABEL maintainer="ERP LEIVA"
LABEL description="ERP multi-tenant para almacenes y construccion. Modo SaaS o instalable."

WORKDIR /app

# Dependencias del sistema: curl para healthcheck, tini para senales correctas
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    tini \
    && rm -rf /var/lib/apt/lists/*

# Crear usuario no-root para seguridad
RUN groupadd --system --gid 1000 erp && \
    useradd --system --uid 1000 --gid erp --no-create-home --shell /sbin/nologin erp

# Dependencias Python
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Codigo fuente
COPY backend/ ./backend/
COPY frontend/ ./frontend/
COPY scripts/ ./scripts/
COPY run.py ./
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# Datos persistentes
ENV ERP_DATA_DIR=/data
RUN mkdir -p /data && chown -R erp:erp /data
VOLUME ["/data"]

# Permisos no-root
RUN chown -R erp:erp /app

USER erp

EXPOSE 8000

# Healthcheck
HEALTHCHECK --interval=30s --timeout=5s --retries=3 --start-period=15s \
    CMD curl -fs http://localhost:8000/api/health || exit 1

# tini para propagar senales correctamente (SIGTERM, etc.)
ENTRYPOINT ["/usr/bin/tini", "--", "/usr/local/bin/docker-entrypoint.sh"]

CMD ["python", "run.py"]