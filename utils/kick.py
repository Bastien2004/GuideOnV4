"""
utils/kick.py — Logique métier pour /dev kick : fait quitter GuideOn d'un
serveur, extraite de cogs/dev/kick.py (même traitement que les autres
commandes /dev).
"""
from __future__ import annotations

import logging

import discord

log = logging.getLogger(__name__)


class KickError(Exception):
    """Erreur métier à afficher à l'utilisateur (pas une exception technique) —
    levée quand le départ du serveur échoue côté Discord."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


async def leave_guild(guild: discord.Guild) -> None:
    """Fait quitter GuideOn du serveur donné.

    Lève KickError si Discord refuse l'opération.
    """
    try:
        await guild.leave()
    except discord.HTTPException:
        log.exception("[DEV_KICK] Erreur leave() guild=%d", guild.id)
        raise KickError("Une **erreur Discord** est survenue lors du __kick__.") from None