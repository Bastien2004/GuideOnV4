"""
cogs/alpha/event_list.py — Affiche les events M+ du Alpha
"""

from __future__ import annotations

import discord
from discord import app_commands, Interaction

from utils.botbancmd import verifier_ban_utilisateur
from utils.control_admin import verifier_commande
from utils.track_commande import tracker_commande

from utils.perm_alpha import check_modo_plus
from utils.error_handler import handle_app_command_error
from views.alpha.event_list_view import EventListView


# ============================================================
# 🧭 Commande : /alpha event_list
# ============================================================

@app_commands.guild_only()
@app_commands.checks.cooldown(1, 10)
@app_commands.command(name="event_list", description="🗂️ [M+] Affiche la liste des events Alpha")
async def event_list(interaction: Interaction) -> None:

    # 🛡️ Vérification ban utilisateur.
    if not await verifier_ban_utilisateur(interaction):
        return

    # 🔐 Vérification des permissions.
    if not await check_modo_plus(interaction, "**consulter** la liste des __events__"):
        return

    # 🕒 Defer.
    try:
        await interaction.response.defer(ephemeral=True)
    except (discord.NotFound, discord.HTTPException):
        return

    # ⚙️ Vérification maintenance.
    if not await verifier_commande(interaction, "alpha_event_list"):
        return

    # 📊 Tracking.
    await tracker_commande(interaction, "alpha_event_list")

    # ✉️ Envoi du menu
    await interaction.followup.send(view=EventListView(interaction.user.id), ephemeral=True)


# ============================================================
# ❌ Gestion des erreurs
# ============================================================

@event_list.error
async def event_list_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    await handle_app_command_error(interaction, error)