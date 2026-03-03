$install = 'C:\Users\palme\AppData\Local\Programs\Milhas UP Telegram Monitor'

Write-Host "=== monitor.pid ==="
$pidFile = "$install\monitor.pid"
if (Test-Path $pidFile) {
    $pidVal = (Get-Content $pidFile).Trim()
    Write-Host "PID: $pidVal"
    if ($pidVal) {
        $proc = Get-Process -Id ([int]$pidVal) -ErrorAction SilentlyContinue
        if ($proc) {
            Write-Host "Status: RODANDO ($($proc.ProcessName))"
        } else {
            Write-Host "Status: MORTO (PID $pidVal nao existe)"
        }
        # Teste do os.kill equivalente — tenta OpenProcess
        try {
            $kernel32 = [System.Runtime.InteropServices.Marshal]::GetDelegateForFunctionPointer(
                [System.Runtime.InteropServices.Marshal]::GetFunctionPointerForDelegate({}), [System.Delegate])
        } catch { }
    }
} else {
    Write-Host "Arquivo nao existe!"
}

Write-Host "`n=== monitor.lock ==="
if (Test-Path "$install\monitor.lock") { Write-Host "Existe" } else { Write-Host "Nao existe" }

Write-Host "`n=== Processos Python/monitor_bg ==="
Get-Process python, monitor_bg -ErrorAction SilentlyContinue |
    Select-Object Name, Id, StartTime, CPU | Format-Table -AutoSize
