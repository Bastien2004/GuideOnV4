"""
utils/managers/bot_avatar_manager.py — Avatar de bot personnalisé par
serveur ("Avatar Perso", add-on boutique).
"""

from __future__ import annotations

import logging

import discord

log = logging.getLogger(__name__)

# Formats acceptés par Discord pour un avatar (membre/serveur ou global).
ALLOWED_CONTENT_TYPES = {"image/png", "image/jpeg", "image/gif", "image/webp"}
ALLOWED_EXTENSIONS = (".png", ".jpg", ".jpeg", ".gif", ".webp")

# Limite Discord pour une image d'avatar.
MAX_AVATAR_SIZE_BYTES = 10 * 1024 * 1024  # 10 Mio


class GuildNotFoundError(Exception):
    """Le serveur ciblé n'est pas (ou plus) accessible par le bot."""


def validate_avatar_attachment(attachment: discord.Attachment) -> str | None:
    """Valide le fichier envoyé avant même de le télécharger/l'appliquer.

    Renvoie un message d'erreur (str) si invalide, ou None si OK. Vérifie
    le `content_type` ET l'extension du nom de fichier (le content_type
    Discord peut être absent sur certains clients/anciens messages — voir
    cogs/qr/scan.py pour le même filet de sécurité par extension).
    """
    content_type = (attachment.content_type or "").split(";")[0].strip().lower()
    filename = attachment.filename.lower()

    if content_type not in ALLOWED_CONTENT_TYPES and not filename.endswith(ALLOWED_EXTENSIONS):
        return "Le fichier doit être une **image** (png, jpg, jpeg, gif ou webp)."

    if attachment.size > MAX_AVATAR_SIZE_BYTES:
        taille_mo = attachment.size / (1024 * 1024)
        return f"Fichier trop volumineux (**{taille_mo:.1f} Mo** — 10 Mo maximum pour un avatar Discord)."

    return None


def _resolve_bot_member(bot: discord.Client, guild_id: int) -> discord.Member:
    """Résout `guild.me` pour ce serveur, ou lève GuildNotFoundError."""
    guild = bot.get_guild(guild_id)
    if guild is None:
        raise GuildNotFoundError(f"GuideOn n'est présent sur aucun serveur avec l'ID {guild_id}.")
    if guild.me is None:
        raise GuildNotFoundError(f"Membre du bot introuvable sur le serveur {guild.name} ({guild.id}).")
    return guild.me


async def apply_guild_avatar(bot: discord.Client, guild_id: int, image_bytes: bytes, *, reason: str) -> discord.Member:
    """Applique un avatar personnalisé pour ce serveur.

    Laisse remonter discord.Forbidden / discord.HTTPException tel quel —
    c'est à l'appelant (cogs/dev/avatar_bot.py) de les traduire en message
    clair, puisque les causes possibles (format refusé par Discord,
    permissions, 429...) appellent des messages différents.
    """
    member = _resolve_bot_member(bot, guild_id)
    updated = await member.edit(avatar=image_bytes, reason=reason)
    log.info(
        "[AVATAR_PERSO] Avatar personnalisé appliqué : guild=%s (%s) | reason=%s",
        member.guild.id, member.guild.name, reason,
    )
    return updated or member


async def reset_guild_avatar(bot: discord.Client, guild_id: int, *, reason: str) -> discord.Member:
    """Retire l'avatar personnalisé de ce serveur (retour à l'avatar global)."""
    member = _resolve_bot_member(bot, guild_id)
    updated = await member.edit(avatar=None, reason=reason)
    log.info(
        "[AVATAR_PERSO] Avatar personnalisé retiré : guild=%s (%s) | reason=%s",
        member.guild.id, member.guild.name, reason,
    )
    return updated or member


def get_current_avatar_url(bot: discord.Client, guild_id: int) -> str | None:
    """URL de l'avatar actuellement appliqué sur ce serveur, ou None si pas
    d'avatar personnalisé (avatar global utilisé). Lecture pure, aucun appel
    API (guild_avatar est déjà en cache local discord.py)."""
    guild = bot.get_guild(guild_id)
    if guild is None or guild.me is None:
        return None
    avatar = guild.me.guild_avatar
    return avatar.url if avatar is not None else None
