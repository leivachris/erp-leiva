#!/usr/bin/env bash
# ============================================================
# Cloudflare Tunnel - setup automatico
# ============================================================
# USO:
#   bash scripts/setup_cloudflared.sh TUNNEL_TOKEN_HERE
#
# Pasos previos:
#   1. https://one.dash.cloudflare.com -> Zero Trust -> Networks -> Tunnels
#   2. Create a tunnel -> nombre "erpleiva"
#   3. Copiar el token (largo, empieza por eyJh...)
#   4. Crear un public hostname:
#      - Subdomain: erp
#      - Domain: tudominio.com
#      - Service: http://erp:8000
#   5. Ejecutar este script con el token
# ============================================================

set -e

TOKEN="${1:-}"
if [ -z "$TOKEN" ]; then
    echo "USO: bash $0 TUNNEL_TOKEN"
    echo ""
    echo "Obtener token en:"
    echo "  https://one.dash.cloudflare.com -> Zero Trust -> Networks -> Tunnels"
    exit 1
fi

APPDATA="/mnt/user/appdata/erpleiva"
mkdir -p "$APPDATA/cloudflared"

# Crear .env si no existe con el token
ENV="$APPDATA/.env.shared"
if ! grep -q "^TUNNEL_TOKEN=" "$ENV" 2>/dev/null; then
    echo "TUNNEL_TOKEN=$TOKEN" >> "$ENV"
    echo "Anadido TUNNEL_TOKEN a $ENV"
else
    sed -i "s|^TUNNEL_TOKEN=.*|TUNNEL_TOKEN=$TOKEN|" "$ENV"
    echo "Actualizado TUNNEL_TOKEN en $ENV"
fi

echo ""
echo "Cloudflare Tunnel configurado."
echo "Verifica en: https://one.dash.cloudflare.com -> Zero Trust -> Tunnels"
echo "El contenedor erp-cloudflared se reinicia automaticamente con la nueva config."