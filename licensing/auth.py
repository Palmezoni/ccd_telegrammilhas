"""Autenticação: X-API-Key para clientes, Bearer token para admin."""
from __future__ import annotations

import os
import time
from typing import Optional

import jwt
from fastapi import Depends, Header, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

SHARED_API_SECRET = os.getenv("SHARED_API_SECRET", "mup-api-87d8deb37f1b06530dffc2b8a35ea32359eb9c54")
JWT_SECRET        = os.getenv("JWT_SECRET",        "f9ad917756061f7440b945cb3253f557f351097b3af2cceafe9180278222cbd1")
ADMIN_TOKEN       = os.getenv("ADMIN_TOKEN",       "change-me-in-production")
JWT_EXPIRE_DAYS   = int(os.getenv("JWT_EXPIRE_DAYS", "7"))


def verify_api_key(x_api_key: str = Header(...)):
    """Verifica o header X-API-Key enviado pelo cliente Windows."""
    if x_api_key != SHARED_API_SECRET:
        raise HTTPException(401, "Unauthorized")


def create_jwt(license_key: str) -> str:
    payload = {
        "sub": license_key,
        "iat": int(time.time()),
        "exp": int(time.time()) + JWT_EXPIRE_DAYS * 86400,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def verify_jwt(token: str, expected_key: str) -> bool:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        return payload.get("sub") == expected_key
    except Exception:
        return False


def verify_admin(request: Request):
    """Verifica cookie ou header de autenticação do admin."""
    token = request.cookies.get("admin_token") or request.headers.get("X-Admin-Token", "")
    if token != ADMIN_TOKEN:
        raise HTTPException(401, "Unauthorized")
    return True
