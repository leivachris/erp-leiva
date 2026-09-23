@echo off
REM ============================================================
REM ERP LEIVA - Inicia el servidor en modo 24/7 (sin ventana)
REM ============================================================
REM Este script arranca el ERP como proceso desacoplado de la sesion
REM de PowerShell. Sigue corriendo aunque cierres la terminal.
REM ============================================================

setlocal
set ROOT=%~dp0..
set ROOT=%ROOT:~0,-1%
cd /d "%ROOT%"

echo Iniciando ERP LEIVA en modo 24/7...
echo Directorio: %ROOT%

REM Usar pythonw.exe (sin ventana de consola) si esta disponible
set PYTHON_EXE=%ROOT%\.venv\Scripts\python.exe
if exist "%ROOT%\.venv\Scripts\pythonw.exe" set PYTHON_EXE=%ROOT%\.venv\Scripts\pythonw.exe

echo Python: %PYTHON_EXE%

REM Lanzar como proceso desacoplado
REM /B = no abrir nueva ventana (se ejecuta en background)
REM start con /MIN = ventana minimizada
start "ERP-LEIVA" /MIN /B "%PYTHON_EXE%" "%ROOT%\run.py"

echo.
echo ERP LEIVA arrancado. Espera 5 segundos y abre:
echo   http://localhost:8000
echo.
echo Para parar el ERP:
echo   taskkill /F /IM python.exe
echo.
echo Para hacerlo 24/7 de verdad:
echo   1. Abre "Programador de tareas" de Windows
echo   2. Crear tarea basica
echo   3. Desencadenador: "Al iniciar el sistema"
echo   4. Accion: ejecutar scripts\start_24x7_windows.bat
echo   5. Configuracion: "Si falla, reiniciar cada 1 minuto"
echo.
endlocal