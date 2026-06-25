"""
Migration ONU V3 → V4
Crée les tables onu_config et onu_ping, puis insère les données du JSON.

Usage:
    docker exec guideon-v4-bot python /app/migrations/onu.py
"""
import asyncio
import json
import os
import sys
import logging

# Fix pour les imports depuis migrations/
sys.path.insert(0, '/app')

from utils.db.engine import engine, get_session
from utils.db.models.onu import ONUConfig, ONUPing
from cogs.api.base import Base

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)


async def run_migration():
    """Crée les tables et insère les données ONU"""

    # 1. Créer les tables
    log.info("Création des tables ONU...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    log.info("✅ Tables créées")

    # 2. Charger les données du JSON V3
    json_file = os.path.join(
        "/app",
        "data", "alpha", "onu", "config_onu_alpha.json"
    )

    if not os.path.exists(json_file):
        log.warning("⚠️ Fichier JSON ONU non trouvé à %s", json_file)
        log.info("Création d'une config par défaut...")
        json_data = {
            "jour_onu": 4,
            "pre_annonce": {"heure": 16, "minute": 42},
            "annonce": {"heure": 16, "minute": 44},
            "timezone": "Europe/Paris",
            "ping_mp": True,
            "ping_list": {},
            "role_id": 1496771752142049351,
            "channel_id": 1496995563554476227,
            "guild_id": 1496765275670839306,
            "image_name": "onu_alpha_1.png"
        }
    else:
        with open(json_file, encoding="utf-8") as f:
            json_data = json.load(f)
        log.info("✅ Données JSON chargées")

    # 3. Insérer dans la DB
    async with get_session() as session:
        guild_id = str(json_data["guild_id"])
        ping_list = json_data.pop("ping_list", {})

        # Crée ou met à jour la config
        existing = await session.get(ONUConfig, guild_id)
        if existing is None:
            config = ONUConfig(
                id_guild=guild_id,
                jour_onu=json_data["jour_onu"],
                pre_annonce=json_data["pre_annonce"],
                annonce=json_data["annonce"],
                timezone=json_data["timezone"],
                ping_mp=json_data["ping_mp"],
                role_id=str(json_data["role_id"]),
                channel_id=str(json_data["channel_id"]),
                image_name=json_data["image_name"],
            )
            session.add(config)
            log.info("Nouvelle config ONU créée (guild=%s)", guild_id)
        else:
            log.info("Config ONU existante mise à jour (guild=%s)", guild_id)

        # Ajoute les pings
        for discord_id, name in ping_list.items():
            ping = ONUPing(
                guild_id=guild_id,
                discord_id=discord_id,
                name=name
            )
            session.add(ping)

        await session.commit()
        log.info(f"✅ {len(ping_list)} pings insérés")

    log.info("✅ Migration ONU terminée!")


if __name__ == "__main__":
    asyncio.run(run_migration())