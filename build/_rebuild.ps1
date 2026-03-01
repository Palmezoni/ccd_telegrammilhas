$ErrorActionPreference = 'Stop'
Set-Location 'C:\Users\palme\ccd\ccd_telegrammilhas'

$pyinstaller = 'C:\Users\palme\ccd\ccd_telegrammilhas\.venv\Scripts\pyinstaller.exe'
$base   = 'C:\Users\palme\ccd\ccd_telegrammilhas'
$dist   = "$base\dist"
$assets = "$base\assets"
$install = 'C:\Users\palme\AppData\Local\Programs\Milhas UP Telegram Monitor'

# ── 1. Matar processos em execução ───────────────────────────────────────────
Write-Host "`n[0] Encerrando processos..."
Get-Process MilhasUP, monitor_bg -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2
Write-Host "    OK"

# ── 2. Build MilhasUP.exe (GUI — primeiro) ────────────────────────────────────
Write-Host "`n[1/2] Compilando MilhasUP.exe (GUI)..."
& $pyinstaller `
    --onedir --noconsole -y `
    --name MilhasUP `
    --icon "$assets\icon.ico" `
    --distpath "$dist" `
    --workpath "$base\build\_work\app" `
    --specpath "$base\build" `
    --add-data "${assets};assets" `
    --collect-all customtkinter `
    --hidden-import "pystray._win32" `
    --hidden-import "PIL._tkinter_finder" `
    "$base\app.py"
if ($LASTEXITCODE -ne 0) { throw "PyInstaller falhou para MilhasUP" }
Write-Host "    OK"

# ── 3. Build monitor_bg.exe (--onedir) ─────────────────────────────────────
Write-Host "`n[2/2] Compilando monitor_bg.exe (background)..."
& $pyinstaller `
    --onedir --noconsole `
    --name monitor_bg `
    --icon "$assets\icon.ico" `
    --distpath "$dist\MilhasUP" `
    --workpath "$base\build\_work\monitor" `
    --specpath "$base\build" `
    "$base\monitor.py"
if ($LASTEXITCODE -ne 0) { throw "PyInstaller falhou para monitor_bg" }
Write-Host "    OK"

# ── 4. Copiar .env.example ────────────────────────────────────────────────────
Write-Host "`n[3/3] Copiando .env.example..."
Copy-Item "$base\.env.example" "$dist\MilhasUP\" -Force
Write-Host "    OK"

# ── 5. Copiar para diretório de instalação (preservar .env e session) ─────────
Write-Host "`n[4/4] Atualizando instalação em $install..."

# MilhasUP.exe
Copy-Item "$dist\MilhasUP\MilhasUP.exe" "$install\" -Force

# _internal (dependências da GUI)
if (Test-Path "$install\_internal") { Remove-Item "$install\_internal" -Recurse -Force }
Copy-Item "$dist\MilhasUP\_internal" "$install\" -Recurse -Force

# monitor_bg (pasta inteira com _BASE fix)
if (Test-Path "$install\monitor_bg") { Remove-Item "$install\monitor_bg" -Recurse -Force }
Copy-Item "$dist\MilhasUP\monitor_bg" "$install\" -Recurse -Force

# .env.example
Copy-Item "$dist\MilhasUP\.env.example" "$install\" -Force

Write-Host "    OK`n"
Write-Host "========================================================"
Write-Host "  BUILD + DEPLOY CONCLUIDO!"
Write-Host "  Instalação em: $install"
Write-Host "  Estrutura:"
Get-ChildItem $install | Select-Object Mode, LastWriteTime, Name | Format-Table -AutoSize
Write-Host "========================================================"
