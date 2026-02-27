@echo off
setlocal

set "LOCK=%~dp0monitor.lock"

if not exist "%LOCK%" (
    echo [PARADO] Lock nao encontrado.
    exit /b 1
)

set /p PID=<"%LOCK%"

if "%PID%"=="" (
    echo [PARADO] Lock existe mas esta vazio.
    exit /b 1
)

tasklist /FI "PID eq %PID%" 2>nul | find "%PID%" >nul
if %errorlevel%==0 (
    echo [RODANDO] PID %PID%
    exit /b 0
) else (
    echo [PARADO] Lock existe mas processo %PID% nao esta ativo ^(crash?^).
    exit /b 1
)
