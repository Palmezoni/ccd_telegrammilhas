$desk  = [System.Environment]::GetFolderPath('Desktop')
$local = [System.Environment]::GetFolderPath('LocalApplicationData')

# Atalho desktop
$lnk = "$desk\Milhas UP Telegram Monitor.lnk"
Write-Host "Atalho desktop: $(if (Test-Path $lnk) { 'EXISTE — ' + $lnk } else { 'NAO EXISTE' })"

# Possíveis pastas de instalação
$candidates = @(
    "$local\Milhas UP Telegram Monitor",
    "$local\Programs\Milhas UP Telegram Monitor"
)
foreach ($p in $candidates) {
    if (Test-Path $p) {
        Write-Host "`nPasta encontrada: $p"
        Get-ChildItem $p -ErrorAction SilentlyContinue |
            Select-Object Name, @{N='Tamanho';E={ if ($_.Length) { "$([math]::Round($_.Length/1KB))KB" } else { "<dir>" } }} |
            Format-Table -AutoSize
    }
}

# Menu iniciar
$startMenu = [System.Environment]::GetFolderPath('StartMenu')
$sm = "$startMenu\Programs\Milhas UP Telegram Monitor"
Write-Host "Menu Iniciar: $(if (Test-Path $sm) { 'EXISTE — ' + $sm } else { 'NAO EXISTE' })"
