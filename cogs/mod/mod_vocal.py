"""
cogs/mod/mod_vocal.py — Gestion vocale de masse (mute/déplacer/expulser).
"""

from __future__ import annotations

import discord
from discord import app_commands

from utils.botbancmd import verifier_ban_utilisateur
from utils.control_admin import verifier_commande
from utils.track_commande import tracker_commande

from utils.error_handler import handle_app_command_error
from utils.perm_mod import check_mod_permission

from views.mod.voice_manage_builder_view import VoiceManageBuilderView


# ============================================================
# 🧭 Commande : /mod vocal
# ============================================================

@app_commands.guild_only()
@app_commands.checks.cooldown(1, 10)
@app_commands.command(name="vocal", description="🔊 Gestion vocale de masse")
async def mod_vocal(interaction: discord.Interaction) -> None:

    # 🛡️ Vérification ban utilisateur.
    if not await verifier_ban_utilisateur(interaction):
        return

    # 🔐 Vérification permission /mod.
    if not await check_mod_permission(interaction, "mod_voice_manage"):
        return

    # 🕒 Defer.
    try:
        await interaction.response.defer(ephemeral=True)
    except (discord.NotFound, discord.HTTPException):
        return

    # ⚙️ Vérification maintenance.
    if not await verifier_commande(interaction, "mod_voice_manage"):
        return

    # 📊 Tracking.
    await tracker_commande(interaction, "mod_voice_manage")

    # 💻 Envoi de l'interface.
    view = VoiceManageBuilderView(guild=interaction.guild, moderator_id=interaction.user.id)
    await interaction.followup.send(view=view, ephemeral=True)


# ============================================================
# ❌ Gestion des erreurs
# ============================================================

@mod_vocal.error
async def mod_vocal_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    await handle_app_command_error(interaction, error)