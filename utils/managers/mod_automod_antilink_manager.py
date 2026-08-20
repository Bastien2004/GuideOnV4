"""
utils/managers/mod_automod_antilink_manager.py — CRUD du système Anti Link.

Deux niveaux d'API, sur le même modèle que mod_automod_banword_manager.py :
  - config globale (enabled) via load_config / save_config / set_enabled
  - liste des extensions bloquées via list_extensions / add_extension /
    remove_extension / clear_extensions

Particularité : à la toute première activation (set_enabled(guild_id, True)
alors qu'aucune ligne config n'existait encore ET aucune extension n'est
déjà en base), la liste par défaut (_DEFAULT_EXTENSIONS) est auto-semée —
ça donne un point de départ utilisable direct, que l'admin peut ensuite
éditer via la page "Gérer" (comme le ferait un `alembic --autogenerate`
côté DB, mais pour la config d'un serveur).

Cache TTL 60s sur la config ET sur la liste d'extensions — les deux sont
lues à chaque message reçu quand le système est activé.
"""
from __future__ import annotations

import time

from sqlalchemy import delete, select

from utils.db.models.mod_automod_antilink import (
    ModAutomodAntilinkConfig,
    ModAutomodAntilinkExtension,
)
from utils.db.session import get_session

# Extensions bloquées par défaut, semées à la première activation.
_DEFAULT_EXTENSIONS: tuple[str, ...] = (
    ".exe", ".zip", ".rar", ".bat", ".cmd", ".js", ".vbs", ".scr", ".msi",
)

# ═══ Cache config ══════════════════════════════════════════════════
_CFG_TTL = 60
_cfg_cache: dict[int, tuple[dict, float]] = {}

# ═══ Cache extensions ═════════════════════════════════════════════════
_EXT_TTL = 60
_ext_cache: dict[int, tuple[list[str], float]] = {}


def _cfg_fresh(guild_id: int) -> dict | None:
    entry = _cfg_cache.get(guild_id)
    if entry is None:
        return None
    payload, ts = entry
    if time.monotonic() - ts > _CFG_TTL:
        return None
    return dict(payload)


def _cfg_prime(guild_id: int, payload: dict) -> None:
    _cfg_cache[guild_id] = (dict(payload), time.monotonic())


def _ext_fresh(guild_id: int) -> list[str] | None:
    entry = _ext_cache.get(guild_id)
    if entry is None:
        return None
    extensions, ts = entry
    if time.monotonic() - ts > _EXT_TTL:
        return None
    return list(extensions)


def _ext_prime(guild_id: int, extensions: list[str]) -> None:
    _ext_cache[guild_id] = (list(extensions), time.monotonic())


def _ext_invalidate(guild_id: int) -> None:
    _ext_cache.pop(guild_id, None)


def _normalize(extension: str) -> str:
    """
    Normalise une extension utilisateur : lowercase, strip, garantit un
    "." en préfixe. "EXE", ".exe", " .Exe " → ".exe".
    """
    cleaned = extension.strip().lower()
    if not cleaned:
        return ""
    if not cleaned.startswith("."):
        cleaned = f".{cleaned}"
    return cleaned


# ═══ Config (enabled) ═══════════════════════════════════════════════

async def load_config(guild_id: int) -> dict:
    """Retourne {'guild_id', 'enabled'}. Defaults: enabled=False."""
    cached = _cfg_fresh(guild_id)
    if cached is not None:
        return cached

    async with get_session() as session:
        row = await session.get(ModAutomodAntilinkConfig, guild_id)
        payload = row.to_dict() if row else {"guild_id": guild_id, "enabled": False}

    _cfg_prime(guild_id, payload)
    return dict(payload)


async def set_enabled(guild_id: int, enabled: bool) -> dict:
    """
    Active ou désactive le système pour un serveur. À la toute première
    activation (première ligne config créée), sème les extensions par
    défaut si la liste est encore vide.
    """
    async with get_session() as session:
        row = await session.get(ModAutomodAntilinkConfig, guild_id)
        first_time = row is None
        if row is None:
            row = ModAutomodAntilinkConfig(guild_id=guild_id, enabled=enabled)
            session.add(row)
        else:
            row.enabled = enabled
        await session.flush()
        payload = row.to_dict()

    _cfg_prime(guild_id, payload)

    if first_time and enabled:
        await _seed_defaults_if_empty(guild_id)

    return payload


async def _seed_defaults_if_empty(guild_id: int) -> None:
    """Sème _DEFAULT_EXTENSIONS si aucune extension n'est déjà configurée."""
    existing = await list_extensions(guild_id)
    if existing:
        return

    async with get_session() as session:
        for ext in _DEFAULT_EXTENSIONS:
            session.add(ModAutomodAntilinkExtension(guild_id=guild_id, extension=ext))

    _ext_invalidate(guild_id)


# ═══ Extensions bloquées ═══════════════════════════════════════════════

async def list_extensions(guild_id: int) -> list[str]:
    """Retourne les extensions bloquées d'un serveur, triées alphabétiquement."""
    cached = _ext_fresh(guild_id)
    if cached is not None:
        return cached

    async with get_session() as session:
        rows = (await session.execute(
            select(ModAutomodAntilinkExtension.extension)
            .where(ModAutomodAntilinkExtension.guild_id == guild_id)
            .order_by(ModAutomodAntilinkExtension.extension)
        )).scalars().all()

    extensions = list(rows)
    _ext_prime(guild_id, extensions)
    return list(extensions)


async def add_extension(guild_id: int, extension: str) -> bool:
    """Ajoute une extension. Retourne True si ajoutée, False si vide/déjà présente."""
    normalized = _normalize(extension)
    if not normalized or normalized == ".":
        return False

    async with get_session() as session:
        existing = await session.scalar(
            select(ModAutomodAntilinkExtension.id).where(
                ModAutomodAntilinkExtension.guild_id == guild_id,
                ModAutomodAntilinkExtension.extension == normalized,
            )
        )
        if existing is not None:
            return False
        session.add(ModAutomodAntilinkExtension(guild_id=guild_id, extension=normalized))

    _ext_invalidate(guild_id)
    return True


async def remove_extension(guild_id: int, extension: str) -> bool:
    """Retire une extension. Retourne True si retirée, False si absente."""
    normalized = _normalize(extension)
    if not normalized:
        return False

    async with get_session() as session:
        row = await session.scalar(
            select(ModAutomodAntilinkExtension).where(
                ModAutomodAntilinkExtension.guild_id == guild_id,
                ModAutomodAntilinkExtension.extension == normalized,
            )
        )
        if row is None:
            return False
        await session.delete(row)

    _ext_invalidate(guild_id)
    return True


async def clear_extensions(guild_id: int) -> int:
    """Supprime toutes les extensions bloquées d'un serveur. Retourne le nombre supprimé."""
    async with get_session() as session:
        result = await session.execute(
            delete(ModAutomodAntilinkExtension).where(
                ModAutomodAntilinkExtension.guild_id == guild_id
            )
        )
        deleted = result.rowcount or 0

    _ext_invalidate(guild_id)
    return int(deleted)