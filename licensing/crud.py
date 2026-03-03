"""Operações CRUD."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy.orm import Session

from . import models, schemas
from .key_gen import generate_key


def get_license_by_key(db: Session, key: str) -> Optional[models.License]:
    return db.query(models.License).filter(models.License.key == key.upper()).first()


def get_license_by_id(db: Session, lic_id: int) -> Optional[models.License]:
    return db.query(models.License).filter(models.License.id == lic_id).first()


def get_license_by_email(db: Session, email: str) -> Optional[models.License]:
    """Retorna a licença mais recente para um e-mail (para renovação via webhook)."""
    return (
        db.query(models.License)
        .filter(models.License.customer_email == email.lower().strip())
        .order_by(models.License.created_at.desc())
        .first()
    )


def list_licenses(db: Session, search: str = "", status: str = "", page: int = 1, per_page: int = 30):
    q = db.query(models.License)
    if search:
        like = f"%{search}%"
        q = q.filter(
            models.License.customer_name.ilike(like)
            | models.License.customer_email.ilike(like)
            | models.License.key.ilike(like)
        )
    if status:
        q = q.filter(models.License.status == status)
    total = q.count()
    items = q.order_by(models.License.created_at.desc()).offset((page - 1) * per_page).limit(per_page).all()
    return items, total


def create_license(db: Session, data: schemas.LicenseCreate) -> models.License:
    lic = models.License(
        key=generate_key(),
        customer_name=data.customer_name,
        customer_email=data.customer_email,
        plan=data.plan,
        status="pending",
        expires_at=data.expires_at,
        notes=data.notes,
    )
    db.add(lic)
    db.commit()
    db.refresh(lic)
    return lic


def bind_hardware(db: Session, lic: models.License, hw: str, hw_label: str):
    lic.hw_fingerprint = hw
    lic.hw_label = hw_label
    lic.hw_bound_at = datetime.now(timezone.utc)
    db.commit()


def set_active(db: Session, lic: models.License):
    if not lic.activated_at:
        lic.activated_at = datetime.now(timezone.utc)
    lic.status = "active"
    db.commit()


def expire_license(db: Session, lic: models.License):
    lic.status = "expired"
    db.commit()


def revoke_license(db: Session, lic: models.License):
    lic.status = "revoked"
    db.commit()


def unbind_hardware(db: Session, lic: models.License):
    lic.hw_fingerprint = None
    lic.hw_label = None
    lic.hw_bound_at = None
    if lic.status == "active":
        lic.status = "pending"
    db.commit()


def extend_license(db: Session, lic: models.License, days: int):
    from datetime import timedelta
    base = max(lic.expires_at, datetime.now(timezone.utc))
    lic.expires_at = base + timedelta(days=days)
    if lic.status in ("expired",):
        lic.status = "pending"
    db.commit()
    db.refresh(lic)


def log_check(db: Session, lic: models.License, action: str, hw: str, result: str,
              ip: str = "", detail: str = ""):
    entry = models.LicenseCheck(
        license_id=lic.id,
        action=action,
        ip_address=ip or None,
        hw_fingerprint=hw or None,
        result=result,
        detail=detail or None,
    )
    db.add(entry)
    db.commit()


def get_checks(db: Session, lic_id: int, limit: int = 20) -> List[models.LicenseCheck]:
    return (
        db.query(models.LicenseCheck)
        .filter(models.LicenseCheck.license_id == lic_id)
        .order_by(models.LicenseCheck.checked_at.desc())
        .limit(limit)
        .all()
    )


def stats(db: Session) -> dict:
    total    = db.query(models.License).count()
    active   = db.query(models.License).filter(models.License.status == "active").count()
    expired  = db.query(models.License).filter(models.License.status == "expired").count()
    revoked  = db.query(models.License).filter(models.License.status == "revoked").count()
    pending  = db.query(models.License).filter(models.License.status == "pending").count()
    return {"total": total, "active": active, "expired": expired, "revoked": revoked, "pending": pending}
