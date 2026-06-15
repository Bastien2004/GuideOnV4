"""
utils/managers/alpha_nota_manager.py — Config, état et historique du système de notations.

Cache TTL 60s pour la config. État et disponibilités non cachés (modifications fréquentes).

API publique :
  Config    : load_nota_config / save_nota_config / list_all_nota_configs
  État      : load_nota_state / set_state_fields / reset_nota_week
  Dispos    : get_available_operators / toggle_availability
  Historique: get_operator_history
  Algo      : generate_notation_ranges
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import datetime

from sqlalchemy import delete, select, update
from zoneinfo import ZoneInfo

from utils.db.models.alpha_nota_config import (
    AlphaNotaConfig, AlphaNotaWeekState,
    AlphaNotaAvailability, AlphaNotaHistory,
    NOTA_OPERATOR_GRADES,
)
from utils.db.models.alpha_staff import AlphaStaffMember, GRADE_LABELS, GRADE_PREFIXES
from utils.db.session import get_session

log = logging.getLogger(__name__)

PARIS_TZ = ZoneInfo("Europe/Paris")
CACHE_TTL = 60

_cfg_cache: dict[int, tuple[dict, float]] = {}
_lock = asyncio.Lock()

_CFG_FIELDS = {
    "channel_staff_id", "channel_public_id", "channel_logs_id", "role_id",
    "countries_count",
    "send_presence_weekday", "send_presence_hour", "send_presence_minute",
    "deadline_weekday", "deadline_hour", "deadline_minute",
    "send_public_weekday", "send_public_hour", "send_public_minute",
    "url_country_lookup", "enabled",
}

_CFG_DEFAULTS: dict = {
    "channel_staff_id": None, "channel_public_id": None,
    "channel_logs_id": None, "role_id": None,
    "countries_count": 238,
    "send_presence_weekday": None, "send_presence_hour": None, "send_presence_minute": None,
    "deadline_weekday": None, "deadline_hour": None, "deadline_minute": None,
    "send_public_weekday": None, "send_public_hour": None, "send_public_minute": None,
    "url_country_lookup": None, "enabled": True,
}

_STATE_DEFAULTS: dict = {
    "availability_message_id": None,
    "public_message_id": None,
    "reminder_sent": False,
    "assigned_ranges": "[]",
}

# ════════════════════════════════════════════════════════════
# ⏰ Utilitaires timing
# ════════════════════════════════════════════════════════════

def now_paris() -> datetime:
    return datetime.now(PARIS_TZ)


def is_time_now(weekday: int | None, hour: int | None, minute: int | None) -> bool:
    if weekday is None or hour is None or minute is None:
        return False
    now = now_paris()
    return (
        now.weekday() == weekday
        and now.hour == hour
        and abs(now.minute - minute) <= 1
    )


def is_past_deadline(weekday: int | None, hour: int | None, minute: int | None) -> bool:
    if weekday is None or hour is None or minute is None:
        return False
    now = now_paris()
    if now.weekday() > weekday:
        return True
    if now.weekday() == weekday:
        if now.hour > hour:
            return True
        if now.hour == hour and now.minute >= minute:
            return True
    return False


# ════════════════════════════════════════════════════════════
# 📋 Config
# ════════════════════════════════════════════════════════════

def _cfg_valid(guild_id: int) -> bool:
    c = _cfg_cache.get(guild_id)
    return c is not None and (time.monotonic() - c[1]) < CACHE_TTL


async def load_nota_config(guild_id: int) -> dict:
    if _cfg_valid(guild_id):
        return dict(_cfg_cache[guild_id][0])
    async with get_session() as session:
        row = await session.get(AlphaNotaConfig, guild_id)
        cfg = row.to_dict() if row else {"guild_id": guild_id, **_CFG_DEFAULTS.copy()}
    _cfg_cache[guild_id] = (cfg, time.monotonic())
    return dict(cfg)


async def save_nota_config(guild_id: int, **fields: object) -> dict:
    clean = {k: v for k, v in fields.items() if k in _CFG_FIELDS}
    if not clean:
        return await load_nota_config(guild_id)
    async with _lock:
        async with get_session() as session:
            row = await session.get(AlphaNotaConfig, guild_id)
            if row is None:
                row = AlphaNotaConfig(guild_id=guild_id, **{**_CFG_DEFAULTS.copy(), **clean})
                session.add(row)
            else:
                for k, v in clean.items():
                    setattr(row, k, v)
            await session.flush()
            result = row.to_dict()
        _cfg_cache[guild_id] = (result, time.monotonic())
    return dict(result)


async def list_all_nota_configs() -> list[dict]:
    """Retourne toutes les configs pour le loop. Non caché."""
    async with get_session() as session:
        rows = (await session.execute(select(AlphaNotaConfig))).scalars().all()
    return [r.to_dict() for r in rows]


# ════════════════════════════════════════════════════════════
# 📊 État de la semaine
# ════════════════════════════════════════════════════════════

async def load_nota_state(guild_id: int) -> dict:
    async with get_session() as session:
        row = await session.get(AlphaNotaWeekState, guild_id)
        return row.to_dict() if row else {"guild_id": guild_id, **_STATE_DEFAULTS.copy()}


async def set_state_fields(guild_id: int, **fields: object) -> None:
    """Met à jour des champs spécifiques de l'état."""
    allowed = {"availability_message_id", "public_message_id", "reminder_sent", "assigned_ranges"}
    clean = {k: v for k, v in fields.items() if k in allowed}
    if not clean:
        return
    async with get_session() as session:
        row = await session.get(AlphaNotaWeekState, guild_id)
        if row is None:
            row = AlphaNotaWeekState(guild_id=guild_id, **{**_STATE_DEFAULTS.copy(), **clean})
            session.add(row)
        else:
            for k, v in clean.items():
                setattr(row, k, v)


async def reset_nota_week(guild_id: int, assignments: list[tuple[int, int, int]]) -> None:
    """
    Après l'envoi public :
      1. Met à jour l'historique par opérateur (pour la rotation suivante)
      2. Remet l'état à zéro
      3. Vide les disponibilités
    """
    async with get_session() as session:
        # 1. Mettre à jour l'historique
        for start, end, discord_id in assignments:
            row = await session.get(AlphaNotaHistory, {"guild_id": guild_id, "discord_id": discord_id})
            if row is None:
                session.add(AlphaNotaHistory(
                    guild_id=guild_id, discord_id=discord_id,
                    last_range_start=start, last_range_end=end,
                ))
            else:
                row.last_range_start = start
                row.last_range_end = end

        # 2. Reset état
        state = await session.get(AlphaNotaWeekState, guild_id)
        if state is None:
            state = AlphaNotaWeekState(guild_id=guild_id, **_STATE_DEFAULTS.copy())
            session.add(state)
        else:
            state.availability_message_id = None
            state.reminder_sent = False
            state.assigned_ranges = "[]"

        # 3. Vider les disponibilités
        await session.execute(
            delete(AlphaNotaAvailability).where(AlphaNotaAvailability.guild_id == guild_id)
        )

    log.info("[NOTATIONS] Semaine resetée | guild=%d assignments=%d", guild_id, len(assignments))


# ════════════════════════════════════════════════════════════
# 👥 Disponibilités
# ════════════════════════════════════════════════════════════

async def get_available_operators(guild_id: int) -> list[int]:
    async with get_session() as session:
        rows = (await session.execute(
            select(AlphaNotaAvailability.discord_id)
            .where(AlphaNotaAvailability.guild_id == guild_id)
        )).scalars().all()
    return list(rows)


async def toggle_availability(guild_id: int, discord_id: int) -> tuple[bool, str]:
    """
    Toggle la disponibilité d'un opérateur.
    Retourne (is_now_available: bool, status_str: str).
    """
    async with get_session() as session:
        existing = await session.scalar(
            select(AlphaNotaAvailability.id).where(
                AlphaNotaAvailability.guild_id == guild_id,
                AlphaNotaAvailability.discord_id == discord_id,
            )
        )
        if existing is not None:
            await session.execute(
                delete(AlphaNotaAvailability).where(
                    AlphaNotaAvailability.guild_id == guild_id,
                    AlphaNotaAvailability.discord_id == discord_id,
                )
            )
            return False, "retiré ❌"
        else:
            session.add(AlphaNotaAvailability(guild_id=guild_id, discord_id=discord_id))
            return True, "ajouté ✅"


# ════════════════════════════════════════════════════════════
# 📜 Historique
# ════════════════════════════════════════════════════════════

async def get_operator_history(guild_id: int) -> dict[int, tuple[int | None, int | None]]:
    """Retourne {discord_id: (last_start, last_end)} pour tous les opérateurs du guild."""
    async with get_session() as session:
        rows = (await session.execute(
            select(AlphaNotaHistory).where(AlphaNotaHistory.guild_id == guild_id)
        )).scalars().all()
    return {r.discord_id: (r.last_range_start, r.last_range_end) for r in rows}


# ════════════════════════════════════════════════════════════
# 🔢 Algorithme de répartition (port fidèle du V3, bug last_ranges corrigé)
# ════════════════════════════════════════════════════════════

def _compute_ranges(total: int, n: int) -> list[tuple[int, int]]:
    base, reste = divmod(total, n)
    ranges, start = [], 1
    for i in range(n):
        size = base + (1 if i < reste else 0)
        ranges.append((start, start + size - 1))
        start += size
    return ranges


def _has_conflict(start: int, end: int, last_start: int | None, last_end: int | None) -> bool:
    if last_start is None or last_end is None:
        return False
    return not (end < last_start or start > last_end)


def _rotate(ops: list[dict], history: dict[int, tuple[int | None, int | None]]) -> list[dict]:
    """Trie les opérateurs selon l'ordre de la semaine précédente, puis décale d'1 position."""
    def key(op: dict) -> float:
        start = (history.get(op["discord_id"]) or (None, None))[0]
        return float(start) if start is not None else float("inf")

    sorted_ops = sorted(ops, key=key)
    has_history = any((history.get(op["discord_id"]) or (None,))[0] is not None for op in sorted_ops)
    if has_history and len(sorted_ops) > 1:
        return sorted_ops[1:] + sorted_ops[:1]
    return sorted_ops


def _avoid_repetition(
    raw_ranges: list[tuple[int, int]],
    ops: list[dict],
    history: dict[int, tuple[int | None, int | None]],
) -> list[tuple[int, int, int]]:
    assigned = [
        (r[0], r[1], op["discord_id"],
         _has_conflict(r[0], r[1], *history.get(op["discord_id"], (None, None))))
        for r, op in zip(raw_ranges, ops)
    ]
    if not any(a[3] for a in assigned):
        return [(a[0], a[1], a[2]) for a in assigned]

    for i in range(len(assigned)):
        if not assigned[i][3]:
            continue
        for j in range(i + 1, len(assigned)):
            a1, a2 = assigned[i], assigned[j]
            hist_i = history.get(ops[i]["discord_id"], (None, None))
            hist_j = history.get(ops[j]["discord_id"], (None, None))
            ok1 = not _has_conflict(a2[0], a2[1], *hist_i)
            ok2 = not _has_conflict(a1[0], a1[1], *hist_j)
            if ok1 and ok2:
                assigned[i] = (a2[0], a2[1], a1[2], False)
                assigned[j] = (a1[0], a1[1], a2[2], False)
                break

    return [(a[0], a[1], a[2]) for a in assigned]


async def generate_notation_ranges(
    guild_id: int,
    countries_count: int,
) -> list[tuple[int, int, int]]:
    """
    Génère les assignments de la semaine :
      1. Filtre les opérateurs disponibles (SM + Admin dans AlphaStaffMember)
      2. Rotation depuis l'historique
      3. Anti-répétition
    Retourne [(start, end, discord_id), ...]
    """
    # Charger les opérateurs disponibles
    available_ids = set(await get_available_operators(guild_id))
    if not available_ids:
        return []

    # Opérateurs disponibles parmi les SM/Admin
    async with get_session() as session:
        rows = (await session.execute(
            select(AlphaStaffMember).where(
                AlphaStaffMember.grade.in_(NOTA_OPERATOR_GRADES)
            )
        )).scalars().all()

    operators = [
        {"discord_id": r.discord_id, "pseudo_jeu": r.pseudo_jeu,
         "grade": r.grade, "skin_head_emoji": r.skin_head_emoji}
        for r in rows
        if r.discord_id in available_ids
    ]

    if not operators:
        return []

    history = await get_operator_history(guild_id)
    ops_rotated = _rotate(operators, history)
    raw_ranges = _compute_ranges(countries_count, len(ops_rotated))
    return _avoid_repetition(raw_ranges, ops_rotated, history)


# ════════════════════════════════════════════════════════════
# 🔧 Helpers pour les vues / le cog
# ════════════════════════════════════════════════════════════

async def get_all_nota_operators(guild_id: int) -> list[dict]:
    """Retourne tous les SM + Admin du guild pour l'affichage."""
    async with get_session() as session:
        rows = (await session.execute(select(AlphaStaffMember))).scalars().all()
    return [
        {
            "discord_id":      r.discord_id,
            "pseudo_jeu":      r.pseudo_jeu,
            "grade":           r.grade,
            "skin_head_emoji": r.skin_head_emoji,
            "label":           f"{GRADE_LABELS.get(r.grade, r.grade)} | {r.pseudo_jeu}",
        }
        for r in rows
        if r.grade in NOTA_OPERATOR_GRADES
    ]