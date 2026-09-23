# ERP LEIVA en Unraid

## Opción A: Modo SaaS (recomendado para tu Unraid casero)

Tu Unraid casero en `192.168.1.100` es perfecto para correr el ERP 24/7 y
acceder desde cualquier sitio vía Cloudflare Tunnel (gratis).

### 1. Copiar el proyecto a Unraid

```bash
# Desde tu PC Windows
scp -r "C:\Users\leiva\Documents\ERP LEIVA" root@192.168.1.100:/mnt/user/appdata/erp-leiva-src/
```

(En tu memoria de Unraid: CT2000 nvme1n1 es el cache pool, donde ya corre
docker.img. NO uses /mnt/disk1 (SPCC array) para datos.)

### 2. Crear el directorio de datos persistente

```bash
ssh root@192.168.1.100
mkdir -p /mnt/user/appdata/erpleiva
```

### 3. Arrancar con docker compose

```bash
cd /mnt/user/appdata/erp-leiva-src
docker compose up -d
docker compose logs -f
```

Verás:
```
erp-leiva arrancando en http://0.0.0.0:8000
```

### 4. Probar desde la LAN

Abre en el navegador de cualquier dispositivo:
- http://192.168.1.100:8000

### 5. Exponer a Internet (Cloudflare Tunnel)

Para que tus clientes accedan desde fuera sin abrir puertos:

```bash
# En Unraid (como root)
docker run -d --name cloudflared \
  --restart unless-stopped \
  -v /mnt/user/appdata/cloudflared:/home/nonroot/.cloudflared \
  cloudflare/cloudflared:latest \
  tunnel --no-autoupdate run <TUNNEL_TOKEN>
```

Creas un tunnel en https://one.dash.cloudflare.com → te da el token.
Apuntas `erp.tudominio.com` → `http://erpleiva:8000`.

**Ventaja**: Cloudflare Tunnel es gratis, no abre puertos en el router, y
Cloudflare cachea + protege contra DDoS.

---

## Opción B: Modo instalable Windows (para vender a clientes)

Cuando un cliente compra el ERP, le envías un `.exe` que incluye todo.
Lo empaquetas UNA vez en tu PC Windows y lo distribuyes:

```powershell
cd "C:\Users\leiva\Documents\ERP LEIVA"
pip install pyinstaller
pyinstaller --onefile --windowed `
  --add-data "frontend;frontend" `
  --add-data "backend;backend" `
  --add-data "scripts;scripts" `
  --name "ERP-LEIVA" `
  run.py
```

El `.exe` queda en `dist/ERP-LEIVA.exe`. Es un solo fichero que el cliente
ejecuta. Al arrancar le abre el navegador automáticamente en
`http://localhost:8000`.

---

## Opción C: Instalar manualmente en Unraid sin Docker

```bash
ssh root@192.168.1.100

# Instalar Python 3.11
docker run --rm -it python:3.11-slim bash -c "echo ok"
# (Usar contenedor de Python como "runtime" sin Docker para el ERP)

# O instalar python3 directamente
apt-get update && apt-get install -y python3 python3-pip python3-venv
# (Requiere Slug de comunidad en Unraid: NerdPack o python3 de la comunidad)

# Crear venv
python3 -m venv /opt/erp-leiva
cd /opt/erp-leiva
git clone <tu-repo> .
source bin/activate
pip install -r requirements.txt
nohup python run.py > /var/log/erp-leiva.log 2>&1 &
```

---

## ¿Cuál elegir?

| Caso | Recomendación |
|------|--------------|
| Eres tú quien lo va a usar (1 cliente) | **C**: instala en Unraid manualmente |
| Quieres vender a 1-5 clientes pequeños | **B**: `.exe` instalable |
| Quieres vender a muchos clientes y cobrar mensual | **A**: SaaS en Unraid + Cloudflare |

Mi recomendación para tu caso actual: **empieza con C** (instalar en Unraid
manualmente con Python + venv). Funciona igual que en tu PC Windows pero
24/7. Cuando vayas a vender, montas **B** y/o **A**.