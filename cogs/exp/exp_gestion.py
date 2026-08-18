"""
cogs/exp/exp_gestion.py — Gère la somme d'exp d'un membre.
"""

from __future__ import annotations

import logging

import discord
from discord import app_commands

from utils.botbancmd import verifier_ban_utilisateur
from utils.control_admin import verifier_commande
from utils.track_commande import tracker_commande

from utils.error_handler import handle_app_command_error
from utils.perm_admin import check_admin
from utils.container_universel import error_container

from views.exp.gestion_view import ExpGestionView

log = logging.getLogger(__name__)


# ============================================================
# 🛠️ Commande : /exp gestion <membre>
# ============================================================

@app_commands.guild_only()
@app_commands.checks.cooldown(1, 10)
@app_commands.command(name="gestion", description="🛠️ Ajuste manuellement l'EXP d'un membre")
@app_commands.describe(membre="Le membre dont tu veux gérer l'EXP")
async def exp_gestion(interaction: discord.Interaction, membre: discord.Member) -> None:

    # 🛡️ Vérification ban utilisateur.
    if not await verifier_ban_utilisateur(interaction):
        return

    # 🔐 Vérification Administrateur.
    if not await check_admin(interaction, "**gérer** l'EXP d'un membre"):
        return

    # 🕒 Defer.
    try:
        await interaction.response.defer(ephemeral=True)
    except (discord.NotFound, discord.HTTPException):
        return

    # ⚙️ Vérification maintenance.
    if not await verifier_commande(interaction, "exp_gestion"):
        return

    # 📊 Tracking.
    await tracker_commande(interaction, "exp_gestion")

    # 🚫 Refus des bots.
    if membre.bot:
        await interaction.followup.send(
            view=error_container("Les **bots** n'ont pas d'EXP."),
            ephemeral=True,
        )
        return

    # 🧩 Création et envoi de l'interface.
    try:
        view = await ExpGestionView.create(
            guild_id=interaction.guild.id,
            target_id=membre.id,
            author_id=interaction.user.id,
            bot=interaction.client,
        )
        await interaction.followup.send(view=view, ephemeral=True)

    except Exception:
        log.exception("[EXP GESTION] Ouverture de l'interface échouée (guild=%s, target=%s)", interaction.guild.id, membre.id)
        await interaction.followup.send(view=error_container("Impossible d'ouvrir l'interface de **gestion**."), ephemeral=True)


# ============================================================
# ❌ Gestion des erreurs
# ============================================================

@exp_gestion.error
async def exp_gestion_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    await handle_app_command_error(interaction, error)