"""
Container de fiabilité des données NationsGlory.
"""

from __future__ import annotations

import os

import discord

from discord import MediaGalleryItem
from discord.ui import Container, TextDisplay, Separator, MediaGallery


# ============================================================
# 📦 Constantes
# ============================================================

DEAD_IMAGE_PATH = os.path.join("source", "dead.webp")


# ============================================================
# ⚠️ Container fiabilité NG
# ============================================================

def build_ng_fiable_container() -> tuple[Container, discord.File | None]:
    """Construit le container de fiabilité NG."""

    container = Container()
    container.add_item(TextDisplay("# ⚠️ Fiabilité des données"))

    container.add_item(Separator())

    container.add_item(
        TextDisplay(
            "Les données affichées proviennent de l’**API officielle** "
            "de __NationsGlory__.\n"
            "Elles peuvent être que **partiellement** mises à jour "
            "ou **légèrement différentes** qu'en __jeu__."
        )
    )

    file = None

    if os.path.exists(DEAD_IMAGE_PATH):

        file = discord.File(DEAD_IMAGE_PATH, filename="dead.webp",)
        container.add_item(Separator())

        container.add_item(
            MediaGallery(
                MediaGalleryItem(
                    "attachment://dead.webp"
                )
            )
        )

    container.add_item(Separator())
    container.add_item(TextDisplay("GuideOn Studio"))

    return container, file