"""
cogs/config/role_react.py — Commande /config role_reaction.
"""

from __future__ import annotations

import logging

import discord
from discord import app_commands

from utils.botbancmd import verifier_ban_utilisateur
from utils.track_commande import tracker_commande
from utils.control_admin import verifier_commande

from utils.perm_admin import check_admin
from utils.container_universel import error_container
from utils.error_handler import handle_app_command_error

from views.reaction_role.config_view import create_reaction_role_view

log = logging.getLogger(__name__)


# ============================================================
# 🎭 Commande : /config role_reaction
# ============================================================

@app_commands.guild_only()
@app_commands.checks.cooldown(1, 10)
@app_commands.command(name="role_reaction", description="🎭 Configure le système de rôles réaction")
async def role_reaction(interaction: discord.Interaction) -> None:

    # 🛡️ Vérification ban utilisateur.
    if not await verifier_ban_utilisateur(interaction):
        return

    # 🔐 Vérification Administrateur.
    if not await check_admin(interaction, "configurer les **rôles réaction**"):
        return

    # 🕒 Defer.
    try:
        await interaction.response.defer(ephemeral=True)
    except (discord.NotFound, discord.HTTPException):
        return

    # ⚙️ Vérification maintenance.
    if not await verifier_commande(interaction, "config_role_reaction"):
        return

    # 📊 Tracking.
    await tracker_commande(interaction, "config_role_reaction")

    # 🧩 Création et envoi de l'interface.
    try:
        view = await create_reaction_role_view(
            guild_id=interaction.guild.id,
            bot=interaction.client,
            page="main",
            author_id=interaction.user.id,
        )
        if view is None:
            return await interaction.followup.send(
                view=error_container(
                    "**Impossible** d'ouvrir la __configuration__.\n"
                    "-# Vérifiez que j'ai la permission **Gérer les rôles**."
                ),
                ephemeral=True,
            )
        await interaction.followup.send(view=view, ephemeral=True)
    except Exception:
        log.exception("Ouverture config role_reaction **échouée** (guild=%s)", interaction.guild.id)
        await interaction.followup.send(
            view=error_container("Une **erreur** est survenue lors de l'__ouverture de l'interface__."),
            ephemeral=True,
        )


# ============================================================
# ❌ Gestion des erreurs
# ============================================================

@role_reaction.error
async def role_reaction_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    await handle_app_command_error(interaction, error)