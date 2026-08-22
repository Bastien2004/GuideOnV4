"""
utils/managers/ng_stafflist_manager.py — Helper de rafraîchissement du message
de liste du staff, généralisé multi-serveurs.

Rescapé de l'ex-cogs/alpha/stafflist.py (fichier supprimé lors du passage à
/ngstaff stafflist). Cette fonction est appelée par les commandes /alpha,
/ngstaff, les rank/derank logics et les vues d'édition — elle DOIT donc
vivre dans utils/ et pas dans un cog (les cogs n'ont pas vocation à
exposer des helpers réutilisables aux autres cogs).

Silencieuse par nature (log en cas de problème mais ne lève rien) : les
appelants sont des flows utilisateur dont la réussite ne dépend pas du
rafraîchissement de la liste.
"""
from __future__ import annotations

import logging

import discord

from utils.managers.alpha_message_manager import (
    clear_alpha_message,
    get_alpha_message,
    upsert_alpha_message,
)
from utils.managers.ng_rank_config_manager import load_rank_config
from utils.managers.ng_staff_manager import list_staff
from views.ngstaff.stafflist_view import build_stafflist_view

log = logging.getLogger(__name__)

MESSAGE_KEY = "stafflist"


async def refresh_staff_message(
    bot: discord.Client,
    guild_id: int,
    *,
    server: str,
) -> None:
    """
    Rafraîchit le message de liste du staff pour un serveur NG.

    `server` sélectionne la source des données (ng_rank_configs / ng_staff)
    ; `guild_id` reste la clé Discord pour savoir où (quel salon, quel
    message) rafraîchir — les deux notions sont indépendantes (cf.
    alpha_message_manager, déjà multi-serveurs par guild_id).

    Sans effet si le salon n'est pas configuré ou introuvable. Ne lève
    jamais : erreurs loguées uniquement.
    """
    cfg = await load_rank_config(server)
    channel_id = cfg.get("content_stafflist_channel_id")
    if not channel_id:
        log.warning(
            "[STAFFLIST] refresh_staff_message : salon non configuré | guild=%d server=%s",
            guild_id, server,
        )
        return

    channel = bot.get_channel(channel_id)
    if channel is None:
        try:
            channel = await bot.fetch_channel(channel_id)
        except (discord.NotFound, discord.HTTPException):
            log.warning(
                "[STAFFLIST] refresh_staff_message : salon %d introuvable | server=%s",
                channel_id, server,
            )
            return

    members = await list_staff(server)
    view = build_stafflist_view(members, server=server)

    msg_cfg = await get_alpha_message(guild_id, MESSAGE_KEY)
    existing: discord.Message | None = None

    if msg_cfg and msg_cfg.message_id:
        try:
            existing = await channel.fetch_message(msg_cfg.message_id)
        except (discord.NotFound, discord.HTTPException):
            existing = None
            await clear_alpha_message(guild_id, MESSAGE_KEY)

    try:
        if existing:
            await existing.edit(view=view)
        else:
            sent = await channel.send(view=view)
            await upsert_alpha_message(guild_id, MESSAGE_KEY, channel_id, sent.id)
    except discord.HTTPException:
        log.exception(
            "[STAFFLIST] refresh_staff_message : erreur HTTP | guild=%d server=%s",
            guild_id, server,
        )