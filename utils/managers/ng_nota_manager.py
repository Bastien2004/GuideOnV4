"""
utils/managers/ng_nota_manager.py — Gestion du système de notations multi-serveurs.

Refonte multi-serveurs phase 9 : remplace utils/managers/alpha_nota_manager.py.
Même API, clé `server` (nom NGServer) au lieu de `guild_id`.

API :
    await load_nota_config(server) -> dict
    await save_nota_config(server, **fields) -> dict
    await load_nota_state(server) -> dict
    await set_state_fields(server, **fields) -> None
    await reset_nota_week(server, assignments) -> None
    async def get_available_operators(server) -> list[int]
    async def toggle_availability(server, discord_id) -> tuple[bool, str]
    async def get_operator_history(server) -> dict[int, tuple[int | None, int | None]]
    async def generate_notation_ranges(server, countries_count) -> list[tuple[int, int, int]]
    async def get_all_nota_operators(server) -> list[dict]
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import delete, select

from utils.db.models.staff_grades import GRADE_LABELS
from utils.db.models.ng_nota_config import (
    NOTA_OPERATOR_GRADES,
    NGNotaAvailability,
    NGNotaConfig,
    NGNotaHistory,
    NGNotaWeekState,
)
from utils.db.models.ng_staff import NGStaffMember
from utils.db.session import get_session

log = logging.getLogger(__name__)


# ============================================================
# 📦 Gestion du cache
# ============================================================

PARIS_TZ = ZoneInfo("Europe/Paris")
CACHE_TTL = 60
_cfg_cache: dict[str, tuple[dict, float]] = {}
_lock = asyncio.Lock()


# ============================================================
# 📋 Constantes
# ============================================================

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


# ============================================================
# 🕛 Fonctions utilitaires (temps)
# ============================================================

def now_paris() -> datetime:
    """Retourne l'heure actuelle à Paris."""
    return datetime.now(PARIS_TZ)


def is_time_now(weekday: int | None, hour: int | None, minute: int | None) -> bool:
    """Vérifie si l'heure actuelle correspond à la configuration (±1 minute)."""
    if weekday is None or hour is None or minute is None:
        return False
    now = now_paris()
    return (
        now.weekday() == weekday
        and now.hour == hour
        and abs(now.minute - minute) <= 1
    )


def is_past_deadline(weekday: int | None, hour: int | None, minute: int | None) -> bool:
    """Vérifie si l'heure actuelle est après la deadline."""
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


# ============================================================
# ⚒️ Fonctions utilitaires (config)
# ============================================================

def _cfg_valid(server: str) -> bool:
    """Vérifie que le cache est valide."""
    c = _cfg_cache.get(server)
    return c is not None and (time.monotonic() - c[1]) < CACHE_TTL


async def load_nota_config(server: str) -> dict:
    """Charge la configuration d'un serveur."""
    if _cfg_valid(server):
        return dict(_cfg_cache[server][0])
    async with get_session() as session:
        row = await session.get(NGNotaConfig, server)
        cfg = row.to_dict() if row else {"server": server, **_CFG_DEFAULTS.copy()}
    _cfg_cache[server] = (cfg, time.monotonic())
    return dict(cfg)


async def save_nota_config(server: str, **fields: object) -> dict:
    """Sauvegarde la configuration d'un serveur."""
    clean = {k: v for k, v in fields.items() if k in _CFG_FIELDS}
    if not clean:
        return await load_nota_config(server)
    async with _lock:
        async with get_session() as session:
            row = await session.get(NGNotaConfig, server)
            if row is None:
                row = NGNotaConfig(server=server, **{**_CFG_DEFAULTS.copy(), **clean})
                session.add(row)
            else:
                for k, v in clean.items():
                    setattr(row, k, v)
            await session.flush()
            result = row.to_dict()
        _cfg_cache[server] = (result, time.monotonic())
    return dict(result)


async def list_all_nota_configs() -> list[dict]:
    """Retourne toutes les configurations de notations (tous serveurs)."""
    async with get_session() as session:
        rows = (await session.execute(select(NGNotaConfig))).scalars().all()
    return [r.to_dict() for r in rows]


# ============================================================
# 📊 Fonctions utilitaires (état actuel - debug)
# ============================================================

async def load_nota_state(server: str) -> dict:
    """Charge l'état de la semaine en cours pour un serveur."""
    async with get_session() as session:
        row = await session.get(NGNotaWeekState, server)
        return row.to_dict() if row else {"server": server, **_STATE_DEFAULTS.copy()}


async def set_state_fields(server: str, **fields: object) -> None:
    """Met à jour des champs spécifiques de l'état d'un serveur."""
    allowed = {"availability_message_id", "public_message_id", "reminder_sent", "assigned_ranges"}
    clean = {k: v for k, v in fields.items() if k in allowed}
    if not clean:
        return
    async with get_session() as session:
        row = await session.get(NGNotaWeekState, server)
        if row is None:
            row = NGNotaWeekState(server=server, **{**_STATE_DEFAULTS.copy(), **clean})
            session.add(row)
        else:
            for k, v in clean.items():
                setattr(row, k, v)


async def reset_nota_week(server: str, assignments: list[tuple[int, int, int]]) -> None:
    """Tâche de réinitialisation pour la prochaine semaine de notations d'un serveur."""
    async with get_session() as session:
        for start, end, discord_id in assignments:
            row = await session.get(NGNotaHistory, {"server": server, "discord_id": discord_id})
            if row is None:
                session.add(NGNotaHistory(
                    server=server, discord_id=discord_id,
                    last_range_start=start, last_range_end=end,
                ))
            else:
                row.last_range_start = start
                row.last_range_end = end

        state = await session.get(NGNotaWeekState, server)
        if state is None:
            state = NGNotaWeekState(server=server, **_STATE_DEFAULTS.copy())
            session.add(state)
        else:
            state.availability_message_id = None
            state.reminder_sent = False
            state.assigned_ranges = "[]"

        await session.execute(
            delete(NGNotaAvailability).where(NGNotaAvailability.server == server)
        )

    log.info("[NOTATIONS] Reset notations effectué | server=%s assignments=%d", server, len(assignments))


# ============================================================
# ✅ Fonctions utilitaires (présence)
# ============================================================

async def get_available_operators(server: str) -> list[int]:
    """Renvoie la liste des discord_id des opérateurs disponibles pour un serveur."""
    async with get_session() as session:
        rows = (await session.execute(
            select(NGNotaAvailability.discord_id)
            .where(NGNotaAvailability.server == server)
        )).scalars().all()
    return list(rows)


async def toggle_availability(server: str, discord_id: int) -> tuple[bool, str]:
    """Gestion de la présence d'un opérateur pour un serveur."""
    async with get_session() as session:
        existing = await session.scalar(
            select(NGNotaAvailability.id).where(
                NGNotaAvailability.server == server,
                NGNotaAvailability.discord_id == discord_id,
            )
        )
        if existing is not None:
            await session.execute(
                delete(NGNotaAvailability).where(
                    NGNotaAvailability.server == server,
                    NGNotaAvailability.discord_id == discord_id,
                )
            )
            return False, "retiré ❌"
        else:
            session.add(NGNotaAvailability(server=server, discord_id=discord_id))
            return True, "ajouté ✅"


# ============================================================
# 📑 Fonctions utilitaires (historique)
# ============================================================

async def get_operator_history(server: str) -> dict[int, tuple[int | None, int | None]]:
    """Renvoie les pays notés de la semaine précédente pour chaque opérateur d'un serveur."""
    async with get_session() as session:
        rows = (await session.execute(
            select(NGNotaHistory).where(NGNotaHistory.server == server)
        )).scalars().all()
    return {r.discord_id: (r.last_range_start, r.last_range_end) for r in rows}


# ============================================================
# 📑 Fonctions utilitaires (répartition)
# ============================================================

def _compute_ranges(total: int, n: int) -> list[tuple[int, int]]:
    """Divise les pays en n partie le plus également possible."""
    base, reste = divmod(total, n)
    ranges, start = [], 1
    for i in range(n):
        size = base + (1 if i < reste else 0)
        ranges.append((start, start + size - 1))
        start += size
    return ranges


def _has_conflict(start: int, end: int, last_start: int | None, last_end: int | None) -> bool:
    """Vérifie si les parts de pays à noter par un op sont en conflit avec la semaine précédente."""
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


def _avoid_repetition(raw_ranges: list[tuple[int, int]], ops: list[dict], history: dict[int, tuple[int | None, int | None]]) -> list[tuple[int, int, int]]:
    """Évite de réassigner le même bloc de pays à un opérateur que la semaine précédente."""
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


async def generate_notation_ranges(server: str, countries_count: int) -> list[tuple[int, int, int]]:
    """Gère l'assignation des pays à noter par opérateur, pour un serveur."""
    available_ids = set(await get_available_operators(server))
    if not available_ids:
        return []

    async with get_session() as session:
        rows = (await session.execute(
            select(NGStaffMember).where(
                NGStaffMember.server == server,
                NGStaffMember.grade.in_(NOTA_OPERATOR_GRADES),
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

    history = await get_operator_history(server)
    ops_rotated = _rotate(operators, history)
    raw_ranges = _compute_ranges(countries_count, len(ops_rotated))
    return _avoid_repetition(raw_ranges, ops_rotated, history)


# ============================================================
# 💻 Fonctions utilitaires (affichage)
# ============================================================

async def get_all_nota_operators(server: str) -> list[dict]:
    """Retourne la liste des OPs d'un serveur pour l'affichage."""
    async with get_session() as session:
        rows = (
            await session.execute(select(NGStaffMember).where(NGStaffMember.server == server))
        ).scalars().all()
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
