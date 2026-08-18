"""
views/qr/scan_view.py — Vue de résultat pour /qr scan.
"""

from __future__ import annotations

from typing import Optional

import discord
from discord.ui import Container, LayoutView, Separator, TextDisplay

from views.qr._shared import format_date


# ============================================================
# 🎨 View — /qr scan
# ============================================================

def build_qr_scan_view(contenu: str, origine: Optional[object]) -> LayoutView:
    """Construit la vue de résultat après décodage d'un QR code scanné.

    `origine` est un QRCode (modèle DB) si le contenu correspond à un QR
    déjà généré via /qr generate, sinon None.
    """

    view = LayoutView(timeout=300)
    container = Container()

    container.add_item(TextDisplay("# 🔍 __QR Code scanné__"))
    container.add_item(Separator())

    contenu_affiche = contenu if len(contenu) <= 300 else contenu[:297] + "..."
    container.add_item(TextDisplay(f"**Contenu détecté :**\n`{contenu_affiche}`"))

    if origine is not None:
        date = format_date(origine.created_at)
        container.add_item(TextDisplay(
            f"\n-# ✅ Ce QR code a été généré ici par <@{origine.user_id}> — <t:{date}:R>"
        ))
    else:
        container.add_item(TextDisplay("\n-# ℹ️ Ce QR code n'a pas été généré via ce bot."))

    container.add_item(Separator())
    container.add_item(TextDisplay("-# GuideOn Studio"))

    view.add_item(container)
    return view