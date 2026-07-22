"""
views/mod/sanction_dm_view.py — Notification MP envoyée au membre sanctionné.

Vue purement informative (aucun callback bot-side) : LayoutView(timeout=None)
simple, pas de BaseLayoutView. L'envoi (best-effort, jamais bloquant) est
géré par le cog appelant, pas ici.
"""
from __future__ import annotations

from datetime import timedelta

from discord.ui import Container, LayoutView, Separator, TextDisplay

from utils.datetime_utils import format_duration
from utils.managers.mod_sanction_manager import SANCTION_LABELS, SanctionType


def build_sanction_dm_view(
    guild_name: str,
    sanction_type: SanctionType,
    reason: str,
    *,
    duration_seconds: int | None = None,
) -> LayoutView:
    """Construit le MP de notification envoyé au membre sanctionné."""
    emoji, label = SANCTION_LABELS[sanction_type]

    view = LayoutView(timeout=None)
    container = Container()

    container.add_item(TextDisplay(f"# {emoji} {label}"))
    container.add_item(Separator())

    lines = [f"Tu as reçu une sanction sur **{guild_name}**.", f"**Raison :** {reason}"]
    if duration_seconds is not None:
        lines.append(f"**Durée :** {format_duration(timedelta(seconds=duration_seconds))}")

    container.add_item(TextDisplay("\n".join(lines)))
    container.add_item(Separator())
    container.add_item(TextDisplay("-# GuideOn Studio"))

    view.add_item(container)
    return view
