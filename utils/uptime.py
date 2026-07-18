"""
utils/uptime.py - Gère l'uptime du bot.
"""
from datetime import datetime, timezone

START_TIME: datetime = datetime.now(timezone.utc)


def uptime_seconds() -> float:
    """Nombre de secondes depuis le démarrage."""
    return (datetime.now(timezone.utc) - START_TIME).total_seconds()