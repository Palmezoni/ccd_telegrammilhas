#!/usr/bin/env python3
"""
Milhas UP Telegram Monitor — Interface Gráfica
Versão 1.0.0
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from tkinter import messagebox

import customtkinter as ctk

# ── System tray (opcional — instale pystray e pillow) ────────────────────────
try:
    import pystray
    from PIL import Image, ImageDraw
    HAS_TRAY = True
except ImportError:
    HAS_TRAY = False

# ── Constantes ────────────────────────────────────────────────────────────────
APP_NAME = "Milhas UP Telegram Monitor"
VERSION  = "1.0.0"

IS_FROZEN = getattr(sys, "frozen", False)
BASE_DIR  = Path(sys.executable).parent if IS_FROZEN else Path(__file__).parent.resolve()

ENV_PATH    = BASE_DIR / ".env"
PID_PATH    = BASE_DIR / "monitor.pid"
LOCK_PATH   = BASE_DIR / "monitor.lock"
EVENTS_PATH = BASE_DIR / "events.jsonl"

# Produção: monitor_bg.exe gerado pelo PyInstaller
# Dev: pythonw do venv + monitor.py
if IS_FROZEN:
    MONITOR_CMD = [str(BASE_DIR / "monitor_bg.exe")]
else:
    _pythonw = BASE_DIR / ".venv" / "Scripts" / "pythonw.exe"
    MONITOR_CMD = [str(_pythonw), str(BASE_DIR / "monitor.py")]

# Paleta
C_GREEN  = "#2ecc71"
C_RED    = "#e74c3c"
C_ORANGE = "#e67e22"
C_BLUE   = "#3498db"
C_GRAY   = "#7f8c8d"
C_DARK   = "#0d1117"

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


# ── Helpers ───────────────────────────────────────────────────────────────────

def read_env() -> dict:
    result: dict = {}
    if not ENV_PATH.exists():
        return result
    with open(ENV_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                k, _, v = line.partition("=")
                result[k.strip()] = v.strip()
    return result


def write_env_keys(updates: dict):
    """Atualiza chaves específicas no .env, preservando comentários."""
    lines: list[str] = []
    if ENV_PATH.exists():
        with open(ENV_PATH, encoding="utf-8") as f:
            lines = f.readlines()
    updated: set = set()
    for i, line in enumerate(lines):
        s = line.strip()
        if s.startswith("#") or "=" not in s:
            continue
        key = s.split("=", 1)[0].strip()
        if key in updates:
            lines[i] = f"{key}={updates[key]}\n"
            updated.add(key)
    for key, val in updates.items():
        if key not in updated:
            lines.append(f"{key}={val}\n")
    with open(ENV_PATH, "w", encoding="utf-8") as f:
        f.writelines(lines)


def get_pid():
    try:
        if PID_PATH.exists():
            v = PID_PATH.read_text(encoding="utf-8").strip()
            return int(v) if v else None
    except Exception:
        return None


def is_running():
    pid = get_pid()
    if pid is None:
        return False, None
    try:
        out = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}"],
            capture_output=True, text=True,
        ).stdout
        return str(pid) in out, pid
    except Exception:
        return False, None


def do_start():
    running, pid = is_running()
    if running:
        return False, f"Monitor já está rodando (PID {pid})"
    PID_PATH.unlink(missing_ok=True)
    LOCK_PATH.unlink(missing_ok=True)
    cmd = MONITOR_CMD
    if not Path(cmd[0]).exists():
        return False, f"Executável não encontrado:\n{cmd[0]}"
    try:
        subprocess.Popen(
            cmd,
            cwd=str(BASE_DIR),
            creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NO_WINDOW,
        )
    except Exception as e:
        return False, str(e)
    for _ in range(10):
        time.sleep(0.5)
        if get_pid():
            return True, f"Monitor iniciado! (PID {get_pid()})"
    return False, "Timeout — verifique o .env e as credenciais Telegram"


def do_stop():
    running, pid = is_running()
    if not running:
        return False, "Monitor não está rodando"
    try:
        subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True)
        time.sleep(0.8)
        PID_PATH.unlink(missing_ok=True)
        LOCK_PATH.unlink(missing_ok=True)
        return True, f"Monitor encerrado (era PID {pid})"
    except Exception as e:
        return False, str(e)


def load_events(n: int = 300) -> list:
    if not EVENTS_PATH.exists():
        return []
    try:
        with open(EVENTS_PATH, encoding="utf-8") as f:
            raw = [l.strip() for l in f if l.strip()]
        result = []
        for line in raw[-n:]:
            try:
                result.append(json.loads(line))
            except Exception:
                pass
        return result
    except Exception:
        return []


# ── Aplicação Principal ───────────────────────────────────────────────────────

class MilhasUpApp(ctk.CTk):

    def __init__(self):
        super().__init__()
        self.title(APP_NAME)
        self.geometry("920x680")
        self.minsize(780, 580)
        self._setup_icon()
        self._build_ui()
        self._setup_tray()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(200, self._poll)

    # ── Ícone ─────────────────────────────────────────────────────────────────

    def _setup_icon(self):
        ico = BASE_DIR / "assets" / "icon.ico"
        if ico.exists():
            try:
                self.iconbitmap(str(ico))
            except Exception:
                pass

    def _make_tray_image(self):
        size = 64
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.ellipse([2, 2, size - 2, size - 2], fill="#1a5fa8")
        d.ellipse([8, 8, size - 8, size - 8], fill="#2471c2")
        cx = size // 2
        pts = [
            (cx, 10), (cx + 18, 28), (cx + 8, 28),
            (cx + 8, 52), (cx - 8, 52), (cx - 8, 28), (cx - 18, 28),
        ]
        d.polygon(pts, fill="white")
        return img

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        # Header
        hdr = ctk.CTkFrame(self, height=54, corner_radius=0, fg_color=C_DARK)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        ctk.CTkLabel(
            hdr,
            text="✈  Milhas UP Telegram Monitor",
            font=ctk.CTkFont(size=17, weight="bold"),
            text_color="#58a6ff",
        ).pack(side="left", padx=20)
        self._hdr_dot = ctk.CTkLabel(
            hdr, text="⬤  Verificando...",
            font=ctk.CTkFont(size=12), text_color=C_GRAY,
        )
        self._hdr_dot.pack(side="right", padx=20)

        # Tabs
        self._tabs = ctk.CTkTabview(self, anchor="nw")
        self._tabs.pack(fill="both", expand=True, padx=8, pady=(4, 8))
        self._t_dash = self._tabs.add("  Dashboard  ")
        self._t_cfg  = self._tabs.add("  Configuração  ")
        self._t_log  = self._tabs.add("  Logs  ")

        self._build_dashboard()
        self._build_config()
        self._build_logs()

    # ── Dashboard ─────────────────────────────────────────────────────────────

    def _build_dashboard(self):
        p = self._t_dash

        # Card de status
        card = ctk.CTkFrame(p, corner_radius=12)
        card.pack(fill="x", padx=6, pady=(8, 4))

        left = ctk.CTkFrame(card, fg_color="transparent")
        left.pack(side="left", fill="y", padx=16, pady=16)

        self._dot = ctk.CTkLabel(
            left, text="⬤", font=ctk.CTkFont(size=40), text_color=C_GRAY,
        )
        self._dot.pack(side="left", padx=(0, 14))

        info = ctk.CTkFrame(left, fg_color="transparent")
        info.pack(side="left")
        self._lbl_status = ctk.CTkLabel(
            info, text="Verificando...", font=ctk.CTkFont(size=16, weight="bold"),
        )
        self._lbl_status.pack(anchor="w")
        self._lbl_pid = ctk.CTkLabel(
            info, text="", font=ctk.CTkFont(size=11), text_color=C_GRAY,
        )
        self._lbl_pid.pack(anchor="w")

        # Botões
        right = ctk.CTkFrame(card, fg_color="transparent")
        right.pack(side="right", padx=16, pady=16)

        self._btn_start = ctk.CTkButton(
            right, text="▶  Iniciar", width=120, height=38,
            fg_color="#27ae60", hover_color="#2ecc71",
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self._start,
        )
        self._btn_start.pack(side="left", padx=4)

        self._btn_restart = ctk.CTkButton(
            right, text="↺  Reiniciar", width=120, height=38,
            fg_color="#d35400", hover_color="#e67e22",
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self._restart,
        )
        self._btn_restart.pack(side="left", padx=4)

        self._btn_stop = ctk.CTkButton(
            right, text="■  Parar", width=120, height=38,
            fg_color="#c0392b", hover_color="#e74c3c",
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self._stop,
        )
        self._btn_stop.pack(side="left", padx=4)

        # Stats
        sf = ctk.CTkFrame(p, corner_radius=12)
        sf.pack(fill="x", padx=6, pady=4)
        sf.grid_columnconfigure((0, 1, 2, 3), weight=1)
        self._st_total  = self._stat(sf, "Total Respondidas", "—", 0)
        self._st_smiles = self._stat(sf, "SMILES",            "—", 1)
        self._st_latam  = self._stat(sf, "LATAM",             "—", 2)
        self._st_last   = self._stat(sf, "Última Resposta",   "—", 3)

        # Atividade recente
        ctk.CTkLabel(
            p, text="Atividade Recente",
            font=ctk.CTkFont(size=12, weight="bold"), anchor="w",
        ).pack(fill="x", padx=10, pady=(6, 2))

        self._act = ctk.CTkTextbox(
            p, font=ctk.CTkFont(family="Consolas", size=11),
            state="disabled", corner_radius=8,
        )
        self._act.pack(fill="both", expand=True, padx=6, pady=(0, 6))

    def _stat(self, parent, label: str, value: str, col: int) -> ctk.CTkLabel:
        f = ctk.CTkFrame(parent, corner_radius=8)
        f.grid(row=0, column=col, padx=6, pady=8, sticky="nsew")
        ctk.CTkLabel(f, text=label, font=ctk.CTkFont(size=10), text_color=C_GRAY).pack(pady=(8, 0))
        lbl = ctk.CTkLabel(f, text=value, font=ctk.CTkFont(size=22, weight="bold"))
        lbl.pack(pady=(0, 8))
        return lbl

    def _start(self):
        self._btn_start.configure(state="disabled", text="Iniciando...")
        threading.Thread(target=self._do_start, daemon=True).start()

    def _stop(self):
        self._btn_stop.configure(state="disabled", text="Parando...")
        threading.Thread(target=self._do_stop, daemon=True).start()

    def _restart(self):
        self._btn_restart.configure(state="disabled", text="Reiniciando...")
        def _do():
            do_stop()
            time.sleep(1.5)
            ok, msg = do_start()
            self.after(0, lambda: self.toast(msg, ok))
            self.after(0, lambda: self._btn_restart.configure(state="normal", text="↺  Reiniciar"))
            self.after(0, self._update_status)
        threading.Thread(target=_do, daemon=True).start()

    def _do_start(self):
        ok, msg = do_start()
        self.after(0, lambda: self.toast(msg, ok))
        self.after(0, lambda: self._btn_start.configure(state="normal", text="▶  Iniciar"))
        self.after(0, self._update_status)

    def _do_stop(self):
        ok, msg = do_stop()
        self.after(0, lambda: self.toast(msg, ok))
        self.after(0, lambda: self._btn_stop.configure(state="normal", text="■  Parar"))
        self.after(0, self._update_status)

    # ── Configuração ──────────────────────────────────────────────────────────

    def _build_config(self):
        p = self._t_cfg
        self._cfg: dict = {}

        scroll = ctk.CTkScrollableFrame(p)
        scroll.pack(fill="both", expand=True, padx=6, pady=6)
        scroll.grid_columnconfigure(1, weight=1)

        row = [0]

        def section(title: str, emoji: str = ""):
            r = row[0]
            text = f"{emoji}  {title}" if emoji else title
            ctk.CTkLabel(
                scroll, text=text,
                font=ctk.CTkFont(size=13, weight="bold"), anchor="w",
            ).grid(row=r, column=0, columnspan=2, sticky="w", padx=6, pady=(16, 2))
            row[0] += 1
            sep = ctk.CTkFrame(scroll, height=1, fg_color="gray30")
            sep.grid(row=row[0], column=0, columnspan=2, sticky="ew", padx=6, pady=(0, 6))
            row[0] += 1

        def field(label: str, key: str, placeholder: str = "", password: bool = False, width: int = 340):
            r = row[0]
            ctk.CTkLabel(scroll, text=label, anchor="w", width=210).grid(
                row=r, column=0, sticky="w", padx=(6, 10), pady=3,
            )
            var = ctk.StringVar()
            ctk.CTkEntry(
                scroll, textvariable=var, placeholder_text=placeholder,
                width=width, show="*" if password else "",
            ).grid(row=r, column=1, sticky="ew", padx=6, pady=3)
            self._cfg[key] = ("entry", var)
            row[0] += 1

        def check(label: str, key: str):
            r = row[0]
            ctk.CTkLabel(scroll, text=label, anchor="w", width=210).grid(
                row=r, column=0, sticky="w", padx=(6, 10), pady=3,
            )
            var = ctk.BooleanVar()
            ctk.CTkSwitch(scroll, text="", variable=var, width=50).grid(
                row=r, column=1, sticky="w", padx=6, pady=3,
            )
            self._cfg[key] = ("check", var)
            row[0] += 1

        def multiline(label: str, key: str, height: int = 90):
            r = row[0]
            ctk.CTkLabel(scroll, text=label, anchor="nw", width=210).grid(
                row=r, column=0, sticky="nw", padx=(6, 10), pady=3,
            )
            tb = ctk.CTkTextbox(scroll, height=height, corner_radius=6)
            tb.grid(row=r, column=1, sticky="ew", padx=6, pady=3)
            self._cfg[key] = ("text", tb)
            row[0] += 1

        # ── Seções ────────────────────────────────────────────────────────────
        section("Credenciais Telegram", "🔐")
        field("API ID",    "TG_API_ID",   "Ex: 12345678")
        field("API Hash",  "TG_API_HASH", "Ex: a1b2c3d4e5f...", password=True)
        field("Telefone",  "TG_PHONE",    "Ex: +5534999768872")

        section("Grupos Monitorados", "📡")
        multiline("Nomes dos Grupos\n(um por linha)", "TG_TARGETS", height=110)

        section("Regras LATAM", "✈")
        field("Mínimo por CPF (milhas)", "LATAM_THRESHOLD_PER_CPF", "Ex: 50000")
        field("Preço de Resposta (R$)",  "LATAM_REPLY",              "Ex: 25,00")
        field("Máximo total (milhas)",   "LATAM_MAX_MILES",          "Ex: 194000")

        section("Regras SMILES", "🌟")
        field("Mínimo por CPF (milhas)", "SMILES_THRESHOLD_PER_CPF", "Ex: 27000")
        field("Preço de Resposta (R$)",  "SMILES_REPLY",              "Ex: 16,00")
        field("Máximo total (milhas)",   "SMILES_MAX_MILES",          "Ex: 675000")

        section("Notificações", "🔔")
        field("Telegram — alvo (Salvas)", "TG_NOTIFY_TARGET", "Ex: me")
        field("Tópico ntfy.sh",           "NTFY_TOPIC",       "Ex: milhas-meu-topico")

        section("Avançado", "⚙")
        field("Delay entre envios (s)", "SEND_DELAY_SECONDS", "Ex: 3")
        check("Modo Teste — Dry-run (não envia)", "DRY_RUN")

        # Botões
        r = row[0]
        bf = ctk.CTkFrame(scroll, fg_color="transparent")
        bf.grid(row=r, column=0, columnspan=2, pady=18)

        ctk.CTkButton(
            bf, text="💾  Salvar Configurações", width=220, height=40,
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self._save_cfg,
        ).pack(side="left", padx=6)

        ctk.CTkButton(
            bf, text="↺  Recarregar", width=140, height=40,
            fg_color="gray40", hover_color="gray50",
            command=self._load_cfg,
        ).pack(side="left", padx=6)

        self._load_cfg()

    def _load_cfg(self):
        env = read_env()
        for key, (typ, var) in self._cfg.items():
            val = env.get(key, "")
            if typ == "check":
                var.set(val == "1")
            elif typ == "entry":
                var.set(val)
            elif typ == "text":
                var.delete("1.0", "end")
                if key == "TG_TARGETS":
                    items = [x.strip() for x in val.split(",") if x.strip()]
                    var.insert("1.0", "\n".join(items))
                else:
                    var.insert("1.0", val)

    def _save_cfg(self):
        data: dict = {}
        for key, (typ, var) in self._cfg.items():
            if typ == "check":
                data[key] = "1" if var.get() else "0"
            elif typ == "entry":
                data[key] = var.get().strip()
            elif typ == "text":
                val = var.get("1.0", "end").strip()
                if key == "TG_TARGETS":
                    val = ", ".join(l.strip() for l in val.splitlines() if l.strip())
                data[key] = val
        write_env_keys(data)
        running, _ = is_running()
        suffix = "\n⚠  Reinicie o monitor para aplicar as mudanças." if running else ""
        self.toast(f"Configurações salvas!{suffix}", True)

    # ── Logs ─────────────────────────────────────────────────────────────────

    def _build_logs(self):
        p = self._t_log

        tb = ctk.CTkFrame(p, fg_color="transparent")
        tb.pack(fill="x", padx=6, pady=(6, 4))

        ctk.CTkLabel(
            tb, text="Histórico de Eventos",
            font=ctk.CTkFont(size=12, weight="bold"),
        ).pack(side="left")

        ctk.CTkButton(
            tb, text="🔄  Atualizar", width=110, height=28,
            command=self._refresh_logs,
        ).pack(side="right", padx=4)

        ctk.CTkButton(
            tb, text="🗑  Limpar", width=90, height=28,
            fg_color="gray40", hover_color="gray50",
            command=self._clear_logs,
        ).pack(side="right", padx=4)

        self._logbox = ctk.CTkTextbox(
            p, font=ctk.CTkFont(family="Consolas", size=11),
            state="disabled", corner_radius=8,
        )
        self._logbox.pack(fill="both", expand=True, padx=6, pady=(0, 6))
        self._refresh_logs()

    def _refresh_logs(self):
        events = load_events(400)
        self._logbox.configure(state="normal")
        self._logbox.delete("1.0", "end")

        ICONS = {
            "sent": "✅", "eligible": "🔍", "skipped": "⏭",
            "error": "❌", "notify_error": "⚠",
        }
        for e in reversed(events):
            ts   = datetime.fromtimestamp(e.get("ts", 0)).strftime("%d/%m %H:%M:%S")
            kind = e.get("kind", "?")
            prog = e.get("program", "")
            icon = ICONS.get(kind, "•")

            parts = [icon, ts, f"[{kind.upper():<14}]"]
            if prog:                    parts.append(f"{prog:<6}")
            if "miles"       in e:      parts.append(f"{e['miles']:>8,} mi")
            if "cpfs"        in e:      parts.append(f"{e['cpfs']} CPF")
            if "per_cpf"     in e:      parts.append(f"= {e['per_cpf']:,}/CPF")
            if "final_reply" in e:      parts.append(f"→ R${e['final_reply']}")
            if "sender"      in e:      parts.append(f"| de: {e['sender'][:25]}")
            if "chat_title"  in e:      parts.append(f"| {e['chat_title'][:30]}")
            if "reason"      in e:      parts.append(f"  {e['reason']}")
            if "error"       in e:      parts.append(f"  ERRO: {e['error'][:50]}")

            self._logbox.insert("end", "  ".join(parts) + "\n")

        self._logbox.configure(state="disabled")

    def _clear_logs(self):
        if messagebox.askyesno("Limpar Log", "Deseja apagar o histórico de eventos (events.jsonl)?"):
            try:
                EVENTS_PATH.write_text("", encoding="utf-8")
                self._refresh_logs()
                self.toast("Log limpo com sucesso.", True)
            except Exception as ex:
                self.toast(f"Erro ao limpar: {ex}", False)

    # ── Polling ───────────────────────────────────────────────────────────────

    def _poll(self):
        self._update_status()
        self.after(4000, self._poll)

    def _update_status(self):
        running, pid = is_running()

        if running:
            self._dot.configure(text_color=C_GREEN)
            self._lbl_status.configure(text="Monitor Rodando")
            self._lbl_pid.configure(text=f"PID {pid} · atualiza a cada 4s")
            self._hdr_dot.configure(text="⬤  Rodando", text_color=C_GREEN)
        else:
            self._dot.configure(text_color=C_RED)
            self._lbl_status.configure(text="Monitor Parado")
            self._lbl_pid.configure(text="")
            self._hdr_dot.configure(text="⬤  Parado", text_color=C_RED)

        # Atividade recente
        events = load_events(60)
        self._act.configure(state="normal")
        self._act.delete("1.0", "end")

        total = smiles = latam = 0
        last_time = "—"

        for e in events:
            kind = e.get("kind", "")
            prog = e.get("program", "")
            ts   = datetime.fromtimestamp(e.get("ts", 0)).strftime("%d/%m %H:%M")

            if kind == "sent":
                total += 1
                if prog == "SMILES":  smiles += 1
                elif prog == "LATAM": latam  += 1
                last_time = ts.split()[1] if " " in ts else ts
                miles  = e.get("miles", 0)
                cpfs   = e.get("cpfs", 0)
                per    = e.get("per_cpf", 0)
                reply  = e.get("final_reply", "?")
                sender = e.get("sender", "?")[:22]
                chat   = e.get("chat_title", "")[:28]
                line   = (
                    f"{ts}  ✅ {prog:<6}  {miles:>7,}mi / {cpfs} CPF"
                    f"  = {per:>6,}/CPF  → R${reply:<5}"
                    f"  {sender:<24}  {chat}\n"
                )
            elif kind == "eligible" and e.get("dry_run"):
                line = (
                    f"{ts}  🔍 {prog:<6}  {e.get('miles',0):>7,}mi"
                    f"  {e.get('per_cpf',0):>6,}/CPF  [dry-run — sem envio]\n"
                )
            elif kind == "skipped":
                line = f"{ts}  ⏭  {prog:<6}  {e.get('reason','')}\n"
            elif kind in ("error", "notify_error"):
                line = f"{ts}  ❌  ERRO: {e.get('error','')[:80]}\n"
            else:
                continue

            self._act.insert("end", line)

        self._act.configure(state="disabled")
        self._act.see("end")

        self._st_total.configure( text=str(total)  if events else "—")
        self._st_smiles.configure(text=str(smiles) if events else "—")
        self._st_latam.configure( text=str(latam)  if events else "—")
        self._st_last.configure(  text=last_time)

    # ── Toast ─────────────────────────────────────────────────────────────────

    def toast(self, msg: str, ok: bool = True):
        t = ctk.CTkToplevel(self)
        t.overrideredirect(True)
        t.attributes("-topmost", True)
        t.configure(fg_color=C_GREEN if ok else C_RED)
        ctk.CTkLabel(
            t, text=msg,
            font=ctk.CTkFont(size=12),
            text_color="white",
            wraplength=380,
        ).pack(padx=18, pady=14)
        self.update_idletasks()
        x = self.winfo_x() + self.winfo_width()  - 430
        y = self.winfo_y() + self.winfo_height() - 90
        t.geometry(f"+{x}+{y}")
        t.after(4000, t.destroy)

    # ── System Tray ───────────────────────────────────────────────────────────

    def _setup_tray(self):
        if not HAS_TRAY:
            return
        try:
            img = self._make_tray_image()
            menu = pystray.Menu(
                pystray.MenuItem("Abrir",           self._show_window, default=True),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Iniciar Monitor", lambda i, item: self.after(0, self._start)),
                pystray.MenuItem("Parar Monitor",   lambda i, item: self.after(0, self._stop)),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Sair",            lambda i, item: self.after(0, self._quit)),
            )
            self._tray = pystray.Icon("milhasup", img, APP_NAME, menu)
            threading.Thread(target=self._tray.run, daemon=True).start()
        except Exception:
            self._tray = None

    def _show_window(self, *_):
        self.after(0, lambda: (self.deiconify(), self.lift(), self.focus_force()))

    def _hide_to_tray(self):
        if HAS_TRAY and getattr(self, "_tray", None):
            self.withdraw()
        else:
            self._quit()

    def _on_close(self):
        self._hide_to_tray()

    def _quit(self):
        if getattr(self, "_tray", None):
            try:
                self._tray.stop()
            except Exception:
                pass
        self.destroy()


# ── Entry Point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = MilhasUpApp()
    app.mainloop()
