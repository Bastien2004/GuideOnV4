"""
cogs/giveaway/giveaway_list.py — Commande /giveaway list (Gold+).

Liste les giveaways actifs et les 10 derniers terminés du serveur.
Réservé aux serveurs Gold+.

Pipeline :
    verifier_ban_utilisateur → defer → verifier_commande → tracker_commande
    → check Gold → GiveawayListView
"""
from __future__ import annotations

import logging

import discord
from discord import app_commands

from utils.botbancmd import verifier_ban_utilisateur
from utils.boutique.gold_manager import is_gold, send_gold_error
from utils.container_universel import error_container, info_container
from utils.control_admin import verifier_commande
from utils.error_handler import handle_app_command_error
from utils.managers.giveaway_manager import get_active_giveaways, get_ended_giveaways
from utils.track_commande import tracker_commande

from views.giveaway.list_view import GiveawayListView

log = logging.getLogger(__name__)


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
            await interaction.followup.send(
                view=info_container("Aucun giveaway sur ce serveur."),
                ephemeral=True,
            )
            return

        view = GiveawayListView(
            guild=interaction.guild,
            active=active,
            ended=ended,
            owner_id=interaction.user.id,
        )
        await interaction.followup.send(view=view, ephemeral=True)
    except Exception:
        log.exception("/giveaway list échoué (guild=%s)", interaction.guild.id)
        await interaction.followup.send(
            view=error_container("Impossible d'afficher la **liste**."),
            ephemeral=True,
        )


@giveaway_list.error
async def giveaway_list_error(
    interaction: discord.Interaction, error: app_commands.AppCommandError
) -> None:
    await handle_app_command_error(interaction, error)