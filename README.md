# Telegram MTProto Monitor (Telethon)

Este projeto monitora um grupo do Telegram como **usuário** (MTProto — não é bot), aplica regras e pode responder automaticamente.

## 0) Pré-requisitos
- Windows
- Python 3.10+ (recomendado 3.11/3.12)

## 1) Criar credenciais Telegram (API_ID / API_HASH)
1. Acesse: https://my.telegram.org
2. Faça login com seu número.
3. Vá em **API development tools**.
4. Crie um app (qualquer nome).
5. Anote **API_ID** e **API_HASH**.

> Não cole essas credenciais em grupo/chat. Guarde localmente.

## 2) Instalar dependências
Abra **cmd** dentro desta pasta e rode:

```bat
py -m venv .venv
.venv\Scripts\pip install -U pip
.venv\Scripts\pip install -r requirements.txt
```

## 3) Configurar variáveis de ambiente
Copie o arquivo `.env.example` para `.env` e preencha.

## 4) Primeira execução (login)
```bat
.venv\Scripts\python monitor.py --dry-run
```
Ele vai pedir o código do Telegram (SMS/app) e possivelmente senha 2FA.

## 5) Ativar envio automático
Por segurança, o padrão é **DRY RUN**.
Quando quiser realmente responder no grupo:

```bat
.venv\Scripts\python monitor.py --send
```

## Regras implementadas
- LATAM: milhas/CPF >= 50.000 => responde (padrão) `25,00`
- SMILES: milhas/CPF > 60.000 => responde (padrão) `15,50`
- **Nunca responde com valor abaixo do valor ofertado no texto** (ex.: oferta 16,00 => responde 16,00)
- Delay antes de enviar: `SEND_DELAY_SECONDS` (padrão 2s)
- Case-insensitive
- Reconhece formatos tipo `94,2k`, `94.2K`, `94200`, `81.600k`
- Dedupe: responde 1 vez por oportunidade (hash do texto normalizado)

## Logs
- Saída no console
- `state.json` guarda os hashes já respondidos
