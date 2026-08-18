"""
cogs/qr/list.py — /qr list : liste les QR codes générés par un utilisateur.
"""

from __future__ import annotations

import logging
from typing import Optional

import discord
from discord import app_commands

from utils.botbancmd import verifier_ban_utilisateur
from utils.track_commande import tracker_commande
from utils.control_admin import verifier_commande

from utils.error_handler import handle_app_command_error
from utils.container_universel import error_container
from utils.managers.qr_manager import list_qr_by_user

from views.qr.list_view import build_qr_list_view

log = logging.getLogger(__name__)


# ============================================================
# 📋 /qr list
# ============================================================

@app_commands.command(name="list", description="📋 Liste les QR codes générés par un utilisateur")
@app_commands.describe(utilisateur="L'utilisateur concerné (toi par défaut)")
async def qr_list(interaction: discord.Interaction, utilisateur: Optional[discord.User] = None) -> None:

    # 🛡️ Vérification ban utilisateur.
    if not await verifier_ban_utilisateur(interaction):
        return

    # 🕒 Defer.
    try:
        await interaction.response.defer(ephemeral=True)
    except (discord.NotFound, discord.HTTPException):
        return

    # ⚙️ Vérification maintenance.
    if not await verifier_commande(interaction, "qr_list_cmd"):
        return

    # 📊 Tracking.
    await tracker_commande(interaction, "qr_list_cmd")

    cible = utilisateur or interaction.user

    # 📖 Lecture de l'historique.
    try:
        historique = await list_qr_by_user(cible.id)
    except Exception:
        log.exception("Lecture historique QR échouée (user=%s)", cible.id)
        await interaction.followup.send(
            view=error_container("Impossible de récupérer l'**historique**."),
            ephemeral=True,
        )
        return

    view = build_qr_list_view(cible, historique)
    await interaction.followup.send(view=view, ephemeral=True)


# ============================================================
# ❌ Gestion des erreurs
# ============================================================

@qr_list.error
async def qr_list_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    await handle_app_command_error(interaction, error)