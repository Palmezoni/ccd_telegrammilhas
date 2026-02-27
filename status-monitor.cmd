@echo off
setlocal

set "LOCK=%~dp0monitor.lock"

if not exist "%LOCK%" (
    echo [PARADO] Lock nao encontrado.
    goto :end
)

set /p PID=<"%LOCK%"

if "%PID%"=="" (
    echo [PARADO] Lock existe mas esta vazio.
    goto :end
)

tasklist /FI "PID eq %PID%" 2>nul | find "%PID%" >nul
if %errorlevel%==0 (
    echo [RODANDO] PID %PID%
) else (
    echo [PARADO] Lock existe mas processo %PID% nao esta ativo ^(crash?^).
)

:end
pause
