"""
cogs/mod/mod_unmute.py — Commande /mod unmute (interface : liste des membres mutes).
"""
from __future__ import annotations

import logging

import discord
from discord import app_commands

from utils.botbancmd import verifier_ban_utilisateur
from utils.container_universel import error_container, info_container
from utils.control_admin import verifier_commande
from utils.error_handler import handle_app_command_error
from utils.managers.mod_sanction_manager import get_active_mutes
from utils.perm_mod import check_mod_permission
from utils.track_commande import tracker_commande

from views.mod.unmute_select_view import UnmuteSelectView

log = logging.getLogger(__name__)


# ============================================================
# 🔊 Commande : /mod unmute
# ============================================================

@app_commands.guild_only()
@app_commands.checks.cooldown(1, 5)
@app_commands.command(name="unmute", description="🔊 Lève le mute d'un membre via la liste des membres mutés")
async def mod_unmute(interaction: discord.Interaction) -> None:

    # 🛡️ Vérification ban utilisateur.
    if not await verifier_ban_utilisateur(interaction):
        return

    # 🔐 Vérification permission /mod.
    if not await check_mod_permission(interaction, "mod_unmute"):
        return

    # 🕒 Defer.
    try:
        await interaction.response.defer(ephemeral=True)
    except (discord.NotFound, discord.HTTPException):
        return

    # ⚙️ Vérification maintenance.
    if not await verifier_commande(interaction, "mod_unmute"):
        return

    # 📊 Tracking.
    await tracker_commande(interaction, "mod_unmute")

    try:
        entries = await get_active_mutes(interaction.guild.id)
    except Exception:
        log.exception("[MOD_UNMUTE] Échec récupération mutes actifs guild=%s", interaction.guild.id)
        await interaction.followup.send(
            view=error_container("Impossible de récupérer les **membres mutés**."), ephemeral=True,
        )
        return

    if not entries:
        await interaction.followup.send(
            view=info_container("Aucun membre n'est actuellement muet sur ce serveur."), ephemeral=True,
        )
        return

    view = UnmuteSelectView(entries, guild=interaction.guild, moderator_id=interaction.user.id)
    await interaction.followup.send(view=view, ephemeral=True)


# ============================================================
# ❌ Gestion des erreurs
# ============================================================

@mod_unmute.error
async def mod_unmute_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    await handle_app_command_error(interaction, error)
