$install = 'C:\Users\palme\AppData\Local\Programs\Milhas UP Telegram Monitor'
$pidFile  = Join-Path $install 'monitor.pid'
$lockFile = Join-Path $install 'monitor.lock'

if (Test-Path $pidFile) {
    $pidVal = (Get-Content $pidFile -Raw).Trim()
    Write-Host "monitor.pid: $pidVal"
    if ($pidVal) {
        $proc = Get-Process -Id ([int]$pidVal) -ErrorAction SilentlyContinue
        if ($proc) { Write-Host "  -> ATIVO (PID $pidVal)" }
        else { Write-Host "  -> morto (PID $pidVal nao existe)" }
    }
} else {
    Write-Host "monitor.pid: nao existe"
}

if (Test-Path $lockFile) { Write-Host "monitor.lock: existe" }
else { Write-Host "monitor.lock: nao existe" }

Write-Host "`n--- Processos monitor_bg ---"
Get-Process monitor_bg -ErrorAction SilentlyContinue | Select-Object Name, Id, StartTime | Format-Table -AutoSize

Write-Host "--- Processos MilhasUP ---"
Get-Process MilhasUP -ErrorAction SilentlyContinue | Select-Object Name, Id, StartTime | Format-Table -AutoSize
