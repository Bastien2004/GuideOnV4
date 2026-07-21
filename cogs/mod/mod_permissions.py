"""
cogs/mod/mod_permissions.py — Commande /mod permissions.

Panneau admin-only (deny-by-default, cf. utils.perm_mod) qui assigne les
rôles autorisés à utiliser chaque commande/panneau du système /mod.
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

from views.mod.permissions_view import ModPermissionsView

log = logging.getLogger(__name__)


# ============================================================
# 🔐 Commande : /mod permissions
# ============================================================

@app_commands.guild_only()
@app_commands.checks.cooldown(1, 10)
@app_commands.command(name="permissions", description="🔐 Assigne les rôles autorisés à utiliser les commandes /mod")
async def mod_permissions(interaction: discord.Interaction) -> None:

    # 🛡️ Vérification ban utilisateur.
    if not await verifier_ban_utilisateur(interaction):
        return

    # 🔐 Vérification Administrateur (ce panneau contrôle TOUTES les autres
    # permissions /mod, il reste donc réservé aux administrateurs — pas
    # configurable via lui-même, pour éviter tout verrouillage accidentel).
    if not await check_admin(interaction, "configurer les **permissions** du système de modération"):
        return

    # 🕒 Defer.
    try:
        await interaction.response.defer(ephemeral=True)
    except (discord.NotFound, discord.HTTPException):
        return

    # ⚙️ Vérification maintenance.
    if not await verifier_commande(interaction, "mod_permissions"):
        return

    # 📊 Tracking.
    await tracker_commande(interaction, "mod_permissions")

    # 🧩 Création et envoi de l'interface.
    try:
        view = await ModPermissionsView.create(
            guild_id=interaction.guild.id,
            author_id=interaction.user.id,
            bot=interaction.client,
        )
        await interaction.followup.send(view=view, ephemeral=True)

    except Exception:
        log.exception("[MOD_PERM] Ouverture /mod permissions échouée (guild=%s)", interaction.guild.id)
        await interaction.followup.send(
            view=error_container("Impossible d'ouvrir le **dashboard** de permissions."),
            ephemeral=True,
        )


# ============================================================
# ❌ Gestion des erreurs
# ============================================================

@mod_permissions.error
async def mod_permissions_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    await handle_app_command_error(interaction, error)
