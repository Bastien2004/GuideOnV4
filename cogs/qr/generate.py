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
from utils.boutique.vip_manager import is_vip

from utils.error_handler import handle_app_command_error
from utils.container_universel import error_container
from utils.managers.qr_manager import count_qr_by_user, save_qr

from views.qr._shared import MAX_QR_USER_DEFAULT, MAX_QR_USER_VIP
from views.qr.generate_view import build_qr_generate_view

log = logging.getLogger(__name__)


# ============================================================
# 🔳 /qr generate
# ============================================================

@app_commands.guild_only()
@app_commands.checks.cooldown(1, 10)
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
    if not await verifier_commande(interaction, "qr_generate"):
        return

    # 📏 Validation basique du lien saisi.
    if not lien.strip():
        await interaction.followup.send(view=error_container("Le **lien** ne peut pas être vide."), ephemeral=True)
        return

    if len(lien) > 2000:
        await interaction.followup.send(view=error_container("Le **lien** est trop long (2000 caractères max)."), ephemeral=True)
        return

    # 🔒 Limite de génération (historique global, tous serveurs confondus —
    # voir utils/managers/qr_manager.py). 3 par défaut, 10 pour les VIP.
    max_qr = MAX_QR_USER_VIP if is_vip(interaction.user.id) else MAX_QR_USER_DEFAULT
    try:
        nb_actuel = await count_qr_by_user(interaction.user.id)
    except Exception:
        log.exception("[QRC GENERATE] Comptage de l'historique échoué (user=%s)", interaction.user.id)
        nb_actuel = 0

    if nb_actuel >= max_qr:
        hint = (
            "" if max_qr == MAX_QR_USER_VIP else
            "\n-# 💎 Passe **VIP** pour débloquer jusqu'à 10 QR codes."
        )
        await interaction.followup.send(
            view=error_container(
                f"Tu as déjà **{nb_actuel}** QR code(s) dans ton historique.\n"
                f"-# Limite : {max_qr} QR code(s) — supprime une ancienne entrée via `/qr list`."
                f"{hint}"
            ),
            ephemeral=True,
        )
        return

    # 📊 Tracking.
    await tracker_commande(interaction, "qr_generate")

    # 🧩 Génération et envoi.
    try:
        view, file = build_qr_generate_view(lien, owner_id=interaction.user.id)
        await interaction.followup.send(view=view, files=[file], ephemeral=True)

    except Exception:
        log.exception("[QRC GENERATE] Génération du QRCode échouée (user=%s)", interaction.user.id)
        await interaction.followup.send(view=error_container("Impossible de générer le **QR code**."), ephemeral=True)
        return

    # 💾 Sauvegarde en base (guild_id conservé pour /qr scan — voir qr_manager.py).
    try:
        await save_qr(interaction.user.id, interaction.guild.id, lien)
    except Exception:
        log.exception("[QRC GENERATE] Sauvegarde du QRCode échouée (user=%s)", interaction.user.id)


# ============================================================
# ❌ Gestion des erreurs
# ============================================================

@qr_generate.error
async def qr_generate_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    await handle_app_command_error(interaction, error)
