"""
Tracking du temps de démarrage du bot.
"""
from datetime import datetime, timezone

# Capturé au moment où le module est importé (= au démarrage)
START_TIME: datetime = datetime.now(timezone.utc)


def uptime_seconds() -> float:
    """Nombre de secondes depuis le démarrage."""
    return (datetime.now(timezone.utc) - START_TIME).total_seconds()
