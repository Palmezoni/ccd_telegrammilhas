$out = "$env:TEMP\innosetup.exe"
Write-Host "Instalando Inno Setup..."
Start-Process -FilePath $out -ArgumentList '/VERYSILENT /SUPPRESSMSGBOXES /NORESTART' -Wait
$iscc = "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if (Test-Path $iscc) {
    Write-Host "Inno Setup instalado: $iscc"
} else {
    Write-Host "Verificando outros locais..."
    Get-ChildItem "C:\Program Files (x86)\" -ErrorAction SilentlyContinue | Where-Object { $_.Name -like "*Inno*" }
    Get-ChildItem "C:\Program Files\" -ErrorAction SilentlyContinue | Where-Object { $_.Name -like "*Inno*" }
}
