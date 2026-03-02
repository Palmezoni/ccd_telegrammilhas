$install = 'C:\Users\palme\AppData\Local\Programs\Milhas UP Telegram Monitor'
$logFile = "$install\startup_error.log"

Remove-Item "$install\monitor.pid"  -ErrorAction SilentlyContinue
Remove-Item "$install\monitor.lock" -ErrorAction SilentlyContinue
Remove-Item $logFile -ErrorAction SilentlyContinue

Write-Host "Iniciando monitor_bg.exe..."
Start-Process -FilePath "$install\monitor_bg\monitor_bg.exe" -WorkingDirectory $install

Write-Host "Aguardando 20s..."
Start-Sleep -Seconds 20

Write-Host "=== monitor.pid ==="
if (Test-Path "$install\monitor.pid") {
    $pidVal = (Get-Content "$install\monitor.pid").Trim()
    Write-Host "PID escrito: $pidVal"
    $proc = Get-Process -Id ([int]$pidVal) -ErrorAction SilentlyContinue
    if ($proc) {
        Write-Host "Status: ATIVO"
    } else {
        Write-Host "Status: MORTO (processo nao existe mais)"
    }
} else {
    Write-Host "NENHUM PID ESCRITO!"
}

Write-Host "=== startup_error.log ==="
if (Test-Path $logFile) {
    $txt = [System.IO.File]::ReadAllText($logFile, [System.Text.Encoding]::UTF8)
    if ($txt.Trim().Length -gt 0) {
        Write-Host $txt
    } else {
        Write-Host "(log vazio - sem erro capturado)"
    }
} else {
    Write-Host "Log nao existe"
}

Write-Host "=== Processos monitor_bg ==="
Get-Process monitor_bg -ErrorAction SilentlyContinue | Select-Object Name, Id, StartTime | Format-Table -AutoSize
