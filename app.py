#!/usr/bin/env python3
"""
Milhas UP Telegram Monitor — Interface Gráfica
Versão 1.0.0
"""
from __future__ import annotations

import ctypes
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

# ── Licença ────────────────────────────────────────────────────────────────────
try:
    from license import LicenseManager, LicenseState
    HAS_LICENSE = True
except ImportError:
    HAS_LICENSE = False

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

ENV_PATH     = BASE_DIR / ".env"
PID_PATH     = BASE_DIR / "monitor.pid"
LOCK_PATH    = BASE_DIR / "monitor.lock"
EVENTS_PATH  = BASE_DIR / "events.jsonl"
SESSION_PATH = BASE_DIR / "session.session"

# Produção: monitor_bg/monitor_bg.exe (--onedir, sem flash de CMD)
# Dev: pythonw do venv + monitor.py
if IS_FROZEN:
    MONITOR_CMD = [str(BASE_DIR / "monitor_bg" / "monitor_bg.exe")]
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


_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

# ATENÇÃO: os.kill(pid, 0) no Python 3.9 Windows MATA o processo via TerminateProcess!
# O tratamento especial de sig=0 só existe a partir do Python 3.11.
# Usar ctypes diretamente para verificar existência sem matar.
def _pid_alive(pid: int) -> bool:
    """Verifica se o PID existe sem spawnar subprocess e sem matar o processo."""
    try:
        SYNCHRONIZE = 0x00100000
        handle = ctypes.windll.kernel32.OpenProcess(SYNCHRONIZE, False, pid)
        if handle:
            ctypes.windll.kernel32.CloseHandle(handle)
            return True
        return False
    except Exception:
        return False

def is_running():
    pid = get_pid()
    if pid is None:
        return False, None
    return (_pid_alive(pid), pid) if _pid_alive(pid) else (False, None)


def do_start():
    running, pid = is_running()
    if running:
        return False, f"Monitor já está rodando (PID {pid})"
    # Limpa arquivos de estado — ignora erros (ex: lock ainda aberto por processo morto)
    try: PID_PATH.unlink(missing_ok=True)
    except Exception: pass
    try: LOCK_PATH.unlink(missing_ok=True)
    except Exception: pass
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
    for _ in range(30):   # até 15s — Telethon precisa conectar ao Telegram
        time.sleep(0.5)
        if get_pid():
            return True, f"Monitor iniciado! (PID {get_pid()})"
    return False, "Timeout — verifique o .env e as credenciais Telegram"


def do_stop():
    running, pid = is_running()
    if not running:
        return False, "Monitor não está rodando"
    try:
        subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True,
                       creationflags=_NO_WINDOW)
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

        # ── Gate de licença ───────────────────────────────────────────────────
        if HAS_LICENSE:
            self._lic = LicenseManager(BASE_DIR)
            state = self._lic.load_local()
            if state is None or not state.activated:
                self._build_activation_screen()
                return
            ok, reason = self._lic.check_or_grace()
            if not ok:
                msg = {
                    "expired_local": "Licença expirada. Por favor renove sua assinatura.",
                    "revoked":       "Licença revogada. Contate o suporte.",
                    "grace_expired": "Sem conexão com o servidor de licença por mais de 24h. Renove ou verifique a internet.",
                }.get(reason, f"Licença inválida ({reason}). Contate o suporte.")
                self._build_activation_screen(msg=msg)
                return
        else:
            self._lic = None

        self._build_ui()
        self._setup_tray()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(200, self._poll)
        # Onboarding: abre wizard se ainda não configurado
        if self._needs_onboarding():
            self.after(400, self._show_onboarding_wizard)

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

    # ── Tela de Ativação ──────────────────────────────────────────────────────

    def _build_activation_screen(self, msg: str = ""):
        """Exibe a tela de ativação de licença bloqueando o restante da UI."""
        self.protocol("WM_DELETE_WINDOW", self._quit)

        # Header igual ao normal
        hdr = ctk.CTkFrame(self, height=54, corner_radius=0, fg_color=C_DARK)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        ctk.CTkLabel(
            hdr,
            text="✈  Milhas UP Telegram Monitor",
            font=ctk.CTkFont(size=17, weight="bold"),
            text_color="#58a6ff",
        ).pack(side="left", padx=20)

        # Card central
        outer = ctk.CTkFrame(self, fg_color="transparent")
        outer.pack(fill="both", expand=True)

        card = ctk.CTkFrame(outer, corner_radius=16, width=480)
        card.place(relx=0.5, rely=0.5, anchor="center")
        card.pack_propagate(False)
        card.configure(height=380)

        ctk.CTkLabel(
            card, text="🔑  Ativação de Licença",
            font=ctk.CTkFont(size=18, weight="bold"),
        ).pack(pady=(28, 4))

        if msg:
            ctk.CTkLabel(
                card, text=msg,
                font=ctk.CTkFont(size=12), text_color=C_RED,
                wraplength=400,
            ).pack(padx=20, pady=(0, 8))
        else:
            ctk.CTkLabel(
                card, text="Informe sua chave para usar o software.",
                font=ctk.CTkFont(size=12), text_color=C_GRAY,
            ).pack(pady=(0, 8))

        ctk.CTkLabel(
            card, text="Chave de Licença:",
            font=ctk.CTkFont(size=12), anchor="w",
        ).pack(fill="x", padx=40)

        key_var = ctk.StringVar()
        key_entry = ctk.CTkEntry(
            card, textvariable=key_var,
            placeholder_text="MILH-XXXX-XXXX-XXXX",
            width=400, height=40,
            font=ctk.CTkFont(size=14, family="Consolas"),
        )
        key_entry.pack(padx=40, pady=(4, 16))
        key_entry.focus()

        msg_lbl = ctk.CTkLabel(card, text="", font=ctk.CTkFont(size=12), wraplength=400)
        msg_lbl.pack(padx=20, pady=(0, 4))

        btn = ctk.CTkButton(
            card, text="Ativar Software", width=200, height=42,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="#27ae60", hover_color="#2ecc71",
        )
        btn.pack(pady=(0, 8))

        ctk.CTkLabel(
            card, text="Não tem uma chave? Contate: suporte@milhasup.com.br",
            font=ctk.CTkFont(size=10), text_color=C_GRAY,
        ).pack(pady=(4, 20))

        def _do_activate():
            key = key_var.get().strip()
            if not key:
                msg_lbl.configure(text="Digite a chave de licença.", text_color=C_RED)
                return
            btn.configure(state="disabled", text="Verificando...")
            msg_lbl.configure(text="Conectando ao servidor...", text_color=C_GRAY)

            def _run():
                ok, result_msg = self._lic.activate(key)
                def _update():
                    btn.configure(state="normal", text="Ativar Software")
                    if ok:
                        msg_lbl.configure(text=result_msg, text_color=C_GREEN)
                        # Reinicia a aplicação com a licença ativa
                        self.after(1500, self._restart_with_license)
                    else:
                        msg_lbl.configure(text=result_msg, text_color=C_RED)
                self.after(0, _update)
            threading.Thread(target=_run, daemon=True).start()

        btn.configure(command=_do_activate)
        key_entry.bind("<Return>", lambda e: _do_activate())

    def _restart_with_license(self):
        """Reconstrói a UI completa após ativação bem-sucedida."""
        for widget in self.winfo_children():
            widget.destroy()
        self._build_ui()
        self._setup_tray()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(200, self._poll)

    # ── Onboarding ────────────────────────────────────────────────────────────

    def _needs_onboarding(self) -> bool:
        """Retorna True se .env não tiver TG_API_ID configurado."""
        return not read_env().get("TG_API_ID", "").strip()

    def _show_onboarding_wizard(self):
        """Wizard de configuração inicial — aparece quando o .env está vazio."""
        wiz = ctk.CTkToplevel(self)
        wiz.title("✈  Configuração Inicial — Milhas UP")
        wiz.geometry("660x700")
        wiz.minsize(560, 580)
        wiz.resizable(True, True)
        wiz.transient(self)
        wiz.grab_set()
        wiz.focus_force()

        # ── Variáveis de dados ────────────────────────────────────────────────
        env = read_env()
        def _sv(key, default=""):
            v = ctk.StringVar(value=env.get(key, default))
            return v
        def _bv(key, default=False):
            v = ctk.BooleanVar(value=(env.get(key, "1" if default else "0") == "1"))
            return v

        V: dict = {
            "TG_API_ID":              _sv("TG_API_ID"),
            "TG_API_HASH":            _sv("TG_API_HASH"),
            "TG_PHONE":               _sv("TG_PHONE"),
            "LATAM_THRESHOLD_PER_CPF": _sv("LATAM_THRESHOLD_PER_CPF", "50000"),
            "LATAM_REPLY":            _sv("LATAM_REPLY",  "25,00"),
            "LATAM_MAX_MILES":        _sv("LATAM_MAX_MILES",  "194000"),
            "SMILES_THRESHOLD_PER_CPF": _sv("SMILES_THRESHOLD_PER_CPF", "27000"),
            "SMILES_REPLY":           _sv("SMILES_REPLY", "16,00"),
            "SMILES_MAX_MILES":       _sv("SMILES_MAX_MILES", "675000"),
            "AZUL_THRESHOLD_PER_CPF": _sv("AZUL_THRESHOLD_PER_CPF", "30000"),
            "AZUL_REPLY":             _sv("AZUL_REPLY",   "18,00"),
            "AZUL_MAX_MILES":         _sv("AZUL_MAX_MILES", "200000"),
            "NTFY_TOPIC":             _sv("NTFY_TOPIC"),
            "SEND_DELAY_SECONDS":     _sv("SEND_DELAY_SECONDS", "3"),
            "ACEITA_LIMINAR":         _bv("ACEITA_LIMINAR", True),
            "DRY_RUN":                _bv("DRY_RUN", False),
            "_targets_box":           None,  # textbox, atribuído no build_step_2
        }

        step_state = [0]

        TITLES = [
            ("🎉  Bem-vindo ao Milhas UP!",           ""),
            ("📱  Credenciais do Telegram",            "Passo 1 de 4"),
            ("📡  Grupos para Monitorar",              "Passo 2 de 4"),
            ("✈  Regras de Compra por Programa",      "Passo 3 de 4"),
            ("⚙  Preferências e Notificações",        "Passo 4 de 4"),
            ("✅  Configuração Concluída!",            ""),
        ]

        # ── Layout ────────────────────────────────────────────────────────────
        hdr = ctk.CTkFrame(wiz, height=62, corner_radius=0, fg_color=C_DARK)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        lbl_title = ctk.CTkLabel(hdr, text="", font=ctk.CTkFont(size=15, weight="bold"))
        lbl_title.pack(pady=(10, 0))
        lbl_sub = ctk.CTkLabel(hdr, text="", font=ctk.CTkFont(size=10), text_color=C_GRAY)
        lbl_sub.pack()

        content = ctk.CTkScrollableFrame(wiz, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=24, pady=10)

        ftr = ctk.CTkFrame(wiz, height=68, corner_radius=0, fg_color=C_DARK)
        ftr.pack(fill="x")
        ftr.pack_propagate(False)
        err_lbl = ctk.CTkLabel(ftr, text="", font=ctk.CTkFont(size=11), text_color=C_RED)
        err_lbl.pack(pady=(6, 0))
        btn_row = ctk.CTkFrame(ftr, fg_color="transparent")
        btn_row.pack(fill="x", padx=20, pady=(2, 10))
        btn_back = ctk.CTkButton(btn_row, text="← Voltar", width=110, height=36,
                                  fg_color="gray40", hover_color="gray50")
        btn_back.pack(side="left")
        btn_next = ctk.CTkButton(btn_row, text="Próximo →", width=150, height=36,
                                  fg_color="#27ae60", hover_color="#2ecc71",
                                  font=ctk.CTkFont(size=13, weight="bold"))
        btn_next.pack(side="right")

        # ── Helpers de widget ─────────────────────────────────────────────────
        def _h1(parent, text):
            ctk.CTkLabel(parent, text=text, anchor="w", wraplength=580,
                         font=ctk.CTkFont(size=13, weight="bold")).pack(fill="x", pady=(4, 2))

        def _txt(parent, text, color=None):
            kw = {"text": text, "anchor": "w", "wraplength": 580,
                  "justify": "left", "font": ctk.CTkFont(size=11)}
            if color:
                kw["text_color"] = color
            ctk.CTkLabel(parent, **kw).pack(fill="x", pady=(2, 0))

        def _field(parent, label, var, placeholder="", password=False, hint=""):
            ctk.CTkLabel(parent, text=label, anchor="w",
                         font=ctk.CTkFont(size=12, weight="bold")).pack(fill="x", pady=(10, 0))
            if hint:
                ctk.CTkLabel(parent, text=hint, anchor="w", wraplength=580,
                             font=ctk.CTkFont(size=10), text_color=C_GRAY).pack(fill="x")
            e = ctk.CTkEntry(parent, textvariable=var, placeholder_text=placeholder,
                             show="*" if password else "", height=36)
            e.pack(fill="x", pady=(3, 0))
            return e

        def _sep(parent, pady=6):
            ctk.CTkFrame(parent, height=1, fg_color="gray30").pack(fill="x", pady=pady)

        def _prog_3cols(parent, label, key_prefix):
            _sep(parent, pady=4)
            ctk.CTkLabel(parent, text=label, anchor="w",
                         font=ctk.CTkFont(size=12, weight="bold")).pack(fill="x", pady=(4, 4))
            row = ctk.CTkFrame(parent, fg_color="transparent")
            row.pack(fill="x")
            row.grid_columnconfigure((0, 1, 2), weight=1)
            specs = [
                ("Mínimo/CPF (milhas)",   f"{key_prefix}_THRESHOLD_PER_CPF",
                 "Ofertas abaixo desse valor por CPF são ignoradas"),
                ("Preço de Resposta (R$)", f"{key_prefix}_REPLY",
                 "Quanto você paga por lote de milhas"),
                ("Máximo total (milhas)",  f"{key_prefix}_MAX_MILES",
                 "Ignora oferta se total de milhas for maior"),
            ]
            for col, (lbl, key, hint) in enumerate(specs):
                f = ctk.CTkFrame(row, corner_radius=8)
                f.grid(row=0, column=col, padx=3, pady=3, sticky="nsew")
                ctk.CTkLabel(f, text=lbl, wraplength=155, justify="left",
                             font=ctk.CTkFont(size=10), text_color=C_GRAY).pack(padx=8, pady=(6,1), anchor="w")
                ctk.CTkEntry(f, textvariable=V[key], height=32).pack(padx=8, pady=(0,4), fill="x")
                ctk.CTkLabel(f, text=hint, wraplength=155, justify="left",
                             font=ctk.CTkFont(size=9), text_color="gray50").pack(padx=8, pady=(0,6), anchor="w")

        # ── Builders de passo ─────────────────────────────────────────────────
        def build_0():
            _h1(content, "🎉  Bem-vindo ao Milhas UP Telegram Monitor!")
            _txt(content,
                 "Este assistente vai te guiar pela configuração inicial. "
                 "Em poucos passos o monitor estará pronto para capturar as melhores ofertas de milhas do Telegram!")
            ctk.CTkFrame(content, height=10, fg_color="transparent").pack()
            for icon, title, desc in [
                ("📱", "Credenciais do Telegram",
                 "API ID, API Hash e número de telefone — necessários para conectar ao Telegram"),
                ("📡", "Grupos para Monitorar",
                 "Os grupos do Telegram que o monitor vai acompanhar em tempo real"),
                ("✈", "Regras de Compra",
                 "Limites mínimos por CPF e preços de resposta para LATAM, SMILES e Azul"),
                ("⚙", "Preferências",
                 "Notificações no celular (ntfy), filtros e configurações avançadas"),
            ]:
                r = ctk.CTkFrame(content, corner_radius=10)
                r.pack(fill="x", pady=3)
                ctk.CTkLabel(r, text=icon, font=ctk.CTkFont(size=22), width=44
                             ).pack(side="left", padx=10, pady=10)
                c = ctk.CTkFrame(r, fg_color="transparent")
                c.pack(side="left", fill="both", expand=True, pady=8)
                ctk.CTkLabel(c, text=title, anchor="w",
                             font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w")
                ctk.CTkLabel(c, text=desc, anchor="w", wraplength=490,
                             font=ctk.CTkFont(size=10), text_color=C_GRAY).pack(anchor="w")
            ctk.CTkFrame(content, height=6, fg_color="transparent").pack()
            _txt(content,
                 "💡 Todas as configurações podem ser editadas depois, na aba Configuração.",
                 color=C_BLUE)

        def build_1():
            _h1(content, "Como obter suas credenciais do Telegram:")
            info = ctk.CTkFrame(content, corner_radius=8, fg_color="#162032")
            info.pack(fill="x", pady=(4, 10))
            ctk.CTkLabel(info,
                text="  1. Abra  https://my.telegram.org  no seu navegador\n"
                     "  2. Faça login com o mesmo número de telefone que usa no Telegram\n"
                     "  3. Clique em  'API development tools'\n"
                     "  4. Crie um app — coloque qualquer nome (ex: MilhasUP)\n"
                     "  5. Copie o  App api_id  (número) e o  App api_hash  (código longo)",
                justify="left", font=ctk.CTkFont(size=11, family="Consolas"),
                text_color="#79c0ff").pack(padx=14, pady=10, anchor="w")

            _field(content, "API ID", V["TG_API_ID"],
                   placeholder="Ex: 12345678",
                   hint="Número inteiro. Obtido em my.telegram.org → API development tools")
            _field(content, "API Hash", V["TG_API_HASH"],
                   placeholder="Ex: a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6",
                   password=True,
                   hint="Código hexadecimal longo. Trate como senha — nunca compartilhe!")
            _field(content, "Número de Telefone", V["TG_PHONE"],
                   placeholder="Ex: +5534999768872",
                   hint="Com código do país (+55 para Brasil). Deve ser o mesmo número da sua conta Telegram.")
            ctk.CTkFrame(content, height=6, fg_color="transparent").pack()
            _txt(content,
                 "⚠  Na primeira vez que o monitor iniciar, o Telegram vai enviar um código de "
                 "verificação para o seu app do Telegram. Uma janelinha vai abrir para você digitar o código.",
                 color=C_ORANGE)

        def build_2():
            _h1(content, "Quais grupos o monitor deve acompanhar?")
            _txt(content,
                 "Cole abaixo os nomes EXATOS dos grupos do Telegram — um grupo por linha. "
                 "O nome deve ser idêntico ao que aparece no cabeçalho do grupo no app do Telegram "
                 "(incluindo maiúsculas, acentos e espaços).")
            ex = ctk.CTkFrame(content, corner_radius=8, fg_color="#162032")
            ex.pack(fill="x", pady=(8, 4))
            ctk.CTkLabel(ex,
                text="  Exemplos (use os nomes reais dos seus grupos):\n"
                     "  Milhas e Pontos Brasil\n"
                     "  Clube de Milhas LATAM\n"
                     "  Grupo Smiles Promoções",
                justify="left", font=ctk.CTkFont(size=11, family="Consolas"),
                text_color="#79c0ff").pack(padx=14, pady=8, anchor="w")
            ctk.CTkLabel(content, text="Grupos para monitorar (um por linha):",
                         anchor="w", font=ctk.CTkFont(size=12, weight="bold")).pack(fill="x", pady=(8, 3))
            V["_targets_box"] = ctk.CTkTextbox(
                content, height=170, corner_radius=6,
                font=ctk.CTkFont(family="Consolas", size=11))
            V["_targets_box"].pack(fill="x")
            existing = read_env().get("TG_TARGETS", "")
            if existing:
                items = [x.strip() for x in existing.split(",") if x.strip()]
                V["_targets_box"].insert("1.0", "\n".join(items))
            _txt(content,
                 "💡 O monitor detecta automaticamente ofertas de LATAM, SMILES e Azul — "
                 "não é necessário configurar palavras-chave.", color=C_BLUE)

        def build_3():
            _h1(content, "Configure os limites de compra para cada programa")
            _txt(content,
                 "O monitor verifica cada oferta e responde automaticamente quando ela atinge "
                 "seus critérios. Configure abaixo os valores mínimos por CPF e o preço que você quer pagar.",
                 color=C_GRAY)
            _prog_3cols(content, "✈  LATAM Pass", "LATAM")
            _prog_3cols(content, "🌟  SMILES",     "SMILES")
            _prog_3cols(content, "🔵  Azul Fidelidade", "AZUL")
            ctk.CTkFrame(content, height=6, fg_color="transparent").pack()
            _txt(content,
                 "💡 Você pode ajustar esses valores a qualquer momento na aba Configuração.",
                 color=C_BLUE)

        def build_4():
            _h1(content, "Notificações no celular com ntfy.sh")
            ntfy_info = ctk.CTkFrame(content, corner_radius=8, fg_color="#162032")
            ntfy_info.pack(fill="x", pady=(4, 10))
            ctk.CTkLabel(ntfy_info,
                text="  Como configurar notificações ntfy (opcional):\n"
                     "  1. Instale o app 'ntfy' no seu celular (Android ou iOS)\n"
                     "  2. Acesse https://ntfy.sh e crie um tópico (ex: milhas-meu-nome-123)\n"
                     "  3. Cole o nome do tópico abaixo — o monitor vai te notificar a cada oferta!",
                justify="left", font=ctk.CTkFont(size=11, family="Consolas"),
                text_color="#79c0ff").pack(padx=14, pady=10, anchor="w")
            _field(content, "Tópico ntfy.sh (opcional)", V["NTFY_TOPIC"],
                   placeholder="Ex: milhas-joao-secreto-2026",
                   hint="Deixe em branco para desativar notificações no celular.")

            _sep(content)
            _h1(content, "⚙  Configurações avançadas")
            _field(content, "Delay entre envios (segundos)", V["SEND_DELAY_SECONDS"],
                   placeholder="3",
                   hint="Tempo de espera entre respostas para evitar flood no Telegram. Recomendado: 3 segundos.")

            _sep(content)
            _h1(content, "🎛  Filtros de Oferta")
            for lbl, key, title_hint, body_hint in [
                ("Aceita Liminar", "ACEITA_LIMINAR",
                 "O que é 'liminar'?",
                 "Algumas ofertas de milhas envolvem disputas judiciais chamadas 'liminares'. "
                 "Se ATIVADO, o monitor responde essas ofertas. Se DESATIVADO, as ofertas com a "
                 "palavra 'liminar' são ignoradas. Ative apenas se você aceitar esse tipo de oferta."),
                ("Modo Teste (Dry-run)", "DRY_RUN",
                 "O que é Dry-run?",
                 "Se ATIVADO, o monitor analisa as ofertas normalmente mas NÃO envia nenhuma resposta. "
                 "Útil para testar se as configurações estão certas sem gastar nada. "
                 "Desative quando estiver pronto para usar de verdade."),
            ]:
                r = ctk.CTkFrame(content, corner_radius=10)
                r.pack(fill="x", pady=5)
                col = ctk.CTkFrame(r, fg_color="transparent")
                col.pack(side="left", fill="both", expand=True, padx=12, pady=8)
                ctk.CTkLabel(col, text=lbl, anchor="w",
                             font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w")
                ctk.CTkLabel(col, text=title_hint, anchor="w",
                             font=ctk.CTkFont(size=10, weight="bold"),
                             text_color=C_BLUE).pack(anchor="w")
                ctk.CTkLabel(col, text=body_hint, anchor="w", wraplength=470,
                             font=ctk.CTkFont(size=10), text_color=C_GRAY).pack(anchor="w")
                ctk.CTkSwitch(r, text="", variable=V[key], width=50
                              ).pack(side="right", padx=16, pady=8)

        def build_5():
            _h1(content, "🎉  Tudo certo! O monitor está configurado.")
            _txt(content, "Aqui está um resumo do que você configurou:", color=C_GRAY)
            summary = ctk.CTkFrame(content, corner_radius=10)
            summary.pack(fill="x", pady=(8, 12))
            env_now = read_env()
            rows = [
                ("📱 Telefone Telegram",    V["TG_PHONE"].get() or env_now.get("TG_PHONE", "—")),
                ("✈  LATAM mínimo/CPF",     f"{V['LATAM_THRESHOLD_PER_CPF'].get()} milhas"),
                ("🌟 SMILES mínimo/CPF",     f"{V['SMILES_THRESHOLD_PER_CPF'].get()} milhas"),
                ("🔵 Azul mínimo/CPF",       f"{V['AZUL_THRESHOLD_PER_CPF'].get()} milhas"),
                ("🔔 Notificações ntfy",     V["NTFY_TOPIC"].get() or "Desativado"),
                ("🎛 Aceita Liminar",        "Sim" if V["ACEITA_LIMINAR"].get() else "Não"),
                ("🧪 Modo Teste (Dry-run)",  "Ativado (não envia)" if V["DRY_RUN"].get() else "Desativado (envio real)"),
            ]
            for label, value in rows:
                r = ctk.CTkFrame(summary, fg_color="transparent")
                r.pack(fill="x", padx=12, pady=2)
                ctk.CTkLabel(r, text=label, anchor="w", width=220,
                             font=ctk.CTkFont(size=11), text_color=C_GRAY).pack(side="left")
                ctk.CTkLabel(r, text=value, anchor="w",
                             font=ctk.CTkFont(size=11, weight="bold")).pack(side="left")
            _sep(content, pady=8)
            _txt(content,
                 "⚠  Na primeira vez que iniciar, o Telegram vai enviar um código de verificação "
                 "para o seu celular. Uma janela vai aparecer para você digitar o código.",
                 color=C_ORANGE)
            ctk.CTkFrame(content, height=8, fg_color="transparent").pack()
            ctk.CTkButton(
                content, text="▶  Iniciar Monitor Agora", height=46,
                fg_color="#27ae60", hover_color="#2ecc71",
                font=ctk.CTkFont(size=14, weight="bold"),
                command=lambda: (wiz.destroy(), self.after(600, self._start)),
            ).pack(fill="x")
            ctk.CTkButton(
                content, text="Fechar e configurar manualmente depois",
                height=32, fg_color="transparent", hover_color="gray20",
                font=ctk.CTkFont(size=10), text_color=C_GRAY,
                command=wiz.destroy,
            ).pack(pady=(6, 0))

        BUILDERS = [build_0, build_1, build_2, build_3, build_4, build_5]

        # ── Validação ─────────────────────────────────────────────────────────
        def validate(n) -> bool:
            err_lbl.configure(text="")
            if n == 1:
                if not V["TG_API_ID"].get().strip():
                    err_lbl.configure(text="⚠  Preencha o API ID do Telegram")
                    return False
                if not V["TG_API_ID"].get().strip().isdigit():
                    err_lbl.configure(text="⚠  O API ID deve conter apenas números (ex: 12345678)")
                    return False
                if not V["TG_API_HASH"].get().strip():
                    err_lbl.configure(text="⚠  Preencha o API Hash do Telegram")
                    return False
                ph = V["TG_PHONE"].get().strip()
                if not ph:
                    err_lbl.configure(text="⚠  Preencha o número de telefone")
                    return False
                if not ph.startswith("+"):
                    err_lbl.configure(text="⚠  O telefone deve começar com + (ex: +5511999999999)")
                    return False
            if n == 2:
                tb = V.get("_targets_box")
                if tb and not tb.get("1.0", "end").strip():
                    err_lbl.configure(text="⚠  Adicione pelo menos um grupo para monitorar")
                    return False
            return True

        # ── Coleta e salva no .env ────────────────────────────────────────────
        def collect(n):
            updates: dict = {}
            if n >= 1:
                updates["TG_API_ID"]   = V["TG_API_ID"].get().strip()
                updates["TG_API_HASH"] = V["TG_API_HASH"].get().strip()
                updates["TG_PHONE"]    = V["TG_PHONE"].get().strip()
            if n >= 2:
                tb = V.get("_targets_box")
                if tb:
                    raw = tb.get("1.0", "end").strip()
                    updates["TG_TARGETS"] = ", ".join(
                        l.strip() for l in raw.splitlines() if l.strip()
                    )
            if n >= 3:
                for prog in ("LATAM", "SMILES", "AZUL"):
                    for suf in ("THRESHOLD_PER_CPF", "REPLY", "MAX_MILES"):
                        k = f"{prog}_{suf}"
                        updates[k] = V[k].get().strip()
            if n >= 4:
                updates["NTFY_TOPIC"]         = V["NTFY_TOPIC"].get().strip()
                updates["SEND_DELAY_SECONDS"] = V["SEND_DELAY_SECONDS"].get().strip() or "3"
                updates["ACEITA_LIMINAR"]     = "1" if V["ACEITA_LIMINAR"].get() else "0"
                updates["DRY_RUN"]            = "1" if V["DRY_RUN"].get() else "0"
            if updates:
                write_env_keys(updates)

        # ── Navegação ─────────────────────────────────────────────────────────
        def show_step(n):
            step_state[0] = n
            for w in content.winfo_children():
                w.destroy()
            t, s = TITLES[n]
            lbl_title.configure(text=t)
            lbl_sub.configure(text=s)
            btn_back.configure(state="disabled" if n == 0 else "normal")
            if n == 0:
                btn_next.configure(text="Começar →", width=150)
            elif n == 5:
                btn_next.configure(text="Fechar", fg_color="gray40",
                                   hover_color="gray50", width=110)
            else:
                btn_next.configure(text="Próximo →", fg_color="#27ae60",
                                   hover_color="#2ecc71", width=150)
            BUILDERS[n]()

        def go_next():
            n = step_state[0]
            if n == 5:
                wiz.destroy()
                return
            if not validate(n):
                return
            collect(n)
            show_step(n + 1)

        def go_back():
            if step_state[0] > 0:
                show_step(step_state[0] - 1)

        btn_back.configure(command=go_back)
        btn_next.configure(command=go_next)
        wiz.bind("<Return>", lambda e: go_next())

        # Centraliza sobre a janela principal
        self.update_idletasks()
        x = self.winfo_x() + (self.winfo_width()  - 660) // 2
        y = self.winfo_y() + (self.winfo_height() - 700) // 2
        wiz.geometry(f"660x700+{max(0,x)}+{max(0,y)}")

        show_step(0)

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
        self._t_lic  = self._tabs.add("  Licença  ")

        self._build_dashboard()
        self._build_config()
        self._build_logs()
        self._build_license_tab()

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
        sf.grid_columnconfigure((0, 1, 2, 3, 4), weight=1)
        self._st_total  = self._stat(sf, "Total Respondidas", "—", 0)
        self._st_latam  = self._stat(sf, "LATAM",             "—", 1)
        self._st_smiles = self._stat(sf, "SMILES",            "—", 2)
        self._st_azul   = self._stat(sf, "AZUL",              "—", 3)
        self._st_last   = self._stat(sf, "Última Resposta",   "—", 4)

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
        if HAS_LICENSE and self._lic is not None:
            ok, reason = self._lic.check_or_grace()
            if not ok:
                msgs = {
                    "expired_local": "Licença expirada. Renove sua assinatura.",
                    "revoked":       "Licença revogada. Contate o suporte.",
                    "grace_expired": "Sem conexão com servidor de licença por mais de 24h.",
                }
                self.toast(msgs.get(reason, f"Licença inválida: {reason}"), False)
                return
        # Verifica se a sessão Telegram existe — se não, faz auth primeiro
        if not SESSION_PATH.exists():
            self._do_telegram_auth(then_start=True)
            return
        self._btn_start.configure(state="disabled", text="Iniciando...")
        threading.Thread(target=self._do_start, daemon=True).start()

    def _do_telegram_auth(self, then_start: bool = False):
        """Abre uma janela de terminal para autenticar o Telegram via --auth."""
        monitor_exe = BASE_DIR / "monitor_bg" / "monitor_bg.exe"
        if not monitor_exe.exists():
            messagebox.showerror("Erro", f"Executável não encontrado:\n{monitor_exe}")
            return

        # Confirma com o usuário
        answer = messagebox.askokcancel(
            "Autenticar Telegram",
            "A sessão do Telegram não está autenticada.\n\n"
            "Uma janela de terminal será aberta.\n"
            "Siga as instruções e informe o código que chegará no seu Telegram.\n\n"
            "Clique OK para continuar."
        )
        if not answer:
            return

        # Lança o executável com --auth em uma janela de console visível
        try:
            subprocess.Popen(
                [str(monitor_exe), "--auth"],
                cwd=str(BASE_DIR),
                creationflags=subprocess.CREATE_NEW_CONSOLE,
            )
        except Exception as e:
            messagebox.showerror("Erro ao abrir terminal", str(e))
            return

        # Aguarda a criação do session.session em background
        def _wait_for_session():
            self.after(0, lambda: self.toast("Aguardando autenticação Telegram...", True))
            for _ in range(300):   # até 5 minutos
                time.sleep(1)
                if SESSION_PATH.exists():
                    self.after(0, lambda: self.toast("✅ Telegram autenticado!", True))
                    if then_start:
                        time.sleep(0.8)
                        self.after(0, self._start)
                    return
            self.after(0, lambda: self.toast("Timeout: sessão Telegram não foi criada.", False))

        threading.Thread(target=_wait_for_session, daemon=True).start()

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

        section("Regras Azul Fidelidade", "🔵")
        field("Mínimo por CPF (milhas)", "AZUL_THRESHOLD_PER_CPF", "Ex: 30000")
        field("Preço de Resposta (R$)",  "AZUL_REPLY",              "Ex: 18,00")
        field("Máximo total (milhas)",   "AZUL_MAX_MILES",          "Ex: 200000")

        section("Notificações", "🔔")
        field("Telegram — alvo (Salvas)", "TG_NOTIFY_TARGET", "Ex: me")
        field("Tópico ntfy.sh",           "NTFY_TOPIC",       "Ex: milhas-meu-topico")

        section("Avançado", "⚙")
        field("Delay entre envios (s)", "SEND_DELAY_SECONDS", "Ex: 3")
        check("Modo Teste — Dry-run (não envia)", "DRY_RUN")
        check("Aceita Liminar (responder ofertas com 'liminar')", "ACEITA_LIMINAR")

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

    # ── Aba Licença ───────────────────────────────────────────────────────────

    def _build_license_tab(self):
        p = self._t_lic

        card = ctk.CTkFrame(p, corner_radius=12)
        card.pack(fill="x", padx=16, pady=16)

        ctk.CTkLabel(
            card, text="Status da Licença",
            font=ctk.CTkFont(size=13, weight="bold"), anchor="w",
        ).pack(fill="x", padx=16, pady=(14, 4))

        # Labels de status (serão atualizados por _update_license_tab)
        self._lic_status_lbl = ctk.CTkLabel(
            card, text="...", font=ctk.CTkFont(size=14, weight="bold"),
        )
        self._lic_status_lbl.pack(anchor="w", padx=16)

        grid = ctk.CTkFrame(card, fg_color="transparent")
        grid.pack(fill="x", padx=16, pady=(8, 0))
        grid.grid_columnconfigure((0, 1, 2, 3), weight=1)

        def _lf(parent, label, col, row=0):
            f = ctk.CTkFrame(parent, corner_radius=8)
            f.grid(row=row, column=col, padx=4, pady=4, sticky="nsew")
            ctk.CTkLabel(f, text=label, font=ctk.CTkFont(size=10),
                         text_color=C_GRAY).pack(pady=(6, 0))
            lbl = ctk.CTkLabel(f, text="—", font=ctk.CTkFont(size=13, weight="bold"))
            lbl.pack(pady=(0, 6))
            return lbl

        self._lic_name_lbl    = _lf(grid, "Cliente",    0)
        self._lic_plan_lbl    = _lf(grid, "Plano",      1)
        self._lic_expiry_lbl  = _lf(grid, "Expira em",  2)
        self._lic_days_lbl    = _lf(grid, "Dias restantes", 3)

        self._lic_check_lbl = ctk.CTkLabel(
            card, text="", font=ctk.CTkFont(size=10), text_color=C_GRAY,
        )
        self._lic_check_lbl.pack(anchor="w", padx=16, pady=(8, 4))

        self._lic_key_lbl = ctk.CTkLabel(
            card, text="", font=ctk.CTkFont(size=10, family="Consolas"),
            text_color=C_GRAY,
        )
        self._lic_key_lbl.pack(anchor="w", padx=16, pady=(0, 4))

        btns = ctk.CTkFrame(card, fg_color="transparent")
        btns.pack(fill="x", padx=16, pady=(8, 14))

        ctk.CTkButton(
            btns, text="↺  Verificar Agora", width=160, height=34,
            command=self._check_license_now,
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            btns, text="🔑  Trocar Chave", width=140, height=34,
            fg_color="gray40", hover_color="gray50",
            command=self._reset_license,
        ).pack(side="left")

        # ── Card de Gerenciamento de Assinatura ───────────────────────────────
        mgmt = ctk.CTkFrame(p, corner_radius=12, border_width=1, border_color="#30363d")
        mgmt.pack(fill="x", padx=16, pady=(12, 0))

        ctk.CTkLabel(
            mgmt, text="Gerenciar Assinatura",
            font=ctk.CTkFont(size=13, weight="bold"), anchor="w",
        ).pack(fill="x", padx=16, pady=(14, 2))

        ctk.CTkLabel(
            mgmt,
            text=(
                "Cancele, renove ou atualize sua assinatura pelo portal da Cakto. "
                "O acesso permanece ativo até o fim do período pago."
            ),
            font=ctk.CTkFont(size=11), text_color=C_GRAY,
            wraplength=640, justify="left", anchor="w",
        ).pack(fill="x", padx=16, pady=(0, 8))

        mgmt_btns = ctk.CTkFrame(mgmt, fg_color="transparent")
        mgmt_btns.pack(fill="x", padx=16, pady=(0, 14))

        ctk.CTkButton(
            mgmt_btns, text="⚙  Gerenciar / Cancelar Assinatura", width=240, height=34,
            fg_color="#1e40af", hover_color="#1d4ed8",
            command=self._open_subscription_portal,
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            mgmt_btns, text="👤  Minha Conta (web)", width=180, height=34,
            fg_color="gray40", hover_color="gray50",
            command=self._open_account_page,
        ).pack(side="left")

        ctk.CTkLabel(
            p, text="Suporte: suporte@milhasup.net.br  |  milhasup.net.br/monitor",
            font=ctk.CTkFont(size=10), text_color=C_GRAY,
        ).pack(pady=(12, 0))

        self._update_license_tab()

    def _update_license_tab(self):
        if not HAS_LICENSE or self._lic is None:
            return
        state = self._lic.get_state()
        if not state or not state.activated:
            self._lic_status_lbl.configure(text="⬤  Não ativada", text_color=C_RED)
            return

        if state.is_expired():
            self._lic_status_lbl.configure(text="⬤  Expirada", text_color=C_RED)
        else:
            days = state.days_remaining() or 0
            if days <= 7:
                self._lic_status_lbl.configure(
                    text=f"⚠  Ativa — expira em {days} dia(s)", text_color=C_ORANGE)
            else:
                self._lic_status_lbl.configure(text="⬤  Ativa", text_color=C_GREEN)

        # Expiry display
        exp_str = "—"
        if state.expires_at:
            try:
                from datetime import timezone
                from datetime import datetime as dt
                exp = dt.fromisoformat(state.expires_at.replace("Z", "+00:00"))
                exp_str = exp.strftime("%d/%m/%Y")
            except Exception:
                exp_str = state.expires_at[:10]

        plan_labels = {"monthly": "Mensal", "annual": "Anual", "lifetime": "Vitalício"}

        self._lic_name_lbl.configure(text=state.customer_name or "—")
        self._lic_plan_lbl.configure(text=plan_labels.get(state.plan, state.plan))
        self._lic_expiry_lbl.configure(text=exp_str)
        days = state.days_remaining()
        self._lic_days_lbl.configure(
            text=str(days) if days is not None else "—",
            text_color=C_RED if (days is not None and days <= 7) else C_GREEN,
        )

        # Último check
        if state.last_check_ts:
            last = datetime.fromtimestamp(state.last_check_ts).strftime("%d/%m %H:%M")
            self._lic_check_lbl.configure(text=f"Último check online: {last}")
        else:
            self._lic_check_lbl.configure(text="Nenhum check registrado")

        # Chave (parcialmente oculta)
        k = state.key
        if len(k) > 9:
            k_disp = k[:9] + "••••" + k[-4:]
        else:
            k_disp = k
        self._lic_key_lbl.configure(text=f"Chave: {k_disp}")

    def _check_license_now(self):
        if not HAS_LICENSE or self._lic is None:
            return
        state = self._lic.get_state()
        if not state:
            return
        # Força recheck zerando last_check_ts temporariamente
        state.last_check_ts = 0
        ok, reason = self._lic.check_or_grace()
        self._update_license_tab()
        if ok:
            self.toast("Licença verificada com sucesso!", True)
        else:
            msgs = {
                "expired":      "Licença expirada. Renove sua assinatura.",
                "revoked":      "Licença revogada. Contate o suporte.",
                "grace_expired":"Sem conexão com servidor por mais de 24h.",
                "hw_mismatch":  "Hardware diferente do registrado.",
            }
            self.toast(msgs.get(reason, f"Erro: {reason}"), False)

    def _reset_license(self):
        if messagebox.askyesno("Trocar Chave",
                               "Deseja remover a ativação atual e inserir uma nova chave?"):
            if self._lic:
                self._lic.clear_local()
            for widget in self.winfo_children():
                widget.destroy()
            self._build_activation_screen()

    def _open_subscription_portal(self):
        """Abre o portal da Cakto para gerenciar/cancelar assinatura."""
        import webbrowser
        portal_url = read_env().get("CAKTO_PORTAL_URL", "https://cakto.com.br/minha-conta")
        webbrowser.open(portal_url)

    def _open_account_page(self):
        """Abre o portal web da conta MilhasUP com a chave preenchida."""
        import webbrowser
        state = self._lic.get_state() if self._lic else None
        base = "https://milhasup-licensing-production.up.railway.app/conta"
        if state and state.key:
            webbrowser.open(f"{base}?key={state.key}")
        else:
            webbrowser.open(base)

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
            if e.get("error"):           parts.append(f"  ERRO: {str(e['error'])[:50]}")

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
        if hasattr(self, "_lic_status_lbl"):
            self._update_license_tab()
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

        total = smiles = latam = azul = 0
        last_time = "—"

        for e in events:
            kind = e.get("kind", "")
            prog = e.get("program", "")
            ts   = datetime.fromtimestamp(e.get("ts", 0)).strftime("%d/%m %H:%M")

            if kind == "send_result" and not e.get("error"):
                # Envio confirmado com sucesso
                total += 1
                if prog == "SMILES":  smiles += 1
                elif prog == "LATAM": latam  += 1
                elif prog == "AZUL":  azul   += 1
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
            elif kind == "send_result" and e.get("error"):
                # Envio tentado mas com erro
                line = f"{ts}  ❌ {prog:<6}  ERRO ao enviar: {str(e.get('error',''))[:70]}\n"
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
        self._st_latam.configure( text=str(latam)  if events else "—")
        self._st_smiles.configure(text=str(smiles) if events else "—")
        self._st_azul.configure(  text=str(azul)   if events else "—")
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
