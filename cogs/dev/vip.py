"""
cogs/dev/vip.py — Gère le grade VIP.
"""

from __future__ import annotations

import logging

import discord
from discord import app_commands, Interaction

from utils.control_admin import verifier_commande
from utils.track_commande import tracker_commande

from utils.container_universel import success_container
from utils.error_handler import handle_app_command_error
from utils.managers.boutique_manager import add_entry, remove_entry
from utils.db.models.boutique import ShopRole
from utils.perm_dev import check_dev

log = logging.getLogger(__name__)


# ============================================================
# 🧭 Commande : /dev vip
# ============================================================

@app_commands.guild_only()
@app_commands.checks.cooldown(1, 10)
@app_commands.command(name="vip", description="✨ [DEV] Gère le statut VIP d'un utilisateur")
@app_commands.describe(membre="Membre Discord cible")
async def vip(interaction: Interaction, membre: discord.Member) -> None:

    # 🔐 Vérification des permissions.
    if not await check_dev(interaction, "**gérer le statut VIP** d'un utilisateur"):
        return

    # 🕒 Defer.
    try:
        await interaction.response.defer(ephemeral=True)
    except (discord.NotFound, discord.HTTPException):
        return

    # ⚙️ Activation commande.
    if not await verifier_commande(interaction, "dev_vip"):
        return

    # 📊 Tracking.
    await tracker_commande(interaction, "dev_vip")

    # ✨ Toggle VIP.
    removed = await remove_entry(ShopRole.VIP, membre.id)
    if removed:
        log.info("[DEV_VIP] VIP retiré pour %s (%d) | demandé par %d", membre.display_name, membre.id, interaction.user.id)
        return await interaction.followup.send(
            view=success_container(f"VIP **désactivé** pour **{membre.display_name}** (<@{membre.id}>)."),
            ephemeral=True,
        )

    await add_entry(ShopRole.VIP, membre.id)
    log.info(
        "[DEV_VIP] VIP activé pour %s (%d) | demandé par %d",
        membre.display_name, membre.id, interaction.user.id,
    )
    await interaction.followup.send(
        view=success_container(f"VIP **activé** pour **{membre.display_name}** (<@{membre.id}>)."),
        ephemeral=True,
    )


# ============================================================
# ❌ Gestion des erreurs
# ============================================================

@vip.error
async def vip_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    await handle_app_command_error(interaction, error)