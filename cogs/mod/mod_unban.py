"""
cogs/mod/mod_unban.py — Lève un bannissement via la liste des membres bannis.

Zéro paramètre : la cible est choisie dans le panneau, à partir de
guild.bans() (les membres bannis ne peuvent pas être retrouvés via un
UserSelect natif, limité aux membres actuels du serveur).
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

from views.mod.unban_select_view import UnbanSelectView, fetch_banned_entries

log = logging.getLogger(__name__)


# ============================================================
# 🧭 Commande : /mod unban
# ============================================================

@app_commands.guild_only()
@app_commands.checks.cooldown(1, 10)
@app_commands.command(name="unban", description="🔓 Révoque un bannissement")
async def mod_unban(interaction: discord.Interaction) -> None:

    # 🛡️ Vérification ban utilisateur.
    if not await verifier_ban_utilisateur(interaction):
        return

    # 🔐 Vérification permission /mod.
    if not await check_mod_permission(interaction, "mod_unban"):
        return

    # 🕒 Defer.
    try:
        await interaction.response.defer(ephemeral=True)
    except (discord.NotFound, discord.HTTPException):
        return

    # ⚙️ Vérification maintenance.
    if not await verifier_commande(interaction, "mod_unban"):
        return

    # 📊 Tracking.
    await tracker_commande(interaction, "mod_unban")

    # 📁 Récupération des données.
    try:
        entries = await fetch_banned_entries(interaction.guild)
    except discord.Forbidden:
        await interaction.followup.send(
            view=error_container("Le bot n'a pas la permission de consulter la liste des **bannis**."),
            ephemeral=True,
        )
        return
    except discord.HTTPException:
        log.exception("[MOD_UNBAN] Échec récupération liste des bannis guild=%s", interaction.guild.id)
        await interaction.followup.send(
            view=error_container("Impossible de récupérer la liste des **bannis**."), ephemeral=True,
        )
        return

    if not entries:
        await interaction.followup.send(
            view=info_container("Aucun membre n'est actuellement banni sur ce serveur."), ephemeral=True,
        )
        return

    # 💻 Envoi de l'interface.
    view = UnbanSelectView(entries, guild=interaction.guild, moderator_id=interaction.user.id)
    await interaction.followup.send(view=view, ephemeral=True)


# ============================================================
# ❌ Gestion des erreurs
# ============================================================

@mod_unban.error
async def mod_unban_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    await handle_app_command_error(interaction, error)