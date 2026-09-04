"""
utils/medialink/notification.py — Système de notification.
"""

from __future__ import annotations

import discord

from utils.db.models.medialink_rule import MediaRule
from utils.db.models.medialink_template import MediaTemplate
from utils.db.session import get_session
from utils.medialink.builders import announcement as announcement_builder
from utils.medialink.event_manager import RoutedEvent


_DEFAULT_CONTENT = "🔔 Nouvel événement : **{titre}**\n{url}"


class NotificationError(Exception):
    """Erreur définitive côté notification."""


async def send(bot: discord.Client, routed_event: RoutedEvent, rule: MediaRule) -> None:
    """Construit l'annonce de notification."""

    event = routed_event.event

    template: MediaTemplate | None = None
    if rule.template_id is not None:
        async with get_session() as session:
            template = await session.get(MediaTemplate, rule.template_id)

    if template is None:
        template = MediaTemplate(content=_DEFAULT_CONTENT, container_config=None, buttons=None)

    mention = f"<@&{rule.mention_role_id}>" if rule.mention_role_id else None
    built = announcement_builder.build(template, event, mention=mention)
    kwargs = built.to_kwargs()

    if not kwargs:
        raise NotificationError(
            f"Rien à envoyer pour la règle {rule.id} : template et mention "
            f"vides une fois les placeholders résolus."
        )

    channel = bot.get_channel(rule.channel_id)
    if channel is None:
        try:
            channel = await bot.fetch_channel(rule.channel_id)
        except (discord.NotFound, discord.Forbidden, discord.HTTPException) as exc:
            raise NotificationError(
                f"Salon {rule.channel_id} (règle {rule.id}) introuvable ou inaccessible : {exc}"
            ) from exc

    await channel.send(**kwargs)