"""
cogs/mod/mod_unlock.py — Déverrouille un salon textuel.

Le verrouillage est traité par /mod lock (cogs/mod/mod_lock.py).
Partage la même clé de permission `mod_lock` : quelqu'un qui peut verrouiller
peut déverrouiller (une seule config pour les deux).
"""
from __future__ import annotations

import discord
from discord import app_commands

from utils.botbancmd import verifier_ban_utilisateur
from utils.container_universel import error_container
from utils.control_admin import verifier_commande
from utils.error_handler import handle_app_command_error
from utils.perm_mod import check_mod_permission
from utils.track_commande import tracker_commande

from views.mod.unlock_builder_view import UnlockBuilderView


# ============================================================
# 🧭 Commande : /mod unlock
# ============================================================

@app_commands.guild_only()
@app_commands.checks.cooldown(1, 10)
@app_commands.command(name="unlock", description="🔓 Déverrouille un salon textuel")
async def mod_unlock(interaction: discord.Interaction) -> None:

    # 🛡️ Vérification ban utilisateur.
    if not await verifier_ban_utilisateur(interaction):
        return

    # 🔐 Vérification permission /mod (même clé que /mod lock).
    if not await check_mod_permission(interaction, "mod_lock"):
        return

    # 🕒 Defer.
    try:
        await interaction.response.defer(ephemeral=True)
    except (discord.NotFound, discord.HTTPException):
        return

    # ⚙️ Vérification maintenance.
    if not await verifier_commande(interaction, "mod_unlock"):
        return

    # 📊 Tracking.
    await tracker_commande(interaction, "mod_unlock")

    # 💻 Envoi de l'interface.
    view = UnlockBuilderView(guild=interaction.guild, moderator=interaction.user)
    await interaction.followup.send(view=view, ephemeral=True)


# ============================================================
# ❌ Gestion des erreurs
# ============================================================

@mod_unlock.error
async def mod_unlock_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    await handle_app_command_error(interaction, error)