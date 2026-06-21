"""Migration : créer notation_config + insérer données initiales."""
import asyncio
import json
from sqlalchemy import text
from utils.db.engine import get_session

# Données actuelles
CONFIG_DATA = {
    "id_guild_notations": 1496765275670839306,
    "id_channel_staff_notations": 1496995609482235944,
    "id_channel_notations": 1496995587923644509,
    "id_channel_logs": 1496995811450552463,
    "id_role_notation": 1496892724740096010,
    "time_ask_availability": {"weekday": 4, "hour": 8, "minute": 0},
    "time_ask_beginning": {"weekday": 4, "hour": 8, "minute": 0},
    "time_ask_finish": {"weekday": 4, "hour": 23, "minute": 30},
    "time_send_notations": {"weekday": 5, "hour": 10, "minute": 0},
}

OPERATORS = [
    {
        "discord_id": 460469174175793172,
        "pseudo": "Tintin310704",
        "label": "Administrateur | Tintin310704",
        "role_label": "Administrateur",
        "skin_head_emoji": "<:Tete_Tintin310704:1493513121053147226>",
    },
    {
        "discord_id": 723162640955867186,
        "pseudo": "Bluexiss",
        "label": "Administrateur | Bluexiss",
        "role_label": "Administrateur",
        "skin_head_emoji": "<:Tete_Bluexiss:1493513181560311890>",
    },
    {
        "discord_id": 780698590502060034,
        "pseudo": "MateRubix18",
        "label": "Administrateur | MateRubix18",
        "role_label": "Administrateur",
        "skin_head_emoji": "<:Tete_MateRubix18:1497001626022711506>",
    },
    {
        "discord_id": 646672673522319363,
        "pseudo_jeu": "RayAnderman91",
        "label": "SuperModo | RayAnderman91",
        "role_label": "SuperModo",
        "skin_head_emoji": "<:Tete_RayAnderman91:1493513307280375910>",
    },
    {
        "discord_id": 1048572287550496809,
        "pseudo_jeu": "Raspulse",
        "label": "SuperModo | Raspulse",
        "role_label": "SuperModo",
        "skin_head_emoji": "<:Tete_Raspulse:1493513491280166923>",
    },
    {
        "discord_id": 601372458288807968,
        "pseudo_jeu": "Lechatdude13",
        "label": "SuperModo | Lechatdude13",
        "role_label": "SuperModo",
        "skin_head_emoji": "<:Tete_Lechatdude13:1493513396350353460>",
    },
    {
        "discord_id": 1401373357265653950,
        "pseudo_jeu": "Miloupro_",
        "label": "SuperModo | Miloupro_",
        "role_label": "SuperModo",
        "skin_head_emoji": "<:Tete_Miloupro_:1493513537790672946>",
    },
]


async def migrate():
    async with get_session() as session:
        # 1. Créer la table notation_config
        print("📊 Créant table notation_config...")
        await session.execute(text("""
            CREATE TABLE IF NOT EXISTS notation_config (
                id SERIAL PRIMARY KEY,
                id_guild_notations BIGINT NOT NULL,
                id_channel_staff_notations BIGINT NOT NULL,
                id_channel_notations BIGINT NOT NULL,
                id_channel_logs BIGINT NOT NULL,
                id_role_notation BIGINT NOT NULL,
                time_ask_availability JSONB NOT NULL,
                time_ask_beginning JSONB NOT NULL,
                time_ask_finish JSONB NOT NULL,
                time_send_notations JSONB NOT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP NOT NULL DEFAULT NOW()
            );
        """))

        # 2. Créer la table notation_operator
        print("👥 Créant table notation_operator...")
        await session.execute(text("""
            CREATE TABLE IF NOT EXISTS notation_operator (
                id SERIAL PRIMARY KEY,
                guild_id BIGINT NOT NULL,
                discord_id BIGINT NOT NULL,
                pseudo VARCHAR(255),
                label VARCHAR(255),
                role_label VARCHAR(255),
                skin_head_emoji VARCHAR(255),
                created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                UNIQUE(guild_id, discord_id)
            );
        """))

        # 3. Insérer config notation (si pas déjà présente)
        print("💾 Insérant configuration notation...")
        existing = await session.scalar(text(
            "SELECT id FROM notation_config LIMIT 1"
        ))

        if existing is None:
            await session.execute(text("""
                INSERT INTO notation_config (
                    id_guild_notations,
                    id_channel_staff_notations,
                    id_channel_notations,
                    id_channel_logs,
                    id_role_notation,
                    time_ask_availability,
                    time_ask_beginning,
                    time_ask_finish,
                    time_send_notations,
                    created_at,
                    updated_at
                ) VALUES (
                    :guild_id,
                    :staff_chan,
                    :notif_chan,
                    :logs_chan,
                    :role_id,
                    :time_avail,
                    :time_begin,
                    :time_finish,
                    :time_send,
                    NOW(),
                    NOW()
                )
            """), {
                "guild_id": CONFIG_DATA["id_guild_notations"],
                "staff_chan": CONFIG_DATA["id_channel_staff_notations"],
                "notif_chan": CONFIG_DATA["id_channel_notations"],
                "logs_chan": CONFIG_DATA["id_channel_logs"],
                "role_id": CONFIG_DATA["id_role_notation"],
                "time_avail": json.dumps(CONFIG_DATA["time_ask_availability"]),
                "time_begin": json.dumps(CONFIG_DATA["time_ask_beginning"]),
                "time_finish": json.dumps(CONFIG_DATA["time_ask_finish"]),
                "time_send": json.dumps(CONFIG_DATA["time_send_notations"]),
            })
            print("  ✅ Configuration insérée")
        else:
            print("  ⏭️ Configuration déjà présente")

        # 4. Insérer opérateurs
        print("👥 Insérant opérateurs...")
        guild_id = CONFIG_DATA["id_guild_notations"]
        inserted = 0
        skipped = 0

        for op in OPERATORS:
            existing_op = await session.scalar(text(
                "SELECT id FROM notation_operator WHERE guild_id = :guild AND discord_id = :discord"
            ), {"guild": guild_id, "discord": op["discord_id"]})

            if existing_op is None:
                pseudo = op.get("pseudo") or op.get("pseudo_jeu", "Unknown")
                await session.execute(text("""
                    INSERT INTO notation_operator (
                        guild_id,
                        discord_id,
                        pseudo,
                        label,
                        role_label,
                        skin_head_emoji,
                        created_at
                    ) VALUES (
                        :guild,
                        :discord,
                        :pseudo,
                        :label,
                        :role_label,
                        :emoji,
                        NOW()
                    )
                """), {
                    "guild": guild_id,
                    "discord": op["discord_id"],
                    "pseudo": pseudo,
                    "label": op.get("label"),
                    "role_label": op.get("role_label"),
                    "emoji": op.get("skin_head_emoji"),
                })
                inserted += 1
            else:
                skipped += 1

        await session.commit()
        print(f"  ✅ {inserted} opérateurs insérés, {skipped} déjà présents")
        print("\n✅ Migration terminée avec succès!")


if __name__ == "__main__":
    asyncio.run(migrate())