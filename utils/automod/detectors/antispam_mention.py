"""
utils/automod/detectors/antispam_mention.py — Détection des messages avec trop de mentions.
"""

from __future__ import annotations

import discord


def detect(message: discord.Message, *, max_mentions: int = 5) -> str | None:
    """Retourne "X mentions" si dépassement, None sinon."""
    
    count = (
        len(message.user_mentions)
        + len(message.role_mentions)
        + (1 if message.mention_everyone else 0)
    )
    if count > max_mentions:
        return f"{count} mentions"
    return None