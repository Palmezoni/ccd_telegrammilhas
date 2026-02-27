# Produto — Monitor de Milhas Telegram

## O que é

Ferramenta que monitora grupos do Telegram dedicados à compra e venda de milhas aéreas. Quando alguém posta uma oferta de venda que atende aos critérios configurados (preço por CPF), o sistema **responde automaticamente** no grupo com o valor de compra.

Funciona como se o usuário estivesse online 24h monitorando os grupos — mas de forma automática e configurável.

---

## Como funciona na prática

Um vendedor posta no grupo:
```
compro 94,2k latam 2 cpf 15,00
```

O sistema detecta:
- Programa: **LATAM**
- Milhas totais: **94.200**
- CPFs: **2**
- Milhas por CPF: **47.100** (94.200 ÷ 2)
- Preço ofertado: **R$ 15,00**

Avalia a regra LATAM:
- Threshold: **50.000/CPF** (padrão)
- 47.100 < 50.000 → **não elegível**, não responde

Outro exemplo elegível:
```
compro 106k latam 2 cpf 15,00
```
- Milhas/CPF: **53.000** ≥ 50.000 → **elegível**
- Regra diz `25,00`, oferta diz `15,00` → responde **`25,00`**

Outro exemplo com oferta acima da regra:
```
compro 106k latam 2 cpf 26,00
```
- Elegível → nunca responde abaixo da oferta → responde **`26,00`**

---

## Regras de Negócio

### Programas monitorados

| Programa | Condição de elegibilidade | Resposta padrão |
|----------|--------------------------|-----------------|
| LATAM    | milhas/CPF **≥** 50.000  | `25,00`         |
| SMILES   | milhas/CPF **>** 60.000  | `15,50`         |

> LATAM usa `>=` (maior ou igual). SMILES usa `>` (estritamente maior).

### Cap de milhas totais

Ignora ofertas com milhas totais acima do limite (evita reagir a posts de estoque/inventário):

| Programa | Limite padrão |
|----------|---------------|
| SMILES   | 113.700       |
| LATAM    | 800.000       |

Configurável via `.env`. Setar `0` para desabilitar o limite.

### Preço mínimo de resposta

O sistema **nunca responde com valor abaixo do ofertado** no texto. Se a oferta é `R$26,00` e a regra é `25,00`, responde `26,00`.

### Delay anti-spam

Aguarda `SEND_DELAY_SECONDS` (padrão 2s) antes de enviar. Simula latência humana — admins de grupos detectam respostas instantâneas.

### Deduplicação

Cada oportunidade é respondida **apenas uma vez**, mesmo que a mensagem apareça em múltiplos grupos ou o monitor seja reiniciado. O hash da oferta é salvo em `state.json`.

---

## Configuração das Regras (`.env`)

```env
# Thresholds (milhas/CPF)
LATAM_THRESHOLD_PER_CPF=50000
SMILES_THRESHOLD_PER_CPF=60000

# Preços de resposta
LATAM_REPLY=25,00
SMILES_REPLY=15,50

# Caps de milhas totais (0 = sem limite)
SMILES_MAX_MILES=113700
LATAM_MAX_MILES=800000

# Delay antes de enviar (segundos)
SEND_DELAY_SECONDS=2
```

Para alterar qualquer regra: edite o `.env` e **reinicie o monitor** (`stop-monitor.cmd` + `run-monitor.cmd`).

---

## Ativar e Desativar o Monitor

### Ativar
```bat
run-monitor.cmd
```
Roda em background (sem janela). Confirmação visual: verifique via `status-monitor.cmd`.

### Desativar
```bat
stop-monitor.cmd
```
Lê o PID do `monitor.lock` e encerra o processo.

### Ver status
```bat
status-monitor.cmd
```
Mostra se está rodando e qual o PID.

> **Dica:** crie atalhos desses três arquivos na área de trabalho ou fixe na barra de tarefas para acesso com um duplo clique.

---

## Modo Seguro (Dry Run)

Por padrão, `DRY_RUN=1` no `.env`. O monitor **detecta ofertas e loga, mas não envia nada**.

Útil para validar configuração sem risco de enviar mensagens.

`run-monitor.cmd` já usa `--send`, então quando rodado normalmente, os envios estão ativos.

Para testar sem enviar:
```bat
.venv\Scripts\python monitor.py --dry-run
```

---

## Monitorar Atividade

### Ver últimos eventos
```bat
.venv\Scripts\python tail_events.py
```
Mostra os últimos 10 registros do `events.jsonl`.

### Acompanhar ao vivo (PowerShell)
```powershell
Get-Content events.jsonl -Wait -Tail 10
```

### Contar respostas enviadas hoje
```powershell
Get-Content events.jsonl | ConvertFrom-Json | Where-Object { $_.kind -eq "send_result" } | Measure-Object
```

---

## Notificação via Telegram

Configure `TG_NOTIFY_TARGET=me` no `.env` para receber uma mensagem no **Saved Messages** a cada resposta enviada:

```
[AUTO] LATAM | 106000/2 = 53000/CPF | offer=15,00 | reply 25,00 via reply | group: Grupo XYZ | from: João Silva
```

Outros valores válidos: `@username` ou ID numérico de outro chat/grupo.

---

## Relay para WhatsApp (OpenClaw)

Quando `WHATSAPP_RELAY=1`, cada resposta enviada gera um registro em `whatsapp-events.jsonl`. O serviço OpenClaw consome essa fila e encaminha a notificação para o WhatsApp.

Campos enviados: programa, grupo, vendedor, milhas, CPFs, preço ofertado, preço respondido.

---

## Grupos Monitorados

Configure em `TG_TARGETS` (separados por vírgula). Aceita:
- **Nome do grupo** (título exato ou parcial, case-insensitive): `Milhas LATAM Premium`
- **@username**: `@milhaslatam`
- **ID numérico**: `-1001234567890`

Exemplo:
```env
TG_TARGETS=Grupo Milhas A,Grupo Milhas B,@milhasoficiais
```

---

## Auto-start com Windows (Task Scheduler)

Para iniciar automaticamente com o Windows:

1. Abra **Agendador de Tarefas** (`taskschd.msc`)
2. Criar Tarefa Básica → nome: `Monitor Milhas`
3. Disparar: **Ao fazer logon**
4. Ação: **Iniciar um programa**
   - Programa: `cmd.exe`
   - Argumentos: `/c "C:\Users\palme\ccd\ccd_telegrammilhas\run-monitor.cmd"`
5. Em Condições: desmarque "Iniciar somente com energia CA"
6. Em Configurações: marque "Se a tarefa já estiver em execução, a nova instância não será iniciada"

> O lock de instância única em `monitor.lock` garante que mesmo se o scheduler disparar duas vezes, apenas um processo roda.

---

## Primeiro Setup (do zero)

```bat
rem 1. Criar virtualenv
py -m venv .venv

rem 2. Instalar dependências
.venv\Scripts\pip install -U pip
.venv\Scripts\pip install -r requirements.txt

rem 3. Configurar
copy .env.example .env
rem  → editar .env com API_ID, API_HASH, TG_PHONE, TG_TARGETS

rem 4. Login (primeira vez)
.venv\Scripts\python monitor.py --dry-run
rem  → informar código SMS/app e senha 2FA se necessário

rem 5. Ativar
run-monitor.cmd
```

---

## Troubleshooting

| Sintoma | Causa provável | Solução |
|---------|---------------|---------|
| Monitor não inicia | Outro processo rodando | `stop-monitor.cmd` antes |
| Não detecta ofertas | Grupo não está em `TG_TARGETS` | Verificar nome exato no `.env` |
| Detecta mas não responde | `DRY_RUN=1` e sem `--send` | Verificar `.env` + `run-monitor.cmd` |
| Responde duplicado | Dois processos rodando | `stop-monitor.cmd` e reiniciar |
| Sessão expirada | `session.session` inválida | Deletar `session.session` e re-autenticar |
| Preço errado na resposta | Regra abaixo da oferta do texto | Normal — sistema usa `max(regra, oferta)` |
