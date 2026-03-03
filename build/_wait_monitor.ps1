Write-Host "Aguardando monitor_bg iniciar (max 40s)..."
for ($i = 0; $i -lt 20; $i++) {
    $proc = Get-Process monitor_bg -ErrorAction SilentlyContinue
    if ($proc) {
        Write-Host ("OK! monitor_bg RODANDO, PID=" + $proc.Id)
        $pidFile = 'C:\Users\palme\AppData\Local\Programs\Milhas UP Telegram Monitor\monitor.pid'
        if (Test-Path $pidFile) {
            Write-Host ("monitor.pid = " + (Get-Content $pidFile -Raw).Trim())
        }
        exit 0
    }
    Start-Sleep -Seconds 2
    Write-Host ("Aguardando... (" + ($i+1) + "/20)")
}
Write-Host "monitor_bg nao iniciou no tempo esperado."
Write-Host "(Verifique se clicou em Iniciar Monitor na GUI)"
exit 1
