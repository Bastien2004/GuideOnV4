"""
cogs/birthday/birthday_list.py — Commande /birthday list (VIP).

Affiche les anniversaires des 30 prochains jours, triés par proximité, paginé.

Pipeline :
    verifier_ban_utilisateur → vip check → defer → verifier_commande
    → tracker_commande → BirthdayListView
"""
from __future__ import annotations

import logging
from datetime import datetime
from zoneinfo import ZoneInfo

import discord
from discord import app_commands

from utils.botbancmd import verifier_ban_utilisateur
from utils.boutique.vip_manager import is_vip, send_vip_error
from utils.container_universel import error_container, info_container
from utils.control_admin import verifier_commande
from utils.error_handler import handle_app_command_error
from utils.managers.birthday_manager import get_upcoming
from utils.track_commande import tracker_commande

from views.birthday.list_view import BirthdayListView

log = logging.getLogger(__name__)

PARIS_TZ = ZoneInfo("Europe/Paris")


@app_commands.guild_only()
@app_commands.checks.cooldown(1, 5)
@app_commands.command(
    name="list",
    description="🎂 Affiche les anniversaires des 30 prochains jours (VIP)",
)
async def birthday_list(interaction: discord.Interaction) -> None:

    # 🛡️ Vérification ban utilisateur.
    if not await verifier_ban_utilisateur(interaction):
        return

    # 🌟 Vérification VIP (sync).
    if not is_vip(interaction.user.id):
        await send_vip_error(interaction)
        return

    # 🕒 Defer ephemeral (commande VIP perso).
    try:
        await interaction.response.defer(ephemeral=True)
    except (discord.NotFound, discord.HTTPException):
        return

    # ⚙️ Vérification maintenance.
    if not await verifier_commande(interaction, "birthday_list"):
        return

    # 📊 Tracking.
    await tracker_commande(interaction, "birthday_list")

    # 🧩 Récup + affichage.
    try:
        today = datetime.now(PARIS_TZ).date()
        entries = await get_upcoming(interaction.guild.id, today, days=30)

        if not entries:
            await interaction.followup.send(
                view=info_container(
                    "Aucun anniversaire enregistré dans les **30 prochains jours**."
                ),
                ephemeral=True,
            )
            return

        view = BirthdayListView(
            entries,
            guild=interaction.guild,
            owner_id=interaction.user.id,
            today=today,
            per_page=20,
        )
        await interaction.followup.send(view=view, ephemeral=True)
    except Exception:
        log.exception("/birthday list échoué (guild=%s)", interaction.guild.id)
        await interaction.followup.send(
            view=error_container("Impossible d'afficher la **liste**."),
            ephemeral=True,
        )


@birthday_list.error
async def birthday_list_error(
    interaction: discord.Interaction, error: app_commands.AppCommandError
) -> None:
    await handle_app_command_error(interaction, error)