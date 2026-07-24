"""
utils/managers/mod_channel_lock_manager.py — Verrouillage/déverrouillage d'un salon textuel (/mod lock).

Action de modération ponctuelle (comme mod_clear/mod_voice_manage) : pas de
sanction enregistrée, seulement un log via utils.managers.mod_log_manager.log_channel_action.
"""
from __future__ import annotations

import discord


class LockError(Exception):
    """Erreur métier à afficher à l'utilisateur (warning=True -> warning_container)."""

    def __init__(self, message: str, *, warning: bool = False) -> None:
        super().__init__(message)
        self.message = message
        self.warning = warning


def is_locked(channel: discord.TextChannel) -> bool:
    """True si @everyone n'a plus la permission d'envoyer des messages dans ce salon."""
    overwrite = channel.overwrites_for(channel.guild.default_role)
    return overwrite.send_messages is False


async def set_channel_lock(channel: discord.TextChannel, locked: bool, *, reason: str | None = None) -> None:
    """Verrouille ou déverrouille le salon pour @everyone (réinitialise l'overwrite au déverrouillage)."""
    everyone = channel.guild.default_role
    overwrite = channel.overwrites_for(everyone)
    overwrite.send_messages = False if locked else None

    try:
        await channel.set_permissions(everyone, overwrite=overwrite, reason=reason)
    except discord.Forbidden as exc:
        raise LockError("Le bot n'a pas la permission de modifier ce salon.") from exc
    except discord.HTTPException as exc:
        raise LockError("Une erreur Discord est survenue pendant la modification du salon.") from exc