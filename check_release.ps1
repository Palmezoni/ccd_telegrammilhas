$headers = @{
    "Authorization" = "Bearer $env:GITHUB_TOKEN"
    "Accept" = "application/vnd.github+json"
}
try {
    $r = Invoke-RestMethod -Uri "https://api.github.com/repos/Palmezoni/ccd_telegrammilhas/releases/tags/v1.0.0" -Headers $headers -ErrorAction Stop
    Write-Output "EXISTS"
    $r | ConvertTo-Json
} catch {
    Write-Output "NOT_FOUND"
    Write-Output $_.Exception.Message
}
