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

rem ── [1/5] Dependências ───────────────────────────────────────────────────────
echo [1/5] Instalando dependencias de build...
call "%VENV%\pip" install customtkinter pystray pillow pyinstaller --quiet
if errorlevel 1 (echo [ERRO] Falha ao instalar deps. && pause && exit /b 1)
echo       OK

rem ── [2/5] Icone ──────────────────────────────────────────────────────────────
echo [2/5] Gerando icone...
call "%VENV%\python" "%ASSETS%\make_icon.py"
if errorlevel 1 (echo [ERRO] Falha ao gerar icone. && pause && exit /b 1)
echo       OK

rem ── [3/5] monitor_bg.exe (processo background) ───────────────────────────────
echo [3/5] Compilando monitor background...
call "%VENV%\pyinstaller" ^
    --onefile ^
    --noconsole ^
    --name monitor_bg ^
    --distpath "%DIST%\MilhasUP" ^
    --workpath "%BASE%\build\_work\monitor" ^
    --specpath "%BASE%\build" ^
    "%BASE%\monitor.py"
if errorlevel 1 (echo [ERRO] Falha ao compilar monitor. && pause && exit /b 1)
echo       OK

rem ── [4/5] MilhasUP.exe (interface grafica) ───────────────────────────────────
echo [4/5] Compilando interface grafica...
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

rem ── [5/5] Montar pasta final ──────────────────────────────────────────────────
echo [5/5] Montando pacote final...
copy /y "%DIST%\MilhasUP\monitor_bg.exe" "%DIST%\MilhasUP\MilhasUP\" >nul
copy /y "%BASE%\.env.example" "%DIST%\MilhasUP\MilhasUP\" >nul

echo.
echo ============================================================
echo   BUILD CONCLUIDO!
echo   Arquivos em: dist\MilhasUP\
echo.
echo   Para criar o instalador .exe:
echo   - Instale o Inno Setup (https://jrsoftware.org/isinfo.php)
echo   - Abra build\setup.iss e clique em "Compile"
echo ============================================================
echo.
pause
