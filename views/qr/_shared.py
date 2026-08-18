"""
views/qr/_shared.py — Helpers partagés entre generate_view / list_view / scan_view.
"""

from __future__ import annotations

import io
from datetime import datetime

import qrcode
from PIL import Image

LOGO_PATH = "assets/logo_guideon.png"  # Incrusté au centre, ignoré silencieusement si absent
FILENAME = "qrcode.png"


# ============================================================
# 🧩 Génération d'image QR
# ============================================================

def _add_logo(img: Image.Image) -> Image.Image:
    """Incruste le logo GuideON au centre du QR code (si le fichier existe)."""
    try:
        logo = Image.open(LOGO_PATH).convert("RGBA")
    except (FileNotFoundError, OSError):
        return img

    img = img.convert("RGBA")
    logo_size = min(img.size) // 5
    logo = logo.resize((logo_size, logo_size))

    pos = ((img.width - logo_size) // 2, (img.height - logo_size) // 2)
    img.paste(logo, pos, logo)
    return img


def generate_qr_bytes(contenu: str) -> io.BytesIO:
    """Génère un QR code en PNG (ERROR_CORRECT_H pour tolérer le logo)."""
    qr = qrcode.QRCode(
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )
    qr.add_data(contenu)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    img = _add_logo(img)

    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer


# ============================================================
# 🧩 Formatage
# ============================================================

def format_date(dt: datetime) -> int:
    """Convertit une date en timestamp Discord (secondes) pour <t:...:R>."""
    return int(dt.timestamp())