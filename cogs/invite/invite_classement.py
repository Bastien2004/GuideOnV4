"""
cogs/invite/invite_classement.py — Affiche le classement d'invitations.
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
from utils.managers.invite_manager import get_leaderboard
from views.invite.leaderboard_view import InviteLeaderboardView

log = logging.getLogger(__name__)

LEADERBOARD_MAX = 100


# ============================================================
# 🏆 Commande : /invite classement
# ============================================================

@app_commands.guild_only()
@app_commands.checks.cooldown(1, 10)
@app_commands.command(name="classement", description="🏆 Affiche le classement des invitations du serveur",)
async def invite_classement(interaction: discord.Interaction) -> None:

    # 🛡️ Vérification ban utilisateur.
    if not await verifier_ban_utilisateur(interaction):
        return

    # 🕒 Defer.
    try:
        await interaction.response.defer(ephemeral=True)
    except (discord.NotFound, discord.HTTPException):
        return

    # ⚙️ Vérification maintenance.
    if not await verifier_commande(interaction, "invite_classement"):
        return

    # 📊 Tracking.
    await tracker_commande(interaction, "invite_classement")

    # 🧩 Récupère le classement d'invitations.
    try:
        entries = await get_leaderboard(interaction.guild.id, limit=LEADERBOARD_MAX, offset=0)
        entries = [(uid, s) for uid, s in entries if s["total"] > 0]

        if not entries:
            await interaction.followup.send(view=info_container("**Aucun membre** n'a encore d'__invitations__ sur ce serveur."))
            return

        view = InviteLeaderboardView(entries, guild=interaction.guild, owner_id=interaction.user.id, per_page=10)
        await interaction.followup.send(view=view)

    except Exception:
        log.exception("[INVITE CLASSEMENT] Affichage du classement échoué (guild=%s)", interaction.guild.id)
        await interaction.followup.send(
            view=error_container("Impossible d'afficher le **classement** d'invitations."))


# ============================================================
# ❌ Gestion des erreurs
# ============================================================

@invite_classement.error
async def invite_classement_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    await handle_app_command_error(interaction, error)