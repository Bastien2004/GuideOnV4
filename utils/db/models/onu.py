"""
utils/db/models/onu.py — Modèles ONU Alpha pour V4
"""
from __future__ import annotations

from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, JSON
from sqlalchemy.orm import relationship

from cogs.api.base import Base


class ONUConfig(Base):
    """Configuration ONU Alpha"""
    __tablename__ = "onu_config"

    id_guild = Column(String(20), primary_key=True)  # Discord guild ID
    jour_onu = Column(Integer, default=4)  # 0=lundi, 4=vendredi
    pre_annonce = Column(JSON, default={"heure": 16, "minute": 42})  # TimeModel
    annonce = Column(JSON, default={"heure": 16, "minute": 44})  # TimeModel
    timezone = Column(String(50), default="Europe/Paris")
    ping_mp = Column(Boolean, default=True)
    role_id = Column(String(20), nullable=False)  # Discord role ID
    channel_id = Column(String(20), nullable=False)  # Discord channel ID
    image_name = Column(String(255), default="onu_alpha_1.png")

    # Relation 1-N avec les pings
    pings = relationship("ONUPing", back_populates="config", cascade="all, delete-orphan")

    def to_dict(self) -> dict:
        """Export en dict pour JSON response"""
        return {
            "jour_onu": self.jour_onu,
            "pre_annonce": self.pre_annonce,
            "annonce": self.annonce,
            "timezone": self.timezone,
            "ping_mp": self.ping_mp,
            "ping_list": {p.discord_id: p.name for p in self.pings},
            "role_id": int(self.role_id),
            "channel_id": int(self.channel_id),
            "guild_id": int(self.id_guild),
            "image_name": self.image_name,
        }


class ONUPing(Base):
    """Liste des utilisateurs à ping pour ONU"""
    __tablename__ = "onu_ping"

    id = Column(Integer, primary_key=True)
    guild_id = Column(String(20), ForeignKey("onu_config.id_guild"), nullable=False)
    discord_id = Column(String(20), nullable=False, unique=True)
    name = Column(String(255), nullable=False)

    # Relation back vers ONUConfig
    config = relationship("ONUConfig", back_populates="pings")