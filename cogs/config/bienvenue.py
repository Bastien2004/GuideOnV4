"""
cogs/config/bienvenue.py — Affiche l'interface de configuration du système de bienvenue.
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

from views.bienvenue.config_view import create_bienvenue_view

log = logging.getLogger(__name__)


# ============================================================
# 🧭 Commande : /config bienvenue
# ============================================================

@app_commands.guild_only()
@app_commands.checks.cooldown(1, 10)
@app_commands.command(name="bienvenue", description="👋 Configure le système de bienvenue")
async def bienvenue(interaction: discord.Interaction) -> None:

    # 🛡️ Vérification ban utilisateur.
    if not await verifier_ban_utilisateur(interaction):
        return
    
    # 🔐 Verification Administrateur.
    if not await check_admin(interaction, "configurer le système de **bienvenue**"):
        return
    
    # 🕒 Defer.
    try:
        await interaction.response.defer(ephemeral=True)
    except (discord.NotFound, discord.HTTPException):
        return

    # ⚙️ Vérification maintenance.
    if not await verifier_commande(interaction, "config_bienvenue"):
        return
    
    
    # 📊 Tracking.
    await tracker_commande(interaction, "config_bienvenue")


    # 🧩 Création et envoi de l'interface.
    try:
        view = await create_bienvenue_view(
            guild_id=interaction.guild.id,
            author_id=interaction.user.id,
            bot=interaction.client,
        )
        if view is None:
            return await interaction.followup.send(
                view=error_container("Serveur introuvable."), ephemeral=True
            )
        await interaction.followup.send(view=view, ephemeral=True)
    except Exception:
        log.exception("[BIENVENUE] Ouverture de l'interface de configuration echouée (guild=%s)", interaction.guild.id)
        await interaction.followup.send(
            view=error_container("Impossible d'ouvrir l'**interface de configuration**."),
            ephemeral=True,
        )


# ============================================================
# ❌ Gestion des erreurs
# ============================================================

@bienvenue.error
async def bienvenue_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    await handle_app_command_error(interaction, error)