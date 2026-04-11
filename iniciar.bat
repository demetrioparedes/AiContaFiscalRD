@echo off
title AiContaFiscalRD — Servidor Fiscal
color 0A

echo.
echo  ================================================
echo   AiContaFiscalRD — Iniciando servidor...
echo  ================================================
echo.

REM --- PASO 1: Matar TODOS los procesos Python previos (evita WinError 32 / lock BD) ---
echo [1/3] Liberando procesos Python anteriores...
taskkill /F /IM python.exe /T >nul 2>&1
taskkill /F /IM pythonw.exe /T >nul 2>&1
timeout /t 1 /nobreak >nul

REM --- PASO 2: Liberar también el puerto 8000 si quedó colgado ---
echo [2/3] Verificando puerto 8000...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8000 "') do (
    taskkill /F /PID %%a >nul 2>&1
)
timeout /t 1 /nobreak >nul

REM --- PASO 3: Arrancar el servidor limpio ---
echo [3/3] Arrancando servidor AiContaFiscalRD en http://localhost:8000
echo.
echo  Abre tu browser en: http://localhost:8000
echo  Para cerrar: presiona CTRL+C en esta ventana
echo.

cd /d "c:\GEMINI\AiContaFiscalRD"
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000

pause
