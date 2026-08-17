"""
cogs/dev/gold.py — Gère l'abonnement Gold+.
"""

from __future__ import annotations

import logging

import discord
from discord import app_commands, Interaction

from utils.control_admin import verifier_commande
from utils.track_commande import tracker_commande
from utils.perm_check import has_grade_check

from utils.container_universel import error_container, success_container
from utils.error_handler import handle_app_command_error
from utils.managers.boutique_manager import add_entry, remove_entry
from utils.db.models.boutique import ShopRole

log = logging.getLogger(__name__)


# ============================================================
# 🧭 Commande : /dev gold
# ============================================================

@app_commands.guild_only()
@app_commands.checks.cooldown(1, 10)
@app_commands.command(name="gold", description="✨ [DEV] Gère le statut Gold+ d'un serveur")
@app_commands.describe(id_serveur="ID du serveur cible")
async def gold(interaction: Interaction, id_serveur: str) -> None:

    # 🔐 Vérification des permissions.
    if not await has_grade_check(interaction, "equipe_guideon.dev", "**gérer le statut Gold+** d'un serveur"):
        return

    # 🕒 Defer.
    try:
        await interaction.response.defer(ephemeral=True)
    except (discord.NotFound, discord.HTTPException):
        return

    # ⚙️ Activation commande.
    if not await verifier_commande(interaction, "dev_gold"):
        return

    # 📊 Tracking.
    await tracker_commande(interaction, "dev_gold")

    # 🔎 Vérification de l'ID.
    try:
        guild_id = int(id_serveur)
    except ValueError:
        return await interaction.followup.send(
            view=error_container("`id_serveur` doit être un **identifiant numérique**."), ephemeral=True)

    guild = interaction.client.get_guild(guild_id)
    if guild is None:
        return await interaction.followup.send(
            view=error_container("GuideOn n'est présent sur **aucun serveur** avec cet ID."), ephemeral=True)

    # ✨ Status Gold+.
    removed = await remove_entry(ShopRole.GOLD_PLUS, guild_id)
    if removed:
        log.info("[DEV_GOLD] Gold+ retiré pour %s (%d) | demandé par %d", guild.name, guild.id, interaction.user.id)

        return await interaction.followup.send(
            view=success_container(f"Gold+ **désactivé** pour **{guild.name}** (`{guild.id}`)."),
            ephemeral=True,
        )

    await add_entry(ShopRole.GOLD_PLUS, guild_id)
    log.info("[DEV_GOLD] Gold+ activé pour %s (%d) | demandé par %d", guild.name, guild.id, interaction.user.id)
    
    await interaction.followup.send(
        view=success_container(f"Gold+ **activé** pour **{guild.name}** (`{guild.id}`)."),
        ephemeral=True,
    )


# ============================================================
# ❌ Gestion des erreurs
# ============================================================

@gold.error
async def gold_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    await handle_app_command_error(interaction, error)