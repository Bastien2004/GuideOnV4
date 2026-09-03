"""
inspect_media_columns.py — diagnostic en LECTURE SEULE : liste les
colonnes réelles des 5 tables media_* déjà présentes en base, pour les
comparer à ce qu'attendent les modèles SQLAlchemy
(utils/db/models/medialink_*.py) et la migration
20260903_3557ccbcee08_medialink_tables.py. Ne modifie rien.

Usage (depuis la racine du projet, dans le conteneur) :
    python3 inspect_media_columns.py
"""
import asyncio

from sqlalchemy import text

from utils.db.engine import engine

TABLES = [
    "media_connections",
    "media_templates",
    "media_rules",
    "media_events",
    "media_logs",
]


async def main() -> None:
    async with engine.connect() as conn:
        for table in TABLES:
            print(f"=== {table} ===")
            rows = (
                await conn.execute(
                    text(
                        "SELECT column_name, data_type, is_nullable, column_default "
                        "FROM information_schema.columns "
                        "WHERE table_schema='public' AND table_name=:t "
                        "ORDER BY ordinal_position"
                    ),
                    {"t": table},
                )
            ).all()
            if not rows:
                print("  (table absente ?!)")
            for col_name, data_type, is_nullable, col_default in rows:
                print(f"  - {col_name:24s} {data_type:24s} nullable={is_nullable:3s} default={col_default}")

            constraints = (
                await conn.execute(
                    text(
                        "SELECT conname, contype FROM pg_constraint "
                        "WHERE conrelid = CAST(:t AS regclass) ORDER BY conname"
                    ),
                    {"t": table},
                )
            ).all()
            print("  contraintes :")
            for conname, contype in constraints:
                print(f"    - {conname} ({contype})")
            print()


if __name__ == "__main__":
    asyncio.run(main())