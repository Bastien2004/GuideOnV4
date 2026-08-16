"""
utils/managers/mod_automod_banword_manager.py — CRUD du système ban word.

Deux niveaux d'API :
  - config globale (enabled) via load_config / save_config
  - liste des mots via list_words / add_word / remove_word / clear_words

Cache TTL 60s sur la config (`load_config`) car lue à chaque message reçu.
Les mots sont cachés en même temps (une liste par guild) pour éviter le
round-trip DB sur chaque message quand le système est activé.
"""
from __future__ import annotations

import time

from sqlalchemy import delete, select

from utils.db.models.mod_automod_banword import (
    ModAutomodBanwordConfig,
    ModAutomodBanwordWord,
)
from utils.db.session import get_session

# ═══ Cache config ══════════════════════════════════════════════════
_CFG_TTL = 60
_cfg_cache: dict[int, tuple[dict, float]] = {}

# ═══ Cache mots ═════════════════════════════════════════════════════
_WORDS_TTL = 60
_words_cache: dict[int, tuple[list[str], float]] = {}


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


def _cfg_invalidate(guild_id: int) -> None:
    _cfg_cache.pop(guild_id, None)


def _words_fresh(guild_id: int) -> list[str] | None:
    entry = _words_cache.get(guild_id)
    if entry is None:
        return None
    words, ts = entry
    if time.monotonic() - ts > _WORDS_TTL:
        return None
    return list(words)


def _words_prime(guild_id: int, words: list[str]) -> None:
    _words_cache[guild_id] = (list(words), time.monotonic())


def _words_invalidate(guild_id: int) -> None:
    _words_cache.pop(guild_id, None)


# ═══ Config (enabled) ═══════════════════════════════════════════════

async def load_config(guild_id: int) -> dict:
    """Retourne {'guild_id', 'enabled'}. Defaults: enabled=False."""
    cached = _cfg_fresh(guild_id)
    if cached is not None:
        return cached

    async with get_session() as session:
        row = await session.get(ModAutomodBanwordConfig, guild_id)
        payload = row.to_dict() if row else {"guild_id": guild_id, "enabled": False}

    _cfg_prime(guild_id, payload)
    return dict(payload)


async def set_enabled(guild_id: int, enabled: bool) -> dict:
    """Active ou désactive le système pour un serveur."""
    async with get_session() as session:
        row = await session.get(ModAutomodBanwordConfig, guild_id)
        if row is None:
            row = ModAutomodBanwordConfig(guild_id=guild_id, enabled=enabled)
            session.add(row)
        else:
            row.enabled = enabled
        await session.flush()
        payload = row.to_dict()

    _cfg_prime(guild_id, payload)
    return dict(payload)


# ═══ Mots ═══════════════════════════════════════════════════════════

async def list_words(guild_id: int) -> list[str]:
    """Retourne les mots bannis d'un serveur, triés alphabétiquement."""
    cached = _words_fresh(guild_id)
    if cached is not None:
        return cached

    async with get_session() as session:
        rows = (await session.execute(
            select(ModAutomodBanwordWord.word)
            .where(ModAutomodBanwordWord.guild_id == guild_id)
            .order_by(ModAutomodBanwordWord.word)
        )).scalars().all()

    words = list(rows)
    _words_prime(guild_id, words)
    return list(words)


async def add_word(guild_id: int, word: str) -> bool:
    """
    Ajoute un mot à la liste. Le mot est lowercased+strip avant insert. Retourne
    True si ajouté, False si déjà présent (contrainte UNIQUE respectée).
    """
    normalized = word.strip().lower()
    if not normalized:
        return False

    async with get_session() as session:
        # Vérif préalable pour éviter l'IntegrityError bruyant.
        existing = await session.scalar(
            select(ModAutomodBanwordWord.id).where(
                ModAutomodBanwordWord.guild_id == guild_id,
                ModAutomodBanwordWord.word == normalized,
            )
        )
        if existing is not None:
            return False
        session.add(ModAutomodBanwordWord(guild_id=guild_id, word=normalized))

    _words_invalidate(guild_id)
    return True


async def remove_word(guild_id: int, word: str) -> bool:
    """Retire un mot. Retourne True si retiré, False si absent."""
    normalized = word.strip().lower()
    if not normalized:
        return False

    async with get_session() as session:
        row = await session.scalar(
            select(ModAutomodBanwordWord).where(
                ModAutomodBanwordWord.guild_id == guild_id,
                ModAutomodBanwordWord.word == normalized,
            )
        )
        if row is None:
            return False
        await session.delete(row)

    _words_invalidate(guild_id)
    return True


async def clear_words(guild_id: int) -> int:
    """Supprime tous les mots d'un serveur. Retourne le nombre supprimé."""
    async with get_session() as session:
        result = await session.execute(
            delete(ModAutomodBanwordWord).where(
                ModAutomodBanwordWord.guild_id == guild_id
            )
        )
        deleted = result.rowcount or 0

    _words_invalidate(guild_id)
    return int(deleted)