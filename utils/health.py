"""
utils/health.py — Collecte des métriques de santé du bot (système, DB, API,
environnement), extraite de cogs/dev/health.py — même traitement que
utils/guild_info.py.

Corrige au passage un bug : l'uptime lisait un attribut `bot.start_time`
qui n'était posé nulle part sur le bot -> toujours None -> "Non disponible"
affiché en permanence, quelle que soit la durée réelle de fonctionnement.
Utilise maintenant utils.uptime.uptime_seconds(), fiable puisque
utils/uptime.py pose START_TIME à l'import du module (donc au démarrage du
bot, indépendamment de tout attribut à poser manuellement ailleurs).

Ajouts par rapport à la version d'origine : latence mesurée pour les checks
DB et API (pas juste OK/KO), nombre de threads du process, version Python
et version discord.py.
"""
from __future__ import annotations

import asyncio
import logging
import platform
import time
from dataclasses import dataclass
from datetime import timedelta

import discord
import httpx
import psutil
from sqlalchemy import text

from utils.datetime_utils import format_duration
from utils.db.session import get_session
from utils.settings import settings
from utils.uptime import uptime_seconds

log = logging.getLogger(__name__)

_process = psutil.Process()
# Premier appel à cpu_percent() retourne toujours 0.0 (référence non encore
# établie) — on "amorce" la mesure dès l'import du module, avant la
# première vraie utilisation par la commande.
_process.cpu_percent(interval=None)


@dataclass
class HealthData:
    """Snapshot complet de l'état de santé, prêt pour views/dev/health_view.py."""
    uptime_str: str
    ping_ms: int
    guild_count: int
    user_count: int
    cogs_count: int
    commands_count: int
    ram_mb: float
    cpu_percent: float
    thread_count: int
    python_version: str
    discordpy_version: str
    db_ok: bool
    db_ms: float | None
    api_ok: bool
    api_ms: float | None


def status_emoji(ok: bool) -> str:
    return "🟢 OK" if ok else "🔴 KO"


# ============================================================
# 📁 Checks externes (DB / API), avec mesure de latence
# ============================================================

async def check_database() -> tuple[bool, float | None]:
    """Vérifie que la base de données répond (SELECT 1). Renvoie (ok, latence_ms)."""
    start = time.perf_counter()
    try:
        async with get_session() as session:
            await session.execute(text("SELECT 1"))
        return True, (time.perf_counter() - start) * 1000
    except Exception:
        log.warning("[DEV_HEALTH] Check DB échoué", exc_info=True)
        return False, None


async def check_api() -> tuple[bool, float | None]:
    """Vérifie que l'API FastAPI interne répond sur son endpoint /health. Renvoie (ok, latence_ms)."""
    host = settings.api_host
    if host in ("0.0.0.0", "::"):
        host = "127.0.0.1"
    url = f"http://{host}:{settings.api_port}/health"
    start = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(url)
        elapsed_ms = (time.perf_counter() - start) * 1000
        return resp.status_code == 200, elapsed_ms
    except Exception:
        log.warning("[DEV_HEALTH] Check API échoué (%s)", url, exc_info=True)
        return False, None


# ============================================================
# 🔍 Orchestration — extrait de cogs/dev/health.py
# ============================================================

async def gather_health_data(bot: discord.Client) -> HealthData:
    """Rassemble toutes les métriques nécessaires à l'affichage."""

    # ── Uptime (fiable — voir docstring du module) ─────────────
    uptime_str = format_duration(timedelta(seconds=uptime_seconds()))

    # ── Ressources système ──────────────────────────────────────
    ram_mb = _process.memory_info().rss / (1024 * 1024)
    cpu_percent = _process.cpu_percent(interval=None)
    thread_count = _process.num_threads()

    # ── Checks DB + API (en parallèle pour ne pas cumuler les latences) ──
    (db_ok, db_ms), (api_ok, api_ms) = await asyncio.gather(check_database(), check_api())

    return HealthData(
        uptime_str=uptime_str,
        ping_ms=round(bot.latency * 1000),
        guild_count=len(bot.guilds),
        user_count=sum(g.member_count or 0 for g in bot.guilds),
        cogs_count=len(bot.extensions),
        commands_count=len(bot.tree.get_commands()),
        ram_mb=ram_mb,
        cpu_percent=cpu_percent,
        thread_count=thread_count,
        python_version=platform.python_version(),
        discordpy_version=discord.__version__,
        db_ok=db_ok,
        db_ms=db_ms,
        api_ok=api_ok,
        api_ms=api_ms,
    )