"""
cogs/mod/mod_config.py — Dashboard de l'auto-modération du serveur.

Verrouillée sur permission Discord `administrator` (comme /mod permissions).
Cette clé n'est PAS délégable via /mod permissions : elle contrôle des règles
qui, mal configurées, peuvent bloquer des membres légitimes ou laisser passer
du contenu nuisible.
"""
from __future__ import annotations

import logging

import discord
from discord import app_commands

from utils.botbancmd import verifier_ban_utilisateur
from utils.container_universel import error_container
from utils.control_admin import verifier_commande
from utils.error_handler import handle_app_command_error
from utils.perm_admin import check_admin
from utils.track_commande import tracker_commande

from views.mod.automod_dashboard_view import AutomodDashboardView

log = logging.getLogger(__name__)


# ============================================================
# 🧭 Commande : /mod config
# ============================================================

@app_commands.guild_only()
@app_commands.checks.cooldown(1, 10)
@app_commands.command(name="config", description="🛡️ Configure l'auto-modération du serveur")
async def mod_config(interaction: discord.Interaction) -> None:

    # 🛡️ Vérification ban utilisateur.
    if not await verifier_ban_utilisateur(interaction):
        return

    # 🔐 Verrouillage strict Admin Discord (non-délégable via /mod permissions).
    if not await check_admin(interaction, "configurer l'**auto-modération** du serveur"):
        return

    # 🕒 Defer.
    try:
        await interaction.response.defer(ephemeral=True)
    except (discord.NotFound, discord.HTTPException):
        return

    # ⚙️ Vérification maintenance.
    if not await verifier_commande(interaction, "mod_config"):
        return

    # 📊 Tracking.
    await tracker_commande(interaction, "mod_config")

    # 💻 Envoi du dashboard.
    try:
        view = await AutomodDashboardView.build(
            guild=interaction.guild, owner_id=interaction.user.id,
        )
        await interaction.followup.send(view=view, ephemeral=True)
    except Exception:
        log.exception("[MOD CONFIG] Ouverture dashboard échouée guild=%s", interaction.guild.id)
        await interaction.followup.send(
            view=error_container("Impossible d'ouvrir le **dashboard d'auto-modération**."),
            ephemeral=True,
        )


# ============================================================
# ❌ Gestion des erreurs
# ============================================================

@mod_config.error
async def mod_config_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    await handle_app_command_error(interaction, error)