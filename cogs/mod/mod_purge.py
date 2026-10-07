"""
cogs/mod/mod_purge.py — Supprime un salon et le recrée (vide son historique).
"""

from __future__ import annotations

import discord
from discord import app_commands

from utils.botbancmd import verifier_ban_utilisateur
from utils.control_admin import verifier_commande
from utils.track_commande import tracker_commande

from utils.error_handler import handle_app_command_error
from utils.perm_mod import check_mod_permission

from views.mod.purge_builder_view import PurgeBuilderView


# ============================================================
# 🧭 Commande : /mod purge
# ============================================================

@app_commands.guild_only()
@app_commands.checks.cooldown(1, 10)
@app_commands.command(name="purge", description="💣 Supprime un salon et le recrée (vide son historique)")
async def mod_purge(interaction: discord.Interaction) -> None:

    # 🛡️ Vérification ban utilisateur.
    if not await verifier_ban_utilisateur(interaction):
        return

    # 🔐 Vérification permission /mod.
    if not await check_mod_permission(interaction, "mod_purge"):
        return

    # 🕒 Defer.
    try:
        await interaction.response.defer(ephemeral=True)
    except (discord.NotFound, discord.HTTPException):
        return

    # ⚙️ Vérification maintenance.
    if not await verifier_commande(interaction, "mod_purge"):
        return

    # 📊 Tracking.
    await tracker_commande(interaction, "mod_purge")

    # 💻 Envoi de l'interface.
    view = PurgeBuilderView(guild=interaction.guild, moderator=interaction.user)
    await interaction.followup.send(view=view, ephemeral=True)


# ============================================================
# ❌ Gestion des erreurs
# ============================================================

@mod_purge.error
async def mod_purge_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    await handle_app_command_error(interaction, error)
