$install = 'C:\Users\palme\AppData\Local\Programs\Milhas UP Telegram Monitor'
$base    = 'C:\Users\palme\ccd\ccd_telegrammilhas'

Write-Host "=== Arquivos de sessao ==="
Get-ChildItem $install | Where-Object { $_.Name -like 'session*' } |
    Select-Object Name, LastWriteTime, @{N='KB';E={[Math]::Round($_.Length/1KB,1)}} |
    Format-Table -AutoSize

Write-Host "=== Testando sessao com Python ==="
$py = "$base\.venv\Scripts\python.exe"
& $py -c "
import sys, os
sys.path.insert(0, r'$base')
os.chdir(r'$install')
from dotenv import load_dotenv
load_dotenv(r'$install\.env', override=True)
from telethon.sync import TelegramClient
api_id   = int(os.environ['TG_API_ID'])
api_hash = os.environ['TG_API_HASH']
sess = r'$install\session'
print(f'Testando sessao: {sess}.session')
with TelegramClient(sess, api_id, api_hash) as c:
    authorized = c.is_user_authorized()
    print(f'is_user_authorized: {authorized}')
    if authorized:
        me = c.get_me()
        print(f'Logado como: {me.first_name} ({me.phone})')
    else:
        print('SESSAO INVALIDA - precisa re-autenticar')
" 2>&1
