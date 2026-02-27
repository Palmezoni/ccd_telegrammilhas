@echo off
setlocal

set "PID_FILE=%~dp0monitor.pid"

if not exist "%PID_FILE%" (
    echo [PARADO] monitor.pid nao encontrado. Monitor nao esta rodando.
    goto :end
)

set /p PID=<"%PID_FILE%"

if "%PID%"=="" (
    echo [AVISO] monitor.pid vazio. Removendo.
    del "%PID_FILE%" >nul 2>&1
    goto :end
)

tasklist /FI "PID eq %PID%" 2>nul | find "%PID%" >nul
if %errorlevel% neq 0 (
    echo [PARADO] Processo PID %PID% nao esta ativo. Limpando arquivos.
    del "%PID_FILE%" >nul 2>&1
    del "%~dp0monitor.lock" >nul 2>&1
    goto :end
)

taskkill /PID %PID% /F >nul 2>&1
if %errorlevel%==0 (
    echo [OK] Monitor parado ^(PID %PID%^).
    del "%PID_FILE%" >nul 2>&1
    del "%~dp0monitor.lock" >nul 2>&1
) else (
    echo [ERRO] Nao foi possivel parar PID %PID%.
)

:end
pause
