"""
cogs/giveaway/giveaway_blacklist.py — Commande /giveaway blacklist (admin).

Ouvre le panneau interactif de gestion de la blacklist du serveur :
liste paginée + ajout (avec raison/durée optionnelles) + retrait + purge.

Pipeline :
    verifier_ban_utilisateur → check_admin → defer → verifier_commande
    → tracker_commande → GiveawayBlacklistView.create
"""
from __future__ import annotations

import logging

import discord
from discord import app_commands

from utils.botbancmd import verifier_ban_utilisateur
from utils.container_universel import error_container
from utils.control_admin import verifier_commande
from utils.error_handler import handle_app_command_error
from utils.perm_admin import check_admin
from utils.track_commande import tracker_commande

from views.giveaway.blacklist_view import GiveawayBlacklistView

log = logging.getLogger(__name__)


@app_commands.guild_only()
@app_commands.checks.cooldown(1, 5)
@app_commands.command(
    name="blacklist",
    description="🚫 Gère la blacklist du système de giveaway",
)
async def giveaway_blacklist(interaction: discord.Interaction) -> None:

    # 🛡️ Vérification ban utilisateur.
    if not await verifier_ban_utilisateur(interaction):
        return

    # 🔐 Vérification Administrateur.
    if not await check_admin(interaction, "gérer la **blacklist giveaway**"):
        return

    # 🕒 Defer.
    try:
        await interaction.response.defer(ephemeral=True)
    except (discord.NotFound, discord.HTTPException):
        return

    # ⚙️ Vérification maintenance.
    if not await verifier_commande(interaction, "giveaway_blacklist"):
        return

    # 📊 Tracking.
    await tracker_commande(interaction, "giveaway_blacklist")

    # 🧩 Ouverture du panneau.
    try:
        view = await GiveawayBlacklistView.create(
            guild=interaction.guild,
            owner_id=interaction.user.id,
        )
        await interaction.followup.send(view=view, ephemeral=True)
    except Exception:
        log.exception(
            "Ouverture /giveaway blacklist échouée (guild=%s)", interaction.guild.id
        )
        await interaction.followup.send(
            view=error_container("Impossible d'ouvrir la **blacklist**."),
            ephemeral=True,
        )


@giveaway_blacklist.error
async def giveaway_blacklist_error(
    interaction: discord.Interaction, error: app_commands.AppCommandError
) -> None:
    await handle_app_command_error(interaction, error)