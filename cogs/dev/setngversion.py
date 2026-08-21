"""
cogs/dev/setngversion.py — Modifie la version du /ng version.
"""

from __future__ import annotations

import logging

import discord
from discord import app_commands, Interaction

from utils.control_admin import verifier_commande
from utils.track_commande import tracker_commande

from utils.container_universel import error_container, success_container, warning_container
from utils.error_handler import handle_app_command_error
from utils.perm_check import has_grade_check
from utils.ngversion_manager import ecrire_version, lire_version

log = logging.getLogger(__name__)


# ============================================================
# 🧭 Commande : /dev setngversion
# ============================================================

@app_commands.guild_only()
@app_commands.checks.cooldown(1, 10)
@app_commands.command(name="setngversion", description="🔃 [DEV] Modifie la version actuelle de NationsGlory Bedrock")
@app_commands.describe(nouvelle_version="La nouvelle version à afficher (ex : 1.21.50)")
async def setngversion(interaction: Interaction, nouvelle_version: str) -> None:

    # 🔐 Vérification des permissions.
    if not await has_grade_check(interaction, "equipe_guideon.dev", "modifier la **version** NG Bedrock"):
        return

    # 🕒 Defer.
    try:
        await interaction.response.defer(ephemeral=True)
    except (discord.NotFound, discord.HTTPException):
        return

    # ⚙️ Activation commande.
    if not await verifier_commande(interaction, "dev_setngversion"):
        return

    # 📊 Tracking.
    await tracker_commande(interaction, "dev_setngversion")

    # 🧼 Validation légère.
    nouvelle_version = nouvelle_version.strip()
    if not nouvelle_version:
        await interaction.followup.send(
            view=warning_container("La version ne peut pas être vide."), ephemeral=True,
        )
        return

    # 🧩 Écriture + confirmation.
    try:
        ancienne_version = lire_version()
        ecrire_version(nouvelle_version)

    except Exception:
        log.exception("[DEV SET_NG_VERSION] Erreur modification version NG Bedrock")
        await interaction.followup.send(
            view=error_container("Une erreur est survenue lors de la modification de la version."),
            ephemeral=True,
        )
        return

    log.info("[DEV SET_NG_VERSION] Version NG Bedrock | modifiée par %s : %r -> %r", interaction.user.id, ancienne_version, nouvelle_version)

    await interaction.followup.send(
        view=success_container(f"Version NG Bedrock mise à jour : `{ancienne_version}` → `{nouvelle_version}`."),
        ephemeral=True,
    )


# ============================================================
# ❌ Gestion des erreurs
# ============================================================

@setngversion.error
async def setngversion_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    await handle_app_command_error(interaction, error)