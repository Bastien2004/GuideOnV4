"""
cogs/mod/mod_unwarn.py — Révoque un avertissement via la liste des avertissements actifs.
"""

from __future__ import annotations

import logging

import discord
from discord import app_commands

from utils.botbancmd import verifier_ban_utilisateur
from utils.control_admin import verifier_commande
from utils.track_commande import tracker_commande

from utils.container_universel import error_container, info_container
from utils.error_handler import handle_app_command_error
from utils.perm_mod import check_mod_permission

from utils.managers.mod_sanction_manager import get_active_warns
from views.mod.unwarn_select_view import UnwarnSelectView

log = logging.getLogger(__name__)


# ============================================================
# 🧭 Commande : /mod unwarn
# ============================================================

@app_commands.guild_only()
@app_commands.checks.cooldown(1, 10)
@app_commands.command(name="unwarn", description="🚫 Révoque un avertissement via la liste des avertissements actifs")
async def mod_unwarn(interaction: discord.Interaction) -> None:

    # 🛡️ Vérification ban utilisateur.
    if not await verifier_ban_utilisateur(interaction):
        return

    # 🔐 Vérification permission /mod.
    if not await check_mod_permission(interaction, "mod_unwarn"):
        return

    # 🕒 Defer.
    try:
        await interaction.response.defer(ephemeral=True)
    except (discord.NotFound, discord.HTTPException):
        return

    # ⚙️ Vérification maintenance.
    if not await verifier_commande(interaction, "mod_unwarn"):
        return

    # 📊 Tracking.
    await tracker_commande(interaction, "mod_unwarn")

    # 📁 Récupération des données.
    try:
        entries = await get_active_warns(interaction.guild.id)
    except Exception:
        log.exception("[MOD_UNWARN] Échec récupération avertissements guild=%s", interaction.guild.id)
        await interaction.followup.send(
            view=error_container("Impossible de récupérer les **avertissements actifs**."), ephemeral=True,
        )
        return

    if not entries:
        await interaction.followup.send(
            view=info_container("Aucun avertissement actif sur ce serveur."), ephemeral=True,
        )
        return

    # 💻 Envoi de l'interface.
    view = UnwarnSelectView(entries, guild=interaction.guild, moderator_id=interaction.user.id)
    await interaction.followup.send(view=view, ephemeral=True)


# ============================================================
# ❌ Gestion des erreurs
# ============================================================

@mod_unwarn.error
async def mod_unwarn_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    await handle_app_command_error(interaction, error)