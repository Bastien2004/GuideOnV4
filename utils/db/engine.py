"""
utils/db/engine.py — Moteur SQLAlchemy ASYNC.
"""
from __future__ import annotations

import logging
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from utils.settings import settings

log = logging.getLogger(__name__)

engine: AsyncEngine = create_async_engine(
    settings.database_url,
    echo=settings.database_echo,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    pool_recycle=1800,
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