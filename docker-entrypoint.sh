#!/usr/bin/env bash
# Entrypoint del contenedor ERP LEIVA.
# - Aplica migraciones pendientes
# - Carga planes predefinidos si no existen
# - Arranca el servidor
set -e

echo "[entrypoint] Iniciando ERP LEIVA..."
echo "[entrypoint] ERP_DATA_DIR=${ERP_DATA_DIR:-/data}"

# 1. Migracion idempotente de BD
echo "[entrypoint] Aplicando migraciones..."
python scripts/migrate_almacenes.py 2>&1 | sed 's/^/[migrate] /'

# 2. Sembrar planes si no existen
echo "[entrypoint] Cargando planes predefinidos..."
python scripts/seed.py 2>&1 | sed 's/^/[seed] /' || true

# 3. Si existe ERP_SECRETS_FILE (Unraid template), aplicar permisos
if [ -n "${ERP_SECRET_KEY:-}" ]; then
  echo "[entrypoint] ERP_SECRET_KEY detectado (longitud ${#ERP_SECRET_KEY})"
fi

# 4. Arrancar el servidor (CMD)
echo "[entrypoint] Arrancando servidor..."
exec "$@"