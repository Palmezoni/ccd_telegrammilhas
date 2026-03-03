$headers = @{
    "Authorization" = "Bearer $env:GITHUB_TOKEN"
    "Accept" = "application/vnd.github+json"
    "Content-Type" = "application/json"
}
$body = @{
    tag_name = "v1.0.0"
    name = "MilhasUP Monitor v1.0.0"
    body = "Primeira versao estavel do MilhasUP Monitor.`n`n**Como instalar:**`n1. Baixe o arquivo ``MilhasUP_Setup_1.0.0.exe`` abaixo`n2. Execute o instalador`n3. Siga o assistente de configuracao`n`n**Requisitos:** Windows 10/11"
    draft = $false
    prerelease = $false
} | ConvertTo-Json

$r2 = Invoke-RestMethod -Uri "https://api.github.com/repos/Palmezoni/ccd_telegrammilhas/releases" -Method POST -Headers $headers -Body $body
Write-Output "Release created. ID: $($r2.id)"
Write-Output "Upload URL: $($r2.upload_url)"
$r2 | ConvertTo-Json
