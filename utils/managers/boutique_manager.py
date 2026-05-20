"""
utils/managers/boutique_manager.py — CRUD + cache de la boutique.

DESIGN (validé) : table unique `shop_entries`, cache mémoire TTL 1 min,
lecture SYNC compatible V3 + écriture ASYNC via l'API.

──────────────────────────────────────────────────────────────────────────
Pourquoi un cache + lectures sync ?
──────────────────────────────────────────────────────────────────────────
Le moteur DB est async-only (asyncpg). Or `is_vip()` / `is_gold()` sont
appelés de façon SYNCHRONE un peu partout (héritage V3, notamment dans les
callbacks de View). On ne peut pas `await` dans une fonction sync ni relancer
l'event loop courant.

Solution : un cache en mémoire process rafraîchi en async (au boot, en tâche
de fond toutes les 60 s, et invalidé immédiatement après chaque écriture API).
Les lectures sync ne touchent QUE ce cache → instantané, zéro I/O, jamais
d'await. C'est le compromis classique « eventual consistency à 1 min » : un
ajout VIP via le site est visible au pire 60 s plus tard (ou tout de suite si
l'écriture passe par ce process et invalide le cache).

──────────────────────────────────────────────────────────────────────────
Cycle de vie
──────────────────────────────────────────────────────────────────────────
    bot.setup_hook():
        await refresh_cache()              # préchargement bloquant
        bot.loop.create_task(cache_refresher_loop())   # refresh périodique

    cog / view (sync) :
        if is_vip(user_id): ...
        if is_gold(guild_id): ...

    API FastAPI (async) :
        await add_entry(ShopRole.VIP, "123")   # invalide le cache ensuite
"""
from __future__ import annotations

import asyncio
import logging
import time

from sqlalchemy import delete, select

from utils.db.models.boutique import ShopEntry, ShopRole
from utils.db.session import get_session

log = logging.getLogger(__name__)

# Durée de vie du cache avant qu'un refresh soit considéré comme "périmé".
CACHE_TTL_SECONDS = 60

# ──────────────────────────────────────────────────────────────────────────
# État du cache (module-level, partagé dans le process)
#   _cache[ShopRole] -> set[str] de discord_id
# ──────────────────────────────────────────────────────────────────────────
_cache: dict[ShopRole, set[str]] = {role: set() for role in ShopRole}
_cache_loaded_at: float = 0.0          # time.monotonic() du dernier refresh OK
_cache_ready: bool = False             # True dès qu'un refresh a réussi une fois
_refresh_lock = asyncio.Lock()         # évite deux refresh concurrents


# ══════════════════════════════════════════════════════════════════════════
# 🔄 REFRESH (async) — remplit le cache depuis la DB
# ══════════════════════════════════════════════════════════════════════════

async def refresh_cache() -> None:
    """
    Recharge l'intégralité du cache depuis la DB.

    En cas d'erreur DB, on NE vide PAS le cache existant : on garde l'ancienne
    valeur (mieux qu'un cache vide qui refuserait tous les VIP). L'erreur est
    loguée et le prochain tick réessaiera.
    """
    global _cache, _cache_loaded_at, _cache_ready

    async with _refresh_lock:
        try:
            async with get_session() as session:
                result = await session.execute(
                    select(ShopEntry.role, ShopEntry.discord_id)
                )
                rows = result.all()
        except Exception:
            log.exception("Refresh cache boutique échoué — on garde l'ancien cache")
            return

        new_cache: dict[ShopRole, set[str]] = {role: set() for role in ShopRole}
        for role, discord_id in rows:
            new_cache[role].add(discord_id)

        _cache = new_cache
        _cache_loaded_at = time.monotonic()
        _cache_ready = True

        log.info(
            "Cache boutique rafraîchi : %d VIP, %d Gold+",
            len(_cache[ShopRole.VIP]),
            len(_cache[ShopRole.GOLD_PLUS]),
        )


async def cache_refresher_loop(interval: int = CACHE_TTL_SECONDS) -> None:
    """
    Boucle de fond : refresh toutes les `interval` secondes.
    À lancer via bot.loop.create_task() dans setup_hook().
    """
    log.info("Démarrage de la boucle de refresh boutique (toutes les %ds)", interval)
    while True:
        await asyncio.sleep(interval)
        await refresh_cache()


def cache_is_ready() -> bool:
    """True si au moins un refresh a réussi (cache exploitable)."""
    return _cache_ready


def cache_age_seconds() -> float:
    """Âge du cache en secondes (utile pour du monitoring/healthcheck)."""
    if not _cache_ready:
        return float("inf")
    return time.monotonic() - _cache_loaded_at


# ══════════════════════════════════════════════════════════════════════════
# 📖 LECTURES SYNC (compat V3) — tapent uniquement le cache mémoire
# ══════════════════════════════════════════════════════════════════════════

def _sync_contains(role: ShopRole, discord_id: str) -> bool:
    """
    Lecture sync pure cache. Ne fait JAMAIS d'I/O ni d'await.

    Si le cache n'est pas encore prêt (cas anormal : on précharge au boot avant
    d'accepter des commandes), on logue un warning et on renvoie False. Le
    préchargement bloquant dans setup_hook() rend ce cas quasi impossible en
    pratique.
    """
    if not _cache_ready:
        log.warning(
            "is_* appelé avant que le cache boutique soit prêt "
            "(role=%s, id=%s) → False par défaut",
            role.value,
            discord_id,
        )
        return False
    return discord_id in _cache[role]


def is_vip_id(user_id: int | str) -> bool:
    """True si l'utilisateur est VIP. Lecture sync instantanée."""
    return _sync_contains(ShopRole.VIP, str(user_id))


def is_gold_id(guild_id: int | str) -> bool:
    """True si le serveur a l'abonnement Gold+. Lecture sync instantanée."""
    return _sync_contains(ShopRole.GOLD_PLUS, str(guild_id))


def get_ids_sync(role: ShopRole) -> list[str]:
    """Renvoie la liste des discord_id d'un rôle (copie, depuis le cache)."""
    return sorted(_cache[role])


# ══════════════════════════════════════════════════════════════════════════
# 📚 LECTURES ASYNC — tapent la DB directement (pour l'API / les outils admin)
# ══════════════════════════════════════════════════════════════════════════

async def list_entries(role: ShopRole | None = None) -> dict[str, list[str]]:
    """
    Renvoie {role_value: [discord_id, ...]} depuis la DB (pas le cache).
    Si `role` est fourni, ne renvoie que ce rôle.
    """
    stmt = select(ShopEntry.role, ShopEntry.discord_id)
    if role is not None:
        stmt = stmt.where(ShopEntry.role == role)

    async with get_session() as session:
        rows = (await session.execute(stmt)).all()

    out: dict[str, list[str]] = {r.value: [] for r in ShopRole}
    for r, discord_id in rows:
        out[r.value].append(discord_id)
    return out


async def is_member_async(role: ShopRole, discord_id: int | str) -> bool:
    """Vérification async directe en DB (bypass cache)."""
    async with get_session() as session:
        found = await session.scalar(
            select(ShopEntry.id).where(
                ShopEntry.role == role,
                ShopEntry.discord_id == str(discord_id),
            )
        )
    return found is not None


# ══════════════════════════════════════════════════════════════════════════
# ✍️ ÉCRITURES ASYNC — appelées par l'API ; invalident le cache ensuite
# ══════════════════════════════════════════════════════════════════════════

async def add_entry(role: ShopRole, discord_id: int | str) -> bool:
    """
    Ajoute (role, discord_id). Idempotent : si déjà présent, ne fait rien.
    Renvoie True si une ligne a été créée, False si elle existait déjà.
    Rafraîchit le cache après écriture.
    """
    discord_id = str(discord_id)
    created = False

    async with get_session() as session:
        exists = await session.scalar(
            select(ShopEntry.id).where(
                ShopEntry.role == role,
                ShopEntry.discord_id == discord_id,
            )
        )
        if exists is None:
            session.add(ShopEntry(role=role, discord_id=discord_id))
            created = True
        # commit géré par get_session()

    if created:
        await refresh_cache()
        log.info("Ajout boutique : %s -> %s", role.value, discord_id)
    return created


async def remove_entry(role: ShopRole, discord_id: int | str) -> bool:
    """
    Retire (role, discord_id). Renvoie True si une ligne a été supprimée.
    Rafraîchit le cache après écriture.
    """
    discord_id = str(discord_id)

    async with get_session() as session:
        result = await session.execute(
            delete(ShopEntry).where(
                ShopEntry.role == role,
                ShopEntry.discord_id == discord_id,
            )
        )
        deleted = result.rowcount > 0

    if deleted:
        await refresh_cache()
        log.info("Retrait boutique : %s -> %s", role.value, discord_id)
    return deleted


def role_from_str(value: str) -> ShopRole:
    """
    Convertit une str ('VIP', 'Gold+') en ShopRole.
    Lève ValueError si inconnu (l'API renverra alors un 422/400).
    """
    for role in ShopRole:
        if role.value == value:
            return role
    raise ValueError(f"Rôle boutique inconnu : {value!r}")