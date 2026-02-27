"""
Smoke-test das regras e parsing sem conectar ao Telegram.
Executa: .venv\Scripts\python test_rules.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '.env'), override=True)

from monitor import (
    parse_miles, parse_cpfs, detect_program,
    parse_offer_price_cents, format_price_cents,
    compute_per_cpf, norm_text
)

# --- regras carregadas do .env ---
LATAM_THRESH  = int(os.getenv('LATAM_THRESHOLD_PER_CPF', '50000'))
SMILES_THRESH = int(os.getenv('SMILES_THRESHOLD_PER_CPF', '27000'))
LATAM_REPLY   = os.getenv('LATAM_REPLY', '25,00')
SMILES_REPLY  = os.getenv('SMILES_REPLY', '16,00')
SMILES_MAX    = int(os.getenv('SMILES_MAX_MILES', '675000') or '0')
LATAM_MAX     = int(os.getenv('LATAM_MAX_MILES', '194000') or '0')

def reply_cents(rule_reply_str):
    import re
    m = re.fullmatch(r"(\d{1,2}),(\d{2})", rule_reply_str.strip())
    return int(m.group(1)) * 100 + int(m.group(2)) if m else None

LATAM_REPLY_CENTS  = reply_cents(LATAM_REPLY)
SMILES_REPLY_CENTS = reply_cents(SMILES_REPLY)

def evaluate(text):
    tnorm = norm_text(text)
    program = detect_program(tnorm)
    if not program:
        return None, "programa nao detectado"

    miles = parse_miles(text)
    cpfs  = parse_cpfs(text)
    if miles is None:
        return None, "milhas nao detectadas"
    if cpfs is None or cpfs <= 0:
        return None, "CPFs nao detectados"

    if program == 'SMILES' and SMILES_MAX and miles > SMILES_MAX:
        return None, f"SMILES acima do cap ({miles} > {SMILES_MAX})"
    if program == 'LATAM' and LATAM_MAX and miles > LATAM_MAX:
        return None, f"LATAM acima do cap ({miles} > {LATAM_MAX})"

    per_cpf = compute_per_cpf(miles, cpfs)
    thresh = LATAM_THRESH if program == 'LATAM' else SMILES_THRESH
    op     = ">=" if program == 'LATAM' else ">"
    eligible = (per_cpf >= thresh) if program == 'LATAM' else (per_cpf > thresh)
    if not eligible:
        return None, f"{program} {per_cpf}/CPF nao atinge threshold {thresh} ({op})"

    offer_cents  = parse_offer_price_cents(text)
    rule_cents   = LATAM_REPLY_CENTS if program == 'LATAM' else SMILES_REPLY_CENTS
    final_cents  = max(rule_cents, offer_cents) if offer_cents is not None else rule_cents
    reply        = format_price_cents(final_cents)

    return reply, f"{program} {miles}/{cpfs}={per_cpf}/CPF | oferta={format_price_cents(offer_cents) if offer_cents else '?'} | resposta={reply}"

# ── CASOS DE TESTE ─────────────────────────────────────────────────────────────
# (mensagem, resposta_esperada_ou_None)
cases = [
    # LATAM - elegíveis
    ("compro 100k latam 2 cpf 14,00",          "25,00"),   # 50k/cpf >= 50k OK
    ("compro latam 110k 2 cpf",                "25,00"),   # sem preço → usa regra
    ("compro 194.000 latam 2 cpf 20,00",       "25,00"),   # exatamente no cap
    ("LATAM 55k 1 cpf 26,00",                  "26,00"),   # oferta > regra → usa oferta
    # LATAM - não elegíveis
    ("compro 80k latam 2 cpf 15,00",            None),     # 40k/cpf < 50k
    ("compro 200k latam 2 cpf",                 None),     # 200k > cap 194k
    # SMILES - elegíveis
    ("smiles 81.600 3 cpf 15,00",              "16,00"),   # 27200/cpf > 27k OK
    ("compro 94,2k smiles 3 cpf 15,50",        "16,00"),   # 31400/cpf > 27k
    ("smiles 675k 2 cpf 14,00",                "16,00"),   # exatamente no cap
    ("SMILES 30k 1 cpf 17,00",                 "17,00"),   # oferta > regra
    # SMILES - não elegíveis
    ("compro 54k smiles 2 cpf",                 None),     # 27k/cpf não é > 27k (threshold estrito)
    ("smiles 700k 1 cpf 15,00",                 None),     # 700k > cap 675k
    # Formatos variados de milhas
    ("latam 106,8 2 cpf 20,00",               "25,00"),   # 106800 → 53400/cpf
    ("latam 37.800K 1 cpf 14,00",               None),     # 37800K = 37.800 (K redundante) → 37800/CPF < 50k
    ("latam 94.200 2 cpf 22,00",               None),     # 94200/2 = 47100/CPF < 50k
    # Sem programa identificado
    ("vendo milhas 50k 1 cpf",                  None),
    ("compro azul 50k 1 cpf",                   None),
]

VERDE = "\033[92m"
VERM  = "\033[91m"
RESET = "\033[0m"
ok = err = 0

print(f"\nRegras carregadas:")
print(f"  LATAM:  threshold={LATAM_THRESH}/CPF  reply={LATAM_REPLY}  max={LATAM_MAX}")
print(f"  SMILES: threshold={SMILES_THRESH}/CPF  reply={SMILES_REPLY}  max={SMILES_MAX}")
print(f"\n{'─'*72}")

for msg, expected in cases:
    result, detail = evaluate(msg)
    passed = result == expected
    icon = "✓" if passed else "✗"
    color = VERDE if passed else VERM
    exp_str = f'"{expected}"' if expected else "None"
    got_str = f'"{result}"'   if result   else "None"
    status = "OK" if passed else f"ESPERADO {exp_str} GOT {got_str}"
    print(f"{color}{icon} {status:30s}{RESET}  {detail}")
    print(f"   msg: {msg!r}")
    if passed: ok  += 1
    else:      err += 1

print(f"\n{'─'*72}")
print(f"Resultado: {ok} OK  |  {err} FALHAS")
if err:
    sys.exit(1)
