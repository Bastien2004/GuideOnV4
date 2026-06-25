"""
utils/db/models/notations.py — Modèle config notations.

Table unique `notation_config` avec une seule ligne (singleton, guild_id PK).
Les créneaux horaires sont stockés en JSON (weekday, hour, minute).

Exemple de ligne :
    NotationConfig(
        id_guild_notations=123456789,
        id_channel_staff_notations=111,
        id_channel_notations=222,
        id_channel_logs=333,
        id_role_notation=444,
        time_ask_availability={"weekday": 0, "hour": 9, "minute": 0},
        time_ask_beginning={"weekday": 1, "hour": 10, "minute": 0},
        time_ask_finish={"weekday": 2, "hour": 11, "minute": 0},
        time_send_notations={"weekday": 3, "hour": 12, "minute": 0},
    )
"""
from __future__ import annotations

from sqlalchemy import BigInteger, JSON
from sqlalchemy.orm import Mapped, mapped_column

from cogs.api.base import Base, TimestampMixin


class NotationConfig(Base, TimestampMixin):
    """
    Configuration singleton du système de notations.
    La PK est le guild_id — il ne peut exister qu'une config par serveur.
    """

    __tablename__ = "notation_config"

    # Clé primaire = guild Discord (snowflake 64 bits → BigInteger)
    id_guild_notations: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=False
    )

    id_channel_staff_notations: Mapped[int] = mapped_column(BigInteger, nullable=False)
    id_channel_notations: Mapped[int] = mapped_column(BigInteger, nullable=False)
    id_channel_logs: Mapped[int] = mapped_column(BigInteger, nullable=False)
    id_role_notation: Mapped[int] = mapped_column(BigInteger, nullable=False)

    # Créneaux horaires : {"weekday": int, "hour": int, "minute": int}
    time_ask_availability: Mapped[dict] = mapped_column(JSON, nullable=False)
    time_ask_beginning: Mapped[dict] = mapped_column(JSON, nullable=False)
    time_ask_finish: Mapped[dict] = mapped_column(JSON, nullable=False)
    time_send_notations: Mapped[dict] = mapped_column(JSON, nullable=False)

    def to_dict(self) -> dict:
        return {
            "id_guild_notations": self.id_guild_notations,
            "id_channel_staff_notations": self.id_channel_staff_notations,
            "id_channel_notations": self.id_channel_notations,
            "id_channel_logs": self.id_channel_logs,
            "id_role_notation": self.id_role_notation,
            "time_ask_availability": self.time_ask_availability,
            "time_ask_beginning": self.time_ask_beginning,
            "time_ask_finish": self.time_ask_finish,
            "time_send_notations": self.time_send_notations,
        }

    def __repr__(self) -> str:
        return f"<NotationConfig guild={self.id_guild_notations!r}>"