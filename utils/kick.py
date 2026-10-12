"""
utils/kick.py — Logique métier du /dev kick.
"""

from __future__ import annotations

import logging
import discord

log = logging.getLogger(__name__)


class KickError(Exception):
    """Erreurà afficher à l'utilisateur."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


async def leave_guild(guild: discord.Guild) -> None:
    """Fait quitter GuideOn du serveur donné."""
    
    try:
        await guild.leave()
    except discord.HTTPException:
        log.exception("[DEV_KICK] Erreur leave() guild=%d", guild.id)
        raise KickError("Une **erreur Discord** est survenue lors du __kick__.") from None