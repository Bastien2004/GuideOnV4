"""
utils/control_admin.py — Gestion du système de maintenance.py des commandes.

🟡 En attente Lewyvernien :
- verifier_commande() retourne toujours True (= aucune commande désactivée)
- La logique sera complétée avec la table command_toggles en DB

À FAIRE Lewyvernien (DB) :
    Implémenter une fonction async qui retourne True/False selon l'état de la commande dans la table `command_toggles`.

Signature attendue côté DB :
    async def is_command_enabled(guild_id: int | None, command_name: str) -> bool
"""
from __future__ import annotations

import logging
import os

import discord
from discord import MediaGalleryItem
from discord.ui import Container, LayoutView, MediaGallery, Separator, TextDisplay

# ============================================================
# 📂 Constantes
# ============================================================

log = logging.getLogger(__name__)

IMAGE_PATH = os.path.join("source", "dead.png")


# ============================================================
# 🛡️ Vérification commande activée
# ============================================================

async def verifier_commande(interaction: discord.Interaction, nom_commande: str,) -> bool:
    """
    Vérifie si la commande est activée pour ce serveur.

    🟡 STUB : retourne True (= commande toujours activée).
    À câbler à la DB par le collègue.
    """
    # TODO (collègue DB) : remplacer par
    #   from utils.managers.command_toggle_manager import is_command_enabled
    #   guild_id = interaction.guild.id if interaction.guild else None
    #   if not await is_command_enabled(guild_id, nom_commande):
    #       await send_maintenance_message(interaction)
    #       return False
    log.debug("verifier_commande stub appelé pour : %s", nom_commande)
    return True


# ============================================================
# 🖼️ Récupération image maintenance.py
# ============================================================

def get_maintenance_file() -> discord.File | None:
    """Récupère le fichier image de maintenance.py."""
    if not os.path.exists(IMAGE_PATH):
        return None
    return discord.File(IMAGE_PATH, filename="dead.png")


# ============================================================
# 🧱 View maintenance.py
# ============================================================

def build_maintenance_view(with_image: bool = True) -> LayoutView:
    view = LayoutView(timeout=None)
    container = Container()

    container.add_item(TextDisplay("# 🚧 Commande en maintenance.py"))
    container.add_item(Separator())
    container.add_item(
        TextDisplay(
            "Cette commande est actuellement **désactivée**.\n"
            "<:information:1495446355395612794> Pour plus d'informations, contactez l'équipe **développeur**."
        )
    )

    if with_image:
        container.add_item(
            MediaGallery(MediaGalleryItem("attachment://dead.png"))
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

    kwargs = {"view": view, "ephemeral": True}
    if file:
        kwargs["file"] = file

    try:
        if interaction.response.is_done():
            await interaction.followup.send(**kwargs)
        else:
            await interaction.response.send_message(**kwargs)
    except discord.HTTPException:
        log.exception("Impossible d'envoyer le message de maintenance.py")