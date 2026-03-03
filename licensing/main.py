"""FastAPI — Licensing Server para MilhasUP Telegram Monitor."""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import BackgroundTasks, Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from . import auth, crud, models, schemas
from .database import Base, engine, get_db
from .email_service import (
    CAKTO_PORTAL, INSTALLER_URL, LANDING_URL, SMTP_USER, SUPPORT_EMAIL,
    send_welcome_email,
)

log = logging.getLogger(__name__)

# Cria tabelas se não existirem
Base.metadata.create_all(bind=engine)

# ── Webhook config ────────────────────────────────────────────────────────────
CAKTO_WEBHOOK_SECRET = os.getenv("CAKTO_WEBHOOK_SECRET", "")
CAKTO_URL            = os.getenv("CAKTO_URL", "#assinar")

app = FastAPI(title="MilhasUP License API", docs_url=None, redoc_url=None)

_HERE = os.path.dirname(__file__)
templates = Jinja2Templates(directory=os.path.join(_HERE, "templates"))
app.mount("/static", StaticFiles(directory=os.path.join(_HERE, "static")), name="static")


# ── Filtros Jinja ─────────────────────────────────────────────────────────────

def _status_badge(status: str) -> str:
    colors = {
        "active":  "success",
        "pending": "warning",
        "expired": "secondary",
        "revoked": "danger",
    }
    labels = {
        "active":  "● Ativa",
        "pending": "○ Pendente",
        "expired": "✗ Expirada",
        "revoked": "✗ Revogada",
    }
    c = colors.get(status, "secondary")
    l = labels.get(status, status)
    return f'<span class="badge bg-{c}">{l}</span>'


templates.env.filters["status_badge"] = _status_badge


def _fmtdt(dt) -> str:
    if not dt:
        return "—"
    if isinstance(dt, str):
        return dt[:16].replace("T", " ")
    return dt.strftime("%d/%m/%Y %H:%M")


templates.env.filters["fmtdt"] = _fmtdt


def _days_remaining(expires_at) -> str:
    if not expires_at:
        return ""
    try:
        delta = expires_at - datetime.now(timezone.utc)
        d = delta.days
        if d < 0:
            return f'<span class="text-danger">({abs(d)} dias atrás)</span>'
        if d <= 7:
            return f'<span class="text-warning">({d} dias)</span>'
        return f'<span class="text-muted">({d} dias)</span>'
    except Exception:
        return ""


templates.env.filters["days_remaining"] = _days_remaining


# ── Client API Endpoints ──────────────────────────────────────────────────────

@app.post("/api/v1/activate")
def api_activate(
    body: schemas.ActivateRequest,
    request: Request,
    db: Session = Depends(get_db),
    _: str = Depends(auth.verify_api_key),
):
    lic = crud.get_license_by_key(db, body.license_key)
    ip = request.client.host if request.client else ""

    if not lic:
        raise HTTPException(404, {"error": "not_found", "message": "Chave de licença inválida."})

    if lic.status == "revoked":
        crud.log_check(db, lic, "activate", body.hw_fingerprint, "revoked", ip)
        raise HTTPException(403, {"error": "revoked", "message": "Licença revogada. Contate o suporte."})

    if lic.expires_at and lic.expires_at < datetime.now(timezone.utc):
        crud.expire_license(db, lic)
        crud.log_check(db, lic, "activate", body.hw_fingerprint, "expired", ip)
        raise HTTPException(410, {"error": "expired", "message": "Licença expirada. Por favor renove."})

    if lic.hw_fingerprint and lic.hw_fingerprint != body.hw_fingerprint:
        crud.log_check(db, lic, "activate", body.hw_fingerprint, "hw_mismatch", ip)
        raise HTTPException(409, {"error": "hw_mismatch",
                                  "message": "Licença vinculada a outro hardware. Contate o suporte."})

    # Bind hardware na primeira ativação
    if not lic.hw_fingerprint:
        crud.bind_hardware(db, lic, body.hw_fingerprint, body.hw_label)

    crud.set_active(db, lic)
    crud.log_check(db, lic, "activate", body.hw_fingerprint, "ok", ip)
    token = auth.create_jwt(lic.key)

    return {
        "status": "activated",
        "token": token,
        "customer_name": lic.customer_name,
        "plan": lic.plan,
        "expires_at": lic.expires_at.isoformat(),
    }


@app.post("/api/v1/check")
def api_check(
    body: schemas.CheckRequest,
    request: Request,
    db: Session = Depends(get_db),
    _: str = Depends(auth.verify_api_key),
):
    lic = crud.get_license_by_key(db, body.license_key)
    ip = request.client.host if request.client else ""

    if not lic:
        raise HTTPException(404, {"error": "not_found"})

    if lic.status == "revoked":
        crud.log_check(db, lic, "check", body.hw_fingerprint, "revoked", ip)
        raise HTTPException(403, {"error": "revoked"})

    if lic.expires_at and lic.expires_at < datetime.now(timezone.utc):
        crud.expire_license(db, lic)
        crud.log_check(db, lic, "check", body.hw_fingerprint, "expired", ip)
        raise HTTPException(410, {"error": "expired"})

    if lic.hw_fingerprint and lic.hw_fingerprint != body.hw_fingerprint:
        crud.log_check(db, lic, "check", body.hw_fingerprint, "hw_mismatch", ip)
        raise HTTPException(409, {"error": "hw_mismatch"})

    crud.log_check(db, lic, "check", body.hw_fingerprint, "ok", ip)
    days = (lic.expires_at - datetime.now(timezone.utc)).days if lic.expires_at else None

    return {
        "status": "ok",
        "expires_at": lic.expires_at.isoformat(),
        "days_remaining": days,
    }


# ── Admin Login ───────────────────────────────────────────────────────────────

@app.get("/admin/login", response_class=HTMLResponse)
def admin_login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "error": ""})


@app.post("/admin/login")
def admin_login(request: Request, password: str = Form(...)):
    if password == auth.ADMIN_TOKEN:
        resp = RedirectResponse("/admin/", status_code=302)
        resp.set_cookie("admin_token", password, httponly=True, max_age=86400 * 7)
        return resp
    return templates.TemplateResponse("login.html", {"request": request, "error": "Senha incorreta."})


@app.get("/admin/logout")
def admin_logout():
    resp = RedirectResponse("/admin/login", status_code=302)
    resp.delete_cookie("admin_token")
    return resp


# ── Admin — Licenças ─────────────────────────────────────────────────────────

@app.get("/admin/", response_class=HTMLResponse)
def admin_list(
    request: Request,
    search: str = "",
    status: str = "",
    page: int = 1,
    db: Session = Depends(get_db),
    _=Depends(auth.verify_admin),
):
    per_page = 25
    items, total = crud.list_licenses(db, search=search, status=status, page=page, per_page=per_page)
    s = crud.stats(db)
    pages = max(1, (total + per_page - 1) // per_page)
    return templates.TemplateResponse("licenses_list.html", {
        "request": request,
        "licenses": items,
        "stats": s,
        "search": search,
        "status_filter": status,
        "page": page,
        "pages": pages,
        "total": total,
    })


@app.get("/admin/new", response_class=HTMLResponse)
def admin_new_form(request: Request, _=Depends(auth.verify_admin)):
    from datetime import date
    default_expires = (datetime.now(timezone.utc) + timedelta(days=30)).strftime("%Y-%m-%d")
    return templates.TemplateResponse("license_create.html", {
        "request": request,
        "default_expires": default_expires,
        "error": "",
    })


@app.post("/admin/new")
def admin_new_submit(
    request: Request,
    customer_name: str = Form(...),
    customer_email: str = Form(...),
    plan: str = Form("monthly"),
    expires_at: str = Form(...),
    notes: str = Form(""),
    db: Session = Depends(get_db),
    _=Depends(auth.verify_admin),
):
    try:
        exp_dt = datetime.fromisoformat(expires_at).replace(tzinfo=timezone.utc)
    except ValueError:
        return templates.TemplateResponse("license_create.html", {
            "request": request,
            "default_expires": expires_at,
            "error": "Data inválida.",
        })
    data = schemas.LicenseCreate(
        customer_name=customer_name,
        customer_email=customer_email,
        plan=plan,
        expires_at=exp_dt,
        notes=notes or None,
    )
    lic = crud.create_license(db, data)
    return RedirectResponse(f"/admin/{lic.id}", status_code=302)


@app.get("/admin/{lic_id}", response_class=HTMLResponse)
def admin_detail(
    request: Request,
    lic_id: int,
    msg: str = "",
    db: Session = Depends(get_db),
    _=Depends(auth.verify_admin),
):
    lic = crud.get_license_by_id(db, lic_id)
    if not lic:
        raise HTTPException(404, "Licença não encontrada")
    checks = crud.get_checks(db, lic_id, limit=20)
    return templates.TemplateResponse("license_detail.html", {
        "request": request,
        "lic": lic,
        "checks": checks,
        "msg": msg,
    })


@app.post("/admin/{lic_id}/revoke")
def admin_revoke(lic_id: int, db: Session = Depends(get_db), _=Depends(auth.verify_admin)):
    lic = crud.get_license_by_id(db, lic_id)
    if lic:
        crud.revoke_license(db, lic)
    return RedirectResponse(f"/admin/{lic_id}?msg=Licença+revogada.", status_code=302)


@app.post("/admin/{lic_id}/extend")
def admin_extend(
    lic_id: int,
    days: int = Form(30),
    db: Session = Depends(get_db),
    _=Depends(auth.verify_admin),
):
    lic = crud.get_license_by_id(db, lic_id)
    if lic:
        crud.extend_license(db, lic, days)
    return RedirectResponse(f"/admin/{lic_id}?msg=Renovada+por+{days}+dias.", status_code=302)


@app.post("/admin/{lic_id}/unbind")
def admin_unbind(lic_id: int, db: Session = Depends(get_db), _=Depends(auth.verify_admin)):
    lic = crud.get_license_by_id(db, lic_id)
    if lic:
        crud.unbind_hardware(db, lic)
    return RedirectResponse(f"/admin/{lic_id}?msg=Hardware+desvinculado.", status_code=302)


@app.post("/admin/{lic_id}/notes")
def admin_notes(
    lic_id: int,
    notes: str = Form(""),
    db: Session = Depends(get_db),
    _=Depends(auth.verify_admin),
):
    lic = crud.get_license_by_id(db, lic_id)
    if lic:
        lic.notes = notes or None
        db.commit()
    return RedirectResponse(f"/admin/{lic_id}?msg=Notas+salvas.", status_code=302)


# ── Landing Page & Folder (marketing) ────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
def landing(request: Request):
    from datetime import date
    return templates.TemplateResponse("landing.html", {
        "request": request,
        "cakto_url": CAKTO_URL,
        "current_year": date.today().year,
    })


@app.get("/folder", response_class=HTMLResponse)
def folder_page(request: Request):
    return templates.TemplateResponse("folder.html", {
        "request": request,
        "cakto_url": CAKTO_URL,
    })


# ── Portal do Cliente — /conta ────────────────────────────────────────────────

@app.get("/conta", response_class=HTMLResponse)
def conta_get(
    request: Request,
    key: str = "",
    db: Session = Depends(get_db),
):
    ctx: dict[str, Any] = {
        "request":       request,
        "license":       None,
        "days_remaining": None,
        "error":         "",
        "query_key":     key,
        "support_email": SUPPORT_EMAIL,
        "cakto_portal":  CAKTO_PORTAL,
        "cakto_url":     CAKTO_URL,
        "landing_url":   LANDING_URL,
    }
    if key:
        lic = crud.get_license_by_key(db, key.strip().upper())
        if not lic:
            ctx["error"] = "Chave não encontrada. Verifique se digitou corretamente."
        else:
            ctx["license"] = lic
            if lic.expires_at:
                ctx["days_remaining"] = max(
                    0, (lic.expires_at - datetime.now(timezone.utc)).days
                )
    return templates.TemplateResponse("conta.html", ctx)


# ── Webhook Cakto (pagamento confirmado) ──────────────────────────────────────

def _extract_customer(payload: dict) -> tuple[str, str]:
    """Tenta extrair (nome, email) de múltiplos formatos possíveis do Cakto."""
    # Formatos possíveis: data.customer, checkout.customer, customer
    for path in ["data.customer", "checkout.customer", "customer", "data.buyer", "buyer"]:
        obj = payload
        for part in path.split("."):
            obj = obj.get(part, {}) if isinstance(obj, dict) else {}
        if isinstance(obj, dict) and obj.get("email"):
            return obj.get("name", ""), obj.get("email", "")
    return "", ""


def _is_payment_event(payload: dict) -> bool:
    """Detecta eventos de pagamento confirmado em múltiplos formatos."""
    event = (payload.get("event") or payload.get("type") or "").lower()
    paid_keywords = ("paid", "approved", "confirmed", "payment.paid",
                     "purchase", "order.paid", "subscription.created")
    if any(kw in event for kw in paid_keywords):
        return True
    # Verifica status dentro do payload
    for path in ["data.status", "checkout.status", "status"]:
        obj = payload
        for part in path.split("."):
            obj = obj.get(part, "") if isinstance(obj, dict) else ""
        if isinstance(obj, str) and obj.lower() in ("paid", "approved", "active"):
            return True
    return False


async def _process_cakto_payment(payload: dict, db: Session):
    """Processa pagamento: cria licença + envia e-mail de boas-vindas."""
    name, email = _extract_customer(payload)
    if not email:
        log.warning("Webhook Cakto: e-mail do cliente não encontrado. Payload: %s",
                    json.dumps(payload)[:400])
        return

    # Verifica se já existe licença ativa para este e-mail
    existing = crud.get_license_by_email(db, email)
    if existing and existing.status == "active":
        # Apenas estende por 30 dias
        crud.extend_license(db, existing, 30)
        log.info("Webhook Cakto: licença renovada para %s", email)
        return

    # Cria nova licença (30 dias)
    expires = datetime.now(timezone.utc) + timedelta(days=30)
    lic_data = schemas.LicenseCreate(
        customer_name=name or email.split("@")[0],
        customer_email=email,
        plan="monthly",
        expires_at=expires,
        notes=f"Criada automaticamente via webhook Cakto — {datetime.now().isoformat()}",
    )
    lic = crud.create_license(db, lic_data)
    log.info("Webhook Cakto: nova licença %s criada para %s", lic.key, email)

    # Envia e-mail em thread separada (não bloqueia o event loop)
    await asyncio.to_thread(
        send_welcome_email,
        to_email=email,
        customer_name=name or email.split("@")[0],
        license_key=lic.key,
        plan="Mensal",
        expires_at=expires.isoformat(),
    )


@app.post("/webhook/cakto")
async def webhook_cakto(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Recebe notificações de pagamento da Cakto e cria licenças automaticamente."""
    body = await request.body()

    # ── Verificação de assinatura (opcional) ──────────────────────────────────
    if CAKTO_WEBHOOK_SECRET:
        sig_header = (
            request.headers.get("x-cakto-signature")
            or request.headers.get("x-webhook-secret")
            or request.headers.get("x-signature")
            or ""
        )
        expected = hmac.new(
            CAKTO_WEBHOOK_SECRET.encode(),
            body,
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(sig_header, expected):
            log.warning("Webhook Cakto: assinatura inválida")
            raise HTTPException(401, "Invalid signature")

    try:
        payload = json.loads(body)
    except Exception:
        raise HTTPException(400, "Invalid JSON")

    log.info("Webhook Cakto recebido: event=%s", payload.get("event", "?"))

    if _is_payment_event(payload):
        background_tasks.add_task(_process_cakto_payment, payload, db)

    return {"received": True}


# ── Health check ─────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok"}
