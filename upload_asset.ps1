$uploadUrl = "https://uploads.github.com/repos/Palmezoni/ccd_telegrammilhas/releases/292362709/assets?name=MilhasUP_Setup_1.0.0.exe"
$fileBytes = [System.IO.File]::ReadAllBytes("C:\Users\palme\ccd\ccd_telegrammilhas\build\dist\MilhasUP_Setup_1.0.0.exe")
Write-Output "File size: $($fileBytes.Length) bytes"
$uploadResult = Invoke-RestMethod -Uri $uploadUrl -Method POST -Headers @{
    "Authorization" = "Bearer $env:GITHUB_TOKEN"
    "Content-Type" = "application/octet-stream"
} -Body $fileBytes
Write-Output "Upload complete!"
$uploadResult | ConvertTo-Json -Depth 5
