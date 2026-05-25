"""
cogs/config/autorole.py — Commande /config autorole.
"""
from __future__ import annotations

import logging

import discord
from discord import app_commands

from utils.botbancmd import verifier_ban_utilisateur
from utils.track_commande import tracker_commande
from utils.control_admin import verifier_commande

from utils.perm_admin import check_admin
from utils.container_universel import error_container
from utils.error_handler import handle_app_command_error

from views.autorole.config_view import create_autorole_view

log = logging.getLogger(__name__)


# ============================================================
# 🧭 Commande : /config autorole
# ============================================================

@app_commands.guild_only()
@app_commands.checks.cooldown(1, 10)
@app_commands.command(name="autorole", description="🎭 Configure l'attribution automatique de rôles")
async def autorole(interaction: discord.Interaction) -> None:

    # 🛡️ Vérification ban utilisateur.
    if not await verifier_ban_utilisateur(interaction):
        return

    # 🔐 Vérification Administrateur.
    if not await check_admin(interaction, "configurer l'**auto-rôle**"):
        return

    # 🕒 Defer.
    try:
        await interaction.response.defer(ephemeral=True)
    except (discord.NotFound, discord.HTTPException):
        return

    # ⚙️ Vérification maintenance.
    if not await verifier_commande(interaction, "config_autorole"):
        return

    # 📊 Tracking
    await tracker_commande(interaction, "config_autorole")

    # 🪟 Création et envoi de la View
    try:
        view = await create_autorole_view(
            guild_id=interaction.guild.id,
            bot=interaction.client,
            author_id=interaction.user.id,
        )
        if view is None:
            return await interaction.followup.send(
                view=error_container("Serveur introuvable."), ephemeral=True
            )
        await interaction.followup.send(view=view, ephemeral=True)
    except Exception:
        log.exception("**Ouverture** config autorole **échouée** (guild=%s)", interaction.guild.id)
        await interaction.followup.send(
            view=error_container("**Impossible** d'ouvrir la __configuration__."),
            ephemeral=True,
        )


# ============================================================
# ❌ Gestion des erreurs
# ============================================================

@autorole.error
async def autorole_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    await handle_app_command_error(interaction, error)