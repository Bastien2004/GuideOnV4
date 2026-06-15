"""
utils/events_alpha.py — Chargement et mise à jour des events Alpha.

Stockage : source/events_alpha.json (statut inclus).
Cache en mémoire invalidé à chaque écriture de statut.
"""
from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

log = logging.getLogger(__name__)

EVENTS_PATH = Path("data/event_json/event_alpha.json")

STATUS_EMOJIS: dict[str, str] = {
    "fonctionne":  "✅",
    "maintenance": "🔧",
    "fermé":       "🔴",
}
STATUS_LABELS: dict[str, str] = {
    "fonctionne":  "Opérationnel",
    "maintenance": "En maintenance",
    "fermé":       "Fermé",
}
STATUS_VALUES = list(STATUS_EMOJIS.keys())

_cache: list[dict] | None = None
_lock = asyncio.Lock()


def _load_sync() -> list[dict]:
    global _cache
    if _cache is not None:
        return _cache
    try:
        with open(EVENTS_PATH, encoding="utf-8") as f:
            data = json.load(f)
        _cache = data["events"]
    except (FileNotFoundError, KeyError, json.JSONDecodeError) as e:
        log.error("Impossible de charger events_alpha.json : %s", e)
        _cache = []
    return _cache


def load_events() -> list[dict]:
    """Retourne la liste complète des events (cache mémoire)."""
    return list(_load_sync())


def get_event(event_id: int) -> dict | None:
    return next((e for e in _load_sync() if e["id"] == event_id), None)


def get_event_by_name(name: str) -> dict | None:
    return next(
        (e for e in _load_sync() if e["name"].lower() == name.lower()),
        None,
    )


async def update_event_status(event_id: int, new_status: str) -> bool:
    """Modifie le statut d'un event et sauvegarde le JSON. Thread-safe."""
    global _cache
    async with _lock:
        events = _load_sync()
        event = next((e for e in events if e["id"] == event_id), None)
        if event is None:
            return False
        event["status"] = new_status
        _cache = events
        try:
            EVENTS_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(EVENTS_PATH, "w", encoding="utf-8") as f:
                json.dump({"events": events}, f, ensure_ascii=False, indent=2)
        except OSError as e:
            log.error("Impossible de sauvegarder events_alpha.json : %s", e)
            return False
    log.info("Statut event %d mis à jour : %s", event_id, new_status)
    return True