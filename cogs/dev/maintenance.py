"""
cogs/dev/maintenance.py — Gère l'activation des commandes du bot.
"""

from __future__ import annotations

import discord
from discord import Interaction, app_commands

from utils.control_admin import verifier_commande
from utils.perm_check import has_grade_check
from utils.track_commande import tracker_commande

from utils.error_handler import handle_app_command_error
from utils.container_universel import error_container

from utils.managers.command_toggle_manager import get_all_commands
from views.dev.maintenance_view import create_maintenance_view


# ============================================================
# 🧭 Commande : /dev maintenance
# ============================================================

@app_commands.guild_only()
@app_commands.checks.cooldown(1, 10)
@app_commands.command(name="maintenance", description="🛠️ [DEV] Gérer l'activation des commandes du bot")
async def maintenance(interaction: Interaction) -> None:

    # 🔐 Vérification des permissions.
    if not await has_grade_check(interaction, "equipe_guideon.dev", "gérer le **mode maintenance** du bot"):
        return
    
    # 🕒 Defer.
    try:
        await interaction.response.defer(ephemeral=True)
    except (discord.NotFound, discord.HTTPException):
        return

    # ⚙️ Vérification maintenance.
    if not await verifier_commande(interaction, "dev_maintenance"):
        return

    # 📊 Tracking.
    await tracker_commande(interaction, "dev_maintenance")

    # 📋 Récupération des données.
    try:
        data = await get_all_commands()
        view = await create_maintenance_view(data)
    except Exception:
        return await interaction.followup.send(
            view=error_container("Impossible de charger l'**interface de maintenance**."),
            ephemeral=True,
        )

    # ✉️ Envoi de l'interface
    await interaction.followup.send(view=view, ephemeral=True)


# ============================================================
# ❌ Gestion erreurs
# ============================================================

@maintenance.error
async def maintenance_error(interaction: Interaction, error: app_commands.AppCommandError) -> None:
    await handle_app_command_error(interaction, error)