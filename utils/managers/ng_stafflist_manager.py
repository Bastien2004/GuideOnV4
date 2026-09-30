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

PAGINATION (2026-09, bug de prod sur Iris) : un message Discord ne peut pas
dépasser 4000 caractères de texte cumulé sur ses composants ("Components
displayable text size exceeds maximum size of 4000"). Une stafflist avec
suffisamment de staff/statuts dépasse cette limite sur un message unique.
views/ngstaff/stafflist_view.py::build_stafflist_view retourne donc
maintenant une LISTE de pages (une LayoutView par page) ; sync_stafflist_messages
ci-dessous gère l'envoi/édition d'UN message Discord par page (clés
"stafflist_0", "stafflist_1", ... plutôt qu'une seule clé "stafflist"),
avec migration transparente de l'ancien schéma à page unique et nettoyage
des pages devenues excédentaires si la liste rétrécit. Cette logique était
dupliquée entre refresh_staff_message et cogs/ngstaff/ngstaff_stafflist.py
(la commande a besoin de savoir si un message a été créé ou mis à jour
pour son message de confirmation) — extraite ici pour que les deux
bénéficient du correctif sans dupliquer le correctif lui-même.

CONCURRENCE (2026-09, question de Paul) : rank/derank/edit_stafflist et
/ngstaff stafflist appellent tous, in fine, sync_stafflist_messages pour
le même guild_id. Deux appels concurrents sur le MÊME serveur (ex : deux
membres rankés à quelques millisecondes d'écart, ou une commande manuelle
pendant qu'un rank vient de se déclencher) lisent tous les deux l'état
"page 0 n'existe pas encore" avant que l'un des deux ait eu le temps
d'écrire — sans protection, ça produit un message Discord dupliqué (les
deux envoient), et le second upsert_alpha_message écrase la ligne du
premier en base : le message du premier devient orphelin (plus aucune
ligne ne pointe dessus, jamais nettoyé par la suite). Pire, un INSERT
concurrent sur la même clé primaire (guild_id, key) peut lever une
IntegrityError SQLAlchemy — non interceptée par le `except
discord.HTTPException` des deux appelants, ce qui casserait le contrat
"ne lève jamais" de refresh_staff_message.

Le bot tourne en un seul process (pas de sharding — vérifié dans bot.py),
donc un verrou asyncio.Lock par guild_id, tenu pendant toute la durée de
sync_stafflist_messages, suffit à sérialiser les appels concurrents pour
un même serveur sans bloquer les autres serveurs entre eux. Si le bot
devait un jour tourner en plusieurs process/instances (sharding
inter-process, plusieurs conteneurs), ce verrou en mémoire ne suffirait
plus — il faudrait alors un verrou côté base (ex. pg_advisory_xact_lock
sur guild_id).
"""
from __future__ import annotations

import asyncio
import logging
from collections import defaultdict

import discord
from discord.ui import LayoutView

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

# Un verrou par guild_id : sérialise les appels concurrents à
# sync_stafflist_messages pour UN MÊME serveur (deux rank/derank
# quasi-simultanés, ou une commande manuelle pendant un refresh
# automatique), sans jamais bloquer un serveur à cause d'un autre.
# defaultdict(asyncio.Lock) : chaque guild_id obtient paresseusement son
# propre verrou au premier accès, jamais recréé ensuite (vit pour la durée
# du process — un dict de quelques dizaines/centaines de Lock ne pèse
# rien).
_guild_locks: dict[int, asyncio.Lock] = defaultdict(asyncio.Lock)


async def sync_stafflist_messages(
    channel: discord.abc.Messageable,
    channel_id: int,
    guild_id: int,
    pages: list[LayoutView],
) -> bool:
    """
    Envoie/édite un message par page de `pages` dans `channel`, sous les
    clés "stafflist_0", "stafflist_1", ... (une par page). Migre
    silencieusement l'ancien schéma à message unique (clé "stafflist") en
    page 0 s'il existe encore, pour ne pas dupliquer le message existant.
    Supprime les pages devenues excédentaires si la liste a rétréci
    (moins de pages qu'avant cet appel).

    Retourne True si la page 0 n'avait aucun message existant avant cet
    appel (i.e. première création de la stafflist pour ce serveur), False
    si elle a été éditée en place — pour distinguer "créée" vs "mise à
    jour" dans les messages de confirmation utilisateur.

    Peut lever discord.HTTPException (non interceptée ici à dessein : les
    deux appelants ont des besoins différents en cas d'erreur — l'un logue
    et avale silencieusement, l'autre répond à l'utilisateur).

    Tenu sous _guild_locks[guild_id] (voir note "CONCURRENCE" en tête de
    fichier) : deux appels concurrents pour le MÊME serveur s'exécutent
    l'un après l'autre plutôt que de courir sur les mêmes lignes en base.
    """
    async with _guild_locks[guild_id]:
        return await _sync_stafflist_messages_locked(channel, channel_id, guild_id, pages)


async def _sync_stafflist_messages_locked(
    channel: discord.abc.Messageable,
    channel_id: int,
    guild_id: int,
    pages: list[LayoutView],
) -> bool:
    """Corps réel de sync_stafflist_messages, à appeler uniquement sous
    _guild_locks[guild_id] (voir wrapper ci-dessus) — jamais directement."""
    # ── Migration transparente ancien schéma → page 0 ────────────────────
    legacy_cfg = await get_alpha_message(guild_id, MESSAGE_KEY)
    if legacy_cfg and legacy_cfg.message_id:
        await upsert_alpha_message(guild_id, f"{MESSAGE_KEY}_0", legacy_cfg.channel_id, legacy_cfg.message_id)
        await clear_alpha_message(guild_id, MESSAGE_KEY)

    created = False
    i = 0
    while True:
        key = f"{MESSAGE_KEY}_{i}"
        page_view = pages[i] if i < len(pages) else None
        msg_cfg = await get_alpha_message(guild_id, key)

        if page_view is None and msg_cfg is None:
            break  # plus aucune page attendue, plus rien à nettoyer

        if page_view is None:
            # Page excédentaire (la liste a rétréci depuis le dernier
            # rafraîchissement) : on supprime le message Discord et son
            # entrée, pour ne pas laisser une page obsolète dans le salon.
            if msg_cfg.message_id:
                try:
                    old_msg = await channel.fetch_message(msg_cfg.message_id)
                    await old_msg.delete()
                except (discord.NotFound, discord.HTTPException):
                    pass
            await clear_alpha_message(guild_id, key)
            i += 1
            continue

        existing: discord.Message | None = None
        if msg_cfg and msg_cfg.message_id:
            try:
                existing = await channel.fetch_message(msg_cfg.message_id)
            except (discord.NotFound, discord.HTTPException):
                existing = None
                await clear_alpha_message(guild_id, key)

        if existing:
            await existing.edit(view=page_view)
        else:
            if i == 0:
                created = True
            sent = await channel.send(view=page_view)
            await upsert_alpha_message(guild_id, key, channel_id, sent.id)

        i += 1

    return created


async def refresh_staff_message(
    bot: discord.Client,
    guild_id: int,
    *,
    server: str,
) -> None:
    """
    Rafraîchit le message de liste du staff pour un serveur NG.

    `server` sélectionne la source des données (ng_rank_configs / ng_staff)
    ; `guild_id` reste la clé Discord pour savoir où (quel salon, quels
    messages) rafraîchir — les deux notions sont indépendantes (cf.
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
    pages = build_stafflist_view(members, server=server)

    try:
        await sync_stafflist_messages(channel, channel_id, guild_id, pages)
    except discord.HTTPException:
        log.exception(
            "[STAFFLIST] refresh_staff_message : erreur HTTP | guild=%d server=%s",
            guild_id, server,
        )