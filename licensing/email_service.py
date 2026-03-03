"""
Serviço de e-mail para MilhasUP Licensing.
Usa stdlib (smtplib + email) — zero dependências extras.
"""
from __future__ import annotations

import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

# ── Configuração via env ──────────────────────────────────────────────────────
SMTP_HOST     = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT     = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER     = os.getenv("SMTP_USER", "")
SMTP_PASS     = os.getenv("SMTP_PASS", "")
SMTP_FROM     = os.getenv("SMTP_FROM", SMTP_USER)
SMTP_FROM_NAME = os.getenv("SMTP_FROM_NAME", "MilhasUP Monitor")

# URL de download do instalador (GitHub Releases)
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


# ── Envio ─────────────────────────────────────────────────────────────────────

def send_welcome_email(
    to_email: str,
    customer_name: str,
    license_key: str,
    plan: str = "Mensal",
    expires_at: str = "",
) -> bool:
    """
    Envia e-mail de boas-vindas com a chave de licença e link do instalador.
    Retorna True se enviado com sucesso.
    """
    if not SMTP_USER or not SMTP_PASS:
        log.warning("SMTP não configurado (SMTP_USER/SMTP_PASS ausentes). E-mail não enviado.")
        return False

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

    # Fallback texto plano
    text_body = (
        f"Olá, {first_name}!\n\n"
        f"Bem-vindo ao MilhasUP Monitor.\n\n"
        f"Sua chave de licença: {license_key}\n\n"
        f"Plano: {plan}  |  Válido até: {exp_label}\n\n"
        f"Baixe o instalador em:\n{INSTALLER_URL}\n\n"
        f"Dúvidas? {SUPPORT_EMAIL}\n\n"
        f"— Equipe MilhasUP"
    )

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"✈ Bem-vindo ao MilhasUP Monitor — sua chave de licença"
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
        log.info("E-mail de boas-vindas enviado para %s", to_email)
        return True
    except Exception as e:
        log.error("Falha ao enviar e-mail para %s: %s", to_email, e)
        return False
