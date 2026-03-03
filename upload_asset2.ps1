$uploadUrl = "https://uploads.github.com/repos/Palmezoni/ccd_telegrammilhas/releases/292362709/assets?name=MilhasUP_Setup_1.0.0.exe"
$filePath = "C:\Users\palme\ccd\ccd_telegrammilhas\dist\installer\MilhasUP_Setup_1.0.0.exe"
$fileInfo = Get-Item $filePath
Write-Output "File size: $($fileInfo.Length) bytes ($([math]::Round($fileInfo.Length/1MB,2)) MB)"
$fileBytes = [System.IO.File]::ReadAllBytes($filePath)
$uploadResult = Invoke-RestMethod -Uri $uploadUrl -Method POST -Headers @{
    "Authorization" = "Bearer $env:GITHUB_TOKEN"
    "Content-Type" = "application/octet-stream"
} -Body $fileBytes
Write-Output "Upload complete!"
Write-Output "Download URL: $($uploadResult.browser_download_url)"
$uploadResult | ConvertTo-Json -Depth 5
