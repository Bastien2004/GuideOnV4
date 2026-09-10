"""
cogs/mod/mod_piege.py — Configure le système HoneyPot / "Piège" anti-raid.

Verrouillée sur permission Discord `administrator` (comme /mod config) :
ce n'est pas une sanction ponctuelle mais la configuration d'un système qui
sanctionne automatiquement — mal réglé (mauvais salon, exemptions trop
larges/étroites), l'impact est bien plus large qu'une commande /mod
classique. Cette clé n'est donc PAS délégable via /mod permissions, comme
/mod config.
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

from views.mod.piege_config_view import PiegeConfigView

log = logging.getLogger(__name__)


# ============================================================
# 🧭 Commande : /mod piege
# ============================================================

@app_commands.guild_only()
@app_commands.checks.cooldown(1, 10)
@app_commands.command(name="piege", description="🍯 Configure le salon-piège anti-raid (HoneyPot)")
async def mod_piege(interaction: discord.Interaction) -> None:

    # 🛡️ Vérification ban utilisateur.
    if not await verifier_ban_utilisateur(interaction):
        return

    # 🔐 Verrouillage strict Admin Discord (non-délégable via /mod permissions).
    if not await check_admin(interaction, "configurer le **Piège** (HoneyPot)"):
        return

    # 🕒 Defer.
    try:
        await interaction.response.defer(ephemeral=True)
    except (discord.NotFound, discord.HTTPException):
        return

    # ⚙️ Vérification maintenance.
    if not await verifier_commande(interaction, "mod_piege"):
        return

    # 📊 Tracking.
    await tracker_commande(interaction, "mod_piege")

    # 💻 Envoi de l'interface.
    try:
        view = await PiegeConfigView.create(guild=interaction.guild, moderator_id=interaction.user.id)
        await interaction.followup.send(view=view, ephemeral=True)
    except Exception:
        log.exception("[MOD PIEGE] Ouverture de l'interface échouée guild=%s", interaction.guild.id)
        await interaction.followup.send(
            view=error_container("Impossible d'ouvrir la configuration du **Piège**."), ephemeral=True)


# ============================================================
# ❌ Gestion des erreurs
# ============================================================

@mod_piege.error
async def mod_piege_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    await handle_app_command_error(interaction, error)
