$install = 'C:\Users\palme\AppData\Local\Programs\Milhas UP Telegram Monitor'
$logFile = "$install\startup_error.log"

Remove-Item "$install\monitor.pid"  -ErrorAction SilentlyContinue
Remove-Item "$install\monitor.lock" -ErrorAction SilentlyContinue
Remove-Item $logFile -ErrorAction SilentlyContinue

Write-Host "Iniciando monitor_bg.exe..."
Start-Process -FilePath "$install\monitor_bg\monitor_bg.exe" -WorkingDirectory $install

Write-Host "Aguardando ate 60s (checar a cada 5s)..."
for ($i = 0; $i -lt 12; $i++) {
    Start-Sleep -Seconds 5
    $pidContent = Get-Content "$install\monitor.pid" -ErrorAction SilentlyContinue
    $pidStr = if ($pidContent) { $pidContent.Trim() } else { "N/A" }
    $logContent = if (Test-Path $logFile) {
        [System.IO.File]::ReadAllText($logFile, [System.Text.Encoding]::UTF8)
    } else { "" }
    $lineCount = if ($logContent.Trim().Length -gt 0) { $logContent.Trim().Split("`n").Count } else { 0 }
    $elapsed = ($i + 1) * 5
    Write-Host "t=${elapsed}s | pid=$pidStr | log_linhas=$lineCount"
}

Write-Host ""
Write-Host "=== startup_error.log COMPLETO ==="
if (Test-Path $logFile) {
    $txt = [System.IO.File]::ReadAllText($logFile, [System.Text.Encoding]::UTF8)
    Write-Host $txt
} else {
    Write-Host "Arquivo nao existe"
}

Write-Host "=== Processos monitor_bg ==="
Get-Process monitor_bg -ErrorAction SilentlyContinue | Select-Object Name, Id, StartTime | Format-Table -AutoSize
