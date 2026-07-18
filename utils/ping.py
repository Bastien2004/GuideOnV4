"""
utils/ping.py — Récupération et classification de la latence du bot,
extrait de cogs/commande/ping.py.
"""
from __future__ import annotations

from discord.ext import commands


def get_latency_ms(bot: commands.Bot) -> int:
    """Latence WebSocket du bot, en millisecondes (arrondie)."""
    return round(bot.latency * 1000)


def get_latency_status(latency_ms: int) -> tuple[str, str]:
    """Retourne l'emoji + statut selon la latence."""

    if latency_ms < 100:
        return "🟢", "Excellente"

    if latency_ms < 250:
        return "🟡", "Correcte"

    return "🔴", "Dégradée"