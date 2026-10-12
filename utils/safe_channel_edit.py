"""
Outils d'édition sécurisé de salons Discord.
"""

import logging
import discord

log = logging.getLogger(__name__)


async def safe_channel_edit(channel: discord.abc.GuildChannel, **kwargs) -> bool:
    """Tente de modifier un salon avec gestion du rate-limit."""

    try:
        await channel.edit(**kwargs)
        return True
    except discord.HTTPException as e:
        if e.status == 429:
            log.warning("Rate-limit sur edit channel %s (%s)", channel.id, channel.name)
            return False
        log.error("Erreur edit channel %s : %s", channel.id, e)
        return False