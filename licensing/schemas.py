"""Pydantic schemas para request/response."""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, EmailStr


# ── Client API ────────────────────────────────────────────────────────────────

class ActivateRequest(BaseModel):
    license_key:    str
    hw_fingerprint: str
    hw_label:       str = ""


class ActivateResponse(BaseModel):
    status:        str
    token:         str
    customer_name: str
    plan:          str
    expires_at:    str


class CheckRequest(BaseModel):
    license_key:    str
    hw_fingerprint: str


class CheckResponse(BaseModel):
    status:         str
    expires_at:     str
    days_remaining: Optional[int] = None


# ── Admin ─────────────────────────────────────────────────────────────────────

class LicenseCreate(BaseModel):
    customer_name:  str
    customer_email: str
    plan:           str = "monthly"   # monthly|annual|lifetime
    expires_at:     datetime
    notes:          Optional[str] = None


class LicenseOut(BaseModel):
    id:             int
    key:            str
    customer_name:  str
    customer_email: str
    plan:           str
    status:         str
    created_at:     datetime
    activated_at:   Optional[datetime]
    expires_at:     datetime
    notes:          Optional[str]
    hw_label:       Optional[str]
    hw_fingerprint: Optional[str]
    hw_bound_at:    Optional[datetime]

    class Config:
        from_attributes = True


class LicenseCheckOut(BaseModel):
    id:             int
    checked_at:     datetime
    action:         str
    ip_address:     Optional[str]
    hw_fingerprint: Optional[str]
    result:         str
    detail:         Optional[str]

    class Config:
        from_attributes = True
