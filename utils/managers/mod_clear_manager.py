"""
utils/managers/mod_clear_manager.py — Suppression de messages en masse (/mod clear).

Action de modération ponctuelle (comme mod_lock/mod_voice_manage) : pas de
sanction enregistrée, seulement un log via utils.managers.mod_log_manager.log_channel_action.
"""
from __future__ import annotations

import discord

MIN_CLEAR_AMOUNT = 1
MAX_CLEAR_AMOUNT = 500


class ClearError(Exception):
    """Erreur métier à afficher à l'utilisateur (warning=True -> warning_container)."""

    def __init__(self, message: str, *, warning: bool = False) -> None:
        super().__init__(message)
        self.message = message
        self.warning = warning


async def clear_messages(
    channel: discord.TextChannel, amount: int, *, author_filter: discord.abc.User | None = None,
) -> int:
    """Supprime jusqu'à `amount` messages dans `channel`, filtrés sur `author_filter` si fourni.

    Retourne le nombre de messages effectivement supprimés.
    """
    if not (MIN_CLEAR_AMOUNT <= amount <= MAX_CLEAR_AMOUNT):
        raise ClearError(
            f"Le nombre de messages doit être compris entre **{MIN_CLEAR_AMOUNT}** et **{MAX_CLEAR_AMOUNT}**.",
            warning=True,
        )

    def _check(message: discord.Message) -> bool:
        return author_filter is None or message.author.id == author_filter.id

    try:
        deleted = await channel.purge(limit=amount, check=_check)
    except discord.Forbidden as exc:
        raise ClearError("Le bot n'a pas la permission de supprimer des messages dans ce salon.") from exc
    except discord.HTTPException as exc:
        raise ClearError("Une erreur Discord est survenue pendant la suppression des messages.") from exc

    return len(deleted)