"""
utils/db/models/boutique.py — Modèle boutique (VIP + Gold+).

Table unique `shop_entries` pour les deux types d'abonnement :
- VIP   : rattaché à un utilisateur Discord (discord_id = user_id)
- Gold+ : rattaché à un serveur Discord (discord_id = guild_id)

On stocke discord_id en String : les IDs Discord sont des snowflakes 64 bits
qui dépassent l'INT signé de PostgreSQL et qu'on manipule en str partout
ailleurs dans le bot (compat V3). Une seule table = un seul endroit à migrer,
un seul refresh de cache, un seul endpoint d'écriture.
"""
from __future__ import annotations

import enum

from sqlalchemy import Enum, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from utils.db.base import Base, TimestampMixin


class ShopRole(str, enum.Enum):
    """Type d'entrée boutique. La valeur str matche les clés JSON V3."""

    VIP = "VIP"
    GOLD_PLUS = "Gold+"


class ShopEntry(Base, TimestampMixin):
    """
    Une entrée = (role, discord_id).

    Exemples :
        ShopEntry(role=ShopRole.VIP,       discord_id="930821995787091988")
        ShopEntry(role=ShopRole.GOLD_PLUS, discord_id="1411296579528294402")
    """

    __tablename__ = "shop_entries"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    role: Mapped[ShopRole] = mapped_column(
        Enum(ShopRole, name="shop_role", native_enum=False, length=16),
        nullable=False,
        index=True,
    )

    # snowflake Discord (user_id pour VIP, guild_id pour Gold+)
    discord_id: Mapped[str] = mapped_column(String(32), nullable=False)

    __table_args__ = (
        # On ne veut pas deux fois le même couple (role, discord_id)
        UniqueConstraint("role", "discord_id", name="uq_shop_role_discord_id"),
        # Lookup principal du refresh cache : "tous les discord_id d'un role"
        Index("ix_shop_role_discord", "role", "discord_id"),
    )

    def __repr__(self) -> str:
        return f"<ShopEntry role={self.role.value!r} discord_id={self.discord_id!r}>"