import os
import re
import json
import time
import hashlib
import argparse
import sys
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

# Force UTF-8 output on Windows consoles to avoid crashes on emojis/special chars in names.
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

from telethon import TelegramClient, events
from telethon.errors import SessionPasswordNeededError
from dotenv import load_dotenv

STATE_PATH = os.path.join(os.path.dirname(__file__), 'state.json')
EVENTS_LOG_PATH = os.path.join(os.path.dirname(__file__), 'events.jsonl')
WHATSAPP_EVENTS_PATH = os.path.join(os.path.dirname(__file__), 'whatsapp-events.jsonl')
LOCK_PATH = os.path.join(os.path.dirname(__file__), 'monitor.lock')
PID_PATH = os.path.join(os.path.dirname(__file__), 'monitor.pid')

@dataclass
class Rule:
    program: str  # 'LATAM' or 'SMILES'
    threshold_per_cpf: int
    reply: str

K_MULTIPLIER = 1000

def load_state():
    if not os.path.exists(STATE_PATH):
        return {"seen": {}}
    with open(STATE_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_state(state):
    tmp = STATE_PATH + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    os.replace(tmp, STATE_PATH)

def append_event_log(obj: dict):
    # JSONL for easy tail/grep.
    with open(EVENTS_LOG_PATH, 'a', encoding='utf-8') as f:
        f.write(json.dumps(obj, ensure_ascii=False) + '\n')

def append_whatsapp_event(obj: dict):
    # Separate JSONL stream for WhatsApp relay.
    with open(WHATSAPP_EVENTS_PATH, 'a', encoding='utf-8') as f:
        f.write(json.dumps(obj, ensure_ascii=False) + '\n')

def norm_text(s: str) -> str:
    s = s.strip()
    s = re.sub(r"\s+", " ", s)
    return s.lower()

def acquire_single_instance_lock():
    """Prevent multiple instances (avoids Telethon sqlite session lock + double replies).

    Uses a simple Windows-friendly file lock. Keep the file handle open for the process lifetime.
    """
    try:
        import msvcrt
        fh = open(LOCK_PATH, 'a+', encoding='utf-8')
        try:
            msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            # Another instance holds the lock.
            try:
                fh.close()
            except Exception:
                pass
            return None
        fh.seek(0)
        fh.truncate(0)
        fh.write(str(os.getpid()))
        fh.flush()
        # Write PID to a separate readable file (monitor.lock is byte-locked and unreadable
        # by external tools like status-monitor.cmd).
        try:
            with open(PID_PATH, 'w', encoding='utf-8') as pf:
                pf.write(str(os.getpid()))
        except Exception:
            pass
        return fh
    except Exception:
        # If locking isn't available for some reason, fail open (keep behavior).
        return 'noop'

def sha1(s: str) -> str:
    return hashlib.sha1(s.encode('utf-8')).hexdigest()

def parse_miles(text: str):
    """Returns miles as int or None.

    Accepts:
    - 94,2k / 94.2k / 94,2 K
    - 81.600 (pt-BR thousand separator)
    - 37.800K (common redundant "K"; interpret as 37,800)
    - 94200
    """
    t = text.lower()

    # Patterns like 81.600k or 81,600k (pt-BR thousands separators).
    # In these groups, people often write the thousands-separated number AND add a trailing "k" redundantly.
    # Example: "37.800K" usually means 37,800 (not 37,800,000).
    # So for "\d{1,3}([.,]\d{3})+k" we interpret as the plain thousands-separated integer (NO extra x1000).
    m = re.search(r"\b(\d{1,3}(?:[\.,]\d{3})+)\s*[kK]\b", text)
    if m:
        num = m.group(1)
        num = num.replace('.', '').replace(',', '')
        try:
            return int(num)
        except ValueError:
            pass

    # 2) capture "94,2k" / "94.2k" and also "94,2 k"
    m = re.search(r"\b(\d+)([\.,](\d+))?\s*[kK]\b", text)
    if m:
        whole = m.group(1)
        frac = m.group(3)
        if frac:
            # 94,2k => 94.2 * 1000
            val = float(f"{whole}.{frac}")
            return int(round(val * K_MULTIPLIER))
        return int(whole) * K_MULTIPLIER

    # 3) capture thousand-separated numbers without 'k' (e.g. 160,134 or 160.134)
    m = re.search(r"\b(\d{1,3}(?:[\.,]\d{3})+)\b", text)
    if m:
        num = m.group(1).replace('.', '').replace(',', '')
        try:
            return int(num)
        except ValueError:
            pass

    # 4) heuristic: formats like "106,8" / "106.8" used as shorthand for "106,8k" in these groups.
    # We treat 2-3 digits + 1 decimal digit as thousands (x1000). This avoids matching prices like 14,50.
    m = re.search(r"\b(\d{2,3})[\.,](\d)\b", text)
    if m:
        whole = int(m.group(1))
        frac = int(m.group(2))
        # 106,8 => 106.8k => 106800
        return whole * 1000 + frac * 100

    # 5) plain integer like 94200 or 101512
    m = re.search(r"\b(\d{4,})\b", text)
    if m:
        try:
            return int(m.group(1))
        except ValueError:
            pass

    return None

def parse_cpfs(text: str):
    """Returns cpf count as int or None.

    Accepts: '1 cpf', '2 cpfs', '10 cpf', '3CPF', '3 cpf.'
    """
    # Accept: cpf, cpfs, cpf's, cpf’s, CPF, etc.
    m = re.search(r"\b(\d{1,2})\s*cpf(?:s|['’]s)?\b", text, re.IGNORECASE)
    if not m:
        return None
    try:
        n = int(m.group(1))
        return n if n > 0 else None
    except ValueError:
        return None

def parse_offer_price_cents(text: str):
    """Best-effort: parse the offered price from the message.

    We assume the offer is a money price like 15,00 / 16.50 / 25,00.
    Returns cents as int or None.

    Notes:
    - We only match 2 decimal digits to avoid conflicting with miles shorthand like 106,8.
    - If multiple prices appear, we pick the FIRST match (can be refined later).
    """
    # Optional currency markers (R$, rs, etc.), but not required.
    m = re.search(r"\b(?:r\$\s*)?(\d{1,2})[\.,](\d{2})\b", text, re.IGNORECASE)
    if not m:
        return None
    try:
        reais = int(m.group(1))
        cents = int(m.group(2))
        if reais < 0 or cents < 0 or cents > 99:
            return None
        return reais * 100 + cents
    except ValueError:
        return None

def format_price_cents(cents: int) -> str:
    reais = int(cents // 100)
    c = int(cents % 100)
    return f"{reais},{c:02d}"

def detect_program(text: str):
    """Detects the loyalty program mentioned in the message.

    Be permissive: in groups people write variations like "smile", "smiles", "latam", "tam".
    """
    t = text.lower()
    if 'latam' in t or re.search(r"\btam\b", t):
        return 'LATAM'
    if 'smiles' in t or re.search(r"\bsmile\b", t):
        return 'SMILES'
    return None

def is_buy_message(text: str):
    # keep permissive: 'compro', 'c>', 'compra' etc.
    t = text.lower()
    return ('compro' in t) or ('c>' in t) or ('compra' in t)

def compute_per_cpf(miles: int, cpfs: int) -> int:
    return int(miles // cpfs)

async def ensure_login(client: TelegramClient, phone: str):
    if await client.is_user_authorized():
        return
    await client.send_code_request(phone)
    code = input('Telegram code (SMS/app): ').strip()
    try:
        await client.sign_in(phone=phone, code=code)
    except SessionPasswordNeededError:
        pw = input('2FA password: ').strip()
        await client.sign_in(password=pw)

async def resolve_target(client: TelegramClient, target: str):
    """Resolve TG_TARGET to an entity.

    Supports:
    - numeric id (e.g. -100123...)
    - exact @username
    - group title (exact or partial, case-insensitive)
    """
    target = (target or '').strip()
    if re.fullmatch(r"-?\d+", target):
        return int(target)

    # Try Telethon resolution first (works for @username and some titles)
    try:
        return await client.get_entity(target)
    except Exception:
        pass

    # Fallback: scan dialogs and match by title (case-insensitive, partial)
    wanted = norm_text(target)
    best = None
    async for d in client.iter_dialogs():
        title = getattr(d, 'name', None) or ''
        tnorm = norm_text(title)
        if not tnorm:
            continue
        if tnorm == wanted:
            return d.entity
        if wanted and wanted in tnorm:
            best = d.entity
            # keep searching for exact match; otherwise the first partial match wins
    if best is not None:
        return best

    raise ValueError(f'Cannot find any entity corresponding to "{target}". Set TG_TARGET to the exact title or numeric id.')

async def main():
    load_dotenv()

    lock_handle = acquire_single_instance_lock()
    if lock_handle is None:
        print('[INFO] Another monitor instance is already running. Exiting.')
        return

    ap = argparse.ArgumentParser()
    ap.add_argument('--send', action='store_true', help='actually send messages (overrides DRY_RUN=1)')
    ap.add_argument('--dry-run', action='store_true', help='force dry run (never send)')
    args = ap.parse_args()

    api_id = os.getenv('TG_API_ID')
    api_hash = os.getenv('TG_API_HASH')
    phone = os.getenv('TG_PHONE')
    targets_raw = os.getenv('TG_TARGETS') or os.getenv('TG_TARGET')

    if not api_id or not api_hash or not phone or not targets_raw:
        raise SystemExit('Missing env vars. Fill .env (TG_API_ID, TG_API_HASH, TG_PHONE, TG_TARGETS).')

    targets = [t.strip() for t in targets_raw.split(',') if t.strip()]

    api_id = int(api_id)

    dry_env = os.getenv('DRY_RUN', '1').strip() == '1'
    dry_run = True
    if args.send and not args.dry_run:
        dry_run = False
    if args.dry_run:
        dry_run = True
    if dry_env and not args.send:
        dry_run = True

    rules = {
        'LATAM': Rule('LATAM', int(os.getenv('LATAM_THRESHOLD_PER_CPF', '50000')), os.getenv('LATAM_REPLY', '25,00')),
        'SMILES': Rule('SMILES', int(os.getenv('SMILES_THRESHOLD_PER_CPF', '60000')), os.getenv('SMILES_REPLY', '15,50')),
    }

    send_delay_seconds = float(os.getenv('SEND_DELAY_SECONDS', '2').strip() or '2')
    whatsapp_relay_enabled = os.getenv('WHATSAPP_RELAY', '1').strip() == '1'

    state = load_state()
    seen = state.setdefault('seen', {})

    client = TelegramClient('session', api_id, api_hash)
    await client.connect()
    await ensure_login(client, phone)

    entities = []
    for t in targets:
        ent = await resolve_target(client, t)
        entities.append(ent)

    print('---')
    print('Targets:', targets)
    print('Dry run:', dry_run)
    print('Rules:', {k: {'threshold_per_cpf': v.threshold_per_cpf, 'reply': v.reply} for k,v in rules.items()})
    print('---')

    @client.on(events.NewMessage(chats=entities))
    async def handler(event):
        text = event.raw_text or ''
        tnorm = norm_text(text)

        program = detect_program(tnorm)
        if program not in rules:
            return

        # Only proceed when we can extract both miles and CPF count.
        miles = parse_miles(text)
        cpfs = parse_cpfs(text)

        if miles is None or cpfs is None or cpfs <= 0:
            return

        # Optional caps: only evaluate offers up to a max miles count (total miles in the message)
        # Defaults match current business rules: SMILES up to 249k, LATAM up to 800k.
        try:
            smiles_max = int((os.getenv('SMILES_MAX_MILES', '113700') or '113700').strip())
        except Exception:
            smiles_max = 113700
        try:
            latam_max = int((os.getenv('LATAM_MAX_MILES', '800000') or '800000').strip())
        except Exception:
            latam_max = 800000

        if program == 'SMILES' and miles > smiles_max:
            return
        if program == 'LATAM' and miles > latam_max:
            return

        per_cpf = compute_per_cpf(miles, cpfs)
        rule = rules[program]

        eligible = False
        if program == 'LATAM':
            eligible = per_cpf >= rule.threshold_per_cpf
        else:
            eligible = per_cpf > rule.threshold_per_cpf

        if not eligible:
            return

        # Dedupe per-chat: the same proposal can appear in multiple groups and we want to reply in each one.
        chat_id = getattr(event, 'chat_id', None)
        key_src = f"{program}|{chat_id}|{tnorm}|{miles}|{cpfs}|{per_cpf}"
        key = sha1(key_src)

        # Get chat/group info (best-effort)
        chat_title = None
        try:
            chat = await event.get_chat()
            chat_title = (getattr(chat, 'title', None) or getattr(chat, 'username', None) or str(chat_id) or '').strip() or None
        except Exception:
            pass

        if key in seen:
            return

        # Try to capture sender display name (best-effort)
        sender_name = None
        try:
            sender = await event.get_sender()
            if sender is not None:
                sender_name = (getattr(sender, 'first_name', None) or '').strip() or None
                last = (getattr(sender, 'last_name', None) or '').strip() or None
                if sender_name and last:
                    sender_name = f"{sender_name} {last}".strip()
                if not sender_name:
                    sender_name = (getattr(sender, 'title', None) or '').strip() or None
                if not sender_name:
                    sender_name = (getattr(sender, 'username', None) or '').strip() or None
        except Exception:
            pass

        ts = int(time.time())
        seen[key] = {
            'ts': ts,
            'program': program,
            'miles': miles,
            'cpfs': cpfs,
            'per_cpf': per_cpf,
            'sender': sender_name,
            'text': text[:500]
        }
        save_state(state)

        # Never bid below the offered price in the message.
        offer_cents = parse_offer_price_cents(text)

        # Rule reply is a string like "15,50". Convert it to cents.
        rule_reply_cents = None
        try:
            rr = rule.reply.strip().replace('.', ',')
            m = re.fullmatch(r"(\d{1,2}),(\d{2})", rr)
            if m:
                rule_reply_cents = int(m.group(1)) * 100 + int(m.group(2))
        except Exception:
            rule_reply_cents = None

        final_cents = rule_reply_cents
        if offer_cents is not None and rule_reply_cents is not None:
            final_cents = max(rule_reply_cents, offer_cents)
        msg = format_price_cents(final_cents) if final_cents is not None else rule.reply

        print(f"[ELIGIBLE] {program} miles={miles} cpfs={cpfs} per_cpf={per_cpf} offer={format_price_cents(offer_cents) if offer_cents is not None else None} -> {msg} | dry_run={dry_run} | sender={sender_name} | chat={chat_title or chat_id}")

        # Write a machine-readable event record
        append_event_log({
            'ts': ts,
            'kind': 'eligible',
            'program': program,
            'chat_id': chat_id,
            'chat_title': chat_title,
            'miles': miles,
            'cpfs': cpfs,
            'per_cpf': per_cpf,
            'offer_price_cents': offer_cents,
            'rule_reply': rule.reply,
            'final_reply': msg,
            'dry_run': dry_run,
            'send_mode': os.getenv('SEND_MODE', 'reply').strip().lower(),
            'sender': sender_name,
            'text': text
        })

        if dry_run:
            return

        # Small delay before sending (anti-spam / mimic human latency)
        try:
            import asyncio
            await asyncio.sleep(send_delay_seconds)
        except Exception:
            pass

        send_mode = os.getenv('SEND_MODE', 'reply').strip().lower()

        sent_via = None
        send_error = None
        try:
            # Prefer reply for speed + contextual threading.
            if send_mode == 'reply':
                await event.reply(msg)
                sent_via = 'reply'
            else:
                # Plain send to the same chat
                await client.send_message(event.chat_id, msg)
                sent_via = 'plain'
        except Exception as e:
            send_error = f"{type(e).__name__}: {e}"
            print(f"[WARN] send failed ({send_error}). Falling back to plain send.")
            try:
                await client.send_message(event.chat_id, msg)
                sent_via = 'plain-fallback'
            except Exception as e2:
                send_error = f"{send_error} | fallback {type(e2).__name__}: {e2}"
                raise

        # Record send result
        append_event_log({
            'ts': int(time.time()),
            'kind': 'send_result',
            'program': program,
            'chat_id': chat_id,
            'chat_title': chat_title,
            'miles': miles,
            'cpfs': cpfs,
            'per_cpf': per_cpf,
            'offer_price_cents': offer_cents,
            'rule_reply': rule.reply,
            'final_reply': msg,
            'sent_via': sent_via,
            'sender': sender_name,
            'error': send_error,
        })

        # Queue a WhatsApp relay event (OpenClaw will forward it)
        if whatsapp_relay_enabled:
            append_whatsapp_event({
                # Wall-clock time when we queued the relay event
                'ts': int(time.time()),
                'kind': 'telegram_auto_reply',
                'program': program,
                'group': chat_title,
                'chat_id': chat_id,
                # Telegram message id (stable dedupe key across restarts)
                'msg_id': getattr(getattr(event, 'message', None), 'id', None),
                'sender': sender_name,
                'miles': miles,
                'cpfs': cpfs,
                'per_cpf': per_cpf,
                'offer': format_price_cents(offer_cents) if offer_cents is not None else None,
                'reply': msg,
                'sent_via': sent_via,
            })

        # Optional: notify to Saved Messages / another chat via Telegram
        notify_target = (os.getenv('TG_NOTIFY_TARGET') or '').strip()
        if notify_target:
            summary = (
                f"[AUTO] {program} | {miles}/{cpfs} = {per_cpf}/CPF | offer="
                f"{format_price_cents(offer_cents) if offer_cents is not None else '??'} | "
                f"reply {msg} via {sent_via} | group: {chat_title or chat_id} | from: {sender_name or '??'}"
            )
            try:
                await client.send_message(notify_target, summary)
            except Exception as e:
                append_event_log({'ts': int(time.time()), 'kind': 'notify_error', 'error': str(e)})

    print('Listening... (Ctrl+C to stop)')
    await client.run_until_disconnected()

if __name__ == '__main__':
    import asyncio
    asyncio.run(main())
