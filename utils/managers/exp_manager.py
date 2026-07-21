"""
utils/managers/exp_manager.py — Systeme d'experience (EXP).

Remplace l'ancien stockage JSON V3 (utils/json_manager.py + utils/exp_manager.py
+ utils/exp_lock.py de la V3). Toute la logique de courbe niveau/EXP est reprise
a l'identique de la V3 (formule cubique, 200 niveaux, 7 tiers) : c'est un
refacto de stockage, pas un redesign de la progression.

Concurrence : un verrou asyncio par guild (comme la V3) protege les mutations
lecture-modification-ecriture (add/remove/reset). Un verrou par guild plutot
qu'un verrou global unique evite qu'un pic de messages sur UN serveur ne
bloque les gains d'EXP de tous les autres serveurs.
"""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Optional

from sqlalchemy import delete, select

from utils.db.models.exp import (
    DEFAULT_EXP_PER_MESSAGE,
    DEFAULT_EXP_PER_VOICE_MINUTE,
    ExpConfig,
    ExpUser,
)
from utils.db.session import get_session

log = logging.getLogger(__name__)

# ============================================================
# 🏔️ Rangs (paliers visuels)
# ============================================================

LEVEL_TIERS: list[dict] = [
    {"range": (0, 28), "name": "🪨 Coblithe"},
    {"range": (29, 57), "name": "⚙️ Ferrium"},
    {"range": (58, 85), "name": "🔅 Luminite"},
    {"range": (86, 114), "name": "🔹 Crysolite"},
    {"range": (115, 142), "name": "◼️ Pyronium"},
    {"range": (143, 171), "name": "🏮 Eclipsite"},
    {"range": (172, 200), "name": "💠 Zenthium"},
]

MAX_LEVEL = 200

# ============================================================
# 📈 Courbe d'EXP
# ============================================================
# EXP cumulative necessaire pour atteindre un niveau L (L >= 1)
# Formule : required_exp(L) = A*L + B*L^2 + C*L^3
A = 40.0
B = 2.3
C = 0.035

MAX_EXP_ALLOWED = 10_000_000  # Cap absolu de securite


def required_exp_for_level(level: int) -> int:
    """EXP cumulee necessaire pour atteindre `level` (capee a MAX_LEVEL)."""
    if level <= 0:
        return 0
    if level > MAX_LEVEL:
        level = MAX_LEVEL
    exp = A * level + B * (level ** 2) + C * (level ** 3)
    return int(round(exp))


def _build_level_table(max_level: int = MAX_LEVEL) -> list[int]:
    """Table des EXP cumulees pour chaque niveau 0..max_level."""
    table = [0]
    for level in range(1, max_level + 1):
        table.append(required_exp_for_level(level))
    return table


# Pre-calcul pour performance (recherche binaire dans exp_to_level).
LEVEL_EXP_TABLE = _build_level_table(MAX_LEVEL)


# ============================================================
# 🔁 Conversion EXP <-> Niveau
# ============================================================

def exp_to_level(total_exp: int) -> int:
    """Retourne le niveau atteint pour une EXP totale donnee."""
    if total_exp <= 0:
        return 0
    lo, hi = 0, MAX_LEVEL
    while lo <= hi:
        mid = (lo + hi) // 2
        if LEVEL_EXP_TABLE[mid] <= total_exp:
            lo = mid + 1
        else:
            hi = mid - 1
    return max(0, hi)


def level_to_required_exp(level: int) -> int:
    """EXP cumulee pour atteindre le niveau `level`."""
    if level < 0:
        return 0
    if level > MAX_LEVEL:
        level = MAX_LEVEL
    return LEVEL_EXP_TABLE[level]


def next_level_requirement(current_level: int) -> int:
    """EXP cumulee necessaire pour atteindre le niveau suivant."""
    target_level = min(current_level + 1, MAX_LEVEL)
    return LEVEL_EXP_TABLE[target_level]


def tier_name_for_level(level: int) -> str:
    """Retourne le nom de rang associe au niveau."""
    for tier in LEVEL_TIERS:
        lo, hi = tier["range"]
        if lo <= level <= hi:
            return tier["name"]
    return "Debutant"


def level_progress(total_exp: int) -> dict:
    """Niveau, rang, EXP courante, bornes du niveau, ratio de progression."""
    level = exp_to_level(total_exp)
    tier = tier_name_for_level(level)
    start_exp = level_to_required_exp(level)
    end_exp = next_level_requirement(level)
    span = max(1, end_exp - start_exp)
    progress = max(0.0, min(1.0, (total_exp - start_exp) / span))
    return {
        "level": level,
        "tier": tier,
        "current_exp": total_exp,
        "level_start_exp": start_exp,
        "next_level_exp": end_exp,
        "progress_ratio": progress,
    }


def text_progress_bar(ratio: float, size: int = 20) -> str:
    """Barre de progression textuelle."""
    ratio = max(0.0, min(1.0, ratio))
    filled = int(round(size * ratio))
    bar = "█" * filled + "─" * (size - filled)
    percent = int(round(ratio * 100))
    return f"[{bar}] {percent}%"


def apply_boost(amount: int, has_boost_role: bool, boost_percent: int) -> int:
    """Applique un boost en pourcentage si l'utilisateur a le role boost."""
    if has_boost_role and boost_percent > 0:
        return int(amount * (1 + (boost_percent / 100)))
    return amount


# ============================================================
# 🔒 Verrous par guild (anti race condition)
# ============================================================

_locks: dict[int, asyncio.Lock] = {}


def _get_lock(guild_id: int) -> asyncio.Lock:
    """Retourne (ou cree) un Lock asyncio unique par guild."""
    lock = _locks.get(guild_id)
    if lock is None:
        lock = asyncio.Lock()
        _locks[guild_id] = lock
    return lock


# ============================================================
# ⚙️ Configuration (par guild)
# ============================================================

CACHE_TTL_SECONDS = 60

DEFAULT_CONFIG: dict = {
    "enabled": False,
    "exp_per_message": DEFAULT_EXP_PER_MESSAGE,
    "exp_per_voice_minute": DEFAULT_EXP_PER_VOICE_MINUTE,
    "boost_role_id": None,
    "boost_percent": 0,
}

_config_cache: dict[int, tuple[dict, float]] = {}
_config_cache_lock = asyncio.Lock()


def _default_config() -> dict:
    return DEFAULT_CONFIG.copy()


async def load_exp_config(guild_id: int) -> dict:
    """Charge la config EXP d'un serveur (cache 60s)."""
    now = time.monotonic()
    cached = _config_cache.get(guild_id)
    if cached is not None and (now - cached[1]) < CACHE_TTL_SECONDS:
        return cached[0].copy()

    async with get_session() as session:
        row = await session.get(ExpConfig, guild_id)
        cfg = row.to_dict() if row is not None else _default_config()

    _config_cache[guild_id] = (cfg, now)
    return cfg.copy()


async def save_exp_config(guild_id: int, partial: dict) -> dict:
    """Sauvegarde (partiellement) la config EXP d'un serveur."""
    allowed = set(DEFAULT_CONFIG.keys())
    clean = {k: v for k, v in partial.items() if k in allowed}

    async with _config_cache_lock:
        async with get_session() as session:
            row = await session.get(ExpConfig, guild_id)
            if row is None:
                merged = {**_default_config(), **clean}
                row = ExpConfig(guild_id=guild_id, **merged)
                session.add(row)
            else:
                for key, value in clean.items():
                    setattr(row, key, value)
            await session.flush()
            result = row.to_dict()

        _config_cache[guild_id] = (result, time.monotonic())

    return result.copy()


async def reset_exp_config(guild_id: int) -> dict:
    """Remet la config aux valeurs par defaut."""
    return await save_exp_config(guild_id, _default_config())


async def delete_exp_config(guild_id: int) -> bool:
    """Supprime la config d'un serveur."""
    async with _config_cache_lock:
        async with get_session() as session:
            res = await session.execute(
                delete(ExpConfig).where(ExpConfig.guild_id == guild_id)
            )
            deleted = res.rowcount > 0
        _config_cache.pop(guild_id, None)
    return deleted


async def all_active_configs() -> list[dict]:
    """Configs dont enabled=True, avec guild_id inclus (pour le listener)."""
    async with get_session() as session:
        rows = (
            await session.execute(select(ExpConfig).where(ExpConfig.enabled.is_(True)))
        ).scalars().all()

    out = []
    for row in rows:
        item = row.to_dict()
        item["guild_id"] = row.guild_id
        out.append(item)
    return out


# ============================================================
# 🧮 Mutations d'EXP (gains / pertes / reset)
# ============================================================

@dataclass
class ExpMutationResult:
    """Resultat d'une mutation d'EXP (avant/apres pour detecter un level-up)."""

    total_exp: int
    old_level: int
    new_level: int

    @property
    def leveled_up(self) -> bool:
        return self.new_level > self.old_level


async def _get_or_create_user(session, guild_id: int, user_id: int) -> ExpUser:
    row = await session.get(ExpUser, (guild_id, user_id))
    if row is None:
        row = ExpUser(guild_id=guild_id, user_id=user_id, total_exp=0)
        session.add(row)
        await session.flush()
    return row


async def get_user_exp(guild_id: int, user_id: int) -> int:
    """EXP totale d'un membre (0 si jamais gagne)."""
    async with get_session() as session:
        row = await session.get(ExpUser, (guild_id, user_id))
        return row.total_exp if row is not None else 0


async def add_exp(
    guild_id: int,
    user_id: int,
    amount: int,
    *,
    has_boost_role: bool = False,
    boost_percent: int = 0,
) -> ExpMutationResult:
    """Ajoute de l'EXP a un membre (avec boost eventuel, cap MAX_EXP_ALLOWED)."""
    amount = max(0, int(amount))
    boosted = apply_boost(amount, has_boost_role, boost_percent)

    async with _get_lock(guild_id):
        async with get_session() as session:
            row = await _get_or_create_user(session, guild_id, user_id)
            old_total = row.total_exp
            new_total = min(old_total + boosted, MAX_EXP_ALLOWED)
            row.total_exp = new_total
            await session.flush()

    return ExpMutationResult(
        total_exp=new_total,
        old_level=exp_to_level(old_total),
        new_level=exp_to_level(new_total),
    )


async def remove_exp(guild_id: int, user_id: int, amount: int) -> ExpMutationResult:
    """Retire de l'EXP a un membre (sans passer en negatif)."""
    amount = max(0, int(amount))

    async with _get_lock(guild_id):
        async with get_session() as session:
            row = await _get_or_create_user(session, guild_id, user_id)
            old_total = row.total_exp
            new_total = max(0, old_total - amount)
            row.total_exp = new_total
            await session.flush()

    return ExpMutationResult(
        total_exp=new_total,
        old_level=exp_to_level(old_total),
        new_level=exp_to_level(new_total),
    )


async def reset_exp(guild_id: int, user_id: int) -> ExpMutationResult:
    """Reinitialise l'EXP d'un membre a 0."""
    async with _get_lock(guild_id):
        async with get_session() as session:
            row = await _get_or_create_user(session, guild_id, user_id)
            old_total = row.total_exp
            row.total_exp = 0
            await session.flush()

    return ExpMutationResult(total_exp=0, old_level=exp_to_level(old_total), new_level=0)


# ============================================================
# 🏆 Classement
# ============================================================

async def get_leaderboard(guild_id: int, limit: int = 100, offset: int = 0) -> list[tuple[int, int]]:
    """Classement des membres d'un serveur, tries par EXP totale decroissante."""
    async with get_session() as session:
        rows = (
            await session.execute(select(ExpUser).where(ExpUser.guild_id == guild_id))
        ).scalars().all()

    ranked = sorted(rows, key=lambda r: r.total_exp, reverse=True)
    sliced = ranked[offset : offset + limit] if limit else ranked[offset:]
    return [(r.user_id, r.total_exp) for r in sliced]


async def get_user_rank(guild_id: int, user_id: int) -> Optional[int]:
    """Position (1-indexee) d'un membre dans le classement, None si aucune EXP."""
    exp = await get_user_exp(guild_id, user_id)
    if exp <= 0:
        return None

    async with get_session() as session:
        rows = (
            await session.execute(select(ExpUser).where(ExpUser.guild_id == guild_id))
        ).scalars().all()

    ranked = sorted(rows, key=lambda r: r.total_exp, reverse=True)
    for index, row in enumerate(ranked, start=1):
        if row.user_id == user_id:
            return index
    return None
