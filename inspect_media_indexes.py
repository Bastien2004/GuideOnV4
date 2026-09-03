"""
inspect_media_indexes.py — diagnostic en LECTURE SEULE : liste les index
réels et le comportement ON DELETE des FK des 5 tables media_*, pour
finir la comparaison avec la migration
20260903_3557ccbcee08_medialink_tables.py. Ne modifie rien.

Usage (depuis la racine du projet, dans le conteneur) :
    python3 inspect_media_indexes.py
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
            print(f"=== {table} — index ===")
            rows = (
                await conn.execute(
                    text(
                        "SELECT indexname, indexdef FROM pg_indexes "
                        "WHERE schemaname='public' AND tablename=:t ORDER BY indexname"
                    ),
                    {"t": table},
                )
            ).all()
            for indexname, indexdef in rows:
                print(f"  - {indexname}: {indexdef}")

            print(f"=== {table} — FK (ON DELETE) ===")
            fk_rows = (
                await conn.execute(
                    text(
                        "SELECT conname, "
                        "CASE confdeltype "
                        "  WHEN 'c' THEN 'CASCADE' "
                        "  WHEN 'n' THEN 'SET NULL' "
                        "  WHEN 'a' THEN 'NO ACTION' "
                        "  WHEN 'r' THEN 'RESTRICT' "
                        "  ELSE confdeltype::text "
                        "END AS on_delete "
                        "FROM pg_constraint "
                        "WHERE conrelid = CAST(:t AS regclass) AND contype = 'f' "
                        "ORDER BY conname"
                    ),
                    {"t": table},
                )
            ).all()
            for conname, on_delete in fk_rows:
                print(f"  - {conname}: ON DELETE {on_delete}")
            print()


if __name__ == "__main__":
    asyncio.run(main())