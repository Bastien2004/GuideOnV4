"""
views/ticket/persistence.py — Réenregistrement des vues persistantes au redem.
"""
from __future__ import annotations

import logging
from discord.ext import commands

from utils.managers import ticket_manager as tm

log = logging.getLogger(__name__)


async def register_persistent_views(bot: commands.Bot) -> None:
    """Recharge et ré-attache toutes les vues persistantes du système de tickets."""
    from views.ticket.panel_public_view import PanelPublicView
    from views.ticket.welcome_view import WelcomeView
    from views.ticket.lifecycle import ReopenView

    panels_ok = tickets_ok = errors = 0

    # ── Panels (bouton « Ouvrir un ticket ») ──
    try:
        panels = await tm.all_panels()
    except Exception:
        log.exception("Tickets: lecture des panels échouée — vues panels non réenregistrées")
        panels = []

    for panel in panels:
        try:
            bot.add_view(PanelPublicView.from_panel(panel))
            panels_ok += 1
        except Exception:
            errors += 1
            log.exception(
                "Tickets: add_view panel échoué (guild=%s, panel=%s)",
                panel.get("guild_id"), panel.get("panel_id"),
            )

    # ── Tickets (toolbar si ouvert, vue Réouvrir si fermé) ──
    try:
        tickets = await tm.all_tickets()  # une seule requête, on trie en mémoire
    except Exception:
        log.exception("Tickets: lecture des tickets échouée — vues tickets non réenregistrées")
        tickets = []

    for t in tickets:
        channel_id = t.get("channel_id")
        guild_id = t.get("guild_id")
        try:
            if t.get("closed"):
                bot.add_view(ReopenView(channel_id))
            else:
                # toolbar-only (pas de bloc d'accueil au réenregistrement)
                bot.add_view(WelcomeView(channel_id=channel_id, guild_id=guild_id))
            tickets_ok += 1
        except Exception:
            errors += 1
            log.exception("Tickets: add_view ticket échoué (channel=%s)", channel_id)

    log.info(
        "🎫 Vues tickets réenregistrées — panels: %d | tickets: %d | erreurs: %d",
        panels_ok, tickets_ok, errors,
    )