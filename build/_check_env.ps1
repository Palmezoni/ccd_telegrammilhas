$install = 'C:\Users\palme\AppData\Local\Programs\Milhas UP Telegram Monitor'
$envFile = "$install\.env"

Write-Host "=== .env da instalacao ==="
if (Test-Path $envFile) {
    $lines = Get-Content $envFile
    foreach ($line in $lines) {
        $s = $line.Trim()
        if ($s -eq '' -or $s.StartsWith('#')) { continue }
        # Mascarar valores sensiveis
        if ($s -match '^(TG_API_HASH|TG_API_ID|TG_PHONE|TG_TARGETS)\s*=\s*(.+)$') {
            $key = $Matches[1]
            $val = $Matches[2]
            if ($val.Length -gt 0) {
                Write-Host "$key = [DEFINIDO - $($val.Length) chars]"
            } else {
                Write-Host "$key = [VAZIO!]"
            }
        } else {
            Write-Host $line
        }
    }
} else {
    Write-Host "ARQUIVO .env NAO ENCONTRADO!"
}

Write-Host ""
Write-Host "=== Verificando variaveis criticas ==="
$env_content = Get-Content $envFile -Raw -ErrorAction SilentlyContinue
$vars = @('TG_API_ID','TG_API_HASH','TG_PHONE','TG_TARGETS')
foreach ($v in $vars) {
    if ($env_content -match "(?m)^$v\s*=\s*(.+)$") {
        $val = $Matches[1].Trim()
        if ($val -eq '') {
            Write-Host "$v : VAZIO!"
        } else {
            Write-Host "$v : OK ($($val.Length) chars)"
        }
    } else {
        Write-Host "$v : NAO ENCONTRADO!"
    }
}
