$install = 'C:\Users\palme\AppData\Local\Programs\Milhas UP Telegram Monitor'

Write-Host "=== Processos atuais ==="
Get-Process monitor_bg, python -ErrorAction SilentlyContinue | Select-Object Name, Id, StartTime | Format-Table -AutoSize

Write-Host "Matando monitor_bg e python..."
Get-Process monitor_bg -ErrorAction SilentlyContinue | Stop-Process -Force
Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Seconds 2

Write-Host "Limpando arquivos de estado..."
Remove-Item "$install\monitor.pid"  -ErrorAction SilentlyContinue
Remove-Item "$install\monitor.lock" -ErrorAction SilentlyContinue
Remove-Item "$install\startup_error.log" -ErrorAction SilentlyContinue

Write-Host "Limpando project dir tambem..."
Remove-Item 'C:\Users\palme\ccd\ccd_telegrammilhas\monitor.pid'  -ErrorAction SilentlyContinue
Remove-Item 'C:\Users\palme\ccd\ccd_telegrammilhas\monitor.lock' -ErrorAction SilentlyContinue

Write-Host "Verificando..."
Get-Process monitor_bg, python -ErrorAction SilentlyContinue | Select-Object Name, Id | Format-Table -AutoSize

Write-Host "Pronto! Agora teste o Iniciar na GUI."
