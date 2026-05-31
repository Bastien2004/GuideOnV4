"""
views/giveaway/panel_view.py — Message public d'un giveaway.

Construit le LayoutView affiché dans le salon. Réutilisé :
- à l'envoi initial du giveaway
- à chaque update de compteur de participants (listener)
- à la clôture (affiche les gagnants)

Fidèle à la mise en page V3 : prix / gagnants / participants / fin /
prérequis / call-to-action 🎉. Pas de boutons : la participation se fait
via la réaction 🎉 (décision de cadrage).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

import discord
from discord.ui import Container, LayoutView, Separator, TextDisplay


def _format_requirements(req: dict, guild: Optional[discord.Guild]) -> list[str]:
    """Liste des lignes de prérequis à afficher. Vide si aucun."""
    lines: list[str] = []
    role_id = req.get("role_id")
    if role_id:
        lines.append(f"• Avoir le rôle <@&{role_id}>")
    min_invites = req.get("min_invites")
    if min_invites:
        lines.append(f"• Avoir au moins **{min_invites}** invitation(s)")
    min_age = req.get("min_server_age_days")
    if min_age:
        s = "s" if min_age > 1 else ""
        lines.append(f"• Être sur le serveur depuis au moins **{min_age}** jour{s}")
    forbidden_role_id = req.get("forbidden_role_id")
    if forbidden_role_id:
        lines.append(f"• **Ne pas** avoir le rôle <@&{forbidden_role_id}>")
    return lines


def build_giveaway_panel(
    giveaway_data: dict, guild: Optional[discord.Guild] = None
) -> LayoutView:
    """
    Construit le panneau public du giveaway. `giveaway_data` est le dict renvoyé
    par le manager : id, prize, winners_count, end_time, ended, host_id,
    participants_count (optionnel — sinon 0), winners, requirements.
    """
    view = LayoutView(timeout=None)
    container = Container()

    gid = giveaway_data["id"]
    prize = giveaway_data["prize"]
    winners_count = giveaway_data["winners_count"]
    end_time = giveaway_data["end_time"]
    ended = giveaway_data.get("ended", False)
    host_id = giveaway_data["host_id"]
    winners = giveaway_data.get("winners", [])
    participants_count = giveaway_data.get("participants_count", 0)
    requirements = giveaway_data.get("requirements", {}) or {}

    # Normalisation end_time tz-aware (compat SQLite)
    if isinstance(end_time, datetime) and end_time.tzinfo is None:
        end_time = end_time.replace(tzinfo=timezone.utc)
    end_ts = int(end_time.timestamp()) if isinstance(end_time, datetime) else int(end_time)

    # --- En-tête ---
    if ended:
        container.add_item(TextDisplay("# 🎉 GIVEAWAY TERMINÉ"))
    else:
        container.add_item(TextDisplay("# 🎉 GIVEAWAY"))
    container.add_item(Separator())

    # --- Corps ---
    if ended:
        if winners:
            mentions = " ".join(f"<@{w}>" for w in winners)
            container.add_item(TextDisplay(
                f"🏆 **Prix :** {prize}\n"
                f"🎊 **Gagnant(s) :** {mentions}"
            ))
        else:
            container.add_item(TextDisplay(
                f"🏆 **Prix :** {prize}\n"
                f"😔 **Aucun gagnant** — pas assez de participants."
            ))
        container.add_item(TextDisplay(
            f"🆔 **ID :** `{gid}`\n"
            f"👤 **Participants :** {participants_count}"
        ))
    else:
        container.add_item(TextDisplay(
            f"🏆 **Prix :** {prize}\n"
            f"👥 **Gagnants tirés :** {winners_count}\n"
            f"👤 **Participants :** {participants_count}\n"
            f"📅 **Se termine :** <t:{end_ts}:R>\n"
            f"🆔 **ID :** `{gid}`"
        ))

    # --- Prérequis ---
    req_lines = _format_requirements(requirements, guild)
    if req_lines:
        container.add_item(Separator())
        container.add_item(TextDisplay(
            "📋 **Prérequis pour participer :**\n" + "\n".join(req_lines)
        ))

    # --- Call-to-action ---
    if not ended:
        container.add_item(Separator())
        container.add_item(TextDisplay("🎊 **Réagissez avec 🎉 pour participer !**"))

    # --- Footer ---
    container.add_item(Separator())
    container.add_item(TextDisplay(f"-# Organisé par <@{host_id}> · GuideOn Studio"))

    view.add_item(container)
    return view