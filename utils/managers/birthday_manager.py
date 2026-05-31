"""
utils/managers/birthday_manager.py — Système d'anniversaires utilisateurs.
"""
from __future__ import annotations

import asyncio
import calendar
import logging
import time
from datetime import date, datetime
from typing import Optional

from sqlalchemy import and_, delete, or_, select

from utils.db.models.birthday import BirthdayConfig, BirthdayUser
from utils.db.session import get_session

log = logging.getLogger(__name__)

CACHE_TTL_SECONDS = 60

MIN_YEAR = 1900

DEFAULT_CONFIG: dict = {
    "enabled": False,
    "channel_id": None,
    "role_id": None,
}

_config_cache: dict[int, tuple[dict, float]] = {}
_lock = asyncio.Lock()


def _default_config() -> dict:
    return DEFAULT_CONFIG.copy()


# ======================================================
# ============== HELPERS PURS (DATES) ==================
# ======================================================


_MAX_DAYS_PER_MONTH = {
    1: 31, 2: 29, 3: 31, 4: 30, 5: 31, 6: 30,
    7: 31, 8: 31, 9: 30, 10: 31, 11: 30, 12: 31,
}


def validate_date(day: int, month: int, year: Optional[int] = None) -> tuple[bool, str]:
    """Validation d'une date d'anniversaire."""

    if not isinstance(month, int) or not (1 <= month <= 12):
        return False, "Le mois doit être compris entre **1 et 12**."
    if not isinstance(day, int) or not (1 <= day <= 31):
        return False, "Le jour doit être compris entre **1 et 31**."
    max_day = _MAX_DAYS_PER_MONTH[month]
    if day > max_day:
        return False, f"Le **{day:02d}/{month:02d}** n'existe pas."
    if year is not None:
        current_year = datetime.now().year
        if not isinstance(year, int):
            return False, "L'année doit être un nombre entier."
        if year < MIN_YEAR:
            return False, f"L'année doit être supérieure ou égale à **{MIN_YEAR}**."
        if year > current_year:
            return False, "L'année ne peut pas être dans le **futur**."
        if day == 29 and month == 2 and not calendar.isleap(year):
            return False, f"**{year}** n'est pas une année bissextile (pas de 29/02)."
    return True, ""


def next_occurrence(day: int, month: int, today: date) -> date:
    """Renvoie la date de la prochaine occurrence."""

    year = today.year
    target_day = day
    if day == 29 and month == 2 and not calendar.isleap(year):
        target_day = 28

    candidate = date(year, month, target_day)
    if candidate < today:
        year += 1
        target_day = day
        if day == 29 and month == 2 and not calendar.isleap(year):
            target_day = 28
        candidate = date(year, month, target_day)
    return candidate


def compute_age(birth_year: int, on_date: date) -> int:
    """Calcule l'âge d'une personne."""
    return on_date.year - birth_year


# ======================================================
# ===================== CONFIG =========================
# ======================================================

async def load_birthday_config(guild_id: int) -> dict:
    """Charge la config birthday d'un serveur (défauts si absente, cache 1 min)."""
    now = time.monotonic()
    cached = _config_cache.get(guild_id)
    if cached is not None and (now - cached[1]) < CACHE_TTL_SECONDS:
        return cached[0].copy()

    async with get_session() as session:
        row = await session.get(BirthdayConfig, guild_id)
        cfg = row.to_dict() if row is not None else _default_config()

    _config_cache[guild_id] = (cfg, now)
    return cfg.copy()


async def save_birthday_config(guild_id: int, partial: dict) -> dict:
    """Sauvegarde la configuration du système de birthday."""

    allowed = set(DEFAULT_CONFIG.keys())
    clean = {k: v for k, v in partial.items() if k in allowed}

    async with _lock:
        async with get_session() as session:
            row = await session.get(BirthdayConfig, guild_id)
            if row is None:
                merged = {**_default_config(), **clean}
                row = BirthdayConfig(guild_id=guild_id, **merged)
                session.add(row)
            else:
                for k, v in clean.items():
                    setattr(row, k, v)
            await session.flush()
            result = row.to_dict()

        _config_cache[guild_id] = (result, time.monotonic())

    return result.copy()


async def reset_birthday_config(guild_id: int) -> dict:
    """Réinitialise la configuration du système de birthday sur un serveur."""
    return await save_birthday_config(guild_id, _default_config())


async def all_active_configs() -> list[dict]:
    """Récupère la configuration de tous les serveurs ayant le système activé."""

    async with get_session() as session:
        rows = (
            await session.execute(
                select(BirthdayConfig).where(BirthdayConfig.enabled.is_(True))
            )
        ).scalars().all()

    out = []
    for r in rows:
        d = r.to_dict()
        d["guild_id"] = r.guild_id
        out.append(d)
    return out


# ======================================================
# ======================= USERS ========================
# ======================================================

async def get_user_birthday(guild_id: int, user_id: int) -> Optional[dict]:
    """Retourne la date d'un utilisateur."""
    async with get_session() as session:
        row = await session.get(BirthdayUser, (guild_id, user_id))
        return row.to_dict() if row is not None else None


async def set_user_birthday(guild_id: int, user_id: int, day: int, month: int, year: Optional[int] = None) -> bool:
    """Création de la date d'anniversaire d'un utilisateur."""

    ok, _ = validate_date(day, month, year)
    if not ok:
        raise ValueError(f"Date invalide : {day:02d}/{month:02d}"
                         + (f"/{year}" if year else ""))

    async with _lock:
        async with get_session() as session:
            existing = await session.get(BirthdayUser, (guild_id, user_id))
            if existing is not None:
                return False
            row = BirthdayUser(
                guild_id=guild_id, user_id=user_id,
                day=day, month=month, year=year,
            )
            session.add(row)
            await session.flush()
    return True


async def delete_user_birthday(guild_id: int, user_id: int) -> bool:
    """Supprime la date d'un utilisateur."""

    async with _lock:
        async with get_session() as session:
            res = await session.execute(
                delete(BirthdayUser).where(
                    BirthdayUser.guild_id == guild_id,
                    BirthdayUser.user_id == user_id,
                )
            )
            return res.rowcount > 0


async def get_birthdays_today(guild_id: int, today: date) -> list[dict]:
    """Récupère les anniversaires à célébrer aujourd'hui."""

    conditions = [(today.day, today.month)]
    if today.month == 2 and today.day == 28 and not calendar.isleap(today.year):
        conditions.append((29, 2))

    async with get_session() as session:
        stmt = select(BirthdayUser).where(
            BirthdayUser.guild_id == guild_id,
            or_(*[
                and_(BirthdayUser.day == d, BirthdayUser.month == m)
                for d, m in conditions
            ])
        )
        rows = (await session.execute(stmt)).scalars().all()
    return [r.to_dict() for r in rows]


async def get_upcoming(guild_id: int, today: date, days: int = 30) -> list[tuple[date, dict]]:
    """Liste des prochains anniversaires à fêter."""

    async with get_session() as session:
        rows = (
            await session.execute(
                select(BirthdayUser).where(BirthdayUser.guild_id == guild_id)
            )
        ).scalars().all()

    out: list[tuple[date, dict]] = []
    for r in rows:
        nxt = next_occurrence(r.day, r.month, today)
        if (nxt - today).days <= days:
            out.append((nxt, r.to_dict()))
    out.sort(key=lambda x: x[0])
    return out


async def get_next(guild_id: int, today: date) -> Optional[tuple[date, list[dict]]]:
    """Liste les anniversaires à célébrer à la prochaine date d'anniversaire."""

    async with get_session() as session:
        rows = (
            await session.execute(
                select(BirthdayUser).where(BirthdayUser.guild_id == guild_id)
            )
        ).scalars().all()

    if not rows:
        return None

    upcoming = [(next_occurrence(r.day, r.month, today), r) for r in rows]
    upcoming.sort(key=lambda x: x[0])
    target_date = upcoming[0][0]
    same = [r.to_dict() for nxt, r in upcoming if nxt == target_date]
    return target_date, same


async def get_all_for_guild(guild_id: int) -> list[dict]:
    """Toutes les dates enregistrées d'un serveur."""

    async with get_session() as session:
        rows = (
            await session.execute(
                select(BirthdayUser).where(BirthdayUser.guild_id == guild_id)
            )
        ).scalars().all()
    return [r.to_dict() for r in rows]