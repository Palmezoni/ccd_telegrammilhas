$install = 'C:\Users\palme\AppData\Local\Programs\Milhas UP Telegram Monitor'
$base    = 'C:\Users\palme\ccd\ccd_telegrammilhas'
$python  = "$base\.venv\Scripts\python.exe"

# Garante sem lock antigo
Remove-Item "$install\monitor.pid"  -ErrorAction SilentlyContinue
Remove-Item "$install\monitor.lock" -ErrorAction SilentlyContinue

Write-Host "=== Rodando monitor.py direto (com .env da instalacao) ==="
Write-Host "(Ctrl+C para sair)`n"

# Rode com o CWD = pasta de instalacao (onde esta o .env e session.session)
& $python "$base\monitor.py" 2>&1
