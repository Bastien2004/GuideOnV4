"""
cogs/qr/scan.py — /qr scan : décode un QR code envoyé en pièce jointe.
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
from utils.qr_scanner import decode_qr_image
from utils.managers.qr_manager import find_qr_by_content

from views.qr.scan_view import build_qr_scan_view

log = logging.getLogger(__name__)

IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp")


# ============================================================
# 🔍 /qr scan
# ============================================================

@app_commands.command(name="scan", description="🔍 Décode le contenu d'un QR code envoyé en image")
@app_commands.describe(image="L'image contenant le QR code à scanner")
async def qr_scan(interaction: discord.Interaction, image: discord.Attachment) -> None:

    # 🛡️ Vérification ban utilisateur.
    if not await verifier_ban_utilisateur(interaction):
        return

    # 🕒 Defer.
    try:
        await interaction.response.defer(ephemeral=True)
    except (discord.NotFound, discord.HTTPException):
        return

    # ⚙️ Vérification maintenance.
    if not await verifier_commande(interaction, "qr_scan"):
        return

    # 📏 Validation basique du fichier envoyé.
    if not image.filename.lower().endswith(IMAGE_EXTENSIONS):
        await interaction.followup.send(
            view=error_container("Le fichier doit être une **image** (png, jpg, jpeg, webp)."),
            ephemeral=True,
        )
        return

    # 📊 Tracking.
    await tracker_commande(interaction, "qr_scan")

    # 🧩 Décodage.
    try:
        image_bytes = await image.read()
        contenu = decode_qr_image(image_bytes)

    except Exception:
        log.exception("[QRC SCAN] Décodage QR échoué (user=%s)", interaction.user.id)
        await interaction.followup.send(view=error_container("Impossible de lire cette **image**."), ephemeral=True)
        return

    if contenu is None:
        await interaction.followup.send(view=error_container("Aucun **QR code** détecté sur cette image."), ephemeral=True)
        return

    # 🔎 Recherche de l'origine.
    origine = None
    try:
        origine = await find_qr_by_content(contenu)

    except Exception:
        log.exception("[QRC SCAN] Recherche du lien QRCode échouée")

    # 💻 Envoie de la view.
    view = build_qr_scan_view(contenu, origine)
    await interaction.followup.send(view=view, ephemeral=True)


# ============================================================
# ❌ Gestion des erreurs
# ============================================================

@qr_scan.error
async def qr_scan_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    await handle_app_command_error(interaction, error)