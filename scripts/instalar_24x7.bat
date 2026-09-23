@echo off
REM ============================================================
REM ERP LEIVA - Instalar como tarea programada de Windows 24/7
REM ============================================================
REM Ejecutar como Administrador (click derecho -> Ejecutar como administrador)
REM Crea una tarea que arranca el ERP al iniciar Windows y lo reinicia si falla.
REM ============================================================

setlocal enableextensions
set ROOT=%~dp0..
set ROOT=%ROOT:~0,-1%
set TASK=ERP-LEIVA-24x7

echo.
echo ============================================================
echo  Instalando ERP LEIVA como servicio 24/7 de Windows
echo ============================================================
echo.

REM Verificar permisos de admin
net session >nul 2>&1
if errorlevel 1 (
    echo ERROR: Este script necesita permisos de Administrador.
    echo Click derecho en este fichero ^> Ejecutar como administrador.
    pause
    exit /b 1
)

echo [1/4] Eliminando tarea anterior si existe...
schtasks /delete /tn "%TASK%" /f >nul 2>&1

echo [2/4] Creando tarea programada que arranca al iniciar el sistema...
REM /ru SYSTEM corre como SYSTEM (no necesita password)
REM /rl HIGHEST = maximo privilegio
REM /sc ONSTART = al iniciar el sistema
REM /tr = comando a ejecutar
schtasks /create ^
    /tn "%TASK%" ^
    /tr "\"%ROOT%\scripts\start_24x7_windows.bat\"" ^
    /sc onstart ^
    /delay 0000:30 ^
    /ru SYSTEM ^
    /rl HIGHEST ^
    /f

if errorlevel 1 (
    echo ERROR creando tarea programada.
    pause
    exit /b 1
)

echo [3/4] Configurando reinicio automatico si falla...
schtasks /set /tn "%TASK%" /restart ^
    /delay 00:01 ^
    /repeat 999 ^
    /sd 01/01/2026 ^
    /ed 12/31/2099 >nul 2>&1

echo [4/4] Arrancando el ERP ahora mismo...
schtasks /run /tn "%TASK%"

echo.
echo Esperando 8 segundos para que arranque...
timeout /t 8 /nobreak >nul

echo.
echo ============================================================
echo  ERP LEIVA instalado como tarea 24/7
echo ============================================================
echo.
echo  Tarea programada: %TASK%
echo  Comando:         scripts\start_24x7_windows.bat
echo  Arranca:         automaticamente al iniciar Windows
echo  Reinicio:        si falla, cada 1 minuto
echo.
echo  URL local:       http://localhost:8000
echo.
echo  Para verificar:
echo    schtasks /query /tn "%TASK%" /v /fo LIST
echo.
echo  Para parar:
echo    schtasks /end /tn "%TASK%"
echo.
echo  Para desinstalar:
echo    schtasks /delete /tn "%TASK%" /f
echo.
pause
endlocal