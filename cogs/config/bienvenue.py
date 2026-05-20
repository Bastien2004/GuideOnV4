"""
cogs/config/bienvenue.py — Commande /config bienvenue.
"""
from __future__ import annotations

import logging

import discord
from discord import app_commands

from utils.botbancmd import verifier_ban_utilisateur
from utils.perm_admin import check_admin
from utils.track_commande import tracker_commande
from utils.control_admin import verifier_commande

from utils.container_universel import error_container
from utils.error_handler import handle_app_command_error

from views.bienvenue.config_view import BienvenueConfigView

log = logging.getLogger(__name__)


# ============================================================
# 🧭 Commande : /config bienvenue
# ============================================================

@app_commands.guild_only()
@app_commands.checks.cooldown(1, 10)
@app_commands.command(name="bienvenue", description="👋 Configure le système de bienvenue")
async def bienvenue(interaction: discord.Interaction) -> None:

     # 🔒 Vérification ban bot
    if not await verifier_ban_utilisateur(interaction):
        return
    
    # 🔐 Verification Administrateur
    if not await check_admin(interaction, "configurer le système de **bienvenue**"):
        return
    
    # 🕒 Defer
    await interaction.response.defer(ephemeral=True)

    # ⚙️ Maintenance
    if not await verifier_commande(interaction, "config_bienvenue"):
        return
    
    
    # 📊 Tracking
    await tracker_commande(interaction, "config_bienvenue")


    # 🪟 Création et envoie de la View
    try:
        view = await BienvenueConfigView.create(
            guild_id=interaction.guild.id,
            author_id=interaction.user.id,
            bot=interaction.client,
        )
        await interaction.followup.send(view=view, ephemeral=True)
    except Exception:
        log.exception("Ouverture config bienvenue echouee (guild=%s)", interaction.guild.id)
        await interaction.followup.send(
            view=error_container(
                "Impossible d'ouvrir la configuration."
            ),
            ephemeral=True,
        )


# ============================================================
# ❌ Gestion des erreurs
# ============================================================

@bienvenue.error
async def bienvenue_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    await handle_app_command_error(interaction, error)