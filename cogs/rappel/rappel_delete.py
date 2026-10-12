"""
cogs/rappel/rappel_delete.py — Commande /rappel delete <id>.
"""

from __future__ import annotations

import logging

import discord
from discord import app_commands

from utils.botbancmd import verifier_ban_utilisateur
from utils.container_universel import error_container, success_container
from utils.control_admin import verifier_commande
from utils.error_handler import handle_app_command_error
from utils.managers.reminder_manager import ReminderNotFoundError, cancel_reminder
from utils.track_commande import tracker_commande

log = logging.getLogger(__name__)


# ============================================================
# ❌ Commande : /rappel annuler <id>
# ============================================================

@app_commands.guild_only()
@app_commands.checks.cooldown(1, 10)
@app_commands.command(name="delete", description="🗑️ Annule un rappel en attente")
@app_commands.describe(id="L'identifiant du rappel (/rappel list)")
async def rappel_delete(interaction: discord.Interaction, id: int) -> None:

    # 🛡️ Vérification ban utilisateur.
    if not await verifier_ban_utilisateur(interaction):
        return

    # 🕒 Defer.
    try:
        await interaction.response.defer(ephemeral=True)
    except (discord.NotFound, discord.HTTPException):
        return

    # ⚙️ Vérification maintenance.
    if not await verifier_commande(interaction, "rappel_delete"):
        return

    # 📊 Tracking.
    await tracker_commande(interaction, "rappel_delete")

    try:
        await cancel_reminder(id, interaction.user.id)
        await interaction.followup.send(
            view=success_container(f"Rappel **#{id}** annulé."),
            ephemeral=True,
        )

    except ReminderNotFoundError:
        await interaction.followup.send(
            view=error_container(f"Aucun rappel **#{id}** ne t'appartient."),
            ephemeral=True,
        )

    except Exception:
        log.exception(
            "[RAPPEL ANNULER] Échec d'annulation (user=%s, id=%s)",
            interaction.user.id, id,
        )
        await interaction.followup.send(
            view=error_container("Impossible d'annuler ce **rappel**."),
            ephemeral=True,
        )


# ============================================================
# ❌ Gestion des erreurs
# ============================================================

@rappel_delete.error
async def rappel_delete_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    await handle_app_command_error(interaction, error)