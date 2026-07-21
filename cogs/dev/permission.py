"""
cogs/dev/permissions.py — Gère les permissions internes du bot (DEV, STAFF, OP_ALPHA).
"""
from __future__ import annotations

import logging

import discord
from discord import Interaction, app_commands

from utils.control_admin import verifier_commande
from utils.track_commande import tracker_commande
from utils.createur import is_creator

from utils.error_handler import handle_app_command_error
from utils.container_universel import error_container
from views.dev.permissions_view import create_permissions_view

log = logging.getLogger(__name__)


# ============================================================
# 🧭 Commande principale : /dev permissions
# ============================================================

@app_commands.guild_only()
@app_commands.checks.cooldown(1, 10)
@app_commands.command(name="permissions", description="🔐 [DEV] Gérer les permissions internes du bot")
async def permissions(interaction: Interaction) -> None:

    # 🔐 Vérification des permissions.
    if not await is_creator(interaction):
        return

    # 🕒 Defer.
    try:
        await interaction.response.defer(ephemeral=True)
    except (discord.NotFound, discord.HTTPException):
        return

    # ⚙️ Activation commande.
    if not await verifier_commande(interaction, "dev_permissions"):
        return

    # 📊 Tracking.
    await tracker_commande(interaction, "dev_permissions")

    # 🧩 Création interface.
    try:
        view = await create_permissions_view(interaction.client, interaction.user.id)
    except Exception:
        log.exception("[DEV PERMISSIONS] Erreur interface permissions")
        await interaction.followup.send(
            view=error_container("Impossible de charger l'**interface des permissions**."),
            ephemeral=True,
        )
        return

    # 📤 Envoi de l'interface.
    await interaction.followup.send(view=view, ephemeral=True)


# ============================================================
# ❌ Gestion erreurs
# ============================================================

@permissions.error
async def permissions_error(interaction: Interaction, error: app_commands.AppCommandError) -> None:
    await handle_app_command_error(interaction, error)