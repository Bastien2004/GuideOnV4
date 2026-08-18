"""
cogs/invite/invite_user.py — Commande /invite user [membre].
"""

from __future__ import annotations

import logging
from typing import Optional

import discord
from discord import app_commands

from utils.botbancmd import verifier_ban_utilisateur
from utils.container_universel import error_container
from utils.control_admin import verifier_commande
from utils.error_handler import handle_app_command_error
from utils.managers.invite_manager import get_link, get_user_stats
from utils.track_commande import tracker_commande

from views.invite.user_view import build_user_stats_view

log = logging.getLogger(__name__)


# ============================================================
# 📨 Commande : /invite user [membre]
# ============================================================

@app_commands.guild_only()
@app_commands.checks.cooldown(1, 10)
@app_commands.command(name="user", description="📨 Affiche les invitations d'un membre",)
@app_commands.describe(membre="Le membre dont tu veux voir les invitations (toi par défaut)")
async def invite_user(interaction: discord.Interaction, membre: Optional[discord.Member] = None) -> None:

    # 🛡️ Vérification ban utilisateur.
    if not await verifier_ban_utilisateur(interaction):
        return

    # 🕒 Defer.
    try:
        await interaction.response.defer()
    except (discord.NotFound, discord.HTTPException):
        return

    # ⚙️ Vérification maintenance.
    if not await verifier_commande(interaction, "invite_user"):
        return

    # 📊 Tracking.
    await tracker_commande(interaction, "invite_user")

    target = membre or interaction.user

    # 🚫 Refus des bots.
    if isinstance(target, discord.Member) and target.bot:
        await interaction.followup.send(
            view=error_container("Les **bots** n'ont pas de compteurs d'invitations."),
        )
        return

    # 🧩 Récup stats + link, puis affichage.
    try:
        stats = await get_user_stats(interaction.guild.id, target.id)
        link = await get_link(interaction.guild.id, target.id)
        view = build_user_stats_view(target, stats, link, interaction.guild)
        await interaction.followup.send(view=view)

    except Exception:
        log.exception("[INVITE USER] Affichage de l'interface échoué (guild=%s, target=%s)", interaction.guild.id, target.id)
        await interaction.followup.send(view=error_container("Impossible d'afficher les **invitations** d'un membre."))


# ============================================================
# ❌ Gestion des erreurs
# ============================================================

@invite_user.error
async def invite_user_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    await handle_app_command_error(interaction, error)