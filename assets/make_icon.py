#!/usr/bin/env python3
"""Gera icon.ico e tray_icon.png para o Milhas UP Telegram Monitor."""
from pathlib import Path
from PIL import Image, ImageDraw

ASSETS = Path(__file__).parent


def make_base(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # Fundo azul escuro
    d.ellipse([2, 2, size - 2, size - 2], fill="#1a5fa8")
    d.ellipse([8, 8, size - 8, size - 8], fill="#2471c2")
    # Seta UP branca
    cx = size // 2
    s = size / 64  # escala baseada em 64px
    pts = [
        (cx,                    int(10 * s)),   # topo
        (cx + int(22 * s),      int(30 * s)),   # ombro direito
        (cx + int(10 * s),      int(30 * s)),   # dentro direito
        (cx + int(10 * s),      int(54 * s)),   # base direita
        (cx - int(10 * s),      int(54 * s)),   # base esquerda
        (cx - int(10 * s),      int(30 * s)),   # dentro esquerdo
        (cx - int(22 * s),      int(30 * s)),   # ombro esquerdo
    ]
    d.polygon(pts, fill="white")
    # Letra M pequena abaixo da seta
    return img


def build_ico():
    sizes = [256, 128, 64, 48, 32, 16]
    imgs = [make_base(s) for s in sizes]
    out = ASSETS / "icon.ico"
    imgs[0].save(
        out, format="ICO",
        append_images=imgs[1:],
        sizes=[(s, s) for s in sizes],
    )
    print(f"Saved {out}")


def build_png():
    img = make_base(64)
    out = ASSETS / "tray_icon.png"
    img.save(out, format="PNG")
    print(f"Saved {out}")


if __name__ == "__main__":
    ASSETS.mkdir(exist_ok=True)
    build_ico()
    build_png()
    print("Ícones gerados com sucesso!")
