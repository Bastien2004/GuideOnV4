"""
cogs/mod/mod_historique.py — Affiche l'historique des sanctions d'un membre.
"""

from __future__ import annotations

import logging

import discord
from discord import app_commands

from utils.botbancmd import verifier_ban_utilisateur
from utils.track_commande import tracker_commande
from utils.control_admin import verifier_commande

from utils.container_universel import error_container, info_container
from utils.error_handler import handle_app_command_error
from utils.perm_mod import check_mod_permission

from utils.managers.mod_sanction_manager import get_user_history, get_user_stats
from views.mod.historique_view import HistoriqueView

log = logging.getLogger(__name__)


# ============================================================
# 🧭 Commande : /mod historique <utilisateur>
# ============================================================

@app_commands.guild_only()
@app_commands.checks.cooldown(1, 10)
@app_commands.command(name="historique", description="📁 Affiche l'historique de sanction d'un membre")
@app_commands.describe(utilisateur="Le membre dont tu veux voir l'historique de sanctions")
async def mod_historique(interaction: discord.Interaction, utilisateur: discord.User) -> None:

    # 🛡️ Vérification ban utilisateur.
    if not await verifier_ban_utilisateur(interaction):
        return

    # 🔐 Vérification permission /mod.
    if not await check_mod_permission(interaction, "mod_historique"):
        return

    # 🕒 Defer.
    try:
        await interaction.response.defer(ephemeral=True)
    except (discord.NotFound, discord.HTTPException):
        return

    # ⚙️ Vérification maintenance.
    if not await verifier_commande(interaction, "mod_historique"):
        return

    # 📊 Tracking.
    await tracker_commande(interaction, "mod_historique")

    # 📁 Récupération des données.
    try:
        history = await get_user_history(interaction.guild.id, utilisateur.id)
        stats = await get_user_stats(interaction.guild.id, utilisateur.id)

        if not history:
            await interaction.followup.send(
                view=info_container(f"**{utilisateur.mention}** n'a aucune sanction enregistrée sur ce serveur."),
                ephemeral=True,
            )
            return

        view = HistoriqueView(history, target_display=utilisateur.mention, stats=stats, guild=interaction.guild, owner_id=interaction.user.id, per_page=8)
        await interaction.followup.send(view=view, ephemeral=True)

    except Exception:
        log.exception("[MOD_HISTORIQUE] Erreur affichage de l'historique guild=%s target=%s", interaction.guild.id, utilisateur.id)
        
        await interaction.followup.send(
            view=error_container("Impossible d'afficher l'**historique des sanctions** de ce membre'."), ephemeral=True
        )


# ============================================================
# ❌ Gestion des erreurs
# ============================================================

@mod_historique.error
async def mod_historique_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    await handle_app_command_error(interaction, error)