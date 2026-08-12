"""
tests/conftest.py — Setup commun pytest : env de test + DB SQLite en mémoire.

Les managers (utils.managers.ng_server_manager, permission_rbac_manager)
importent `get_session` depuis utils.db.session au chargement du module.
Pour les tests, on monkeypatch cette référence *dans chaque module manager*
pour pointer vers une session SQLite en mémoire au lieu du Postgres de prod
configuré dans utils.settings — aucune connexion réseau n'est jamais faite
par la suite de tests.
"""
from __future__ import annotations

import os

# Doit être posé AVANT tout import de utils.settings (sinon pydantic-settings
# lève une erreur de validation : discord_token est un champ obligatoire).
os.environ.setdefault("DISCORD_TOKEN", "test-token-not-a-real-secret")

import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool


@pytest_asyncio.fixture
async def db_engine():
    """Moteur SQLite en mémoire, partagé entre connexions (StaticPool)."""
    from utils.db.models import Base

    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def patched_get_session(db_engine, monkeypatch):
    """
    Remplace get_session dans les modules managers testés par une session
    liée à la DB SQLite en mémoire du test en cours.
    """
    from contextlib import asynccontextmanager

    session_factory = async_sessionmaker(
        bind=db_engine, expire_on_commit=False, autoflush=False
    )

    @asynccontextmanager
    async def _test_get_session():
        session = session_factory()
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

    import utils.managers.ng_nota_manager as ng_nota_manager
    import utils.managers.ng_onu_manager as ng_onu_manager
    import utils.managers.ng_rank_config_manager as ng_rank_config_manager
    import utils.managers.ng_role_react_manager as ng_role_react_manager
    import utils.managers.ng_server_manager as ng_server_manager
    import utils.managers.ng_staff_manager as ng_staff_manager
    import utils.managers.notations_manager as notations_manager
    import utils.managers.onu_manager as onu_manager
    import utils.managers.permission_rbac_manager as permission_rbac_manager

    monkeypatch.setattr(ng_server_manager, "get_session", _test_get_session)
    monkeypatch.setattr(permission_rbac_manager, "get_session", _test_get_session)
    monkeypatch.setattr(ng_staff_manager, "get_session", _test_get_session)
    monkeypatch.setattr(ng_rank_config_manager, "get_session", _test_get_session)
    monkeypatch.setattr(ng_onu_manager, "get_session", _test_get_session)
    monkeypatch.setattr(onu_manager, "get_session", _test_get_session)
    monkeypatch.setattr(ng_nota_manager, "get_session", _test_get_session)
    monkeypatch.setattr(notations_manager, "get_session", _test_get_session)
    monkeypatch.setattr(ng_role_react_manager, "get_session", _test_get_session)

    # Chaque test démarre avec un cache manager vide, pas de fuite entre tests.
    ng_server_manager._by_guild = {}
    ng_server_manager._by_name = {}
    ng_server_manager._cache_ready = False
    ng_staff_manager._cache = {}
    ng_rank_config_manager._cache = {}
    ng_onu_manager._cache = {}
    ng_nota_manager._cfg_cache = {}
    notations_manager._cache = None
    notations_manager._cache_ready = False
    notations_manager._cache_loaded_at = 0.0
    ng_role_react_manager._cfg_cache = {}
    ng_role_react_manager._list_cache = {}

    from utils.managers.permission_rbac_manager import _GradeCache
    permission_rbac_manager._cache = _GradeCache()
    permission_rbac_manager._cache_ready = False
    permission_rbac_manager._cache_loaded_at = 0.0

    return session_factory
