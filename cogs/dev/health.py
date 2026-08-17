"""
cogs/dev/health.py — État de santé global du bot GuideOn.
"""

from __future__ import annotations

import discord
from discord import app_commands, Interaction

from utils.control_admin import verifier_commande
from utils.track_commande import tracker_commande
from utils.perm_check import has_grade_check

from utils.error_handler import handle_app_command_error
from utils.health import gather_health_data
from views.dev.health_view import build_health_view


# ============================================================
# 🧭 Commande : /dev health
# ============================================================

@app_commands.guild_only()
@app_commands.checks.cooldown(1, 10)
@app_commands.command(name="health", description="🤖 [DEV] Envoie l'état de santé du bot")
async def health(interaction: Interaction) -> None:

    # 🔐 Vérification des permissions.
    if not await has_grade_check(interaction, "equipe_guideon.dev", "consulter l'**état de santé** du bot"):
        return

    # 🕒 Defer.
    try:
        await interaction.response.defer(ephemeral=True)
    except (discord.NotFound, discord.HTTPException):
        return

    # ⚙️ Activation commande.
    if not await verifier_commande(interaction, "dev_health"):
        return

    # 📊 Tracking.
    await tracker_commande(interaction, "dev_health")

    # 🚀 # 🚀 Récupération et envoi des données.
    data = await gather_health_data(interaction.client)
    view = build_health_view(data)

    await interaction.followup.send(view=view, ephemeral=True)


# ============================================================
# ❌ Gestion des erreurs
# ============================================================

@health.error
async def health_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    await handle_app_command_error(interaction, error)