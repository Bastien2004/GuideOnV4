"""
cogs/eco/eco_daily.py — Commande /eco daily.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import discord
from discord import app_commands

from utils.botbancmd import verifier_ban_utilisateur
from utils.control_admin import verifier_commande
from utils.track_commande import tracker_commande

from utils.container_universel import error_container, success_container
from utils.error_handler import handle_app_command_error
from utils.managers.eco_manager import DailyCooldownError, claim_daily, format_amount

log = logging.getLogger(__name__)


# ============================================================
# 🎁 Commande : /eco daily
# ============================================================

@app_commands.guild_only()
@app_commands.checks.cooldown(1, 10)
@app_commands.command(name="daily", description="🎁 Récompense quotidienne")
async def eco_daily(interaction: discord.Interaction) -> None:

    # 🛡️ Vérification ban utilisateur.
    if not await verifier_ban_utilisateur(interaction):
        return

    # 🕒 Defer (éphémère : réclamation personnelle, pas d'intérêt pour le salon).
    try:
        await interaction.response.defer(ephemeral=True)
    except (discord.NotFound, discord.HTTPException):
        return

    # ⚙️ Vérification maintenance.
    if not await verifier_commande(interaction, "eco_daily"):
        return

    # 📊 Tracking.
    await tracker_commande(interaction, "eco_daily")

    try:
        result = await claim_daily(interaction.guild.id, interaction.user.id)
        await interaction.followup.send(
            view=success_container(
                f"Tu as reçu **{format_amount(result.amount_applied)}** !\n"
                f"-# ➥ Nouveau solde : **{format_amount(result.new_balance)}** !"
            ),
            ephemeral=True,
        )

    except DailyCooldownError as exc:
        next_at = datetime.now(timezone.utc) + exc.retry_after
        await interaction.followup.send(
            view=error_container(
                "Tu as déjà reçu ta **récompense quotidienne** !\n"
                f"-# Prochaine récompense disponible <t:{int(next_at.timestamp())}:R>"
            ),
            ephemeral=True,
        )

    except Exception:
        log.exception("[ECO_DAILY] Échec de la récompense quotidienne (guild=%s, user=%s)", interaction.guild.id, interaction.user.id)

        await interaction.followup.send(
            view=error_container("Impossible de récupérer ta **récompense**."),
            ephemeral=True,
        )


# ============================================================
# ❌ Gestion des erreurs
# ============================================================

@eco_daily.error
async def eco_daily_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    await handle_app_command_error(interaction, error)