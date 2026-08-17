"""
cogs/mod/mod_warn.py — Avertit un membre.
"""

from __future__ import annotations

import discord
from discord import app_commands

from utils.botbancmd import verifier_ban_utilisateur
from utils.control_admin import verifier_commande
from utils.track_commande import tracker_commande

from utils.error_handler import handle_app_command_error
from utils.perm_mod import check_mod_permission

from utils.managers.mod_sanction_manager import SanctionType
from views.mod.sanction_builder_view import SanctionBuilderView


# ============================================================
# 🧭 Commande : /mod warn
# ============================================================

@app_commands.guild_only()
@app_commands.checks.cooldown(1, 5)
@app_commands.command(name="warn", description="⚠️ Avertit un membre")
async def mod_warn(interaction: discord.Interaction) -> None:

    # 🛡️ Vérification ban utilisateur.
    if not await verifier_ban_utilisateur(interaction):
        return

    # 🔐 Vérification permission /mod.
    if not await check_mod_permission(interaction, "mod_warn"):
        return

    # 🕒 Defer.
    try:
        await interaction.response.defer(ephemeral=True)
    except (discord.NotFound, discord.HTTPException):
        return

    # ⚙️ Vérification maintenance.
    if not await verifier_commande(interaction, "mod_warn"):
        return

    # 📊 Tracking.
    await tracker_commande(interaction, "mod_warn")

    # 💻 Envoi de l'interface.
    view = SanctionBuilderView(sanction_type=SanctionType.WARN, guild=interaction.guild, moderator_id=interaction.user.id)
    await interaction.followup.send(view=view, ephemeral=True)


# ============================================================
# ❌ Gestion des erreurs
# ============================================================

@mod_warn.error
async def mod_warn_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    await handle_app_command_error(interaction, error)