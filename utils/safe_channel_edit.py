"""
Edit prudent d'un salon avec gestion du rate-limit Discord.

Discord limite à 2 edits/10min sur les channels. Cette fonction tente l'edit,
attrape les rate-limits et log au lieu de planter.
"""
import logging

import discord

log = logging.getLogger(__name__)


async def safe_channel_edit(channel: discord.abc.GuildChannel, **kwargs) -> bool:
    """
    Tente de modifier un salon. Retourne True si OK, False si rate-limited.
    """
    try:
        await channel.edit(**kwargs)
        return True
    except discord.HTTPException as e:
        if e.status == 429:  # rate limit
            log.warning("Rate-limit sur edit channel %s (%s)", channel.id, channel.name)
            return False
        log.error("Erreur edit channel %s : %s", channel.id, e)
        return False
