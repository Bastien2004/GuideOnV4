"""
views/dev/health_view.py — Vue d'état de santé du bot, extraite de
cogs/dev/health.py — même traitement que views/dev/guild_info_view.py.

Reste en LayoutView simple, PAS BaseLayoutView : réponse éphémère one-shot
sans aucun composant interactif.

Vue retravaillée par rapport à l'original : section Environnement (Python /
discord.py), latences DB/API affichées, nombre de threads du process.
"""
from __future__ import annotations

from discord.ui import Container, LayoutView, Separator, TextDisplay

from utils.health import HealthData, status_emoji


def _format_latency(ms: float | None) -> str:
    return f"{ms:.0f}ms" if ms is not None else "—"


# ============================================================
# 🧩 Construction de la vue
# ============================================================

def build_health_view(data: HealthData) -> LayoutView:
    """Construction de la view."""
    view = LayoutView(timeout=None)
    c = Container()

    c.add_item(TextDisplay("# 🤖 GuideOn Health"))
    c.add_item(Separator())

    c.add_item(TextDisplay(
        f"**Version :** V4\n"
        f"**Python :** {data.python_version}\n"
        f"**discord.py :** {data.discordpy_version}"
    ))
    c.add_item(Separator())

    c.add_item(TextDisplay(
        f"**Uptime :** {data.uptime_str}\n"
        f"**Ping Discord :** {data.ping_ms}ms"
    ))
    c.add_item(Separator())

    c.add_item(TextDisplay(
        f"**Serveurs :** {data.guild_count}\n"
        f"**Utilisateurs :** {data.user_count}"
    ))
    c.add_item(Separator())

    c.add_item(TextDisplay(
        f"**Cogs chargés :** {data.cogs_count}\n"
        f"**Slash Commands :** {data.commands_count}"
    ))
    c.add_item(Separator())

    c.add_item(TextDisplay(
        f"**RAM :** {data.ram_mb:.0f} MB\n"
        f"**CPU :** {data.cpu_percent:.1f} %\n"
        f"**Threads :** {data.thread_count}"
    ))
    c.add_item(Separator())

    c.add_item(TextDisplay(
        f"**Database :** {status_emoji(data.db_ok)} ({_format_latency(data.db_ms)})\n"
        f"**API :** {status_emoji(data.api_ok)} ({_format_latency(data.api_ms)})"
    ))
    c.add_item(Separator())
    c.add_item(TextDisplay("-# GuideOn Studio"))

    view.add_item(c)
    return view