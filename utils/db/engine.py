"""
utils/db/engine.py — Moteur SQLAlchemy ASYNC.

Ne fournit QUE le moteur bas niveau (engine, init_db, close_db). Pour une
session, importer get_session() depuis utils.db.session — c'est la seule
implémentation qui commit/rollback correctement (voir son docstring).
"""
from __future__ import annotations

import logging

from sqlalchemy.pool import NullPool
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from utils.settings import settings

log = logging.getLogger(__name__)

engine: AsyncEngine = create_async_engine(
    settings.database_url,
    echo=settings.database_echo,
    poolclass=NullPool,
)


async def init_db() -> None:
    """Vérifie que la DB est joignable au démarrage."""
    from sqlalchemy import text
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    log.info("🧷 Base de données connectée")


async def close_db() -> None:
    """À appeler à l'arrêt du bot pour fermer proprement les connexions."""
    await engine.dispose()