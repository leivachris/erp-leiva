# ERP LEIVA en Unraid — Guía paso a paso

## Resumen

Tu Unraid casero (CT2000 cache pool, IP 192.168.1.100) tiene potencia más que
suficiente para correr este ERP 24/7 y servir a 5-10 clientes pequeños.

Hay **dos métodos**:
- **A. Docker (recomendado)**: 5 minutos, contenedor aislado, fácil de actualizar
- **B. Nativo**: instalar Python manualmente, útil si tienes problemas con Docker

---

## Método A: Docker (recomendado)

### Pre-requisitos en Unraid

- Unraid 6.11+ con Community Applications instalado
- Al menos 2 GB de RAM libres
- 500 MB de disco en cache pool (CT2000 nvme1n1)

### Paso 1: Crear carpetas persistentes

Conecta por SSH a tu Unraid y ejecuta:

```bash
mkdir -p /mnt/user/appdata/erpleiva/logs
chmod -R 777 /mnt/user/appdata/erpleiva
```

Estas carpetas contendrán:
- `/mnt/user/appdata/erpleiva/erp.db` — la base de datos SQLite
- `/mnt/user/appdata/erpleiva/logs/` — logs del servidor

> **Por qué aquí**: el plugin "appdata backup" respalda automáticamente esta
> carpeta a tu disco de backup. Si pierdes el cache, recuperas la BD.

### Paso 2: Crear el template de Docker

Tienes dos opciones:

#### Opción A1: Community Applications (más fácil)

1. Ve a **Settings → Community Applications → Template Repositories**
2. Añade esta URL si no la tienes:
   `https://github.com/selfhosters-net/templates`
3. Busca "ERP LEIVA" (aparecerá cuando publiques el template en la store)

#### Opción A2: Plantilla XML manual (Unraid 6.11+)

Crea el fichero `/boot/config/plugins/dockerMan/templates-user-defined/erpleiva.xml`:

```xml
<?xml version="1.0" encoding="utf-8"?>
<Container version="2">
  <Name>ERP-LEIVA</Name>
  <Repository>erpleiva:latest</Repository>
  <Network>bridge</Network>
  <Privileged>False</Privileged>
  <Support>https://github.com/tu-usuario/erp-leiva</Support>
  <Project>https://github.com/tu-usuario/erp-leiva</Project>
  <Overview>ERP multi-tenant para almacenes y construcción.</Overview>
  <Category>Business:Office</Category>
  <WebUI>http://[IP]:[PORT:8000]</WebUI>
  <TemplateURL/>
  <Icon>https://raw.githubusercontent.com/tu-usuario/erp-leiva/main/icon.png</Icon>
  <ExtraParams/>
  <PostArgs/>
  <CPUset/>
  <DateInstalled>0</DateInstalled>
  <DonateText/>
  <DonateLink/>
  <Description>ERP con inventario, ventas, compras, facturación, tesorería, multi-almacén y tránsitos.</Description>
  <Networking>
    <Mode>bridge</Mode>
    <Publish>
      <Port>
        <HostPort>8000</HostPort>
        <ContainerPort>8000</ContainerPort>
        <Protocol>tcp</Protocol>
        <Description>Web UI y API REST</Description>
      </Port>
    </Publish>
  </Networking>
  <Data>
    <Volume>
      <HostDir>/mnt/user/appdata/erpleiva</HostDir>
      <ContainerDir>/data</ContainerDir>
        <Mode>rw</Mode>
        <Description>Datos persistentes (BD SQLite y logs)</Description>
    </Volume>
  </Data>
  <Environment>
    <Variable>
      <Name>ERP_SECRET_KEY</Name>
      <Value>CAMBIAR-ESTA-CLAVE-MINIMO-32-CARACTERES-ALEATORIOS</Value>
      <Description>Clave de firma de cookies. Minimo 32 caracteres aleatorios. CAMBIAR EN PRODUCCION.</Description>
    </Variable>
    <Variable>
      <Name>ERP_EMPRESA_NOMBRE</Name>
      <Value>Centro Logístico de Almacenes</Value>
      <Description>Nombre por defecto de la empresa</Description>
    </Variable>
    <Variable>
      <Name>TZ</Name>
      <Value>Europe/Madrid</Value>
      <Description>Zona horaria</Description>
    </Variable>
  </Environment>
  <Plugins>
    <Plugin>Community Applications</Plugin>
  </Plugins>
</Container>
```

#### Opción A3: Docker Compose (vía SSH)

Si prefieres control total:

1. Sube el proyecto a Unraid:
   ```bash
   scp -r "C:\Users\leiva\Documents\ERP LEIVA" root@192.168.1.100:/mnt/user/appdata/erp-leiva-src/
   ```

2. Crea `/mnt/user/appdata/erp-leiva-src/.env` con tu ERP_SECRET_KEY real.

3. Lanza:
   ```bash
   cd /mnt/user/appdata/erp-leiva-src
   docker compose up -d
   docker compose logs -f
   ```

### Paso 3: Construir la imagen

**Si usas Community Applications** (A1): el contenedor se descarga solo.

**Si usas plantilla XML** (A2): primero construye la imagen localmente:
```bash
cd /mnt/user/appdata/erp-leiva-src
docker build -t erpleiva:latest .
```

**Si usas Docker Compose** (A3): el build se hace automáticamente.

### Paso 4: Arrancar y verificar

```bash
docker ps | grep erp
docker logs erp-leiva --tail 50
```

Verás algo como:
```
[entrypoint] Iniciando ERP LEIVA...
[migrate]   [skip] tabla 'planes' ya existe
[seed] Empresa ya tiene productos; no se hace seed demo.
[entrypoint] Arrancando servidor...
+----------------------------------------------------------+
|  Servidor:    http://0.0.0.0:8000
|  Frontend:    http://0.0.0.0:8000/
```

### Paso 5: Primer acceso

1. Abre `http://192.168.1.100:8000` desde cualquier dispositivo de tu LAN
2. Te aparecerá la pantalla de instalación inicial
3. Rellena datos de empresa, elige plan (recomendado: Pro), crea usuario admin
4. Instalar y listo

### Paso 6: Exponer a Internet (opcional, para vender como SaaS)

Para que tus clientes accedan desde fuera **sin abrir puertos en el router**,
usa Cloudflare Tunnel (gratis):

```bash
# En Unraid
docker run -d --name cloudflared \
  --restart unless-stopped \
  -v /mnt/user/appdata/cloudflared:/home/nonroot/.cloudflared \
  cloudflare/cloudflared:latest \
  tunnel --no-autoupdate run <TU_TUNNEL_TOKEN>
```

Configura en https://one.dash.cloudflare.com → crea tunnel → apunta
`erp.tudominio.com` → `http://erpleiva:8000`.

---

## Método B: Nativo (sin Docker)

Útil si Docker te da problemas o quieres máximo control.

### Paso 1: Instalar Python 3.11 en Unraid

Por defecto Unraid trae Python 3.x pero puede ser antiguo. Mejor instalar:

```bash
# Instalar pyenv para gestionar versiones
docker run -it --rm -v /mnt/user/appdata/pyenv:/pyenv alpine:latest sh
apk add --no-cache bash git build-base openssl-dev zlib-dev readline-dev sqlite-dev
git clone https://github.com/pyenv/pyenv.git /pyenv
export PYENV_ROOT=/pyenv
export PATH=$PYENV_ROOT/bin:$PATH
pyenv install 3.11.10
exit
```

O usa un slug de la comunidad "python3.11".

### Paso 2: Subir el código

```bash
scp -r "C:\Users\leiva\Documents\ERP LEIVA" root@192.168.1.100:/mnt/user/appdata/erp-leiva/
```

### Paso 3: Crear venv y arrancar

```bash
ssh root@192.168.1.100
cd /mnt/user/appdata/erp-leiva
python3.11 -m venv .venv
.venv/bin/pip install -r requirements.txt

# Crear carpeta de datos
mkdir -p /mnt/user/appdata/erpleiva
ln -s /mnt/user/appdata/erpleiva data

# Migrar BD y arrancar
.venv/bin/python scripts/migrate_almacenes.py
.venv/bin/python scripts/seed.py

# Lanzar (background)
nohup .venv/bin/python run.py > /var/log/erp-leiva.log 2>&1 &
```

### Paso 4: Auto-arranque al boot (rc.local)

Edita `/boot/config/rc.local` o crea `/etc/rc.d/rc.local` con:

```bash
#!/bin/bash
cd /mnt/user/appdata/erp-leiva
nohup .venv/bin/python run.py > /var/log/erp-leiva.log 2>&1 &
```

---

## Actualizaciones

### Docker (método A)

```bash
cd /mnt/user/appdata/erp-leiva-src
git pull  # si usas git
docker compose build
docker compose up -d
```

La migración se aplica automáticamente al arrancar (entrypoint).

### Nativo (método B)

```bash
cd /mnt/user/appdata/erp-leiva
git pull
.venv/bin/pip install -r requirements.txt
# parar el proceso actual
pkill -f "python run.py"
# arrancar de nuevo
nohup .venv/bin/python run.py > /var/log/erp-leiva.log 2>&1 &
```

---

## Backups

### Automático vía appdata backup

Unraid ya respalda `/mnt/user/appdata/` automáticamente si tienes el plugin
**appdata backup** instalado. La BD `erp.db` queda protegida.

### Manual

```bash
# Backup completo
cp /mnt/user/appdata/erpleiva/erp.db /mnt/user/backups/erp-$(date +%Y%m%d).db

# Backup solo de la BD (recomendado antes de migrar)
docker exec erp-leiva cp /data/erp.db /tmp/backup.db
docker cp erp-leiva:/tmp/backup.db ./erp-backup.db
```

---

## Troubleshooting

### El contenedor no arranca

```bash
docker logs erp-leiva --tail 100
docker inspect erp-leiva | grep -i error
```

Común: el puerto 8000 está ocupado por otro contenedor → cambia el
`HostPort` en la plantilla.

### "No module named 'backend'"

El volumen está montado mal. Verifica que `/mnt/user/appdata/erpleiva` se
mapee a `/data` (no a otra ruta).

### Quiero cambiar la clave secreta

1. Para el contenedor: `docker stop erp-leiva`
2. Cambia la variable `ERP_SECRET_KEY` en el template
3. Vuelve a arrancar: `docker start erp-leiva`

⚠️ Al cambiar la clave, **todas las sesiones se invalidan** y los usuarios
tienen que volver a hacer login. No pierdes datos.

### Quiero resetear todo (BD vacía)

```bash
docker stop erp-leiva
rm /mnt/user/appdata/erpleiva/erp.db
docker start erp-leiva
```

La migración y los planes se recrean automáticamente.

---

## Resumen

| | Docker | Nativo |
|---|---|---|
| Tiempo setup | 5 min | 20 min |
| Actualizar | `docker compose up -d --build` | git pull + restart manual |
| Backup | automático (appdata) | manual |
| Autoarranque | sí (restart: unless-stopped) | manual (rc.local) |
| Aislamiento | contenedor separado | usa el sistema base |

**Mi recomendación**: usa Docker. Es lo más limpio.