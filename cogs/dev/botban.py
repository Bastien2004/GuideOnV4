"""
cogs/dev/botban.py — Gestion des bannissements du bot.
"""

from __future__ import annotations

import logging

import discord
from discord import app_commands, Interaction

from utils.control_admin import verifier_commande
from utils.track_commande import tracker_commande

from utils.error_handler import handle_app_command_error
from utils.perm_dev import check_dev

from views.dev.botban_view import BotBanView

log = logging.getLogger(__name__)


# ============================================================
# 🧭 Commande : /dev botban
# ============================================================

@app_commands.guild_only()
@app_commands.checks.cooldown(1, 10)
@app_commands.command(name="botban", description="🚫 [DEV] Gestion des bans globaux du bot")
async def botban(interaction: Interaction) -> None:

    # 🔐 Vérification des permissions.
    if not await check_dev(interaction, "**gérer les bans** du bot"):
        return

    # 🕒 Defer.
    try:
        await interaction.response.defer(ephemeral=True)
    except (discord.NotFound, discord.HTTPException):
        return

    # ⚙️ Activation commande.
    if not await verifier_commande(interaction, "dev_botban"):
        return

    # 📊 Tracking.
    await tracker_commande(interaction, "dev_botban")

    # ✉️ Envoi du dashboard.
    await interaction.followup.send(view=BotBanView(interaction.user.id), ephemeral=True)


# ============================================================
# ❌ Gestion des erreurs
# ============================================================

@botban.error
async def botban_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    await handle_app_command_error(interaction, error)