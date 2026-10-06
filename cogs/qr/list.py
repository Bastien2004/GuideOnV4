"""
cogs/qr/list.py — /qr list : liste tes QR codes générés (tous serveurs confondus).
"""

from __future__ import annotations

import logging

import discord
from discord import app_commands

from utils.botbancmd import verifier_ban_utilisateur
from utils.track_commande import tracker_commande
from utils.control_admin import verifier_commande

from utils.error_handler import handle_app_command_error
from utils.container_universel import error_container
from utils.managers.qr_manager import list_qr_by_user

from views.qr.list_view import QRListView

log = logging.getLogger(__name__)


# ============================================================
# 📋 /qr list
# ============================================================

@app_commands.guild_only()
@app_commands.checks.cooldown(1, 10)
@app_commands.command(name="list", description="📋 Liste tes QR codes générés")
async def qr_list(interaction: discord.Interaction) -> None:
    """2026-10-06 (Paul) : commande strictement personnelle — plus de
    paramètre "membre" (on ne consulte plus que SON PROPRE historique, plus
    besoin de gérer une permission pour consulter celui d'un autre membre).
    Historique global, tous serveurs confondus (voir qr_manager.py)."""

    # 🛡️ Vérification ban utilisateur.
    if not await verifier_ban_utilisateur(interaction):
        return

    # 🕒 Defer.
    try:
        await interaction.response.defer(ephemeral=True)
    except (discord.NotFound, discord.HTTPException):
        return

    # ⚙️ Vérification maintenance.
    if not await verifier_commande(interaction, "qr_list"):
        return

    # 📊 Tracking.
    await tracker_commande(interaction, "qr_list")

    # 📖 Lecture de l'historique (global, tous serveurs confondus).
    try:
        historique = await list_qr_by_user(interaction.user.id)
    except Exception:
        log.exception("[QRC LIST] Récupération de la liste des QRCode échouée (user=%s)", interaction.user.id)
        await interaction.followup.send(view=error_container("Impossible de récupérer la **liste**."), ephemeral=True)
        return

    # 💻 Envoie de la view.
    view = QRListView(historique, owner_id=interaction.user.id)
    await interaction.followup.send(view=view, ephemeral=True)


# ============================================================
# ❌ Gestion des erreurs
# ============================================================

@qr_list.error
async def qr_list_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    await handle_app_command_error(interaction, error)
