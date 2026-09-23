# ============================================================
# ERP LEIVA - Watchdog (asegura que el servidor este siempre vivo)
# ============================================================
# USO:
#   .\scripts\watchdog_erp.ps1          # bucle infinito (Ctrl+C para parar)
#   .\scripts\watchdog_erp.ps1 -Once    # solo una comprobacion
#
# Este script comprueba cada 30 segundos que el ERP responda.
# Si no responde, lo reinicia y avisa.
#
# Para hacerlo 24/7, anade este script a una tarea programada
# que arranque al iniciar el sistema.
# ============================================================

param(
    [switch]$Once = $false,
    [int]$IntervalSec = 30,
    [string]$LogFile = "$PSScriptRoot\..\data\watchdog.log"
)

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

function Log($msg) {
    $line = "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] $msg"
    Write-Host $line
    $parent = Split-Path -Parent $LogFile
    if (-not (Test-Path $parent)) { New-Item -ItemType Directory -Path $parent -Force | Out-Null }
    Add-Content -Path $LogFile -Value $line
}

function Is-Alive {
    try {
        $r = Invoke-WebRequest "http://localhost:8000/api/health" -UseBasicParsing -TimeoutSec 5
        return $r.StatusCode -eq 200
    } catch {
        return $false
    }
}

function Start-Erp {
    Log "ERP no responde. Arrancando..."
    Get-Process python -ErrorAction SilentlyContinue | Where-Object {
        $cmd = (Get-CimInstance Win32_Process -Filter "ProcessId=$($_.Id)").CommandLine
        $cmd -like "*run.py*"
    } | Stop-Process -Force -ErrorAction SilentlyContinue

    Start-Sleep -Seconds 2

    $pythonExe = Join-Path $root ".venv\Scripts\python.exe"
    $logOut = Join-Path $root "data\server.log"
    $logErr = Join-Path $root "data\server.err"

    Start-Process -FilePath $pythonExe `
        -ArgumentList "run.py" `
        -WorkingDirectory $root `
        -RedirectStandardOutput $logOut `
        -RedirectStandardError $logErr `
        -WindowStyle Hidden

    Start-Sleep -Seconds 6
    if (Is-Alive) {
        Log "ERP arrancado OK"
    } else {
        Log "ERROR: ERP no arranca. Revisa data\server.err"
    }
}

# Primer arranque si no esta vivo
if (-not (Is-Alive)) {
    Start-Erp
}

if ($Once) {
    Log "Watchdog: ejecucion unica finalizada"
    exit
}

Log "Watchdog 24/7 iniciado. Ctrl+C para parar."
while ($true) {
    Start-Sleep -Seconds $IntervalSec
    if (-not (Is-Alive)) {
        Start-Erp
    }
}