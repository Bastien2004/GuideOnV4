"""
cogs/birthday/birthday_next.py — Commande /birthday next (VIP).

Affiche le prochain anniversaire à venir (groupe si plusieurs partagent la date).

Pipeline :
    verifier_ban_utilisateur → vip check → defer → verifier_commande
    → tracker_commande → BirthdayNextView
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
from utils.managers.birthday_manager import get_next
from utils.track_commande import tracker_commande

from views.birthday.next_view import BirthdayNextView

log = logging.getLogger(__name__)

PARIS_TZ = ZoneInfo("Europe/Paris")


@app_commands.guild_only()
@app_commands.checks.cooldown(1, 5)
@app_commands.command(
    name="next",
    description="🎂 Affiche le prochain anniversaire à venir (VIP)",
)
async def birthday_next(interaction: discord.Interaction) -> None:

    # 🛡️ Vérification ban utilisateur.
    if not await verifier_ban_utilisateur(interaction):
        return

    # 🌟 Vérification VIP (sync).
    if not is_vip(interaction.user.id):
        await send_vip_error(interaction)
        return

    # 🕒 Defer ephemeral.
    try:
        await interaction.response.defer(ephemeral=True)
    except (discord.NotFound, discord.HTTPException):
        return

    # ⚙️ Vérification maintenance.
    if not await verifier_commande(interaction, "birthday_next"):
        return

    # 📊 Tracking.
    await tracker_commande(interaction, "birthday_next")

    # 🧩 Récup + affichage.
    try:
        today = datetime.now(PARIS_TZ).date()
        result = await get_next(interaction.guild.id, today)

        if result is None:
            await interaction.followup.send(
                view=info_container("Aucun anniversaire enregistré sur ce serveur."),
                ephemeral=True,
            )
            return

        next_date, users = result
        view = BirthdayNextView.create(next_date, users, interaction.guild, today)
        await interaction.followup.send(view=view, ephemeral=True)
    except Exception:
        log.exception("/birthday next échoué (guild=%s)", interaction.guild.id)
        await interaction.followup.send(
            view=error_container("Impossible d'afficher le **prochain anniversaire**."),
            ephemeral=True,
        )


@birthday_next.error
async def birthday_next_error(
    interaction: discord.Interaction, error: app_commands.AppCommandError
) -> None:
    await handle_app_command_error(interaction, error)