"""
utils/managers/ng_server_manager.py — Cache + lookup de la table ng_servers.

La table ng_servers est alimentee par le site (voir utils.db.models.ng_server).
Ce manager ne fait que LIRE et mettre en cache. Les fonctions d'ecriture
(dev_create_server / dev_update_server / dev_delete_server_by_guild) restent
exposees pour usage interne (tests, outils d'administration).

Pattern de cache calque sur utils.managers.permission_manager :
- chargement complet en memoire au demarrage
- reload_cache() idempotent, safe a appeler a chaud
- lectures sync instantanees depuis le cache
"""
from __future__ import annotations

import asyncio
import logging

from sqlalchemy import select

from utils.db.models.ng_server import NGServer
from utils.db.session import get_session

log = logging.getLogger(__name__)

_by_guild: dict[int, NGServer] = {}
_by_name: dict[str, NGServer] = {}
_cache_ready: bool = False
_refresh_lock = asyncio.Lock()


# ══════════════════════════════════════════════════════════════════════════
# 🔄 REFRESH (async)
# ══════════════════════════════════════════════════════════════════════════

async def reload_cache() -> None:
    """
    Recharge tout le cache depuis la DB. Idempotent, safe a appeler a chaud.
    Garde l'ancien cache si la lecture DB echoue.
    """
    global _by_guild, _by_name, _cache_ready

    async with _refresh_lock:
        try:
            async with get_session() as session:
                rows = (await session.execute(select(NGServer))).scalars().all()
        except Exception:
            log.exception("Reload cache ng_servers échoué — on garde l'ancien cache")
            return

        new_by_guild: dict[int, NGServer] = {}
        new_by_name: dict[str, NGServer] = {}
        for server in rows:
            new_by_guild[server.discord_guild_id] = server
            new_by_name[server.name] = server

        _by_guild = new_by_guild
        _by_name = new_by_name
        _cache_ready = True
        log.info("Cache ng_servers rechargé (%d serveur(s))", len(_by_name))


def cache_is_ready() -> bool:
    return _cache_ready


# ══════════════════════════════════════════════════════════════════════════
# 📖 LECTURES SYNC (depuis le cache)
# ══════════════════════════════════════════════════════════════════════════

def get_server_by_guild(guild_id: int) -> NGServer | None:
    """Retourne le NGServer associé à ce guild_id Discord, ou None."""
    if not _cache_ready:
        log.warning("get_server_by_guild appelé avant que le cache ng_servers soit prêt")
        return None
    return _by_guild.get(guild_id)


def get_server_by_name(name: str) -> NGServer | None:
    """Retourne le NGServer associé à ce nom (ex: 'alpha'), ou None."""
    if not _cache_ready:
        log.warning("get_server_by_name appelé avant que le cache ng_servers soit prêt")
        return None
    return _by_name.get(name)


def list_active_servers() -> list[NGServer]:
    """Liste des serveurs NG actifs (active=True), depuis le cache."""
    if not _cache_ready:
        log.warning("list_active_servers appelé avant que le cache ng_servers soit prêt")
        return []
    return [s for s in _by_name.values() if s.active]


def list_all_servers() -> list[NGServer]:
    """Liste de tous les serveurs NG (actifs ou non), depuis le cache."""
    if not _cache_ready:
        log.warning("list_all_servers appelé avant que le cache ng_servers soit prêt")
        return []
    return list(_by_name.values())


# ══════════════════════════════════════════════════════════════════════════
# ✍️ ÉCRITURES ASYNC — usage interne uniquement
# ══════════════════════════════════════════════════════════════════════════
#
# Toute écriture dans ng_servers doit normalement passer par l'interface site
# (source de vérité, voir utils.db.models.ng_server). Ces fonctions sont
# conservées pour les tests et les besoins d'administration (ex: tableau
# admin Laravel via POST /servers/add et /servers/update).


class NGServerNameConflictError(Exception):
    """Un serveur NG avec ce `name` existe déjà."""


class NGServerGuildConflictError(Exception):
    """Ce discord_guild_id est déjà associé à un autre serveur NG."""


class NGServerNotFoundError(Exception):
    """Aucun serveur NG ne correspond à ce discord_guild_id."""


async def dev_create_server(
    *,
    name: str,
    display_name: str,
    edition: str,
    discord_guild_id: int,
    active: bool = True,
) -> NGServer:
    """
    Crée une entrée ng_servers. Lève NGServerNameConflictError ou
    NGServerGuildConflictError si `name` ou `discord_guild_id` sont déjà pris
    (discord_guild_id est UNIQUE en DB — un Discord ne peut simuler qu'un
    seul serveur NG à la fois).
    """
    async with get_session() as session:
        existing_name = await session.scalar(select(NGServer).where(NGServer.name == name))
        if existing_name is not None:
            raise NGServerNameConflictError(
                f"Un serveur NG nommé {name!r} existe déjà (guild_id={existing_name.discord_guild_id})."
            )

        existing_guild = await session.scalar(
            select(NGServer).where(NGServer.discord_guild_id == discord_guild_id)
        )
        if existing_guild is not None:
            raise NGServerGuildConflictError(
                f"Ce Discord simule déjà le serveur NG {existing_guild.name!r}."
            )

        server = NGServer(
            name=name,
            display_name=display_name,
            edition=edition,
            discord_guild_id=discord_guild_id,
            active=active,
        )
        session.add(server)
        await session.flush()
        await session.refresh(server)
        created = NGServer(
            id=server.id,
            name=server.name,
            display_name=server.display_name,
            edition=server.edition,
            discord_guild_id=server.discord_guild_id,
            active=server.active,
        )

    await reload_cache()
    log.info("ng_servers (dev) : serveur créé name=%s guild_id=%s", name, discord_guild_id)
    return created


async def dev_update_server(
    *,
    discord_guild_id: int,
    display_name: str | None = None,
    edition: str | None = None,
    active: bool | None = None,
) -> NGServer:
    """
    Met à jour display_name / edition / active d'un serveur NG existant
    (identifié par discord_guild_id). `name` n'est volontairement PAS
    modifiable ici : c'est la clé technique utilisée partout ailleurs
    (ng_staff, ng_onu_config, ng_nota_config...), la changer casserait
    les jointures existantes.

    Lève NGServerNotFoundError si aucun serveur ne correspond.
    """
    async with get_session() as session:
        server = await session.scalar(
            select(NGServer).where(NGServer.discord_guild_id == discord_guild_id)
        )
        if server is None:
            raise NGServerNotFoundError(
                f"Aucun serveur NG connu pour guild_id={discord_guild_id}"
            )

        if display_name is not None:
            server.display_name = display_name
        if edition is not None:
            server.edition = edition
        if active is not None:
            server.active = active

        await session.flush()
        await session.refresh(server)
        updated = NGServer(
            id=server.id,
            name=server.name,
            display_name=server.display_name,
            edition=server.edition,
            discord_guild_id=server.discord_guild_id,
            active=server.active,
        )

    await reload_cache()
    log.info("ng_servers (dev) : serveur mis à jour guild_id=%s", discord_guild_id)
    return updated


async def dev_delete_server_by_guild(discord_guild_id: int) -> NGServer | None:
    """Retire l'entrée ng_servers pour ce guild_id. None si aucune entrée."""
    async with get_session() as session:
        server = await session.scalar(
            select(NGServer).where(NGServer.discord_guild_id == discord_guild_id)
        )
        if server is None:
            return None
        deleted = NGServer(
            id=server.id,
            name=server.name,
            display_name=server.display_name,
            edition=server.edition,
            discord_guild_id=server.discord_guild_id,
            active=server.active,
        )
        await session.delete(server)

    await reload_cache()
    log.info("ng_servers (dev) : serveur supprimé name=%s guild_id=%s", deleted.name, discord_guild_id)
    return deleted