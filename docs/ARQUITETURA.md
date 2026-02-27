# Arquitetura — Monitor de Milhas Telegram

## Visão Geral

O sistema é um **processo Python assíncrono** que se conecta ao Telegram como usuário normal (protocolo MTProto, via Telethon), escuta mensagens em grupos configurados e responde automaticamente a ofertas de compra de milhas que atendam às regras de negócio.

```
┌───────────────────────────────────────────────────────────────┐
│  Telegram (grupos monitorados)                                │
│   mensagem: "compro 94,2k latam 2 cpf 15,00"                │
└───────────────────┬───────────────────────────────────────────┘
                    │ MTProto (Telethon)
                    ▼
┌───────────────────────────────────────────────────────────────┐
│  monitor.py                                                   │
│  ┌──────────┐  ┌───────────┐  ┌──────────────┐              │
│  │  parse   │→ │  evaluate │→ │  reply/log   │              │
│  └──────────┘  └───────────┘  └──────────────┘              │
│       │              │                │                       │
│  miles, cpfs,   threshold +       event.reply()              │
│  program,       dedup check       events.jsonl               │
│  offer_price                      whatsapp-events.jsonl      │
└───────────────────────────────────────────────────────────────┘
```

---

## Componentes

### `monitor.py` — Núcleo

Processo único, assíncrono (`asyncio`), orientado a eventos via `@client.on(events.NewMessage)`.

**Inicialização (`main()`):**
1. Carrega `.env` com caminho explícito (evita capturar `.env` de diretório pai)
2. Adquire lock de instância única (ver abaixo)
3. Resolve `TG_TARGETS` para entidades Telegram
4. Registra handler de mensagens
5. Aguarda desconexão (`run_until_disconnected`)

**Handler por mensagem:**
```
NewMessage
  → detect_program()     → LATAM | SMILES | None
  → parse_miles()        → int (94200) | None
  → parse_cpfs()         → int (2) | None
  → cap de milhas        → filtro por SMILES_MAX_MILES / LATAM_MAX_MILES
  → compute_per_cpf()    → int (47100)
  → threshold check      → eligible bool
  → dedup (SHA1)         → já respondido? skip
  → save_state()         → grava state.json
  → parse_offer_price()  → cents (1500) | None
  → calcular final_reply → max(rule_reply, offer_price)
  → [delay]              → SEND_DELAY_SECONDS (anti-spam)
  → event.reply(msg)     → resposta no grupo
  → append_event_log()   → events.jsonl
  → append_whatsapp_event() → whatsapp-events.jsonl
  → notify_target?       → mensagem de sumário (opcional)
```

---

### Parsing de Milhas (`parse_miles`)

Reconhece múltiplos formatos usados nos grupos:

| Formato | Interpretação |
|---------|---------------|
| `94,2k` / `94.2K` | 94.200 |
| `81.600K` | 81.600 (K redundante) |
| `81.600` / `81,600` | 81.600 (separador pt-BR) |
| `106,8` / `106.8` | 106.800 (shorthand: 2-3 dígitos + 1 decimal = ×1000) |
| `94200` | 94.200 (inteiro puro) |

**Prioridade de matching:** thousands+K > fracionário+K > thousands sem K > shorthand > inteiro puro.

---

### Lock de Instância Única (`monitor.lock`)

Usa `msvcrt.locking()` (Windows) para lock exclusivo não-bloqueante no arquivo `monitor.lock`.

- Se outro processo já detém o lock → exit imediato
- O PID do processo corrente é gravado no arquivo em texto puro
- O handle do arquivo é mantido aberto durante toda a vida do processo
- `stop-monitor.cmd` lê esse PID para matar o processo

```
monitor.lock:
  42137   ← PID do processo Python ativo
```

---

### Deduplicação (`state.json`)

Cada oportunidade respondida é registrada com uma chave SHA1:

```python
sha1(f"{program}|{chat_id}|{norm_text}|{miles}|{cpfs}|{per_cpf}")
```

- **Per-chat:** mesma oferta em grupos distintos gera respostas separadas
- **Persistente:** sobrevive a reinicializações
- **Write-safe:** gravado via arquivo temporário + `os.replace()` (atômico)

---

### Streams de Log (JSONL)

#### `events.jsonl` — Auditoria completa

Append-only. Dois tipos de registro:

```jsonc
// Quando threshold é atingido (antes de enviar)
{"ts":1709000000,"kind":"eligible","program":"LATAM","chat_title":"Grupo XYZ",
 "miles":94200,"cpfs":2,"per_cpf":47100,"offer_price_cents":1500,
 "final_reply":"25,00","dry_run":false,...}

// Após envio
{"ts":1709000001,"kind":"send_result","sent_via":"reply","error":null,...}
```

#### `whatsapp-events.jsonl` — Fila para OpenClaw

Produzido pelo monitor após cada envio real (quando `WHATSAPP_RELAY=1`). Consumido externamente pelo OpenClaw para encaminhar notificações ao WhatsApp.

```jsonc
{"ts":1709000001,"kind":"telegram_auto_reply","program":"LATAM",
 "group":"Grupo XYZ","msg_id":987654,"miles":94200,"cpfs":2,
 "per_cpf":47100,"offer":"15,00","reply":"25,00","sent_via":"reply"}
```

---

### Lógica de Resposta

```
final_reply = max(rule_reply_cents, offer_price_cents)
```

- Nunca responde abaixo do preço ofertado no texto
- Se oferta for `16,00` e regra for `25,00` → responde `25,00`
- Se oferta for `26,00` e regra for `25,00` → responde `26,00`
- Fallback: se `event.reply()` falhar, tenta `send_message()` direto ao chat

---

## Arquivos: Versionados vs Runtime

| Arquivo | Versionado? | Descrição |
|---------|------------|-----------|
| `monitor.py` | ✅ | Lógica principal |
| `requirements.txt` | ✅ | Dependências Python |
| `.env.example` | ✅ | Template de configuração |
| `.gitignore` | ✅ | Exclusões git |
| `run-monitor.cmd` | ✅ | Launcher (headless) |
| `stop-monitor.cmd` | ✅ | Parar monitor |
| `status-monitor.cmd` | ✅ | Verificar status |
| `tail_events.py` | ✅ | Utilitário de log |
| `deploy-to-prod.ps1` | ✅ | Script de deploy |
| `cleanup-workspace.ps1` | ✅ | Limpeza de artefatos |
| `docs/` | ✅ | Documentação |
| `.env` | ❌ | Segredos (API keys, telefone) |
| `session.session` | ❌ | Sessão Telethon (token de auth) |
| `state.json` | ❌ | Estado de dedup persistente |
| `events.jsonl` | ❌ | Log de auditoria |
| `whatsapp-events.jsonl` | ❌ | Fila de relay WhatsApp |
| `whatsapp-relay-state.json` | ❌ | Estado do relay |
| `monitor.lock` | ❌ | Lock de instância (efêmero) |
| `.venv/` | ❌ | Virtualenv Python |
| `logs/` | ❌ | Logs do processo headless |

---

## Dependências

```
telethon==1.36.0       # MTProto Telegram client (user mode)
python-dotenv==1.0.1   # Carregamento do .env
```

Python 3.10+. Recomendado 3.11/3.12 (suporte ativo).

---

## Fluxo de Deploy (repo → produção)

O `deploy-to-prod.ps1` copia apenas arquivos versionados para a pasta de produção (`../telegram-mtproto`), sem tocar em `.env`, sessão ou estado.

```
ccd_telegrammilhas/   ← git repo (source of truth)
  monitor.py
  deploy-to-prod.ps1
  ...

../telegram-mtproto/  ← pasta de produção (runtime)
  monitor.py          ← copiado pelo deploy
  .env                ← nunca tocado pelo deploy
  session.session     ← nunca tocado pelo deploy
  state.json          ← nunca tocado pelo deploy
  .venv/              ← nunca tocado pelo deploy
```

> **Nota:** quando o repo é usado diretamente como pasta de produção (setup simplificado), o `deploy-to-prod.ps1` não é necessário.

---

## Protocolo de Reinício Seguro

1. `stop-monitor.cmd` — mata o processo pelo PID do lock
2. Aguardar 2-3 segundos (Telethon fecha sessão)
3. `run-monitor.cmd` — reinicia

O `state.json` é preservado entre reinícios — não haverá respostas duplicadas.
