"""
utils/managers/mod_automod_infraction_manager.py — Enregistrement + lecture
des infractions d'auto-modération.

Point d'entrée unique appelé par le listener automod à chaque détection.
Aucun cache : lectures faites par le staff (à la demande) ou par le futur
panel côté site (via requêtes SQL directes). Les écritures sont fréquentes
mais atomiques (une ligne indépendante par infraction).

Contient aussi des helpers de comptage pour :
  - historique d'un membre (list_recent_for_user)
  - statistiques globales par serveur (count_by_system, top_matched_terms)
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import desc, func, select

from utils.db.models.mod_automod_infraction import ModAutomodInfraction
from utils.db.session import get_session


MESSAGE_EXCERPT_MAX = 500


# ═══ Écriture ══════════════════════════════════════════════════════

async def register_infraction(
    *,
    guild_id: int,
    user_id: int,
    channel_id: int,
    system_key: str,
    matched_term: str | None = None,
    message_content: str | None = None,
) -> int:
    """
    Enregistre une infraction. Le message est tronqué à MESSAGE_EXCERPT_MAX
    caractères. Retourne l'ID de l'infraction créée.
    """
    excerpt: str | None = None
    if message_content:
        excerpt = message_content[:MESSAGE_EXCERPT_MAX]

    async with get_session() as session:
        row = ModAutomodInfraction(
            guild_id=guild_id,
            user_id=user_id,
            channel_id=channel_id,
            system_key=system_key,
            matched_term=matched_term,
            message_excerpt=excerpt,
        )
        session.add(row)
        await session.flush()
        return row.id


# ═══ Lectures ══════════════════════════════════════════════════════

async def list_recent_for_user(
    guild_id: int, user_id: int, *, limit: int = 50,
) -> list[dict]:
    """Infractions les plus récentes d'un membre sur ce serveur."""
    async with get_session() as session:
        rows = (await session.execute(
            select(ModAutomodInfraction)
            .where(
                ModAutomodInfraction.guild_id == guild_id,
                ModAutomodInfraction.user_id == user_id,
            )
            .order_by(desc(ModAutomodInfraction.created_at))
            .limit(limit)
        )).scalars().all()
    return [r.to_dict() for r in rows]


async def count_by_system(
    guild_id: int, *, since_days: int | None = 30,
) -> dict[str, int]:
    """
    Compte des infractions par sous-système sur `since_days`. Si since_days
    est None, compte tout l'historique.

    Retourne un dict {system_key: count}.
    """
    stmt = (
        select(ModAutomodInfraction.system_key, func.count().label("n"))
        .where(ModAutomodInfraction.guild_id == guild_id)
        .group_by(ModAutomodInfraction.system_key)
    )
    if since_days is not None:
        since = datetime.now(timezone.utc) - timedelta(days=since_days)
        stmt = stmt.where(ModAutomodInfraction.created_at >= since)

    async with get_session() as session:
        rows = (await session.execute(stmt)).all()
    return {system_key: n for system_key, n in rows}


async def top_matched_terms(
    guild_id: int, system_key: str, *, limit: int = 10, since_days: int | None = 30,
) -> list[tuple[str, int]]:
    """
    Top des `matched_term` les plus fréquents pour un système donné. Ignore
    les infractions sans matched_term. Utile pour "top mots bloqués" côté
    dashboard.
    """
    stmt = (
        select(ModAutomodInfraction.matched_term, func.count().label("n"))
        .where(
            ModAutomodInfraction.guild_id == guild_id,
            ModAutomodInfraction.system_key == system_key,
            ModAutomodInfraction.matched_term.is_not(None),
        )
        .group_by(ModAutomodInfraction.matched_term)
        .order_by(desc("n"))
        .limit(limit)
    )
    if since_days is not None:
        since = datetime.now(timezone.utc) - timedelta(days=since_days)
        stmt = stmt.where(ModAutomodInfraction.created_at >= since)

    async with get_session() as session:
        rows = (await session.execute(stmt)).all()
    return [(term, n) for term, n in rows]