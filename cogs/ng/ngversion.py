"""
Commande /ng version — Affiche la version actuelle de NationsGlory Bedrock.
"""
from __future__ import annotations

import logging

import discord
from discord import app_commands, Interaction
from discord.ui import LayoutView, Container, TextDisplay, Separator

from utils.ngversion_manager import lire_version
from utils.botbancmd import verifier_ban_utilisateur
from utils.control_admin import verifier_commande
from utils.track_commande import tracker_commande

from utils.container_universel import error_container
from utils.error_handler import handle_app_command_error


# ============================================================
# 📁 Constantes
# ============================================================

log = logging.getLogger(__name__)

VIEW_TIMEOUT = 600


# ============================================================
# 📦 Fonctions utilitaires
# ============================================================

def build_version_view(version: str) -> LayoutView:
    """Construit la view de la version NG Bedrock."""
    view = LayoutView(timeout=VIEW_TIMEOUT)

    container = Container()
    container.add_item(TextDisplay("# 📦 Version actuelle NG Bedrock"))
    container.add_item(Separator())
    container.add_item(TextDisplay(f"### 🔃 Version : `{version}`"))
    container.add_item(Separator())
    container.add_item(TextDisplay("-# GuideOn Studio"))

    view.add_item(container)
    return view


# ============================================================
# 🧭 Commande principale
# ============================================================

@app_commands.guild_only()
@app_commands.checks.cooldown(1, 10)
@app_commands.command(name="version", description="🔃 Afficher la version actuelle de NationsGlory Bedrock")
async def version(interaction: Interaction):

    # 🛡️ Vérification ban
    if not await verifier_ban_utilisateur(interaction):
        return

    # 🕒 Defer
    try:
        await interaction.response.defer(ephemeral=True)
    except (discord.NotFound, discord.HTTPException):
        return

    # ⚙️ Vérification activation
    if not await verifier_commande(interaction, "ng_version"):
        return

    # 📊 Tracking
    await tracker_commande(interaction, "ng_version")

    # 🧩 Construction view
    try:
        ver  = lire_version()
        view = build_version_view(ver)
        await interaction.followup.send(view=view)

    except Exception:
        log.exception("Erreur commande /ng version")
        await interaction.followup.send(
            view=error_container("Une erreur est survenue."),
            ephemeral=True,
        )


# ============================================================
# ❌ Gestion erreurs
# ============================================================

@version.error
async def version_error(interaction: Interaction, error: app_commands.AppCommandError):
    await handle_app_command_error(interaction, error)