"""
cogs/rappel/rappel_creer.py — Planifie un rappel personnel.
"""

from __future__ import annotations

import discord
from discord import app_commands

from utils.botbancmd import verifier_ban_utilisateur
from utils.control_admin import verifier_commande
from utils.error_handler import handle_app_command_error
from utils.track_commande import tracker_commande

from views.rappel.creer_view import RappelCreerView


# ============================================================
# ⏰ Commande : /rappel créer
# ============================================================

@app_commands.guild_only()
@app_commands.checks.cooldown(1, 10)
@app_commands.command(name="create", description="⏰ Crée un rappel personnel")
async def rappel_create(interaction: discord.Interaction) -> None:

    # 🛡️ Vérification ban utilisateur.
    if not await verifier_ban_utilisateur(interaction):
        return

    # 🕒 Defer.
    try:
        await interaction.response.defer(ephemeral=True)
    except (discord.NotFound, discord.HTTPException):
        return

    # ⚙️ Vérification maintenance.
    if not await verifier_commande(interaction, "rappel_create"):
        return

    # 📊 Tracking.
    await tracker_commande(interaction, "rappel_create")

    # 💻 Envoi de l'interface.
    view = RappelCreerView(user_id=interaction.user.id, guild_id=interaction.guild.id, channel_id=interaction.channel.id)
    await interaction.followup.send(view=view, ephemeral=True)


# ============================================================
# ❌ Gestion des erreurs
# ============================================================

@rappel_create.error
async def rappel_create_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    await handle_app_command_error(interaction, error)