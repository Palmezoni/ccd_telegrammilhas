$pyinstaller = 'C:\Users\palme\ccd\ccd_telegrammilhas\.venv\Scripts\pyinstaller.exe'
$base   = 'C:\Users\palme\ccd\ccd_telegrammilhas'
$dist   = "$base\dist"
$assets = "$base\assets"
$install = 'C:\Users\palme\AppData\Local\Programs\Milhas UP Telegram Monitor'

Write-Host "[1] Compilando MilhasUP.exe..."
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

if ($LASTEXITCODE -ne 0) { Write-Host "[ERRO] Build falhou!"; exit 1 }
Write-Host "[1] OK"

Write-Host "[2] Copiando para instalacao..."
Copy-Item "$dist\MilhasUP\MilhasUP.exe" "$install\" -Force
if (Test-Path "$install\_internal") { Remove-Item "$install\_internal" -Recurse -Force }
Copy-Item "$dist\MilhasUP\_internal" "$install\" -Recurse -Force
Write-Host "[2] OK"

Write-Host "[3] Abrindo GUI atualizada..."
Start-Process "$install\MilhasUP.exe"
Write-Host "Pronto! Flash de CMD corrigido."
