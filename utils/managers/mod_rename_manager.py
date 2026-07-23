"""
utils/managers/mod_rename_manager.py — Renommage de pseudo (/mod rename).

Action de modération ponctuelle (comme mod_clear/mod_lock) : pas de
persistance en base, contrairement aux sanctions (aucune notion de
"casier judiciaire" pour un renommage). Journalisé via le reason passé
à member.edit(), visible dans l'audit-log Discord du serveur.
"""
from __future__ import annotations

import logging

import discord

from utils.managers.mod_log_manager import log_mod_action

log = logging.getLogger(__name__)

MIN_NICKNAME_LENGTH = 1
MAX_NICKNAME_LENGTH = 32  # limite dure de Discord


class RenameError(Exception):
    """Erreur métier à afficher à l'utilisateur (warning=True -> warning_container)."""

    def __init__(self, message: str, *, warning: bool = False) -> None:
        super().__init__(message)
        self.message = message
        self.warning = warning


def _validate_nickname(new_nickname: str | None) -> str | None:
    if new_nickname is None:
        return None
    new_nickname = new_nickname.strip()
    if not new_nickname:
        return None
    if len(new_nickname) > MAX_NICKNAME_LENGTH:
        raise RenameError(f"Le pseudo doit contenir au maximum **{MAX_NICKNAME_LENGTH} caractères**.", warning=True)
    return new_nickname


async def rename_member(
    member: discord.Member, new_nickname: str | None, moderator_id: int, reason: str,
) -> dict:
    """Change (ou réinitialise si None/vide) le pseudo d'un membre."""
    new_nickname = _validate_nickname(new_nickname)
    old_nickname = member.display_name

    try:
        await member.edit(nick=new_nickname, reason=reason)
    except discord.Forbidden:
        raise RenameError("Le bot n'a pas la permission de **renommer** ce membre.") from None
    except discord.HTTPException:
        log.exception("[MOD_RENAME] Échec renommage guild=%s user=%s", member.guild.id, member.id)
        raise RenameError("Erreur Discord lors du **renommage**.") from None

    log.info(
        "[MOD_RENAME] %s -> %s guild=%s user=%s moderator=%s",
        old_nickname, new_nickname or member.name, member.guild.id, member.id, moderator_id,
    )

    final_nickname = new_nickname or member.name
    await log_mod_action(
        member.guild.id, "Renommage", moderator_id, member.id, reason,
        extra=f"« {old_nickname} » -> « {final_nickname} »",
    )
    return {"user_id": member.id, "old_nickname": old_nickname, "new_nickname": final_nickname}