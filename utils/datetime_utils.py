"""
utils.datetime_utils.py
Utilitaires datetime : parse de durées et timezones.

Parse une chaîne du type "1d2h30m" en timedelta.
Utile pour les giveaways, rappels, sanctions temporaires.
"""
import re
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

PARIS_TZ = ZoneInfo("Europe/Paris")
UTC = timezone.utc

_DURATION_RE = re.compile(r"(\d+)\s*([dhms])", re.IGNORECASE)


def parse_duration(s: str) -> timedelta:
    """
    Parse une durée du type '1d2h30m' ou '15m' ou '2h'.

    Unités : d (jours), h (heures), m (minutes), s (secondes).
    Lève ValueError si invalide.

    >>> parse_duration("1h30m").total_seconds()
    5400.0
    """
    if not s:
        raise ValueError("Durée vide")

    total = timedelta()
    matches = _DURATION_RE.findall(s)
    if not matches:
        raise ValueError(f"Format de durée invalide: {s!r}")

    for value, unit in matches:
        n = int(value)
        u = unit.lower()
        if u == "d":
            total += timedelta(days=n)
        elif u == "h":
            total += timedelta(hours=n)
        elif u == "m":
            total += timedelta(minutes=n)
        elif u == "s":
            total += timedelta(seconds=n)

    if total.total_seconds() <= 0:
        raise ValueError("La durée doit être positive")

    return total


def format_duration(td: timedelta) -> str:
    """Formate un timedelta en chaîne lisible : '2j 3h 15m'."""
    total = int(td.total_seconds())
    days, remainder = divmod(total, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)

    parts = []
    if days:
        parts.append(f"{days}j")
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if seconds and not parts:
        parts.append(f"{seconds}s")

    return " ".join(parts) or "0s"


def now_utc() -> datetime:
    """Datetime actuel en UTC, timezone-aware."""
    return datetime.now(UTC)


def now_paris() -> datetime:
    """Datetime actuel à Paris."""
    return datetime.now(PARIS_TZ)