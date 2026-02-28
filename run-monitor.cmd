@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"

echo.
echo ================================================
echo   MONITOR DE MILHAS TELEGRAM
echo ================================================
echo.

rem ── Verifica se ja existe instancia rodando (via monitor.pid) ──────────────
set "PID_FILE=%~dp0monitor.pid"

if exist "%PID_FILE%" (
    set /p OLD_PID=<"%PID_FILE%"
    if not "!OLD_PID!"=="" (
        tasklist /FI "PID eq !OLD_PID!" 2>nul | find "!OLD_PID!" >nul
        if not errorlevel 1 (
            echo [AVISO] O monitor ja esta rodando com PID !OLD_PID!.
            echo         Use stop-monitor.cmd para encerrar antes de reiniciar.
            echo.
            pause
            exit /b 1
        ) else (
            echo [INFO] Arquivo monitor.pid encontrado ^(PID !OLD_PID!^) mas processo nao existe.
            echo        Limpando arquivos antigos...
            del /f /q "%~dp0monitor.pid" 2>nul
            del /f /q "%~dp0monitor.lock" 2>nul
        )
    )
)

rem ── Inicia o monitor em background ────────────────────────────────────────
echo [1/3] Iniciando monitor em background ^(pythonw - sem janela^)...
start "" /b "%~dp0.venv\Scripts\pythonw.exe" -u "%~dp0monitor.py"

rem ── Aguarda o processo escrever o PID ─────────────────────────────────────
echo [2/3] Aguardando confirmacao de inicio...
timeout /t 1 /nobreak >nul
timeout /t 1 /nobreak >nul
timeout /t 1 /nobreak >nul

rem ── Verifica se subiu corretamente ────────────────────────────────────────
echo [3/3] Verificando processo...
echo.

if not exist "%PID_FILE%" (
    echo [ERRO] monitor.pid nao foi criado - o monitor pode ter falhado ao iniciar.
    echo        Verifique se o .env esta correto e tente novamente.
    echo.
    pause
    exit /b 1
)

set /p NEW_PID=<"%PID_FILE%"

if "%NEW_PID%"=="" (
    echo [ERRO] monitor.pid esta vazio - falha inesperada.
    echo.
    pause
    exit /b 1
)

tasklist /FI "PID eq %NEW_PID%" 2>nul | find "%NEW_PID%" >nul
if %errorlevel%==0 (
    echo ================================================
    echo   [OK] MONITOR RODANDO  ^|  PID %NEW_PID%
    echo ================================================
    echo.
    echo  Grupos monitorados: Balcao Jet Milhas, Agencia de Milhas Pro e outros
    echo  Notificacoes:       Telegram ^(Mensagens Salvas^) + ntfy.sh
    echo  Logs:               events.jsonl ^(nesta pasta^)
    echo.
    echo  Para parar:  stop-monitor.cmd
    echo  Para status: status-monitor.cmd
    echo.
) else (
    echo [ERRO] Processo %NEW_PID% nao encontrado - o monitor encerrou inesperadamente.
    echo        Verifique o .env e as credenciais do Telegram.
    echo.
)

pause
