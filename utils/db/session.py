"""
utils/db/session.py — Gestion des sessions DB en ASYNC.

Pattern :
- crée une session
- commit en sortie normale
- rollback sur exception
- ferme la session dans tous les cas

Usage :
    async with get_session() as session:
        result = await session.execute(...)
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from utils.db.engine import engine


_async_session_factory = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    autoflush=False,
)

@asynccontextmanager
async def get_session() -> AsyncIterator[AsyncSession]:
    """Manager de session DB"""
    session = _async_session_factory()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()