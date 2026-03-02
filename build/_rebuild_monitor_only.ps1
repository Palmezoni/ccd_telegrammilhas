$pyinstaller = 'C:\Users\palme\ccd\ccd_telegrammilhas\.venv\Scripts\pyinstaller.exe'
$base    = 'C:\Users\palme\ccd\ccd_telegrammilhas'
$dist    = "$base\dist"
$assets  = "$base\assets"
$install = 'C:\Users\palme\AppData\Local\Programs\Milhas UP Telegram Monitor'

# Matar monitor em execução
Get-Process monitor_bg -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 1

Write-Host "[1] Compilando monitor_bg.exe (com startup_error.log)..."
& $pyinstaller `
    --onedir --noconsole -y `
    --name monitor_bg `
    --icon "$assets\icon.ico" `
    --distpath "$dist\MilhasUP" `
    --workpath "$base\build\_work\monitor" `
    --specpath "$base\build" `
    "$base\monitor.py"

if ($LASTEXITCODE -ne 0) { Write-Host "[ERRO] Build falhou!"; exit 1 }
Write-Host "[1] OK"

Write-Host "[2] Copiando monitor_bg para instalacao..."
if (Test-Path "$install\monitor_bg") { Remove-Item "$install\monitor_bg" -Recurse -Force }
Copy-Item "$dist\MilhasUP\monitor_bg" "$install\" -Recurse -Force
Write-Host "[2] OK"

# Limpar arquivos de estado antigos
Remove-Item "$install\monitor.pid"  -ErrorAction SilentlyContinue
Remove-Item "$install\monitor.lock" -ErrorAction SilentlyContinue
Remove-Item "$install\startup_error.log" -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "Pronto! Agora:"
Write-Host "  1. Abra a GUI (MilhasUP.exe) e clique em Iniciar Monitor"
Write-Host "  2. Se falhar, leia: $install\startup_error.log"
