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

from views.qr.list_view import QRListView

log = logging.getLogger(__name__)


# ============================================================
# 📋 /qr list
# ============================================================

@app_commands.guild_only()
@app_commands.checks.cooldown(1, 10)
@app_commands.command(name="list", description="📋 Liste les QR codes générés par un utilisateur")
@app_commands.describe(membre="Le membre concerné (toi par défaut)")
async def qr_list(interaction: discord.Interaction, membre: Optional[discord.Member] = None) -> None:

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

    cible = membre or interaction.user

    # 🔐 Consulter l'historique d'un AUTRE membre est réservé à "Gérer le
    # serveur" — le contenu d'un QR est un texte/lien choisi par la personne,
    # potentiellement privé (contrairement à un simple compteur public comme
    # /invite user), donc pas ouvert par défaut à tout le monde.
    if cible.id != interaction.user.id:
        if not interaction.user.guild_permissions.manage_guild:
            await interaction.followup.send(
                view=error_container(
                    "Il faut la permission **Gérer le serveur** pour consulter "
                    "l'historique QR d'un **autre membre**."
                ),
                ephemeral=True,
            )
            return

    # 📊 Tracking.
    await tracker_commande(interaction, "qr_list")

    # 📖 Lecture de l'historique (scopée au serveur courant).
    try:
        historique = await list_qr_by_user(cible.id, interaction.guild.id)
    except Exception:
        log.exception("[QRC LIST] Récupération de la liste des QRCode échouée (user=%s)", cible.id)
        await interaction.followup.send(view=error_container("Impossible de récupérer la **liste**."), ephemeral=True)
        return

    # 💻 Envoie de la view.
    # Suppression activable seulement sur SON PROPRE historique (pas celui
    # consulté par un modérateur sur un autre membre).
    peut_supprimer = cible.id == interaction.user.id
    view = QRListView(
        historique,
        cible=cible,
        guild_id=interaction.guild.id,
        owner_id=interaction.user.id,
        peut_supprimer=peut_supprimer,
    )
    await interaction.followup.send(view=view, ephemeral=True)


# ============================================================
# ❌ Gestion des erreurs
# ============================================================

@qr_list.error
async def qr_list_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    await handle_app_command_error(interaction, error)
