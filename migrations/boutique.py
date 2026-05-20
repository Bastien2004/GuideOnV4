"""
Script de migration des données : JSON V3 → DB (table shop_entries).

Porte l'ancien data/boutique/boutique_id.json :
    { "VIP": ["id", ...], "Gold+": ["id", ...] }
vers la table shop_entries.

Usage :
    python -m migrations.boutique [chemin_json_optionnel]

Par défaut, lit data/boutique/boutique_id.json
Idempotent : relancer ne crée pas de doublons (UniqueConstraint role+discord_id).
"""
from __future__ import annotations

import asyncio
import json
import os
import sys

from sqlalchemy import select

from utils.db.models.boutique import ShopEntry, ShopRole
from utils.db.session import get_session

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Mapping clé JSON V3 -> enum
_ROLE_MAP = {
    "VIP": ShopRole.VIP,
    "Gold+": ShopRole.GOLD_PLUS,
}


async def migrate(json_path: str | None = None) -> None:
    if json_path is None:
        json_path = os.path.join(BASE_DIR, "data", "boutique", "boutique_id.json")

    print(f"Lecture de : {json_path}")

    with open(json_path, encoding="utf-8") as f:
        data: dict[str, list[str]] = json.load(f)

    created = 0
    skipped = 0

    async with get_session() as session:
        for role_key, ids in data.items():
            role = _ROLE_MAP.get(role_key)
            if role is None:
                print(f"  ⚠️ Clé inconnue ignorée : {role_key!r}")
                continue

            for discord_id in ids:
                discord_id = str(discord_id)
                exists = await session.scalar(
                    select(ShopEntry.id).where(
                        ShopEntry.role == role,
                        ShopEntry.discord_id == discord_id,
                    )
                )
                if exists is not None:
                    skipped += 1
                    continue
                session.add(ShopEntry(role=role, discord_id=discord_id))
                created += 1

    print(f"OK boutique migrée : {created} créées, {skipped} déjà présentes.")


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else None
    asyncio.run(migrate(path))