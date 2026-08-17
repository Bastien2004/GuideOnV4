"""
cogs/giveaway/giveaway_create.py — Crée unn nouveau giveaway.
"""

from __future__ import annotations

import logging

import discord
from discord import app_commands

from utils.botbancmd import verifier_ban_utilisateur
from utils.control_admin import verifier_commande
from utils.perm_admin import check_admin
from utils.track_commande import tracker_commande

from utils.error_handler import handle_app_command_error
from utils.container_universel import error_container
from views.giveaway.create_view import GiveawayCreateView

log = logging.getLogger(__name__)


# ============================================================
# 🧭 Commande : /giveaway create
# ============================================================

@app_commands.guild_only()
@app_commands.checks.cooldown(1, 10)
@app_commands.command(name="create", description="🎉 Crée un nouveau giveaway")
async def giveaway_create(interaction: discord.Interaction) -> None:

    # 🛡️ Vérification ban utilisateur.
    if not await verifier_ban_utilisateur(interaction):
        return

    # 🔐 Vérification Administrateur.
    if not await check_admin(interaction, "créer un **giveaway**"):
        return

    # 🕒 Defer.
    try:
        await interaction.response.defer(ephemeral=True)
    except (discord.NotFound, discord.HTTPException):
        return

    # ⚙️ Vérification maintenance.
    if not await verifier_commande(interaction, "giveaway_create"):
        return

    # 📊 Tracking.
    await tracker_commande(interaction, "giveaway_create")

    # 🧩 Ouverture du wizard.
    try:
        view = await GiveawayCreateView.create(guild=interaction.guild, author_id=interaction.user.id)
        await interaction.followup.send(view=view, ephemeral=True)

    except Exception:
        log.exception("[GIVEAWAY CREATE] Ouverture de l'interface de création échouée (guild=%s)", interaction.guild.id)
        await interaction.followup.send(view=error_container("Impossible d'ouvrir l'**interface de création**."), ephemeral=True)


# ============================================================
# ❌ Gestion des erreurs
# ============================================================

@giveaway_create.error
async def giveaway_create_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    await handle_app_command_error(interaction, error)