"""
Migration ONU V3 → V4 (CORRIGÉE)
Crée les tables alpha_onu_configs et alpha_onu_ping_members, puis insère les données du JSON.

Usage:
    docker cp /chemin/to/onu_migration.py guideon-v4-bot:/app/
    docker exec guideon-v4-bot python /app/onu_migration.py
"""
import asyncio
import json
import os
import logging

from utils.db.engine import engine, get_session
from utils.db.models.alpha_onu_config import AlphaONUConfig, AlphaONUPingMember
from utils.db.base import Base

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
        os.path.dirname(__file__),
        "data", "alpha", "onu", "config_onu_alpha.json"
    )

    if not os.path.exists(json_file):
        log.warning("⚠️ Fichier JSON ONU non trouvé à %s", json_file)
        log.info("Création d'une config par défaut...")
        json_data = {
            "jour_onu": 4,
            "pre_heure": 16,
            "pre_minute": 42,
            "ann_heure": 16,
            "ann_minute": 44,
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
        guild_id = int(json_data["guild_id"])
        ping_list = json_data.pop("ping_list", {})

        # Crée ou met à jour la config
        existing = await session.get(AlphaONUConfig, guild_id)
        if existing is None:
            # Construire les champs pour la config
            config_data = {
                "guild_id": guild_id,
                "jour_onu": json_data.get("jour_onu"),
                "pre_heure": json_data.get("pre_heure") or (json_data.get("pre_annonce", {}).get("heure")),
                "pre_minute": json_data.get("pre_minute") or (json_data.get("pre_annonce", {}).get("minute")),
                "ann_heure": json_data.get("ann_heure") or (json_data.get("annonce", {}).get("heure")),
                "ann_minute": json_data.get("ann_minute") or (json_data.get("annonce", {}).get("minute")),
                "timezone": json_data.get("timezone", "Europe/Paris"),
                "ping_mp": json_data.get("ping_mp", False),
                "role_id": int(json_data.get("role_id")) if json_data.get("role_id") else None,
                "channel_id": int(json_data.get("channel_id")) if json_data.get("channel_id") else None,
                "image_name": json_data.get("image_name"),
                "join_url": json_data.get("join_url"),
                "enabled": json_data.get("enabled", True),
            }
            config = AlphaONUConfig(**config_data)
            session.add(config)
            log.info("Nouvelle config ONU créée (guild=%s)", guild_id)
        else:
            log.info("Config ONU existante mise à jour (guild=%s)", guild_id)

        # Ajoute les pings
        for discord_id_str, name in ping_list.items():
            ping = AlphaONUPingMember(
                guild_id=guild_id,
                discord_id=int(discord_id_str)
            )
            session.add(ping)

        await session.commit()
        log.info(f"✅ {len(ping_list)} pings insérés")

    log.info("✅ Migration ONU terminée!")


if __name__ == "__main__":
    asyncio.run(run_migration())