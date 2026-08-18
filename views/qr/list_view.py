"""
views/qr/list_view.py — Vue listant l'historique QR d'un utilisateur (/qr list).
"""

from __future__ import annotations

from typing import Sequence

import discord
from discord.ui import Container, LayoutView, Separator, TextDisplay

from views.qr._shared import format_date


# ============================================================
# 🎨 View — /qr list
# ============================================================

def build_qr_list_view(utilisateur: discord.abc.User, historique: Sequence) -> LayoutView:
    """Construit la vue listant les QR codes générés par un utilisateur."""

    view = LayoutView(timeout=300)
    container = Container()

    container.add_item(TextDisplay(f"# 📋 __Historique QR — {utilisateur.display_name}__"))
    container.add_item(Separator())

    if not historique:
        container.add_item(TextDisplay("-# Aucun QR code généré pour l'instant."))
    else:
        lignes = []
        for entry in historique:
            contenu = entry.contenu if len(entry.contenu) <= 60 else entry.contenu[:57] + "..."
            date = format_date(entry.created_at)
            lignes.append(f"• `{contenu}` — <t:{date}:R>")

        container.add_item(TextDisplay("\n".join(lignes)))

    container.add_item(Separator())
    container.add_item(TextDisplay("-# GuideOn Studio"))

    view.add_item(container)
    return view