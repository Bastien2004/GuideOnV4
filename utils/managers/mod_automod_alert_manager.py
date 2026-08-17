"""
utils/managers/mod_automod_alert_manager.py — CRUD des alertes automod actives.

Table = mod_automod_active_alerts. Une ligne créée à chaque déclenchement
d'un mute auto. Aucune purge automatique : l'historique reste consultable
côté site (le volume attendu est faible — ce n'est PAS la table des
infractions, seulement celle des cas graves).
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select

from utils.db.models.mod_automod_active_alert import ModAutomodActiveAlert
from utils.db.session import get_session


async def create_alert(
    *,
    guild_id: int,
    user_id: int,
    channel_id: int,
    system_key: str,
    alert_channel_id: int,
    alert_message_id: int,
    matched_term: str | None = None,
    message_excerpt: str | None = None,
) -> int:
    """Insère une nouvelle alerte pending. Retourne son id."""
    async with get_session() as session:
        row = ModAutomodActiveAlert(
            guild_id=guild_id,
            user_id=user_id,
            channel_id=channel_id,
            system_key=system_key,
            alert_channel_id=alert_channel_id,
            alert_message_id=alert_message_id,
            matched_term=matched_term,
            message_excerpt=message_excerpt,
        )
        session.add(row)
        await session.flush()
        return row.id


async def get_alert_by_message(alert_message_id: int) -> dict | None:
    """Retrouve une alerte par l'id du message qui la porte. None si absente."""
    async with get_session() as session:
        row = await session.scalar(
            select(ModAutomodActiveAlert).where(
                ModAutomodActiveAlert.alert_message_id == alert_message_id,
            )
        )
    return row.to_dict() if row else None


async def mark_taken(alert_id: int, taken_by_user_id: int) -> dict | None:
    """
    Marque une alerte comme prise en charge. Idempotent : si déjà prise, ne
    modifie rien et retourne la ligne telle quelle (le caller peut détecter
    et afficher "déjà prise par X"). Retourne None si l'alerte n'existe pas.
    """
    async with get_session() as session:
        row = await session.get(ModAutomodActiveAlert, alert_id)
        if row is None:
            return None
        if row.taken_by_user_id is None:
            row.taken_by_user_id = taken_by_user_id
            row.taken_at = datetime.now(timezone.utc)
            await session.flush()
        return row.to_dict()