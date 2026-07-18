"""
utils/join_serv.py — Recherche d'un salon utilisable et création d'une
invitation Discord, extrait de cogs/dev/join_serv.py — même traitement que
utils/delete_message.py.
"""
from __future__ import annotations

import logging

import discord

log = logging.getLogger(__name__)


class JoinServError(Exception):
    """Erreur à afficher à l'utilisateur (pas une exception technique) —
    levée quand aucun salon n'autorise la création d'invitation, ou que
    Discord refuse/échoue la création."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


# ============================================================
# 📁 Recherche d'un salon utilisable
# ============================================================

def find_invitable_channel(guild: discord.Guild) -> discord.TextChannel | None:
    """Cherche un salon libre d'invitations."""

    me = guild.me

    if me is None:
        return None

    candidates: list[discord.TextChannel] = []

    if guild.system_channel is not None:
        candidates.append(guild.system_channel)
    candidates += [c for c in guild.text_channels if c not in candidates]

    for channel in candidates:
        perms = channel.permissions_for(me)
        if perms.create_instant_invite:
            return channel

    return None


# ============================================================
# 🔗 Orchestration — extrait de cogs/dev/join_serv.py
# ============================================================

async def create_server_invite(
    guild: discord.Guild,
    requested_by: discord.abc.User,
) -> tuple[discord.Invite, discord.TextChannel]:
    """Trouve un salon utilisable et crée une invitation dessus.

    Lève JoinServError si aucun salon n'autorise la création d'invitation,
    ou si Discord refuse/échoue la création.
    """
    channel = find_invitable_channel(guild)
    if channel is None:
        raise JoinServError(
            f"Aucun salon de **{guild.name}** ne permet à GuideOn de créer une invitation "
            f"(permission `Créer une invitation` manquante partout)."
        )

    try:
        invite = await channel.create_invite(
            max_age=86400,
            max_uses=0,
            temporary=False,
            unique=True,
            reason=f"Demandé par {requested_by} ({requested_by.id}) via /dev join_serv",
        )
    except discord.Forbidden:
        raise JoinServError(
            f"GuideOn n'a pas la permission de créer une invitation sur **{guild.name}**."
        ) from None
    except discord.HTTPException:
        log.exception("[DEV_JOIN_SERV] Erreur create_invite guild=%d", guild.id)
        raise JoinServError(
            "Une **erreur Discord** est survenue lors de la création de l'invitation."
        ) from None

    log.info(
        "[DEV_JOIN_SERV] Invitation créée pour %s (%d) | salon=%d | demandé par %d",
        guild.name, guild.id, channel.id, requested_by.id,
    )

    return invite, channel