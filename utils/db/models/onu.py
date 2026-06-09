"""
utils/db/models/onu.py — Modèles config ONU + liste de pings.

Deux tables :
- `onu_config`       : singleton par guild (guild_id PK), stocke toute la config
- `onu_ping_entries` : une ligne par (guild_id, discord_id) à pinguer

Les créneaux horaires (pre_annonce, annonce) sont stockés en JSON
{"heure": int, "minute": int}.

Exemple :
    OnuConfig(
        guild_id=123456789,
        jour_onu=2,
        pre_annonce={"heure": 9, "minute": 0},
        annonce={"heure": 10, "minute": 0},
        timezone="Europe/Paris",
        ping_mp=True,
        role_id=111,
        channel_id=222,
        image_name="onu.png",
    )
    OnuPingEntry(guild_id=123456789, discord_id="930821995787091988", name="Alice")
"""
from __future__ import annotations

from sqlalchemy import BigInteger, Boolean, Index, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from utils.db.base import Base, TimestampMixin


class OnuConfig(Base, TimestampMixin):
    """
    Configuration singleton du système ONU.
    La PK est le guild_id — une seule config par serveur.
    """

    __tablename__ = "onu_config"

    guild_id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=False
    )

    jour_onu: Mapped[int] = mapped_column(Integer, nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    ping_mp: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    role_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    channel_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    image_name: Mapped[str] = mapped_column(String(256), nullable=False)

    # Créneaux horaires : {"heure": int, "minute": int}
    pre_annonce: Mapped[dict] = mapped_column(JSON, nullable=False)
    annonce: Mapped[dict] = mapped_column(JSON, nullable=False)

    def to_dict(self) -> dict:
        return {
            "guild_id": self.guild_id,
            "jour_onu": self.jour_onu,
            "pre_annonce": self.pre_annonce,
            "annonce": self.annonce,
            "timezone": self.timezone,
            "ping_mp": self.ping_mp,
            "role_id": self.role_id,
            "channel_id": self.channel_id,
            "image_name": self.image_name,
        }

    def __repr__(self) -> str:
        return f"<OnuConfig guild={self.guild_id!r}>"


# Clés autorisées pour set_value (whitelist explicite)
ONU_SETTABLE_KEYS = frozenset({
    "jour_onu", "timezone", "ping_mp",
    "role_id", "channel_id", "image_name",
    "pre_annonce", "annonce",
})


class OnuPingEntry(Base, TimestampMixin):
    """
    Une entrée = (guild_id, discord_id, name).

    Exemple :
        OnuPingEntry(guild_id=123456789, discord_id="930821995787091988", name="Alice")
    """

    __tablename__ = "onu_ping_entries"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    guild_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)

    # snowflake Discord de l'utilisateur à pinguer
    discord_id: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)

    __table_args__ = (
        UniqueConstraint("guild_id", "discord_id", name="uq_onu_ping_guild_discord"),
        Index("ix_onu_ping_guild_discord", "guild_id", "discord_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<OnuPingEntry guild={self.guild_id!r} "
            f"discord_id={self.discord_id!r} name={self.name!r}>"
        )