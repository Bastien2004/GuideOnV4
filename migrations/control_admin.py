from __future__ import annotations

import asyncio
import json
import os
import sys

from sqlalchemy import select

from utils.db.models.control_admin import CommandControl
from utils.db.session import get_session

BASE_DIR = os.getcwd()


async def migrate(json_path: str | None = None) -> None:
    if json_path is None:
        json_path = os.path.join(BASE_DIR, "data", "admin_json", "control_admin.json")

    print(f"Lecture de : {json_path}")

    if not os.path.exists(json_path):
        print(f"Erreur : Le fichier JSON est introuvable à l'emplacement : {json_path}")
        return

    with open(json_path, encoding="utf-8") as f:
        data: dict[str, bool] = json.load(f)

    async with get_session() as session:
        for command_name, enabled in data.items():
            stmt = select(CommandControl).where(
                CommandControl.command_name == command_name
            )
            existing = (await session.execute(stmt)).scalar_one_or_none()

            if existing:
                existing.enabled = enabled
                print(f"Mise à jour : {command_name} -> {enabled}")
            else:
                session.add(CommandControl(command_name=command_name, enabled=enabled))
                print(f"Ajout : {command_name} -> {enabled}")

        await session.commit()
        print(f"\nOK ! {len(data)} commandes migrées avec succès.")


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else None
    asyncio.run(migrate(path))