$dist    = 'C:\Users\palme\ccd\ccd_telegrammilhas\dist\MilhasUP'
$install = 'C:\Users\palme\AppData\Local\Programs\Milhas UP Telegram Monitor'

Write-Host "=== dist\MilhasUP ==="
Get-ChildItem $dist | Select-Object Name, LastWriteTime | Format-Table -AutoSize

Write-Host "=== monitor_bg na dist ==="
if (Test-Path "$dist\monitor_bg") {
    Get-ChildItem "$dist\monitor_bg" | Select-Object Name | Format-Table -AutoSize
} else {
    Write-Host "AUSENTE — precisa restaurar do install dir"
    Write-Host "Restaurando..."
    Copy-Item "$install\monitor_bg" "$dist\" -Recurse -Force
    Write-Host "Restaurado."
}

Write-Host "=== .env.example na dist ==="
if (Test-Path "$dist\.env.example") {
    Write-Host "OK"
} else {
    Write-Host "AUSENTE — copiando do install dir"
    Copy-Item "$install\.env.example" "$dist\" -Force -ErrorAction SilentlyContinue
    if (Test-Path "$dist\.env.example") { Write-Host "Restaurado." } else { Write-Host "Nao encontrado no install dir tambem." }
}
