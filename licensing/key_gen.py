"""Geração de chaves de licença."""
import secrets
import string


def generate_key() -> str:
    """Gera uma chave no formato MILH-XXXX-XXXX-XXXX (letras maiúsculas + dígitos)."""
    chars = string.ascii_uppercase + string.digits
    segs = ["".join(secrets.choice(chars) for _ in range(4)) for _ in range(3)]
    return "MILH-" + "-".join(segs)
