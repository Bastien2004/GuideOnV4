"""
cogs/exp/exp_level.py — Commande /exp level [membre].
"""
from __future__ import annotations

import logging
from typing import Optional

import discord
from discord import app_commands

from utils.botbancmd import verifier_ban_utilisateur
from utils.container_universel import error_container
from utils.control_admin import verifier_commande
from utils.error_handler import handle_app_command_error
from utils.exp_image import ExpImageBuilder
from utils.managers.exp_manager import get_user_exp
from utils.track_commande import tracker_commande

log = logging.getLogger(__name__)


# ============================================================
# 📊 Commande : /exp level [membre]
# ============================================================

@app_commands.guild_only()
@app_commands.checks.cooldown(1, 5)
@app_commands.command(name="level", description="📊 Affiche le niveau et l'EXP d'un membre")
@app_commands.describe(membre="Le membre dont tu veux voir le niveau (toi par défaut)")
async def exp_level(interaction: discord.Interaction, membre: Optional[discord.Member] = None) -> None:

    # 🛡️ Vérification ban utilisateur.
    if not await verifier_ban_utilisateur(interaction):
        return

    # 🕒 Defer.
    try:
        await interaction.response.defer()
    except (discord.NotFound, discord.HTTPException):
        return

    # ⚙️ Vérification maintenance.
    if not await verifier_commande(interaction, "exp_level"):
        return

    # 📊 Tracking.
    await tracker_commande(interaction, "exp_level")

    target = membre or interaction.user

    # 🚫 Refus des bots.
    if isinstance(target, discord.Member) and target.bot:
        await interaction.followup.send(
            view=error_container("Les **bots** n'ont pas de niveau d'EXP."),
        )
        return

    # 🖼️ Génération de l'image de niveau.
    try:
        total_exp = await get_user_exp(interaction.guild.id, target.id)
        builder = ExpImageBuilder(target, total_exp)
        buffer = await builder.build()

        file = discord.File(buffer, filename="level.png")
        await interaction.followup.send(file=file)

    except Exception:
        log.exception(
            "Affichage /exp level échoué (guild=%s, target=%s)",
            interaction.guild.id, target.id,
        )
        await interaction.followup.send(
            view=error_container("Impossible de générer l'**image de niveau**.")
        )


# ============================================================
# ❌ Gestion des erreurs
# ============================================================

@exp_level.error
async def exp_level_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    await handle_app_command_error(interaction, error)
