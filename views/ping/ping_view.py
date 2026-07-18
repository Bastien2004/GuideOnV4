"""
views/ping/ping_view.py — Vue de la commande /ping
"""

from __future__ import annotations

from discord.ui import Container, LayoutView, Separator, TextDisplay

from utils.ping import get_latency_status

# ============================================================
# 🧩 Construction view CV2
# ============================================================

def build_ping_view(latency_ms: int) -> LayoutView:
    """Construction de la view ping."""

    emoji, status = get_latency_status(latency_ms)
    view = LayoutView(timeout=None)
    container = Container()

    # Header
    container.add_item(TextDisplay("# <:notifier:1495444487206604833> Pong !"))
    container.add_item(Separator())

    # Informations ping
    container.add_item(
        TextDisplay(
            "## 📡 Statut du bot\n"
            f"**Latence :** `{latency_ms} ms`\n"
            f"**État :** {emoji} {status}"
        )
    )

    container.add_item(Separator())

    # Footer
    container.add_item(TextDisplay("-# GuideOn Studio"))
    view.add_item(container)

    return view