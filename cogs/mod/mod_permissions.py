"""
cogs/mod/mod_permissions.py — Gère les permissions de modération.
"""

from __future__ import annotations

import logging

import discord
from discord import app_commands

from utils.botbancmd import verifier_ban_utilisateur
from utils.control_admin import verifier_commande
from utils.track_commande import tracker_commande

from utils.container_universel import error_container
from utils.error_handler import handle_app_command_error
from utils.perm_admin import check_admin

from views.mod.permissions_view import ModPermissionsView

log = logging.getLogger(__name__)


# ============================================================
# 🧭 Commande : /mod permissions
# ============================================================

@app_commands.guild_only()
@app_commands.checks.cooldown(1, 10)
@app_commands.command(name="permissions", description="🔐 Gère les permissions de modération")
async def mod_permissions(interaction: discord.Interaction) -> None:

    # 🛡️ Vérification ban utilisateur.
    if not await verifier_ban_utilisateur(interaction):
        return

    # 🔐 Vérification des permissions.
    if not await check_admin(interaction, "configurer les **permissions** du système de modération"):
        return

    # 🕒 Defer.
    try:
        await interaction.response.defer(ephemeral=True)
    except (discord.NotFound, discord.HTTPException):
        return

    # ⚙️ Vérification maintenance.
    if not await verifier_commande(interaction, "mod_permissions"):
        return

    # 📊 Tracking.
    await tracker_commande(interaction, "mod_permissions")

    # 🧩 Création et envoi de l'interface.
    try:
        view = await ModPermissionsView.create(
            guild_id=interaction.guild.id,
            author_id=interaction.user.id,
            bot=interaction.client,
        )
        await interaction.followup.send(view=view, ephemeral=True)

    except Exception:
        log.exception("[MOD_PERM] Ouverture du /mod permissions échouée (guild=%s)", interaction.guild.id)
        await interaction.followup.send(
            view=error_container("Impossible d'ouvrir l'interface de permissions."),
            ephemeral=True,
        )


# ============================================================
# ❌ Gestion des erreurs
# ============================================================

@mod_permissions.error
async def mod_permissions_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    await handle_app_command_error(interaction, error)