"""
cogs/dev/health.py — État de santé global du bot GuideOn.
"""

from __future__ import annotations

import asyncio
import logging

import discord
import httpx
import psutil
from discord import app_commands, Interaction
from discord.ui import Container, LayoutView, Separator, TextDisplay
from sqlalchemy import text

from utils.control_admin import verifier_commande
from utils.track_commande import tracker_commande

from utils.datetime_utils import format_duration, now_utc
from utils.db.session import get_session
from utils.error_handler import handle_app_command_error
from utils.perm_dev import check_dev
from utils.settings import settings

log = logging.getLogger(__name__)

_process = psutil.Process()
# Premier appel à cpu_percent() retourne toujours 0.0 (référence non encore
# établie) — on "amorce" la mesure dès l'import du module, avant la
# première vraie utilisation par la commande.
_process.cpu_percent(interval=None)


# ============================================================
# 📁  Fonctions utilitaires — checks
# ============================================================

async def _check_database() -> bool:
    """Vérifie que la base de données répond (SELECT 1)."""
    try:
        async with get_session() as session:
            await session.execute(text("SELECT 1"))
        return True
    except Exception:
        log.warning("[DEV_HEALTH] Check DB échoué", exc_info=True)
        return False


async def _check_api() -> bool:
    """Vérifie que l'API FastAPI interne répond sur son endpoint /health."""
    host = settings.api_host
    if host in ("0.0.0.0", "::"):
        host = "127.0.0.1"
    url = f"http://{host}:{settings.api_port}/health"
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(url)
        return resp.status_code == 200
    except Exception:
        log.warning("[DEV_HEALTH] Check API échoué (%s)", url, exc_info=True)
        return False


def _status_emoji(ok: bool) -> str:
    return "🟢 OK" if ok else "🔴 KO"


# ============================================================
# 🧩 Construction de la vue
# ============================================================

def _build_health_view(
    bot: discord.Client,
    *,
    uptime_str: str,
    ping_ms: int,
    ram_mb: float,
    cpu_percent: float,
    db_ok: bool,
    api_ok: bool,
) -> LayoutView:
    view = LayoutView(timeout=None)
    c = Container()

    c.add_item(TextDisplay("# 🤖 GuideOn Health"))
    c.add_item(Separator())

    c.add_item(TextDisplay(
        f"**Version :** V4\n"
        f"**Uptime :** {uptime_str}\n"
        f"**Ping Discord :** {ping_ms}ms"
    ))
    c.add_item(Separator())

    c.add_item(TextDisplay(
        f"**Serveurs :** {len(bot.guilds)}\n"
        f"**Utilisateurs :** {sum(g.member_count or 0 for g in bot.guilds)}"
    ))
    c.add_item(Separator())

    c.add_item(TextDisplay(
        f"**Cogs chargés :** {len(bot.extensions)}\n"
        f"**Slash Commands :** {len(bot.tree.get_commands())}"
    ))
    c.add_item(Separator())

    c.add_item(TextDisplay(
        f"**RAM :** {ram_mb:.0f} MB\n"
        f"**CPU :** {cpu_percent:.1f} %"
    ))
    c.add_item(Separator())

    c.add_item(TextDisplay(
        f"**Database :** {_status_emoji(db_ok)}\n"
        f"**API :** {_status_emoji(api_ok)}"
    ))
    c.add_item(Separator())
    c.add_item(TextDisplay("-# GuideOn Studio"))

    view.add_item(c)
    return view


# ════════════════════════════════════════════════════════════
# 🧭 Commande : /dev health
# ════════════════════════════════════════════════════════════

@app_commands.guild_only()
@app_commands.checks.cooldown(1, 10)
@app_commands.command(name="health", description="🤖 [DEV] État de santé global du bot")
async def health(interaction: Interaction) -> None:

    # 🔐 Vérification des permissions.
    if not await check_dev(interaction, "consulter l'**état de santé** du bot"):
        return

    # 🕒 Defer.
    try:
        await interaction.response.defer(ephemeral=True)
    except (discord.NotFound, discord.HTTPException):
        return

    # ⚙️ Activation commande.
    if not await verifier_commande(interaction, "dev_health"):
        return

    # 📊 Tracking.
    await tracker_commande(interaction, "dev_health")

    bot = interaction.client

    # ── Uptime ────────────────────────────────────────────────
    start_time = getattr(bot, "start_time", None)
    uptime_str = format_duration(now_utc() - start_time) if start_time else "Non disponible"

    # ── Ressources système ──────────────────────────────────────
    ram_mb = _process.memory_info().rss / (1024 * 1024)
    cpu_percent = _process.cpu_percent(interval=None)

    # ── Checks DB + API (en parallèle pour ne pas cumuler les latences) ──
    db_ok, api_ok = await asyncio.gather(_check_database(), _check_api())

    view = _build_health_view(
        bot,
        uptime_str=uptime_str,
        ping_ms=round(bot.latency * 1000),
        ram_mb=ram_mb,
        cpu_percent=cpu_percent,
        db_ok=db_ok,
        api_ok=api_ok,
    )

    await interaction.followup.send(view=view, ephemeral=True)


# ============================================================
# ❌ Gestion des erreurs
# ============================================================

@health.error
async def health_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    await handle_app_command_error(interaction, error)