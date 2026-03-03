$install = 'C:\Users\palme\AppData\Local\Programs\Milhas UP Telegram Monitor'

# Limpar arquivos de lock antigos
Remove-Item "$install\monitor.pid"  -ErrorAction SilentlyContinue
Remove-Item "$install\monitor.lock" -ErrorAction SilentlyContinue

Write-Host "Rodando monitor_bg.exe diretamente para ver erros..."
Write-Host "Pressione Ctrl+C para parar`n"

# Roda com console visivel para capturar output
$p = Start-Process `
    -FilePath "$install\monitor_bg\monitor_bg.exe" `
    -WorkingDirectory $install `
    -PassThru `
    -Wait `
    -RedirectStandardOutput "$install\stdout.txt" `
    -RedirectStandardError  "$install\stderr.txt"

Write-Host "`nExitCode: $($p.ExitCode)"
Write-Host "`n=== STDOUT ==="
Get-Content "$install\stdout.txt" -ErrorAction SilentlyContinue
Write-Host "`n=== STDERR ==="
Get-Content "$install\stderr.txt" -ErrorAction SilentlyContinue
