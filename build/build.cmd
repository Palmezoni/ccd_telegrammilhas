@echo off
setlocal
cd /d "%~dp0.."

echo.
echo ============================================================
echo   MILHAS UP - BUILD  (PyInstaller + Inno Setup)
echo ============================================================
echo.

set BASE=%~dp0..
set VENV=%BASE%\.venv\Scripts
set DIST=%BASE%\dist
set ASSETS=%BASE%\assets

rem ── [1/5] Dependencias ───────────────────────────────────────────────────────
echo [1/5] Instalando dependencias de build...
call "%VENV%\pip" install customtkinter pystray pillow pyinstaller --quiet
if errorlevel 1 (echo [ERRO] Falha ao instalar deps. && pause && exit /b 1)
echo       OK

rem ── [2/5] Icone ──────────────────────────────────────────────────────────────
echo [2/5] Gerando icone...
call "%VENV%\python" "%ASSETS%\make_icon.py"
if errorlevel 1 (echo [ERRO] Falha ao gerar icone. && pause && exit /b 1)
echo       OK

rem ── [3/5] MilhasUP.exe (interface grafica) — PRIMEIRO para nao ser sobrescrito
echo [3/5] Compilando interface grafica...
call "%VENV%\pyinstaller" ^
    --onedir ^
    --noconsole ^
    --name MilhasUP ^
    --icon "%ASSETS%\icon.ico" ^
    --distpath "%DIST%" ^
    --workpath "%BASE%\build\_work\app" ^
    --specpath "%BASE%\build" ^
    --add-data "%ASSETS%;assets" ^
    --collect-all customtkinter ^
    --hidden-import pystray._win32 ^
    --hidden-import PIL._tkinter_finder ^
    "%BASE%\app.py"
if errorlevel 1 (echo [ERRO] Falha ao compilar interface. && pause && exit /b 1)
echo       OK

rem ── [4/5] monitor_bg.exe (--onedir evita flash de janela CMD) ─────────────────
rem     distpath aponta para dentro de dist\MilhasUP\ para que monitor_bg\
rem     ja fique no lugar certo sem necessidade de copia manual.
echo [4/5] Compilando monitor background...
call "%VENV%\pyinstaller" ^
    --onedir ^
    --noconsole ^
    --name monitor_bg ^
    --icon "%ASSETS%\icon.ico" ^
    --distpath "%DIST%\MilhasUP" ^
    --workpath "%BASE%\build\_work\monitor" ^
    --specpath "%BASE%\build" ^
    "%BASE%\monitor.py"
if errorlevel 1 (echo [ERRO] Falha ao compilar monitor. && pause && exit /b 1)
echo       OK

rem ── [5/5] Montar pasta final ──────────────────────────────────────────────────
echo [5/5] Montando pacote final...
rem monitor_bg ja esta em dist\MilhasUP\monitor_bg\ — nada a copiar
copy /y "%BASE%\.env.example" "%DIST%\MilhasUP\" >nul
if errorlevel 1 (echo [AVISO] .env.example nao copiado - verifique se o arquivo existe)
echo       OK

echo.
echo ============================================================
echo   BUILD CONCLUIDO!
echo   Estrutura em dist\MilhasUP\:
echo     MilhasUP.exe  + _internal\
echo     monitor_bg\   (monitor_bg.exe + _internal\)
echo     .env.example
echo.
echo   Para criar o instalador .exe:
echo   - Instale o Inno Setup (https://jrsoftware.org/isinfo.php)
echo   - Abra build\setup.iss e clique em "Compile"  ou  execute:
echo     "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" build\setup.iss
echo ============================================================
echo.
pause
