"""
script/inspect_db.py — diagnostic en LECTURE SEULE : liste les tables réellement
présentes en base + la valeur actuelle de alembic_version, en réutilisant
le moteur/la config déjà en place dans le bot (utils.db.engine /
utils.settings). Ne modifie rien.

Usage (depuis la racine du projet, dans le conteneur) :
    python3 inspect_db.py
"""
import asyncio

from sqlalchemy import text

from utils.db.engine import engine


async def main() -> None:
    async with engine.connect() as conn:
        tables = (
            await conn.execute(
                text("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename")
            )
        ).scalars().all()

        print("=== TABLES PRÉSENTES EN BASE ===")
        for t in tables:
            print(" -", t)
        print(f"({len(tables)} table(s))")

        print()
        print("=== TABLE media_* (MEDIALINK) ===")
        media_tables = [t for t in tables if t.startswith("media_")]
        if media_tables:
            for t in media_tables:
                print(" -", t)
        else:
            print(" (aucune — la migration MEDIALINK n'a pas encore été appliquée)")

        print()
        print("=== alembic_version ===")
        try:
            rows = (await conn.execute(text("SELECT version_num FROM alembic_version"))).scalars().all()
            for r in rows:
                print(" -", r)
        except Exception as e:
            print(" impossible de lire alembic_version :", e)


if __name__ == "__main__":
    asyncio.run(main())