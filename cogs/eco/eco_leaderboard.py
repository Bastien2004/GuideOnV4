"""
cogs/eco/eco_leaderboard.py — Affiche le classement des soldes.
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
from utils.managers.eco_manager import get_leaderboard, load_eco_config
from views.eco.leaderboard_view import EcoLeaderboardView

log = logging.getLogger(__name__)

LEADERBOARD_MAX = 100


# ============================================================
# 🏆 Commande : /eco leaderboard
# ============================================================

@app_commands.guild_only()
@app_commands.checks.cooldown(1, 10)
@app_commands.command(name="leaderboard", description="🏆 Affiche le classement des soldes du serveur")
async def eco_leaderboard(interaction: discord.Interaction) -> None:

    # 🛡️ Vérification ban utilisateur.
    if not await verifier_ban_utilisateur(interaction):
        return

    # 🕒 Defer.
    try:
        await interaction.response.defer(ephemeral=True)
    except (discord.NotFound, discord.HTTPException):
        return

    # ⚙️ Vérification maintenance.
    if not await verifier_commande(interaction, "eco_leaderboard"):
        return

    # 📊 Tracking.
    await tracker_commande(interaction, "eco_leaderboard")

    try:
        # 🔒 Désactivable par serveur depuis /eco config.
        config = await load_eco_config(interaction.guild.id)
        if not config.get("leaderboard_enabled", True):
            await interaction.followup.send(
                view=info_container("Le **classement** de l'économie est __désactivé__ sur ce serveur.")
            )
            return

        # 🧩 Récupère le classement des soldes.
        entries = await get_leaderboard(interaction.guild.id, limit=LEADERBOARD_MAX, offset=0)
        entries = [(uid, data) for uid, data in entries if data["balance"] > 0]

        if not entries:
            await interaction.followup.send(view=info_container("**Aucun membre** n'a encore de __solde__ sur ce serveur."))
            return

        view = EcoLeaderboardView(entries, guild=interaction.guild, owner_id=interaction.user.id, per_page=10)
        await interaction.followup.send(view=view)

    except Exception:
        log.exception("[ECO LEADERBOARD] Affichage du classement échoué (guild=%s)", interaction.guild.id)
        await interaction.followup.send(view=error_container("Impossible d'afficher le **classement** économie."))


# ============================================================
# ❌ Gestion des erreurs
# ============================================================

@eco_leaderboard.error
async def eco_leaderboard_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    await handle_app_command_error(interaction, error)
