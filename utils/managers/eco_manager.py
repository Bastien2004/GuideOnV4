"""
utils/managers/eco_manager.py — Système d'économie (/eco).
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import delete, select

from utils.db.models.eco import (
    DEFAULT_DAILY_AMOUNT,
    DEFAULT_LEADERBOARD_ENABLED,
    EcoAccount,
    EcoConfig,
    EcoTransactionLog,
    EcoTransactionType,
)
from utils.db.session import get_session

DAILY_COOLDOWN = timedelta(hours=24)


class EcoError(Exception):
    """Erreur métier /eco."""


class DailyCooldownError(EcoError):
    """/eco daily déjà réclamé, encore en cooldown."""

    def __init__(self, retry_after: timedelta) -> None:
        self.retry_after = retry_after
        super().__init__(
            f"Prochain /eco daily disponible dans {retry_after}."
        )


@dataclass
class EcoMutationResult:
    """Résultat d'une mutation de solde."""

    guild_id: int
    user_id: int
    old_balance: int
    new_balance: int
    amount_applied: int


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _as_aware_utc(dt: datetime) -> datetime:
    """Normalise un datetime pour le cooldown."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


# ============================================================
# 🔒 Verrous par guild (anti race condition)
# ============================================================

_locks: dict[int, asyncio.Lock] = {}


def _get_lock(guild_id: int) -> asyncio.Lock:
    """Retourne (ou crée) un Lock asyncio unique par guild."""
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
    "daily_amount": DEFAULT_DAILY_AMOUNT,
    "leaderboard_enabled": DEFAULT_LEADERBOARD_ENABLED,
}

_config_cache: dict[int, tuple[dict, float]] = {}
_config_cache_lock = asyncio.Lock()


def _default_config() -> dict:
    return DEFAULT_CONFIG.copy()


async def load_eco_config(guild_id: int) -> dict:
    """Charge la config /eco d'un serveur (cache 60s)."""
    now = time.monotonic()
    cached = _config_cache.get(guild_id)
    if cached is not None and (now - cached[1]) < CACHE_TTL_SECONDS:
        return cached[0].copy()

    async with get_session() as session:
        row = await session.get(EcoConfig, guild_id)
        cfg = row.to_dict() if row is not None else _default_config()

    _config_cache[guild_id] = (cfg, now)
    return cfg.copy()


async def save_eco_config(guild_id: int, partial: dict) -> dict:
    """Sauvegarde (partiellement) la config /eco d'un serveur."""
    allowed = set(DEFAULT_CONFIG.keys())
    clean = {k: v for k, v in partial.items() if k in allowed}

    async with _config_cache_lock:
        async with get_session() as session:
            row = await session.get(EcoConfig, guild_id)
            if row is None:
                merged = {**_default_config(), **clean}
                row = EcoConfig(guild_id=guild_id, **merged)
                session.add(row)
            else:
                for key, value in clean.items():
                    setattr(row, key, value)
            await session.flush()
            result = row.to_dict()

        _config_cache[guild_id] = (result, time.monotonic())

    return result.copy()


async def reset_eco_config(guild_id: int) -> dict:
    """Remet la config aux valeurs par défaut."""
    return await save_eco_config(guild_id, _default_config())


async def delete_eco_config(guild_id: int) -> bool:
    """Supprime la config d'un serveur."""
    async with _config_cache_lock:
        async with get_session() as session:
            res = await session.execute(
                delete(EcoConfig).where(EcoConfig.guild_id == guild_id)
            )
            deleted = res.rowcount > 0
        _config_cache.pop(guild_id, None)
    return deleted


# ============================================================
# 💰 Comptes / Solde
# ============================================================

async def _get_or_create_account(session, guild_id: int, user_id: int) -> EcoAccount:
    row = await session.get(EcoAccount, (guild_id, user_id))
    if row is None:
        row = EcoAccount(guild_id=guild_id, user_id=user_id)
        session.add(row)
        await session.flush()
    return row


async def get_balance(guild_id: int, user_id: int) -> dict:
    """Solde d'un membre sur CE serveur (0 si jamais crédité — pas de ligne créée en lecture)."""
    async with get_session() as session:
        row = await session.get(EcoAccount, (guild_id, user_id))
        if row is None:
            return {"guild_id": guild_id, "user_id": user_id, "balance": 0, "last_daily_at": None}
        return row.to_dict()


async def _log_transaction(
    session,
    *,
    guild_id: int,
    user_id: int,
    type_: EcoTransactionType,
    amount: int,
    balance_after: int,
    actor_id: Optional[int],
    reason: Optional[str],
) -> None:
    session.add(
        EcoTransactionLog(
            guild_id=guild_id,
            user_id=user_id,
            type=type_,
            amount=amount,
            balance_after=balance_after,
            actor_id=actor_id,
            reason=reason,
        )
    )


async def admin_add(
    guild_id: int,
    user_id: int,
    amount: int,
    *,
    actor_id: int,
    reason: Optional[str] = None,
) -> EcoMutationResult:
    """/eco gestion : un admin crédite un membre. `amount` doit être > 0."""
    amount = int(amount)
    if amount <= 0:
        raise ValueError("amount doit être strictement positif pour admin_add().")

    async with _get_lock(guild_id):
        async with get_session() as session:
            row = await _get_or_create_account(session, guild_id, user_id)
            old_balance = row.balance
            new_balance = old_balance + amount
            row.balance = new_balance
            await _log_transaction(
                session,
                guild_id=guild_id,
                user_id=user_id,
                type_=EcoTransactionType.ADMIN_ADD,
                amount=amount,
                balance_after=new_balance,
                actor_id=actor_id,
                reason=reason,
            )
            await session.flush()

    return EcoMutationResult(guild_id, user_id, old_balance, new_balance, amount)


async def admin_remove(
    guild_id: int,
    user_id: int,
    amount: int,
    *,
    actor_id: int,
    reason: Optional[str] = None,
) -> EcoMutationResult:
    """/eco gestion : un admin débite un membre. `amount` doit être > 0 (montant demandé).

    Le solde ne descend jamais sous 0 (pas de dette en V1) : si `amount` >
    solde courant, seul le solde disponible est retiré. Le delta réellement
    appliqué (négatif) est celui enregistré dans l'historique, pour que
    balance_after reste toujours cohérent avec balance_avant + amount_log.
    """
    amount = int(amount)
    if amount <= 0:
        raise ValueError("amount doit être strictement positif pour admin_remove().")

    async with _get_lock(guild_id):
        async with get_session() as session:
            row = await _get_or_create_account(session, guild_id, user_id)
            old_balance = row.balance
            new_balance = max(0, old_balance - amount)
            applied = new_balance - old_balance  # <= 0
            row.balance = new_balance
            await _log_transaction(
                session,
                guild_id=guild_id,
                user_id=user_id,
                type_=EcoTransactionType.ADMIN_REMOVE,
                amount=applied,
                balance_after=new_balance,
                actor_id=actor_id,
                reason=reason,
            )
            await session.flush()

    return EcoMutationResult(guild_id, user_id, old_balance, new_balance, applied)


async def claim_daily(guild_id: int, user_id: int) -> EcoMutationResult:
    """/eco daily : crédite daily_amount (config du serveur) si le cooldown glissant
    de 24h depuis la dernière réclamation est écoulé.

    Lève DailyCooldownError (avec le temps restant) si trop tôt — c'est à
    l'appelant (cog /eco daily) de l'attraper pour afficher un message clair.
    """
    config = await load_eco_config(guild_id)
    daily_amount = config["daily_amount"]

    async with _get_lock(guild_id):
        async with get_session() as session:
            row = await _get_or_create_account(session, guild_id, user_id)
            now = _utcnow()

            if row.last_daily_at is not None:
                elapsed = now - _as_aware_utc(row.last_daily_at)
                if elapsed < DAILY_COOLDOWN:
                    raise DailyCooldownError(DAILY_COOLDOWN - elapsed)

            old_balance = row.balance
            new_balance = old_balance + daily_amount
            row.balance = new_balance
            row.last_daily_at = now
            await _log_transaction(
                session,
                guild_id=guild_id,
                user_id=user_id,
                type_=EcoTransactionType.DAILY,
                amount=daily_amount,
                balance_after=new_balance,
                actor_id=None,
                reason=None,
            )
            await session.flush()

    return EcoMutationResult(guild_id, user_id, old_balance, new_balance, daily_amount)


# ============================================================
# 🏆 Classement
# ============================================================

async def get_leaderboard(guild_id: int, limit: int = 10, offset: int = 0) -> list[tuple[int, dict]]:
    """Classement des membres du serveur, trié par solde décroissant."""
    async with get_session() as session:
        rows = (
            await session.execute(select(EcoAccount).where(EcoAccount.guild_id == guild_id))
        ).scalars().all()

    ranked = sorted(rows, key=lambda r: r.balance, reverse=True)
    sliced = ranked[offset : offset + limit] if limit else ranked[offset:]
    return [(r.user_id, r.to_dict()) for r in sliced]


async def count_ranked(guild_id: int) -> int:
    """Nombre de comptes existants sur le serveur (pagination du leaderboard)."""
    async with get_session() as session:
        rows = (
            await session.execute(select(EcoAccount.user_id).where(EcoAccount.guild_id == guild_id))
        ).all()
    return len(rows)


# ============================================================
# 📜 Historique (support pour un futur /eco historique)
# ============================================================

async def get_transaction_history(guild_id: int, user_id: int, limit: int = 20) -> list[dict]:
    """Derniers mouvements d'un membre sur ce serveur, du plus récent au plus ancien."""
    async with get_session() as session:
        rows = (
            await session.execute(
                select(EcoTransactionLog)
                .where(
                    EcoTransactionLog.guild_id == guild_id,
                    EcoTransactionLog.user_id == user_id,
                )
                .order_by(EcoTransactionLog.created_at.desc(), EcoTransactionLog.id.desc())
                .limit(limit)
            )
        ).scalars().all()
    return [r.to_dict() for r in rows]