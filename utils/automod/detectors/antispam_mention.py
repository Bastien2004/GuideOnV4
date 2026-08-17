"""
utils/automod/detectors/antispam_mention.py — Détection des messages avec
trop de mentions.

Utilise le Message discord.py directement (accès à user_mentions,
role_mentions, mention_everyone) plutôt qu'un parsing regex du contenu :
plus fiable (Discord fait la résolution des mentions correctement, y
compris les cas edge type mention dans un bloc de code qui ne compte pas).

Compte : mentions users + mentions rôles + @everyone/@here (1 si vrai).
"""
from __future__ import annotations

import discord


def detect(
    message: discord.Message,
    *,
    max_mentions: int = 5,
) -> str | None:
    """Retourne "X mentions" si dépassement, None sinon."""
    count = (
        len(message.user_mentions)
        + len(message.role_mentions)
        + (1 if message.mention_everyone else 0)
    )
    if count > max_mentions:
        return f"{count} mentions"
    return None