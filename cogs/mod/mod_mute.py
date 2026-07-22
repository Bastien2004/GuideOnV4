"""
cogs/mod/mod_mute.py — Rend un utilisateur temporairement muet.
"""

from __future__ import annotations

import discord
from discord import app_commands

from utils.botbancmd import verifier_ban_utilisateur
from utils.track_commande import tracker_commande
from utils.control_admin import verifier_commande

from utils.error_handler import handle_app_command_error
from utils.perm_mod import check_mod_permission

from utils.managers.mod_sanction_manager import SanctionType
from views.mod.sanction_builder_view import SanctionBuilderView


# ============================================================
#  🧭 Commande : /mod mute
# ============================================================

@app_commands.guild_only()
@app_commands.checks.cooldown(1, 5)
@app_commands.command(name="mute", description="🔇 Rend un membre muet temporairement")
async def mod_mute(interaction: discord.Interaction) -> None:

    # 🛡️ Vérification ban utilisateur.
    if not await verifier_ban_utilisateur(interaction):
        return

    # 🔐 Vérification permission /mod.
    if not await check_mod_permission(interaction, "mod_mute"):
        return

    # 🕒 Defer.
    try:
        await interaction.response.defer(ephemeral=True)
    except (discord.NotFound, discord.HTTPException):
        return

    # ⚙️ Vérification maintenance.
    if not await verifier_commande(interaction, "mod_mute"):
        return

    # 📊 Tracking.
    await tracker_commande(interaction, "mod_mute")

    # 💻 Envoi de l'interface.
    view = SanctionBuilderView(sanction_type=SanctionType.MUTE, guild=interaction.guild, moderator_id=interaction.user.id)
    await interaction.followup.send(view=view, ephemeral=True)


# ============================================================
# ❌ Gestion des erreurs
# ============================================================

@mod_mute.error
async def mod_mute_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    await handle_app_command_error(interaction, error)