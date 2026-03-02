$install = 'C:\Users\palme\AppData\Local\Programs\Milhas UP Telegram Monitor'

Start-Sleep -Seconds 20
Write-Host "--- Status apos 20s ---"
$pidContent = Get-Content "$install\monitor.pid" -ErrorAction SilentlyContinue
$pidStr = if ($pidContent) { $pidContent.Trim() } else { "N/A" }
Write-Host "PID: $pidStr"
if ($pidStr -ne "N/A") {
    $proc = Get-Process -Id ([int]$pidStr) -ErrorAction SilentlyContinue
    if ($proc) { Write-Host "STATUS: VIVO!" } else { Write-Host "STATUS: MORTO" }
}
Write-Host ""
Write-Host "=== startup_error.log ==="
if (Test-Path "$install\startup_error.log") {
    [System.IO.File]::ReadAllText("$install\startup_error.log", [System.Text.Encoding]::UTF8)
} else {
    Write-Host "Nao existe"
}
Write-Host ""
Write-Host "=== Processos monitor_bg ==="
Get-Process monitor_bg -ErrorAction SilentlyContinue | Select-Object Name, Id, StartTime | Format-Table -AutoSize
