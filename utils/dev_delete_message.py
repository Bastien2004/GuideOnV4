"""
utils/dev_delete_message.py — Récupération et suppression d'un message envoyé
par le bot, extrait de cogs/dev/delete_message.py — même traitement que
utils/alpha_rank_logic.py / utils/birthday.py.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

import discord

log = logging.getLogger(__name__)


class DeleteMessageError(Exception):
    """Erreur métier à afficher à l'utilisateur (pas une exception technique) —
    levée quand la demande doit être refusée (salon/message introuvable,
    type de salon non supporté, message pas envoyé par le bot, déjà
    supprimé, permission manquante, ...)."""

    def __init__(self, message: str, *, warning: bool = False) -> None:
        super().__init__(message)
        self.message = message
        self.warning = warning  # True -> warning_container, False -> error_container


@dataclass
class DeletedMessageInfo:
    """Résumé d'une suppression réussie, pour construction du message de confirmation par le cog."""
    guild_name: str
    channel_name: str
    channel_id: int
    content_preview: str


# ============================================================
# 📁 Résolution salon / message
# ============================================================

_SUPPORTED_CHANNEL_TYPES = (discord.TextChannel, discord.Thread, discord.VoiceChannel, discord.StageChannel)


async def _resolve_channel(client: discord.Client, channel_id: int):
    """Récupère et valide le salon (cache -> fetch, puis type supporté)."""
    channel = client.get_channel(channel_id)
    if channel is None:
        try:
            channel = await client.fetch_channel(channel_id)
        except discord.NotFound:
            raise DeleteMessageError(
                "Salon **introuvable** (ID invalide ou bot non présent sur ce serveur)."
            ) from None
        except discord.Forbidden:
            raise DeleteMessageError("Le bot n'a pas **accès** à ce __salon__.") from None
        except discord.HTTPException:
            log.exception("[DELETE_MESSAGE] Erreur fetch_channel %d", channel_id)
            raise DeleteMessageError(
                "Une **erreur Discord** est survenue lors de la __récupération du salon__."
            ) from None

    if not isinstance(channel, _SUPPORTED_CHANNEL_TYPES):
        raise DeleteMessageError("Ce type de salon n'est pas **supporté**.")

    return channel


async def _resolve_message(channel, channel_id: int, message_id: int):
    """Récupère le message dans le salon."""
    try:
        return await channel.fetch_message(message_id)
    except discord.NotFound:
        raise DeleteMessageError("Message **introuvable** dans ce salon.") from None
    except discord.Forbidden:
        raise DeleteMessageError("Le bot n'a pas la **permission** de lire ce salon.") from None
    except discord.HTTPException:
        log.exception("[DELETE_MESSAGE] Erreur fetch_message %d/%d", channel_id, message_id)
        raise DeleteMessageError(
            "Une **erreur Discord** est survenue lors de la __récupération du message__."
        ) from None


# ============================================================
# 🗑️ Orchestration — extrait de cogs/dev/delete_message.py
# ============================================================

async def delete_bot_message(
    client: discord.Client,
    channel_id: int,
    message_id: int,
    requested_by_id: int,
) -> DeletedMessageInfo:
    """Récupère puis supprime un message envoyé par le bot dans un salon donné.

    Lève DeleteMessageError (warning=True pour les cas "normaux" — message
    pas du bot, déjà supprimé — warning=False pour les vraies erreurs) que
    le cog transforme en warning_container/error_container.
    """
    channel = await _resolve_channel(client, channel_id)
    message = await _resolve_message(channel, channel_id, message_id)

    # 🛡️ Vérification que le message provient du bot.
    if message.author.id != client.user.id:
        raise DeleteMessageError(
            "Ce message n'a **pas été envoyé par GuideOn** — suppression refusée.",
            warning=True,
        )

    # ℹ️ Récupération des informations du message.
    guild_name = getattr(channel.guild, "name", "DM") if hasattr(channel, "guild") else "DM"
    channel_name = getattr(channel, "name", str(channel_id))
    content_preview = (message.content or "*[contenu vide / embed / composants]*")[:200]

    # 🗑️ Suppression.
    try:
        await message.delete()
    except discord.NotFound:
        raise DeleteMessageError("Le message était déjà **supprimé**.", warning=True) from None
    except discord.Forbidden:
        raise DeleteMessageError("Le bot n'a pas la **permission** de __supprimer ce message__.") from None
    except discord.HTTPException:
        log.exception("[DELETE_MESSAGE] Erreur suppression %d/%d", channel_id, message_id)
        raise DeleteMessageError("Une **erreur Discord** est survenue lors de la __suppression__.") from None

    log.info(
        "[DELETE_MESSAGE] Message %d supprimé par %s | salon=%d (%s) guild=%s",
        message_id, requested_by_id, channel_id, channel_name, guild_name,
    )

    return DeletedMessageInfo(
        guild_name=guild_name,
        channel_name=channel_name,
        channel_id=channel_id,
        content_preview=content_preview,
    )