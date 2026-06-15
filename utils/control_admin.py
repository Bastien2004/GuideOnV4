"""
utils/control_admin.py — Gestion du système de maintenance des commandes.

Câblé à la DB via utils.managers.command_toggle_manager (CommandControl).
Système GLOBAL : une commande désactivée le reste sur tous les guilds.
"""
from __future__ import annotations

import logging
import os

import discord
from discord import MediaGalleryItem
from discord.ui import Container, LayoutView, MediaGallery, Separator, TextDisplay

from utils.managers.command_toggle_manager import is_command_enabled

# ============================================================
# 📂 Constantes
# ============================================================

log = logging.getLogger(__name__)

IMAGE_FILENAME = "dead.webp"
IMAGE_PATH = os.path.join("source", IMAGE_FILENAME)


# ============================================================
# 🛡️ Vérification commande activée
# ============================================================

async def verifier_commande(interaction: discord.Interaction, nom_commande: str) -> bool:
    """
    Vérifie si la commande est activée (système global, cache 60s).

    Si désactivée : envoie le message de maintenance (éphémère) et
    retourne False — l'appelant doit alors stopper l'exécution.
    Si activée (ou absente de la table) : retourne True.
    """
    if await is_command_enabled(nom_commande):
        return True

    await send_maintenance_message(interaction)
    log.debug("Commande désactivée (maintenance) : %s | user=%s", nom_commande, interaction.user.id)
    return False


# ============================================================
# 🖼️ Récupération image maintenance
# ============================================================

def get_maintenance_file() -> discord.File | None:
    """Récupère le fichier image de maintenance."""
    if not os.path.exists(IMAGE_PATH):
        return None
    return discord.File(IMAGE_PATH, filename=IMAGE_FILENAME)


# ============================================================
# 🧱 View maintenance
# ============================================================

def build_maintenance_view(with_image: bool = True) -> LayoutView:
    view = LayoutView(timeout=None)
    container = Container()

    container.add_item(TextDisplay("# 🚧 Commande en maintenance"))
    container.add_item(Separator())
    container.add_item(
        TextDisplay(
            "Cette commande est actuellement **désactivée**.\n"
            "<:information:1495446355395612794> Pour plus d'informations, contactez l'équipe **développeur**."
        )
    )

    if with_image:
        container.add_item(
            MediaGallery(MediaGalleryItem(f"attachment://{IMAGE_FILENAME}"))
        )

    container.add_item(Separator())
    container.add_item(TextDisplay("-# GuideOn Studio"))

    view.add_item(container)
    return view


# ============================================================
# 📤 Envoi sécurisé
# ============================================================

async def send_maintenance_message(interaction: discord.Interaction) -> None:
    file = get_maintenance_file()
    view = build_maintenance_view(with_image=file is not None)

    kwargs: dict = {"view": view, "ephemeral": True}
    if file:
        kwargs["file"] = file

    try:
        if interaction.response.is_done():
            await interaction.followup.send(**kwargs)
        else:
            await interaction.response.send_message(**kwargs)
    except discord.HTTPException:
        log.exception("Impossible d'envoyer le message de maintenance")