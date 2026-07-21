"""
cogs/config/role_all.py — Affiche l'interface de gestion du rôle all.
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

from views.role_all.config_view import create_role_all_view

log = logging.getLogger(__name__)


# ============================================================
# 👥 Commande : /config role_all
# ============================================================

@app_commands.guild_only()
@app_commands.checks.cooldown(1, 15)
@app_commands.command(name="role_all", description="👥 Attribue ou retire un rôle à tous les membres du serveur",)
async def role_all(interaction: discord.Interaction) -> None:

    # 🛡️ Vérification ban utilisateur.
    if not await verifier_ban_utilisateur(interaction):
        return

    # 🔐 Vérification Administrateur.
    if not await check_admin(interaction, "gérer les **rôles en masse**"):
        return

    # 🕒 Defer.
    try:
        await interaction.response.defer(ephemeral=True)
    except (discord.NotFound, discord.HTTPException):
        return

    # ⚙️ Vérification maintenance.
    if not await verifier_commande(interaction, "config_role_all"):
        return

    # 📊 Tracking.
    await tracker_commande(interaction, "config_role_all")

    # 🧩 Création et envoi de l'interface.
    try:
        view = await create_role_all_view(
            guild=interaction.guild,
            bot=interaction.client,
            author_id=interaction.user.id,
            page="main",
        )
        await interaction.followup.send(view=view, ephemeral=True)

    except Exception:
        log.exception("[ROLE-ALL] Ouverture de l'interface de gestion échouée (guild=%s)", interaction.guild.id)
        await interaction.followup.send(
            view=error_container("**Impossible** d'ouvrir l'__interface de gestion__."),
            ephemeral=True,
        )


# ============================================================
# ❌ Gestion des erreurs
# ============================================================

@role_all.error
async def role_all_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    await handle_app_command_error(interaction, error)