"""
views/alpha/event_start_view.py — Annonce de début d'event M+ Alpha.
"""

from __future__ import annotations

from pathlib import Path

from discord import MediaGalleryItem
from discord.ui import Container, LayoutView, MediaGallery, Separator, TextDisplay

from utils.events_alpha import STATUS_EMOJIS, STATUS_LABELS

# ============================================================
# 🧩 Construction de la view
# ============================================================

def build_start_event_view(event: dict, ping_role_id: int | None, has_image: bool) -> LayoutView:
    """Construction de la view d'annonce de début d'event."""
    ping = f"<@&{ping_role_id}> " if ping_role_id else ""
    filename = Path(event["image"]).name if event.get("image") else None
    status_emoji = STATUS_EMOJIS.get(event["status"], "")

    view = LayoutView(timeout=None)
    c = Container()
    c.add_item(TextDisplay(f"# 🎮 {event['name']}"))
    c.add_item(Separator())
    c.add_item(TextDisplay(
        f"## {ping}Nous allons débuter un **{event['name']}** !\n\n"
        f"Rejoignez-nous en jeu via la commande `{event['warp']}`."
    ))

    if has_image and filename:
        c.add_item(Separator())
        c.add_item(MediaGallery(MediaGalleryItem(f"attachment://{filename}")))

    c.add_item(Separator())
    c.add_item(TextDisplay(
        f"### 📋 Règles de l'event\n{event['description']}"
    ))
    c.add_item(Separator())
    c.add_item(TextDisplay(f"-# {status_emoji} {STATUS_LABELS.get(event['status'], event['status'])} · GuideOn Studio"))
    view.add_item(c)
    return view