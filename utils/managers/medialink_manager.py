"""
utils/managers/medialink_manager.py — CRUD des connexions, règles et
templates MEDIALINK (media_connections / media_rules / media_templates).

Même pattern que utils/managers/mod_automod_nolink_manager.py : cache TTL
en mémoire par guild sur les connexions (lues à chaque ouverture du
dashboard et à chaque passage du scheduler), invalidé explicitement à
chaque écriture.

NOTE : le CRUD des templates ci-dessous reste volontairement dans CE
fichier (pas de utils/managers/medialink_template_manager.py séparé) —
le volume de code est faible et il n'y a pas encore de raison de le
scinder ; à revoir si ça grossit une fois les Announcement Builders (§7)
branchés dessus. Pas de cache dédié sur les templates (écrans peu
sollicités, contrairement au dashboard des connexions).
"""
from __future__ import annotations

import time

from sqlalchemy import delete, select

from utils.db.models.medialink_connection import MediaConnection
from utils.db.models.medialink_rule import MediaRule
from utils.db.models.medialink_template import MediaTemplate
from utils.db.session import get_session

# ═══ Cache connexions (par guild) ═══════════════════════════════════
_CONN_TTL = 60
_conn_cache: dict[int, tuple[list[dict], float]] = {}


def _conn_fresh(guild_id: int) -> list[dict] | None:
    entry = _conn_cache.get(guild_id)
    if entry is None:
        return None
    payload, ts = entry
    if time.monotonic() - ts > _CONN_TTL:
        return None
    return [dict(row) for row in payload]


def _conn_prime(guild_id: int, payload: list[dict]) -> None:
    _conn_cache[guild_id] = ([dict(row) for row in payload], time.monotonic())


def _conn_invalidate(guild_id: int) -> None:
    _conn_cache.pop(guild_id, None)


# ═══ Connexions ══════════════════════════════════════════════════════

async def list_connections(guild_id: int) -> list[dict]:
    """Connexions actives d'une guild (toutes plateformes confondues)."""
    cached = _conn_fresh(guild_id)
    if cached is not None:
        return cached

    async with get_session() as session:
        result = await session.execute(
            select(MediaConnection).where(MediaConnection.guild_id == guild_id)
        )
        payload = [row.to_dict() for row in result.scalars().all()]

    _conn_prime(guild_id, payload)
    return payload


async def add_connection(
    guild_id: int,
    platform: str,
    external_id: str,
    *,
    external_username: str | None = None,
    external_url: str | None = None,
    avatar_url: str | None = None,
) -> dict:
    """Crée une connexion. À appeler APRÈS un
    BaseMediaProvider.validate_account() réussi côté appelant (cog/vue) —
    ce manager ne valide rien côté plateforme, il ne fait que persister."""
    async with get_session() as session:
        row = MediaConnection(
            guild_id=guild_id,
            platform=platform,
            external_id=external_id,
            external_username=external_username,
            external_url=external_url,
            avatar_url=avatar_url,
        )
        session.add(row)
        await session.flush()
        payload = row.to_dict()

    _conn_invalidate(guild_id)
    return payload


async def remove_connection(guild_id: int, connection_id: int) -> None:
    """Supprime une connexion — cascade sur ses règles (rules,
    cascade="all, delete-orphan" côté modèle) et sur ses événements/
    logs en base (ondelete=CASCADE)."""
    async with get_session() as session:
        await session.execute(
            delete(MediaConnection).where(
                MediaConnection.id == connection_id,
                MediaConnection.guild_id == guild_id,
            )
        )

    _conn_invalidate(guild_id)


async def set_connection_status(connection_id: int, guild_id: int, status: str) -> None:
    """Met à jour l'état d'une connexion (§6.3) — appelé par
    utils.medialink.event_manager / le scheduler après un check_status()."""
    async with get_session() as session:
        row = await session.get(MediaConnection, connection_id)
        if row is not None:
            row.status = status

    _conn_invalidate(guild_id)


# ═══ Règles ══════════════════════════════════════════════════════════
# Pas de cache dédié ici : les règles sont chargées via la relationship
# `MediaConnection.rules` (lazy="selectin"), déjà couverte par le cache
# connexions ci-dessus — un accès direct par connection_id reste rare
# (essentiellement les vues de configuration d'UNE règle à la fois).

async def list_rules(connection_id: int) -> list[dict]:
    async with get_session() as session:
        result = await session.execute(
            select(MediaRule).where(MediaRule.connection_id == connection_id)
        )
        return [row.to_dict() for row in result.scalars().all()]


async def add_rule(
    connection_id: int,
    event_type: str,
    channel_id: int,
    *,
    template_id: int | None = None,
    mention_role_id: int | None = None,
) -> dict:
    async with get_session() as session:
        row = MediaRule(
            connection_id=connection_id,
            event_type=event_type,
            channel_id=channel_id,
            template_id=template_id,
            mention_role_id=mention_role_id,
        )
        session.add(row)
        await session.flush()
        payload = row.to_dict()

    return payload


async def remove_rule(rule_id: int) -> None:
    async with get_session() as session:
        await session.execute(delete(MediaRule).where(MediaRule.id == rule_id))


async def set_rule_enabled(rule_id: int, enabled: bool) -> None:
    async with get_session() as session:
        row = await session.get(MediaRule, rule_id)
        if row is not None:
            row.enabled = enabled


# ═══ Templates ═══════════════════════════════════════════════════════
# CRUD sur media_templates (§7, 4e concept "Announcement Template").
# content/embed_config/buttons restent du texte/JSON non résolu — la
# résolution des placeholders (utils/medialink/builders/placeholders.py)
# se fait au moment de l'ENVOI, jamais ici.

async def list_templates(guild_id: int) -> list[dict]:
    async with get_session() as session:
        result = await session.execute(
            select(MediaTemplate)
            .where(MediaTemplate.guild_id == guild_id)
            .order_by(MediaTemplate.name)
        )
        return [row.to_dict() for row in result.scalars().all()]


async def get_template(template_id: int) -> dict | None:
    async with get_session() as session:
        row = await session.get(MediaTemplate, template_id)
        return row.to_dict() if row is not None else None


async def add_template(
    guild_id: int,
    name: str,
    *,
    content: str | None = None,
    embed_config: dict | None = None,
    buttons: list | None = None,
) -> dict:
    async with get_session() as session:
        row = MediaTemplate(
            guild_id=guild_id,
            name=name,
            content=content,
            embed_config=embed_config,
            buttons=buttons,
        )
        session.add(row)
        await session.flush()
        return row.to_dict()


async def update_template(template_id: int, **fields) -> dict | None:
    """Met à jour uniquement les champs fournis (ex: update_template(id,
    content="...")). Champs acceptés : name, content, embed_config,
    buttons — tout autre nom est ignoré silencieusement pour éviter
    qu'un appelant ne touche accidentellement guild_id/id."""
    allowed = {"name", "content", "embed_config", "buttons"}
    async with get_session() as session:
        row = await session.get(MediaTemplate, template_id)
        if row is None:
            return None
        for key, value in fields.items():
            if key in allowed:
                setattr(row, key, value)
        await session.flush()
        return row.to_dict()


async def remove_template(template_id: int) -> None:
    """Supprime un template. Les règles qui le référencent repassent à
    template_id=NULL (ondelete='SET NULL' côté media_rules, cf. la
    migration) — elles ne sont PAS supprimées, elles perdent juste leur
    mise en forme et retombent sur un envoi sans template tant qu'une
    nouvelle n'est pas choisie."""
    async with get_session() as session:
        await session.execute(delete(MediaTemplate).where(MediaTemplate.id == template_id))