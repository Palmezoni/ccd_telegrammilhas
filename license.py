"""
Módulo de licenciamento do cliente — MilhasUP Telegram Monitor.
Gerencia ativação, verificação e cache local da licença.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import platform
import sys
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional, Tuple

# ── Configuração (embutida no executável via PyInstaller) ─────────────────────

LICENSE_API_URL   = os.getenv("LICENSE_API_URL",
                              "https://milhasup-licensing-production.up.railway.app")
SHARED_API_SECRET = "mup-api-87d8deb37f1b06530dffc2b8a35ea32359eb9c54"
FERNET_SALT       = "mup-14bbd40144e11d2bb72f20b69b59f4122927e832"
LICENSE_DAT_NAME  = "license.dat"
GRACE_HOURS       = 24
CHECK_INTERVAL_H  = 6


# ── Estado da licença ─────────────────────────────────────────────────────────

@dataclass
class LicenseState:
    key:           str   = ""
    token:         str   = ""
    customer_name: str   = ""
    plan:          str   = ""
    expires_at:    str   = ""   # ISO8601 UTC
    hw_fingerprint: str  = ""
    last_check_ts: float = 0.0
    last_check_ok: bool  = False
    activated:     bool  = False

    def is_expired(self) -> bool:
        if not self.expires_at:
            return True
        from datetime import datetime, timezone
        try:
            exp = datetime.fromisoformat(self.expires_at.replace("Z", "+00:00"))
            return datetime.now(timezone.utc) >= exp
        except Exception:
            return True

    def seconds_since_last_check(self) -> float:
        if not self.last_check_ts:
            return float("inf")
        return time.time() - self.last_check_ts

    def days_remaining(self) -> Optional[int]:
        if not self.expires_at:
            return None
        from datetime import datetime, timezone
        try:
            exp = datetime.fromisoformat(self.expires_at.replace("Z", "+00:00"))
            return max(0, (exp - datetime.now(timezone.utc)).days)
        except Exception:
            return None


# ── LicenseManager ────────────────────────────────────────────────────────────

class LicenseManager:
    """Gerencia licença local: ativação, verificação e cache cifrado."""

    def __init__(self, base_dir: Path):
        self._dat   = base_dir / LICENSE_DAT_NAME
        self._state: Optional[LicenseState] = None

    # ── Crypto ────────────────────────────────────────────────────────────────

    def _fernet(self, hw: str):
        from cryptography.fernet import Fernet
        raw = hashlib.sha256(f"{hw}:{FERNET_SALT}".encode()).digest()
        key = base64.urlsafe_b64encode(raw)
        return Fernet(key)

    # ── Hardware fingerprint ───────────────────────────────────────────────────

    @staticmethod
    def hardware_fingerprint() -> str:
        """SHA256 de MAC + Volume Serial + BIOS serial + hostname."""
        parts: list[str] = []
        # 1. MAC address (sempre disponível)
        parts.append(str(uuid.getnode()))
        # 2. Volume serial + BIOS via WMI (Windows)
        try:
            import wmi  # type: ignore
            c = wmi.WMI()
            for disk in c.Win32_LogicalDisk(DeviceID="C:"):
                parts.append(str(disk.VolumeSerialNumber or ""))
            for bios in c.Win32_BIOS():
                parts.append(str(bios.SerialNumber or ""))
        except Exception:
            pass
        # 3. Hostname como fallback
        parts.append(os.environ.get("COMPUTERNAME", platform.node()))
        combined = "|".join(p for p in parts if p and p.strip())
        return "sha256:" + hashlib.sha256(combined.encode()).hexdigest()

    @staticmethod
    def hw_label() -> str:
        name = os.environ.get("COMPUTERNAME", platform.node())
        ver  = platform.version()[:30]
        return f"{name} / {ver}"

    # ── Persistência ──────────────────────────────────────────────────────────

    def load_local(self) -> Optional[LicenseState]:
        """Carrega e decifra license.dat. Retorna None se não existe ou inválido."""
        if not self._dat.exists():
            return None
        try:
            hw   = self.hardware_fingerprint()
            fern = self._fernet(hw)
            raw  = fern.decrypt(self._dat.read_bytes())
            data = json.loads(raw)
            self._state = LicenseState(**{k: v for k, v in data.items()
                                          if k in LicenseState.__dataclass_fields__})
            return self._state
        except Exception:
            return None

    def _save_local(self, state: LicenseState):
        hw   = self.hardware_fingerprint()
        fern = self._fernet(hw)
        raw  = json.dumps(asdict(state), ensure_ascii=False).encode()
        self._dat.write_bytes(fern.encrypt(raw))
        self._state = state

    def clear_local(self):
        """Remove license.dat (reset da ativação)."""
        try:
            self._dat.unlink(missing_ok=True)
        except Exception:
            pass
        self._state = None

    # ── Ativação ──────────────────────────────────────────────────────────────

    def activate(self, key: str) -> Tuple[bool, str]:
        """Ativa a licença no servidor. Retorna (ok, mensagem)."""
        try:
            import httpx  # type: ignore
        except ImportError:
            return False, "Dependência httpx não encontrada."

        hw    = self.hardware_fingerprint()
        label = self.hw_label()
        try:
            r = httpx.post(
                f"{LICENSE_API_URL}/api/v1/activate",
                json={
                    "license_key":    key.strip().upper(),
                    "hw_fingerprint": hw,
                    "hw_label":       label,
                },
                headers={"X-API-Key": SHARED_API_SECRET},
                timeout=15,
            )
            if r.status_code == 200:
                d = r.json()
                state = LicenseState(
                    key=key.strip().upper(),
                    token=d.get("token", ""),
                    customer_name=d.get("customer_name", ""),
                    plan=d.get("plan", "monthly"),
                    expires_at=d.get("expires_at", ""),
                    hw_fingerprint=hw,
                    last_check_ts=time.time(),
                    last_check_ok=True,
                    activated=True,
                )
                self._save_local(state)
                return True, f"Licença ativada! Bem-vindo, {state.customer_name}."
            elif r.status_code == 409:
                return False, ("Esta chave já está vinculada a outro computador.\n"
                               "Contate o suporte para desvincular.")
            elif r.status_code == 410:
                return False, "Licença expirada. Por favor renove sua assinatura."
            elif r.status_code == 403:
                return False, "Licença revogada. Contate o suporte."
            elif r.status_code == 404:
                return False, "Chave de licença inválida. Verifique e tente novamente."
            else:
                return False, f"Erro do servidor ({r.status_code}). Tente novamente."
        except Exception as e:
            if "timeout" in str(e).lower() or "connect" in str(e).lower():
                return False, "Sem conexão com o servidor. Verifique a internet."
            return False, f"Erro: {e}"

    # ── Verificação + Grace Period ─────────────────────────────────────────────

    def check_or_grace(self) -> Tuple[bool, str]:
        """
        Verifica validade da licença. Usado pelo monitor antes de iniciar e
        periodicamente. Retorna (permitido, motivo).

        Lógica:
          1. Sem license.dat → bloqueia
          2. Expirado localmente → bloqueia
          3. < CHECK_INTERVAL_H desde último check → usa cache
          4. ≥ CHECK_INTERVAL_H → tenta API
             - API OK → atualiza cache → permite
             - API falha (rede) → grace period ≤ GRACE_HOURS → permite
             - API falha (rede) → grace period expirou → bloqueia
             - API 403/410 → bloqueia imediatamente
        """
        state = self._state or self.load_local()
        if state is None or not state.activated:
            return False, "not_activated"
        if state.is_expired():
            return False, "expired_local"

        secs = state.seconds_since_last_check()
        check_interval_s = CHECK_INTERVAL_H * 3600
        grace_s          = GRACE_HOURS * 3600

        if secs < check_interval_s:
            return True, "cache_ok"

        # Precisa verificar com API
        try:
            import httpx  # type: ignore
            r = httpx.post(
                f"{LICENSE_API_URL}/api/v1/check",
                json={
                    "license_key":    state.key,
                    "hw_fingerprint": state.hw_fingerprint,
                },
                headers={
                    "X-API-Key":     SHARED_API_SECRET,
                    "Authorization": f"Bearer {state.token}",
                },
                timeout=10,
            )
            if r.status_code == 200:
                d = r.json()
                state.last_check_ts = time.time()
                state.last_check_ok = True
                state.expires_at    = d.get("expires_at", state.expires_at)
                self._save_local(state)
                return True, "api_ok"
            elif r.status_code in (403, 410):
                err = r.json().get("error", str(r.status_code))
                state.last_check_ok = False
                self._save_local(state)
                return False, err
            else:
                raise Exception(f"HTTP {r.status_code}")
        except Exception:
            # Falha de rede — aplica grace period
            if state.last_check_ok and secs < grace_s:
                return True, f"grace_ok ({secs/3600:.1f}h offline)"
            return False, "grace_expired"

    def get_state(self) -> Optional[LicenseState]:
        return self._state or self.load_local()
