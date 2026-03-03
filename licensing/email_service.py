"""
Serviço de e-mail para MilhasUP Licensing.
Suporta Resend API (primário) e SMTP (fallback).
Usa apenas stdlib — zero dependências extras.
"""
from __future__ import annotations

import json
import logging
import os
import smtplib
import urllib.request
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

log = logging.getLogger(__name__)

# ── Configuração via env ──────────────────────────────────────────────────────
RESEND_API_KEY  = os.getenv("RESEND_API_KEY", "")
SMTP_HOST       = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT       = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER       = os.getenv("SMTP_USER", "")
SMTP_PASS       = os.getenv("SMTP_PASS", "")
SMTP_FROM       = os.getenv("SMTP_FROM", SMTP_USER)
SMTP_FROM_NAME  = os.getenv("SMTP_FROM_NAME", "MilhasUP Monitor")

# Remetente padrão Resend (deve ser domínio verificado na conta Resend)
RESEND_FROM     = os.getenv("RESEND_FROM", f"{SMTP_FROM_NAME} <noreply@milhasup.net.br>")

# URLs
INSTALLER_URL = os.getenv(
    "INSTALLER_URL",
    "https://github.com/Palmezoni/ccd_telegrammilhas/releases/download/v1.0.0/MilhasUP_Setup_1.0.0.exe",
)
SUPPORT_EMAIL = os.getenv("SUPPORT_EMAIL", "suporte@milhasup.net.br")
LANDING_URL   = os.getenv("LANDING_URL", "https://milhasup.net.br/monitor")
CAKTO_PORTAL  = os.getenv("CAKTO_PORTAL_URL", "https://cakto.com.br/minha-conta")


# ── Template HTML ─────────────────────────────────────────────────────────────

_HERE = Path(__file__).parent


def _load_template() -> str:
    tpl = _HERE / "templates" / "email_welcome.html"
    return tpl.read_text(encoding="utf-8")


def _render(template: str, **kwargs) -> str:
    result = template
    for key, value in kwargs.items():
        result = result.replace(f"{{{{{key}}}}}", str(value))
    return result


# ── Envio via Resend API ───────────────────────────────────────────────────────

def _send_via_resend(to_email: str, subject: str, html_body: str, text_body: str) -> bool:
    payload = json.dumps({
        "from":    RESEND_FROM,
        "to":      [to_email],
        "subject": subject,
        "html":    html_body,
        "text":    text_body,
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://api.resend.com/emails",
        data=payload,
        headers={
            "Authorization": f"Bearer {RESEND_API_KEY}",
            "Content-Type":  "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            body = resp.read().decode()
            log.info("Resend OK → %s | %s", to_email, body)
            return True
    except urllib.error.HTTPError as e:
        err = e.read().decode()
        log.error("Resend HTTP %s para %s: %s", e.code, to_email, err)
        return False
    except Exception as e:
        log.error("Resend erro para %s: %s", to_email, e)
        return False


# ── Envio via SMTP ─────────────────────────────────────────────────────────────

def _send_via_smtp(to_email: str, subject: str, html_body: str, text_body: str) -> bool:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = f"{SMTP_FROM_NAME} <{SMTP_FROM}>"
    msg["To"]      = to_email

    msg.attach(MIMEText(text_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html",  "utf-8"))

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20) as server:
            server.ehlo()
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(SMTP_FROM, [to_email], msg.as_bytes())
        log.info("SMTP OK → %s", to_email)
        return True
    except Exception as e:
        log.error("SMTP erro para %s: %s", to_email, e)
        return False


# ── Pública ────────────────────────────────────────────────────────────────────

def send_welcome_email(
    to_email: str,
    customer_name: str,
    license_key: str,
    plan: str = "Mensal",
    expires_at: str = "",
) -> bool:
    """
    Envia e-mail de boas-vindas com a chave de licença e link do instalador.
    Tenta Resend primeiro; cai para SMTP se configurado.
    Retorna True se enviado com sucesso.
    """
    first_name = customer_name.split()[0].strip() if customer_name else "assinante"

    # Formata data de expiração
    exp_label = expires_at
    if expires_at:
        try:
            from datetime import datetime, timezone
            exp = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
            exp_label = exp.strftime("%d/%m/%Y")
        except Exception:
            exp_label = expires_at[:10]

    try:
        html_template = _load_template()
    except Exception as e:
        log.error("Falha ao carregar template de e-mail: %s", e)
        return False

    html_body = _render(
        html_template,
        customer_name=customer_name,
        first_name=first_name,
        license_key=license_key,
        plan_name=plan,
        expires_at=exp_label,
        installer_url=INSTALLER_URL,
        support_email=SUPPORT_EMAIL,
        landing_url=LANDING_URL,
        cakto_portal=CAKTO_PORTAL,
    )

    text_body = (
        f"Olá, {first_name}!\n\n"
        f"Bem-vindo ao MilhasUP Monitor.\n\n"
        f"Sua chave de licença: {license_key}\n\n"
        f"Plano: {plan}  |  Válido até: {exp_label}\n\n"
        f"Baixe o instalador em:\n{INSTALLER_URL}\n\n"
        f"Dúvidas? {SUPPORT_EMAIL}\n\n"
        f"— Equipe MilhasUP"
    )

    subject = "✈ Bem-vindo ao MilhasUP Monitor — sua chave de licença"

    # 1) Resend (preferido)
    if RESEND_API_KEY:
        return _send_via_resend(to_email, subject, html_body, text_body)

    # 2) SMTP (fallback)
    if SMTP_USER and SMTP_PASS:
        return _send_via_smtp(to_email, subject, html_body, text_body)

    log.warning("Nenhum serviço de e-mail configurado (RESEND_API_KEY ou SMTP_USER/PASS). E-mail não enviado.")
    return False
