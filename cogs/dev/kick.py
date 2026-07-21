"""
cogs/dev/kick.py — Fait quitter GuideOn d'un serveur.
"""

from __future__ import annotations

import discord
from discord import Interaction, app_commands

from utils.control_admin import verifier_commande
from utils.perm_dev import check_dev
from utils.track_commande import tracker_commande

from utils.container_universel import error_container
from utils.error_handler import handle_app_command_error
from views.dev.kick_view import build_confirm_kick_view


# ============================================================
# 🧭 Commande : /dev kick
# ============================================================

@app_commands.guild_only()
@app_commands.checks.cooldown(1, 10)
@app_commands.command(name="kick", description="💨 [DEV] Kick GuideOn d'un serveur")
@app_commands.describe(id_serveur="ID du serveur à quitter")
async def kick(interaction: Interaction, id_serveur: str) -> None:

    # 🔐 Vérification des permissions.
    if not await check_dev(interaction, "**kick** le bot d'un serveur"):
        return

    # 🕒 Defer.
    try:
        await interaction.response.defer(ephemeral=True)
    except (discord.NotFound, discord.HTTPException):
        return

    # ⚙️ Activation commande.
    if not await verifier_commande(interaction, "dev_kick"):
        return

    # 📊 Tracking.
    await tracker_commande(interaction, "dev_kick")

    # 🔎 Vérification de l'ID.
    try:
        guild_id = int(id_serveur)
    except ValueError:
        return await interaction.followup.send(
            view=error_container("`id_serveur` doit être un **identifiant numérique**."),
            ephemeral=True,
        )

    guild = interaction.client.get_guild(guild_id)
    if guild is None:
        return await interaction.followup.send(
            view=error_container("GuideOn n'est présent sur **aucun serveur** avec cet ID."),
            ephemeral=True,
        )

    # ✉️ Envoi du message de confirmation
    await interaction.followup.send(
        view=build_confirm_kick_view(guild, interaction.user.id),
        ephemeral=True,
    )


# ============================================================
# ❌ Gestion des erreurs
# ============================================================

@kick.error
async def kick_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    await handle_app_command_error(interaction, error)