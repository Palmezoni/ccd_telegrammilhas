@echo off
setlocal

set "PID_FILE=%~dp0monitor.pid"

if not exist "%PID_FILE%" (
    echo [PARADO] monitor.pid nao encontrado.
    goto :end
)

set /p PID=<"%PID_FILE%"

if "%PID%"=="" (
    echo [PARADO] monitor.pid esta vazio.
    goto :end
)

tasklist /FI "PID eq %PID%" 2>nul | find "%PID%" >nul
if %errorlevel%==0 (
    echo [RODANDO] PID %PID%
) else (
    echo [PARADO] Processo %PID% nao esta ativo ^(crash?^).
)

:end
pause
