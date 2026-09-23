#!/usr/bin/env bash
# ============================================================
# ERP LEIVA - Despliegue automatico en Unraid
# ============================================================
# USO (como root en Unraid):
#   bash deploy_unraid.sh
#
# Que hace:
#   1. Crea las carpetas persistentes en /mnt/user/appdata/erpleiva
#   2. Genera un ERP_SECRET_KEY aleatorio de 64 caracteres
#   3. Crea el fichero .env con la clave
#   4. Construye la imagen Docker
#   5. Arranca el contenedor (restart: unless-stopped = 24/7)
# ============================================================

set -e

# Colores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() { echo -e "${GREEN}[deploy]${NC} $1"; }
warn() { echo -e "${YELLOW}[deploy]${NC} $1"; }
err() { echo -e "${RED}[deploy]${NC} $1"; }

# Verificar que estamos en Unraid
if [ ! -d "/mnt/user" ]; then
    err "Este script es para Unraid. /mnt/user no existe."
    exit 1
fi

# Verificar Docker
if ! command -v docker &> /dev/null; then
    err "Docker no esta instalado. Instala el plugin Community Applications primero."
    exit 1
fi

# Detectar directorio del proyecto
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$( dirname "$SCRIPT_DIR" )"
log "Proyecto en: $PROJECT_DIR"

# 1. Crear carpetas persistentes
log "Creando carpetas persistentes en /mnt/user/appdata/erpleiva..."
mkdir -p /mnt/user/appdata/erpleiva/logs
chmod -R 777 /mnt/user/appdata/erpleiva

# 2. Generar o leer ERP_SECRET_KEY
ENV_FILE="$PROJECT_DIR/.env"
if [ -f "$ENV_FILE" ]; then
    warn ".env ya existe. Reutilizando ERP_SECRET_KEY actual."
    source "$ENV_FILE"
fi

if [ -z "${ERP_SECRET_KEY:-}" ]; then
    ERP_SECRET_KEY=$(head -c 48 /dev/urandom | base64 | tr -d '/+=' | cut -c1-64)
    log "Generada nueva ERP_SECRET_KEY"
    cat > "$ENV_FILE" <<EOF
ERP_SECRET_KEY=$ERP_SECRET_KEY
ERP_EMPRESA_NOMBRE=Centro Logistico de Almacenes
TZ=Europe/Madrid
EOF
    log ".env creado en $ENV_FILE"
fi

# 3. Construir imagen
log "Construyendo imagen Docker (puede tardar 3-5 minutos la primera vez)..."
cd "$PROJECT_DIR"
docker build -t erp-leiva:latest . 2>&1 | tail -20

# 4. Detener contenedor existente si existe
if docker ps -a --format '{{.Names}}' | grep -q '^erp-leiva$'; then
    warn "Contenedor existente detectado. Deteniendo..."
    docker stop erp-leiva 2>/dev/null || true
    docker rm erp-leiva 2>/dev/null || true
fi

# 5. Arrancar con docker compose
log "Arrancando contenedor..."
docker compose up -d

# 6. Esperar a que arranque
log "Esperando a que el servidor este listo..."
for i in {1..30}; do
    if curl -fs http://localhost:8000/api/health > /dev/null 2>&1; then
        log "Servidor respondiendo ✓"
        break
    fi
    sleep 2
done

# 7. Verificar
if curl -fs http://localhost:8000/api/health > /dev/null 2>&1; then
    IP=$(ip route | grep default | awk '{print $9}' | head -1)
    echo ""
    echo "================================================================="
    echo "  ERP LEIVA 24/7 DESPLEGADO EN UNRAID"
    echo "================================================================="
    echo ""
    echo "  Local:    http://localhost:8000"
    echo "  LAN:      http://${IP}:8000"
    echo ""
    echo "  Auto-restart: ACTIVO (restart: unless-stopped)"
    echo "  Supervivencia: reinicios del sistema OK, caidas supervisado"
    echo "  Healthcheck:    cada 30s, docker reinicia si falla"
    echo ""
    echo "  Comandos utiles:"
    echo "    Ver logs:      docker logs -f erp-leiva"
    echo "    Estado:        docker ps | grep erp"
    echo "    Parar:         docker stop erp-leiva"
    echo "    Arrancar:      docker start erp-leiva"
    echo "    Actualizar:    cd $PROJECT_DIR && git pull && docker compose build && docker compose up -d"
    echo "    Backup BD:     docker cp erp-leiva:/data/erp.db ./erp-backup.db"
    echo ""
    echo "  Primera vez: abre http://${IP}:8000 y completa la instalacion."
else
    err "El servidor no responde. Revisa los logs:"
    docker logs erp-leiva --tail 50
    exit 1
fi