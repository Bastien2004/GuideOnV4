"""
utils/db/models/ng_role_react.py — Modèles du système Rôle Réaction multi-serveurs.

NGRoleReaction     : config principale par serveur NG (salon cible + message_id)
NGRoleReactCouple  : jusqu'à 10 rôles configurables (label, emoji, description)

Refonte multi-serveurs phase 10 : remplace AlphaRoleReactConfig/
AlphaRoleReactEntry (clés guild_id) par des modèles clés par `NGServer.name`
(server). Contrairement aux tables enfants des phases 6-9 (NGONUPingMember,
NGNotaAvailability, ...) qui n'avaient pas de FK déclarée (fidèle à
l'absence de FK de l'original), le prompt demande explicitement ici une
"FK cascade" (§4.2, ligne role-react du tableau de mapping) : NGRoleReactCouple.
server référence désormais réellement NGRoleReaction.server avec
ON DELETE CASCADE. Voir ng_role_react_manager.add_rr_entry() pour la
contrepartie applicative (get-or-create de la ligne parente avant insertion
d'un couple, afin de ne pas casser le flux existant où un rôle pouvait être
ajouté avant même qu'un salon soit configuré).
"""
from __future__ import annotations

from sqlalchemy import BigInteger, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from utils.db.base import Base, TimestampMixin

MAX_ROLES = 10


class NGRoleReaction(Base, TimestampMixin):
    __tablename__ = "ng_role_reactions"

    server:     Mapped[str] = mapped_column(String(50), primary_key=True)
    channel_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    message_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    def to_dict(self) -> dict:
        return {
            "server":     self.server,
            "channel_id": self.channel_id,
            "message_id": self.message_id,
        }


class NGRoleReactCouple(Base, TimestampMixin):
    """Un rôle dans la liste. position détermine l'ordre d'affichage (0-9)."""
    __tablename__ = "ng_role_react_couples"

    id:          Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    server:      Mapped[str] = mapped_column(
        String(50), ForeignKey("ng_role_reactions.server", ondelete="CASCADE"), nullable=False
    )
    position:    Mapped[int] = mapped_column(Integer, nullable=False)
    role_id:     Mapped[int] = mapped_column(BigInteger, nullable=False)
    label:       Mapped[str] = mapped_column(String(80), nullable=False)
    emoji:       Mapped[str | None] = mapped_column(String(100), nullable=True)
    description: Mapped[str | None] = mapped_column(String(200), nullable=True)

    __table_args__ = (
        UniqueConstraint("server", "position", name="uq_ng_role_react_pos"),
        UniqueConstraint("server", "role_id",  name="uq_ng_role_react_role"),
        Index("ix_ng_role_react_server", "server"),
    )

    def to_dict(self) -> dict:
        return {
            "id":          self.id,
            "server":      self.server,
            "position":    self.position,
            "role_id":     self.role_id,
            "label":       self.label,
            "emoji":       self.emoji,
            "description": self.description,
        }
