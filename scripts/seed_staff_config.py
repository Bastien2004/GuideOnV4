"""
scripts/seed_staff_config.py — Seed/maj de la table staff_config.

Idempotent : utilise ON CONFLICT DO UPDATE, donc relançable sans erreur.
Met à jour la config existante ou la crée si elle n'existe pas.
"""

import asyncio

from sqlalchemy.dialects.postgresql import insert as pg_insert

from utils.db.engine import get_session
from utils.db.models.staff import StaffConfig

STAFF_CONFIG = {
    "id": 1,
    "update_interval_minutes": 60,
    "guild_id": 1496765275670839306,
    "channel_id": 1496770821966925895,
    "message_id": 0,
    "grades_order": [
        "administrateur",
        "super_moderateur",
        "moderateur_plus",
        "moderateur_confirmé",
        "moderateur_test",
        "guide"
    ],
    "staff": []
}


async def seed() -> None:
    """Initialise ou met à jour la config Staff."""
    async with get_session() as session:
        stmt = pg_insert(StaffConfig).values([STAFF_CONFIG])

        stmt = stmt.on_conflict_do_update(
            index_elements=["id"],
            set_={
                "update_interval_minutes": STAFF_CONFIG["update_interval_minutes"],
                "guild_id": STAFF_CONFIG["guild_id"],
                "channel_id": STAFF_CONFIG["channel_id"],
                "message_id": STAFF_CONFIG["message_id"],
                "grades_order": STAFF_CONFIG["grades_order"],
                # "staff" n'est pas mis à jour pour préserver les données existantes
            }
        )

        result = await session.execute(stmt)
        await session.commit()

    if result.rowcount == 1:
        print("✅ Seed terminé — Configuration Staff initialisée/mise à jour.")
    else:
        print("⚠️ Seed exécuté mais aucune ligne affectée.")


if __name__ == "__main__":
    asyncio.run(seed())