"""
utils/botbancmd.py — Vérification du ban global du bot.
"""
from __future__ import annotations

import logging
import os

import discord
from discord import MediaGalleryItem
from discord.ui import Container, LayoutView, MediaGallery, Separator, TextDisplay

from utils.gestion_ban import est_banni, obtenir_info_ban

log = logging.getLogger(__name__)

IMAGE_PATH = os.path.join("source", "GuideOn_ban.webp")
IMAGE_FILENAME = "erreur_GuideON.webp"


def _build_ban_view(raison: str, ban_info: dict, attach_image: bool) -> LayoutView:
    """Construit le message Components V2 d'accès refusé (zéro embed)."""
    view = LayoutView(timeout=None)
    c = Container()

    c.add_item(TextDisplay("# <:sanctionner:1495444382587949086> Accès refusé"))
    c.add_item(Separator())
    c.add_item(TextDisplay("Tu es actuellement banni de l'utilisation de **GuideOn**."))
    c.add_item(Separator())

    c.add_item(TextDisplay(f"<:dialoguer:1495444451244511403> **Raison**\n{raison}"))

    date_ban = ban_info.get("date_ban")
    if date_ban:
        c.add_item(TextDisplay(
            f"<:info:1495443961144152094> **Date du ban**\n<t:{int(date_ban.timestamp())}:F>"
        ))

    expiration = ban_info.get("expiration")
    if expiration:
        c.add_item(TextDisplay(
            f"<:notifier:1495444487206604833> **Expiration**\n<t:{int(expiration.timestamp())}:R>"
        ))

    c.add_item(Separator())
    c.add_item(TextDisplay("-# Pour contester ce ban, contacte l'équipe de développement."))

    if attach_image:
        c.add_item(MediaGallery(MediaGalleryItem(f"attachment://{IMAGE_FILENAME}")))

    view.add_item(c)
    return view


async def verifier_ban_utilisateur(interaction: discord.Interaction) -> bool:
    """Retourne False si l'utilisateur est banni du bot."""

    user_id = interaction.user.id
    banni, raison = await est_banni(user_id)

    if not banni:
        return True

    ban_info = await obtenir_info_ban(user_id)

    if not ban_info:
        return True

    has_image = os.path.exists(IMAGE_PATH)
    view = _build_ban_view(raison, ban_info, attach_image=has_image)

    try:
        if has_image:
            file = discord.File(IMAGE_PATH, filename=IMAGE_FILENAME)
            await interaction.response.send_message(view=view, file=file, ephemeral=True)
        else:
            await interaction.response.send_message(view=view, ephemeral=True)
    except discord.HTTPException:
        log.warning("Impossible de notifier l'utilisateur banni user=%s", user_id, exc_info=True)

    return False