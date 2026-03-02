$dist    = 'C:\Users\palme\ccd\ccd_telegrammilhas\dist'
$install = 'C:\Users\palme\AppData\Local\Programs\Milhas UP Telegram Monitor'

Write-Host "Copiando MilhasUP.exe..."
Copy-Item "$dist\MilhasUP\MilhasUP.exe" "$install\" -Force

Write-Host "Removendo _internal antigo..."
if (Test-Path "$install\_internal") { Remove-Item "$install\_internal" -Recurse -Force }

Write-Host "Copiando _internal novo..."
Copy-Item "$dist\MilhasUP\_internal" "$install\" -Recurse -Force

Write-Host "Pronto! Arquivos atualizados."
