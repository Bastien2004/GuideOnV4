"""
cogs/giveaway/giveaway_list.py — Affiche la liste des giveaways du serveur (✨ Gold+).
"""

from __future__ import annotations

import logging

import discord
from discord import app_commands

from utils.botbancmd import verifier_ban_utilisateur
from utils.control_admin import verifier_commande
from utils.track_commande import tracker_commande

from utils.boutique.gold_manager import is_gold, send_gold_error
from utils.container_universel import error_container, info_container
from utils.error_handler import handle_app_command_error

from utils.managers.giveaway_manager import get_active_giveaways, get_ended_giveaways
from views.giveaway.list_view import GiveawayListView

log = logging.getLogger(__name__)


# ============================================================
# 🧭 Commande : /giveaway list
# ============================================================

@app_commands.guild_only()
@app_commands.checks.cooldown(1, 10)
@app_commands.command(name="list", description="📋 Liste les giveaways du serveur (✨ Gold+)")
async def giveaway_list(interaction: discord.Interaction) -> None:

    # 🛡️ Vérification ban utilisateur.
    if not await verifier_ban_utilisateur(interaction):
        return

    # ✨ Vérification Gold+.
    if not is_gold(interaction.guild.id):
        await send_gold_error(interaction)
        return

    # 🕒 Defer.
    try:
        await interaction.response.defer(ephemeral=True)
    except (discord.NotFound, discord.HTTPException):
        return

    # ⚙️ Vérification maintenance.
    if not await verifier_commande(interaction, "giveaway_list"):
        return

    # 📊 Tracking.
    await tracker_commande(interaction, "giveaway_list")

    # 🧩 Récup + affichage.
    try:
        active = await get_active_giveaways(interaction.guild.id)
        ended = await get_ended_giveaways(interaction.guild.id, limit=10)

        if not active and not ended:
            await interaction.followup.send(view=info_container("Il n'y a aucun giveaway sur ce serveur."), ephemeral=True)
            return

        view = GiveawayListView(guild=interaction.guild, active=active, ended=ended, owner_id=interaction.user.id)
        await interaction.followup.send(view=view, ephemeral=True)

    except Exception:
        log.exception("[GIVEAWAY LIST] Affichage de la liste échouée (guild=%s)", interaction.guild.id)
        await interaction.followup.send(view=error_container("Impossible d'afficher la **liste** des giveaways."), ephemeral=True)


# ============================================================
# ❌ Gestion des erreurs
# ============================================================

@giveaway_list.error
async def giveaway_list_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    await handle_app_command_error(interaction, error)