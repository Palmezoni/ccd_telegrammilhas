$paths = @(
    "C:\Program Files\Milhas UP Telegram Monitor",
    "C:\Program Files (x86)\Milhas UP Telegram Monitor",
    "$env:LOCALAPPDATA\Programs\Milhas UP Telegram Monitor",
    "$env:APPDATA\Milhas UP Telegram Monitor"
)
foreach ($p in $paths) {
    if (Test-Path $p) {
        Write-Host "ENCONTRADO: $p"
        Get-ChildItem $p -ErrorAction SilentlyContinue | Format-Table Name, Length
    } else {
        Write-Host "NAO existe: $p"
    }
}

# Verifica registro HKCU (instalacao de usuario)
$reg = Get-ItemProperty "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*" -ErrorAction SilentlyContinue |
    Where-Object { $_.DisplayName -like "*Milhas*" }
if ($reg) {
    Write-Host "Registro HKCU: $($reg.InstallLocation)"
} else {
    Write-Host "Nao encontrado no registro HKCU"
}

# Verifica HKLM tambem
$reg2 = Get-ItemProperty "HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*" -ErrorAction SilentlyContinue |
    Where-Object { $_.DisplayName -like "*Milhas*" }
if ($reg2) {
    Write-Host "Registro HKLM: $($reg2.InstallLocation)"
} else {
    Write-Host "Nao encontrado no registro HKLM"
}
