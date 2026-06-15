"""
Script de migration des données : JSON V3 → DB (table bienvenue_configs).

Porte l'ancien data/config_json/config_bienvenue.json :
    { "<guild_id>": { "system_active": ..., "arrive_message": ..., ... }, ... }
vers la table bienvenue_configs (une ligne par serveur).

Usage :
    python -m migrations.bienvenue [chemin_json_optionnel]

Par défaut, lit data/config_json/config_bienvenue.json
Idempotent : relancer met à jour les lignes existantes (pas de doublon, PK=guild_id).
"""
from __future__ import annotations

import asyncio
import json
import os
import sys

from utils.db.models.bienvenue import (
    DEFAULT_ARRIVE_MESSAGE,
    DEFAULT_DEPART_MESSAGE,
    BienvenueConfig,
)
from utils.db.session import get_session

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Clés attendues + valeur par défaut si absente dans le JSON V3.
_DEFAULTS: dict = {
    "system_active": False,
    "arrive_active": False,
    "depart_active": False,
    "arrive_channel_id": None,
    "depart_channel_id": None,
    "arrive_message": DEFAULT_ARRIVE_MESSAGE,
    "depart_message": DEFAULT_DEPART_MESSAGE,
}


def _coerce_channel(value) -> int | None:
    """Le JSON V3 stocke parfois les channel_id en str ; on normalise en int."""
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


async def migrate(json_path: str | None = None) -> None:
    if json_path is None:
        json_path = os.path.join(BASE_DIR, "data", "config_json", "config_bienvenue.json")

    print(f"Lecture de : {json_path}")

    with open(json_path, encoding="utf-8") as f:
        data: dict[str, dict] = json.load(f)

    created = 0
    updated = 0

    async with get_session() as session:
        for guild_key, raw in data.items():
            try:
                guild_id = int(guild_key)
            except (TypeError, ValueError):
                print(f"  ⚠️ guild_id invalide ignoré : {guild_key!r}")
                continue

            # Fusionne avec les défauts pour les clés manquantes
            merged = {**_DEFAULTS, **{k: raw.get(k, v) for k, v in _DEFAULTS.items()}}
            merged["arrive_channel_id"] = _coerce_channel(merged["arrive_channel_id"])
            merged["depart_channel_id"] = _coerce_channel(merged["depart_channel_id"])

            row = await session.get(BienvenueConfig, guild_id)
            if row is None:
                session.add(BienvenueConfig(guild_id=guild_id, **merged))
                created += 1
            else:
                for k, v in merged.items():
                    setattr(row, k, v)
                updated += 1

    print(f"OK bienvenue migrée : {created} créées, {updated} mises à jour.")


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else None
    asyncio.run(migrate(path))