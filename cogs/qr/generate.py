"""
cogs/qr/generate.py — /qr generate : crée un QR code à partir d'un lien.
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
from utils.managers.qr_manager import save_qr

from views.qr.generate_view import build_qr_generate_view

log = logging.getLogger(__name__)


# ============================================================
# 🔳 /qr generate
# ============================================================

@app_commands.command(name="generate", description="🔳 Crée un QR code à partir d'un lien")
@app_commands.describe(lien="Le lien (ou texte) à encoder en QR code")
async def qr_generate(interaction: discord.Interaction, lien: str) -> None:

    # 🛡️ Vérification ban utilisateur.
    if not await verifier_ban_utilisateur(interaction):
        return

    # 🕒 Defer.
    try:
        await interaction.response.defer(ephemeral=True)
    except (discord.NotFound, discord.HTTPException):
        return

    # ⚙️ Vérification maintenance.
    if not await verifier_commande(interaction, "qr_generate_cmd"):
        return

    # 📏 Validation basique du lien saisi.
    if not lien.strip():
        await interaction.followup.send(
            view=error_container("Le **lien** ne peut pas être vide."),
            ephemeral=True,
        )
        return

    if len(lien) > 2000:
        await interaction.followup.send(
            view=error_container("Le **lien** est trop long (2000 caractères max)."),
            ephemeral=True,
        )
        return

    # 📊 Tracking.
    await tracker_commande(interaction, "qr_generate_cmd")

    # 🧩 Génération et envoi.
    try:
        view, file = build_qr_generate_view(lien)
        await interaction.followup.send(view=view, files=[file], ephemeral=True)
    except Exception:
        log.exception("Ouverture /qr generate échouée (user=%s)", interaction.user.id)
        await interaction.followup.send(
            view=error_container("Impossible de générer le **QR code**."),
            ephemeral=True,
        )
        return

    # 💾 Sauvegarde en base (best-effort : ne bloque pas l'envoi du QR si ça échoue).
    try:
        await save_qr(interaction.user.id, lien)
    except Exception:
        log.exception("Sauvegarde QR échouée (user=%s)", interaction.user.id)


# ============================================================
# ❌ Gestion des erreurs
# ============================================================

@qr_generate.error
async def qr_generate_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    await handle_app_command_error(interaction, error)