"""SQLAlchemy ORM models."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from .database import Base


class License(Base):
    __tablename__ = "licenses"

    id             = Column(Integer, primary_key=True, index=True)
    key            = Column(String(32), unique=True, nullable=False, index=True)
    customer_name  = Column(String(120), nullable=False)
    customer_email = Column(String(120), nullable=False, index=True)
    plan           = Column(String(20), nullable=False, default="monthly")
    status         = Column(String(20), nullable=False, default="pending")  # pending|active|revoked|expired
    created_at     = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    activated_at   = Column(DateTime(timezone=True), nullable=True)
    expires_at     = Column(DateTime(timezone=True), nullable=False)
    notes          = Column(Text, nullable=True)

    hw_fingerprint = Column(String(80), nullable=True)
    hw_bound_at    = Column(DateTime(timezone=True), nullable=True)
    hw_label       = Column(String(120), nullable=True)

    checks = relationship("LicenseCheck", back_populates="license", cascade="all, delete-orphan")


class LicenseCheck(Base):
    __tablename__ = "license_checks"

    id             = Column(Integer, primary_key=True, index=True)
    license_id     = Column(Integer, ForeignKey("licenses.id"), nullable=False, index=True)
    checked_at     = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    action         = Column(String(20), nullable=False)   # activate|check|check_failed
    ip_address     = Column(String(50), nullable=True)
    hw_fingerprint = Column(String(80), nullable=True)
    result         = Column(String(20), nullable=False)   # ok|invalid|expired|revoked|hw_mismatch
    detail         = Column(Text, nullable=True)

    license = relationship("License", back_populates="checks")
