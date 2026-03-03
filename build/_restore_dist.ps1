$dist    = 'C:\Users\palme\ccd\ccd_telegrammilhas\dist\MilhasUP'
$base    = 'C:\Users\palme\ccd\ccd_telegrammilhas'
$install = 'C:\Users\palme\AppData\Local\Programs\Milhas UP Telegram Monitor'

Write-Host "Restaurando monitor_bg em dist..."
if (Test-Path "$dist\monitor_bg") { Remove-Item "$dist\monitor_bg" -Recurse -Force }
Copy-Item "$install\monitor_bg" "$dist\" -Recurse -Force
Write-Host "OK"

Write-Host "Restaurando .env.example..."
Copy-Item "$base\.env.example" "$dist\" -Force
Write-Host "OK"

Write-Host "Conteudo de $dist :"
Get-ChildItem $dist | Select-Object Name, LastWriteTime | Format-Table -AutoSize

Write-Host "Compilando instalador Inno Setup..."
& 'C:\Program Files (x86)\Inno Setup 6\ISCC.exe' "$base\build\setup.iss"
if ($LASTEXITCODE -eq 0) {
    $size = [Math]::Round((Get-Item "$base\dist\installer\MilhasUP_Setup_1.0.0.exe").Length / 1MB, 1)
    Write-Host ("Instalador gerado: $size MB")
} else {
    Write-Host "ERRO ao compilar instalador!"
}
