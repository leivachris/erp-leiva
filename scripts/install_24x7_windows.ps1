# ============================================================
# ERP LEIVA - Instala el ERP como tarea programada de Windows 24/7
# ============================================================
# USO (como Administrador):
#   .\scripts\install_24x7_windows.ps1
#
# Esto:
#   1. Crea una tarea programada llamada "ERP-LEIVA-24x7"
#   2. Se ejecuta al iniciar el sistema (con maxima prioridad)
#   3. Si falla, se reintenta cada 1 minuto
#   4. Arranca scripts\start_24x7_windows.bat
#   5. Mantiene vivo el ERP indefinidamente
# ============================================================

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$startScript = Join-Path $root "scripts\start_24x7_windows.bat"
$watchdogScript = Join-Path $root "scripts\watchdog_erp.ps1"
$taskName = "ERP-LEIVA-24x7"
$watchdogTaskName = "ERP-LEIVA-Watchdog"

Write-Host "Instalando ERP LEIVA como tarea programada de Windows 24/7..."
Write-Host ""

# Verificar que se ejecuta como Administrador
$principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host "ERROR: Debes ejecutar este script como ADMINISTRADOR." -ForegroundColor Red
    Write-Host "Click derecho en PowerShell -> 'Ejecutar como administrador'" -ForegroundColor Yellow
    exit 1
}

# Eliminar tareas existentes (re-instalacion idempotente)
Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue
Unregister-ScheduledTask -TaskName $watchdogTaskName -Confirm:$false -ErrorAction SilentlyContinue

# Tarea principal: arrancar el ERP al iniciar el sistema
Write-Host "Creando tarea '$taskName'..."
$action = New-ScheduledTaskAction -Execute $startScript
$trigger = New-ScheduledTaskTrigger -AtStartup
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RestartCount 999 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit (New-TimeSpan -Hours 0) `
    -Priority 5

Register-ScheduledTask `
    -TaskName $taskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -User "SYSTEM" `
    -RunLevel Highest `
    -Description "ERP LEIVA - servidor 24/7. Arranca al iniciar el sistema y se reinicia si falla."

# Tarea watchdog: comprobar cada 5 minutos que el ERP esta vivo
Write-Host "Creando tarea watchdog '$watchdogTaskName'..."
$action2 = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$watchdogScript`""
$trigger2 = New-ScheduledTaskTrigger -AtStartup
$trigger2.Delay = "PT2M"  # esperar 2 min tras arranque
$settings2 = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Hours 0)

Register-ScheduledTask `
    -TaskName $watchdogTaskName `
    -Action $action2 `
    -Trigger $trigger2 `
    -Settings $settings2 `
    -User "SYSTEM" `
    -RunLevel Highest `
    -Description "ERP LEIVA - vigila que el servidor este vivo. Bucle infinito."

# Arrancar AHORA MISMO (sin esperar al reinicio)
Write-Host ""
Write-Host "Iniciando ERP ahora mismo..."
Start-ScheduledTask -TaskName $taskName
Start-Sleep -Seconds 8

# Verificar
try {
    $r = Invoke-WebRequest "http://localhost:8000/api/health" -UseBasicParsing -TimeoutSec 5
    if ($r.StatusCode -eq 200) {
        Write-Host ""
        Write-Host "================================================================" -ForegroundColor Green
        Write-Host "  ERP LEIVA 24/7 INSTALADO Y FUNCIONANDO" -ForegroundColor Green
        Write-Host "================================================================" -ForegroundColor Green
        Write-Host ""
        Write-Host "  URL local:    http://localhost:8000"
        Write-Host "  URL LAN:      http://$(Get-NetIPAddress -InterfaceAlias 'Ethernet*' -AddressFamily IPv4 -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty IPAddressToString):8000"
        Write-Host ""
        Write-Host "  Comandos utiles:" -ForegroundColor Yellow
        Write-Host "    Ver estado:    Get-ScheduledTask -TaskName 'ERP-LEIVA-24x7'"
        Write-Host "    Parar:         Stop-ScheduledTask -TaskName 'ERP-LEIVA-24x7'"
        Write-Host "    Arrancar:      Start-ScheduledTask -TaskName 'ERP-LEIVA-24x7'"
        Write-Host "    Logs:          Get-Content 'C:\Users\leiva\Documents\ERP LEIVA\data\server.err' -Tail 20"
        Write-Host ""
        Write-Host "  La tarea se reinicia automaticamente si el proceso muere." -ForegroundColor Cyan
        Write-Host "  Sobrevive a reinicios del sistema." -ForegroundColor Cyan
    } else {
        Write-Host "ERROR: servidor no responde tras 8s" -ForegroundColor Red
    }
} catch {
    Write-Host "ERROR: servidor no responde tras 8s" -ForegroundColor Red
    Write-Host "Detalle: $($_.Exception.Message)" -ForegroundColor Red
}