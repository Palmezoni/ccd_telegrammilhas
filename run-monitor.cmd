@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"

rem Verifica se ja existe uma instancia rodando
if exist "%~dp0monitor.lock" (
    set /p EXISTING_PID=<"%~dp0monitor.lock"
    tasklist /FI "PID eq !EXISTING_PID!" 2>nul | find "!EXISTING_PID!" >nul
    if not errorlevel 1 (
        echo [AVISO] Monitor ja esta rodando ^(PID !EXISTING_PID!^). Use stop-monitor.cmd primeiro.
        pause
        exit /b 1
    )
)

rem Inicia o monitor headless (sem janela de console) via pythonw.
"%~dp0.venv\Scripts\pythonw.exe" -u "%~dp0monitor.py" --send

echo [OK] Monitor iniciado em background.
timeout /t 2 /nobreak >nul
