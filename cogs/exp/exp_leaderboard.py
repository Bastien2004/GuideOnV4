"""
cogs/exp/exp_leaderboard.py — Commande /exp leaderboard.
"""
from __future__ import annotations

import logging

import discord
from discord import app_commands

from utils.botbancmd import verifier_ban_utilisateur
from utils.container_universel import error_container, info_container
from utils.control_admin import verifier_commande
from utils.error_handler import handle_app_command_error
from utils.managers.exp_manager import get_leaderboard
from utils.track_commande import tracker_commande

from views.exp.leaderboard_view import ExpLeaderboardView

log = logging.getLogger(__name__)

LEADERBOARD_MAX = 100


# ============================================================
# 🏆 Commande : /exp leaderboard
# ============================================================

@app_commands.guild_only()
@app_commands.checks.cooldown(1, 10)
@app_commands.command(name="leaderboard", description="🏆 Affiche le classement EXP du serveur")
async def exp_leaderboard(interaction: discord.Interaction) -> None:

    # 🛡️ Vérification ban utilisateur.
    if not await verifier_ban_utilisateur(interaction):
        return

    # 🕒 Defer.
    try:
        await interaction.response.defer()
    except (discord.NotFound, discord.HTTPException):
        return

    # ⚙️ Vérification maintenance.
    if not await verifier_commande(interaction, "exp_leaderboard"):
        return

    # 📊 Tracking.
    await tracker_commande(interaction, "exp_leaderboard")

    # 🧩 Récupère le classement d'EXP.
    try:
        entries = await get_leaderboard(interaction.guild.id, limit=LEADERBOARD_MAX, offset=0)
        entries = [(uid, exp) for uid, exp in entries if exp > 0]

        if not entries:
            await interaction.followup.send(
                view=info_container("**Aucun membre** n'a encore gagné d'__EXP__ sur ce serveur."),
            )
            return

        view = ExpLeaderboardView(entries, guild=interaction.guild, owner_id=interaction.user.id, per_page=10)
        await interaction.followup.send(view=view)

    except Exception:
        log.exception("[EXP] Affichage /exp leaderboard échoué (guild=%s)", interaction.guild.id)
        await interaction.followup.send(
            view=error_container("Impossible d'afficher le **classement**.")
        )


# ============================================================
# ❌ Gestion des erreurs
# ============================================================

@exp_leaderboard.error
async def exp_leaderboard_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    await handle_app_command_error(interaction, error)
