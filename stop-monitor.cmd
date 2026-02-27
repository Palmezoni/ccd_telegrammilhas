@echo off
setlocal

set "LOCK=%~dp0monitor.lock"

if not exist "%LOCK%" (
    echo [PARADO] Lock nao encontrado. Monitor nao esta rodando.
    exit /b 0
)

set /p PID=<"%LOCK%"

if "%PID%"=="" (
    echo [AVISO] Lock existe mas esta vazio. Removendo.
    del "%LOCK%" >nul 2>&1
    exit /b 0
)

tasklist /FI "PID eq %PID%" 2>nul | find "%PID%" >nul
if %errorlevel% neq 0 (
    echo [PARADO] Processo PID %PID% nao esta ativo. Limpando lock.
    del "%LOCK%" >nul 2>&1
    exit /b 0
)

taskkill /PID %PID% /F >nul 2>&1
if %errorlevel%==0 (
    echo [OK] Monitor parado ^(PID %PID%^).
    del "%LOCK%" >nul 2>&1
) else (
    echo [ERRO] Nao foi possivel parar PID %PID%.
)
