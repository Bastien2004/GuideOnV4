"""
Commande /ng onu — Affiche les horaires des ONUs NationsGlory.
"""
from __future__ import annotations

import logging
import os

import discord
from discord import app_commands, Interaction, MediaGalleryItem
from discord.ui import LayoutView, Container, TextDisplay, Separator, MediaGallery

from utils.botbancmd import verifier_ban_utilisateur
from utils.control_admin import verifier_commande
from utils.track_commande import tracker_commande

from utils.container_universel import error_container
from utils.error_handler import handle_app_command_error

from utils.ng_server_choice import SERVER_CHOICES


# ============================================================
# 📁 Constantes
# ============================================================

log = logging.getLogger(__name__)

VIEW_TIMEOUT = 1000
IMAGE_PATH   = os.path.join("source", "onu.png")

ONU_HORAIRES = {
    "alpha":   "Dimanche à 17h",
    "sigma":   "Samedi à 17h",
    "omega":   "Samedi à 17h30",
    "delta":   "Dimanche à 17h30",
    "epsilon": "Dimanche à 15h30",
    "blue":    "Samedi à 17h",
    "orange":  "Samedi à 16h30",
    "yellow":  "Dimanche à 16h30",
    "white":   "Dimanche à 17h",
    "black":   "Dimanche à 16h",
    "cyan":    "Dimanche à 17h30",
    "lime":    "Samedi à 17h30",
    "coral":   "Samedi à 16h",
    "red":     "Samedi à 18h",
    "mocha":   "Samedi à 15h30",
    "jade":    "Dimanche à 15h",
}


# ============================================================
# 📦 Fonctions utilitaires
# ============================================================

def build_onu_view(serveur: str, horaire: str) -> tuple[LayoutView, discord.File | None]:
    """Construit la view principale."""
    view = LayoutView(timeout=VIEW_TIMEOUT)

    main = Container()
    main.add_item(TextDisplay(f"# 🇺🇳 ONU — {serveur.capitalize()}"))
    main.add_item(Separator())
    main.add_item(TextDisplay(
        "## 🕒 Horaire de l'ONU\n\n"
        f"L'ONU du serveur **{serveur.capitalize()}** se déroule le :\n"
        f"**{horaire}**"
    ))
    main.add_item(Separator())
    main.add_item(TextDisplay("-# GuideOn Studio"))
    view.add_item(main)

    info = Container()
    info.add_item(TextDisplay("# <:information:1495446355395612794> Fonctionnement de l'ONU"))
    info.add_item(Separator())
    info.add_item(TextDisplay(
        "Chaque semaine, une session **ONU** est organisée par le staff.\n\n"
        "➡️ Annonces inter-serveurs\n"
        "➡️ Ranks & deranks\n"
        "➡️ Discussions antimatter / autonuke\n\n"
        "⚠️ Les horaires diffèrent selon les serveurs."
    ))

    file = None
    if os.path.exists(IMAGE_PATH):
        file = discord.File(IMAGE_PATH, filename="onu.png")
        info.add_item(Separator())
        info.add_item(MediaGallery(MediaGalleryItem(media="attachment://onu.png")))

    view.add_item(info)

    return view, file


# ============================================================
# 🧭 Commande principale
# ============================================================

@app_commands.guild_only()
@app_commands.checks.cooldown(1, 10)
@app_commands.command(name="onu", description="☕ Informations sur les ONUs NationsGlory")
@app_commands.choices(serveur=SERVER_CHOICES)
async def onu(interaction: Interaction, serveur: str):

    # 🛡️ Vérification ban
    if not await verifier_ban_utilisateur(interaction):
        return

    # 🕒 Defer
    try:
        await interaction.response.defer(ephemeral=True)
    except (discord.NotFound, discord.HTTPException):
        return

    # ⚙️ Vérification activation
    if not await verifier_commande(interaction, "ng_onu"):
        return

    # 📊 Tracking
    await tracker_commande(interaction, "ng_onu")

    # 🧩 Construction view
    horaire = ONU_HORAIRES.get(serveur)

    if horaire is None:
        await interaction.followup.send(view=error_container("Serveur inconnu."), ephemeral=True)
        return

    view, file = build_onu_view(serveur, horaire)
    await interaction.followup.send(view=view, file=file)


# ============================================================
# ❌ Gestion erreurs
# ============================================================

@onu.error
async def onu_error(interaction: Interaction, error: app_commands.AppCommandError):
    await handle_app_command_error(interaction, error)