"""
scripts/seed_command_controls.py — Mise à jour de la table de maintenance.
"""

import asyncio

from sqlalchemy.dialects.postgresql import insert as pg_insert

from utils.db.session import get_session
from utils.db.models.control_admin import CommandControl

COMMANDS = {
    # ── Commande à ajouter ; ──
    "config_join_to_create": False,
}


async def seed() -> None:
    async with get_session() as session:
        stmt = pg_insert(CommandControl).values(
            [{"command_name": name, "enabled": enabled} for name, enabled in COMMANDS.items()]
        )
        stmt = stmt.on_conflict_do_nothing(index_elements=["command_name"])
        result = await session.execute(stmt)
    print(f"✅ Seed terminé — {result.rowcount} nouvelle(s) commande(s) insérée(s) "
          f"({len(COMMANDS)} référencées au total).")


if __name__ == "__main__":
    asyncio.run(seed())