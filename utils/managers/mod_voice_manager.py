"""
utils/managers/mod_voice_manager.py — Gestion vocale de masse (/mod vocal).

Action de modération ponctuelle (comme mod_clear/mod_lock) : pas de sanction
enregistrée, seulement un log via utils.managers.mod_log_manager.log_channel_action.
"""
from __future__ import annotations

import discord


class VoiceManageError(Exception):
    """Erreur métier à afficher à l'utilisateur (warning=True -> warning_container)."""

    def __init__(self, message: str, *, warning: bool = False) -> None:
        super().__init__(message)
        self.message = message
        self.warning = warning


def is_channel_muted(channel: discord.VoiceChannel) -> bool:
    """True si tous les membres actuellement connectés sont mute serveur (False si salon vide)."""
    members = channel.members
    if not members:
        return False
    return all(m.voice is not None and m.voice.mute for m in members)


async def mute_all(channel: discord.VoiceChannel, *, mute: bool, reason: str | None = None) -> int:
    """Mute (ou démute) tous les membres présents dans le salon vocal. Retourne le nombre affecté."""
    count = 0
    for member in list(channel.members):
        try:
            await member.edit(mute=mute, reason=reason)
            count += 1
        except (discord.Forbidden, discord.HTTPException):
            continue
    return count


async def move_all(
    channel: discord.VoiceChannel, destination: discord.VoiceChannel, *, reason: str | None = None,
) -> int:
    """Déplace tous les membres du salon source vers le salon destination."""
    if channel.id == destination.id:
        raise VoiceManageError("Le salon de destination doit être différent du salon source.", warning=True)

    count = 0
    for member in list(channel.members):
        try:
            await member.move_to(destination, reason=reason)
            count += 1
        except (discord.Forbidden, discord.HTTPException):
            continue
    return count


async def disconnect_all(channel: discord.VoiceChannel, *, reason: str | None = None) -> int:
    """Déconnecte tous les membres actuellement présents dans le salon vocal."""
    count = 0
    for member in list(channel.members):
        try:
            await member.move_to(None, reason=reason)
            count += 1
        except (discord.Forbidden, discord.HTTPException):
            continue
    return count