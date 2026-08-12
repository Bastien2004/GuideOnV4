"""
utils/db/models/ng_nota_config.py — Modèles du système de notations multi-serveurs.

NGNotaConfig       : config principale (PK=server)
NGNotaWeekState    : état de la semaine courante (PK=server)
NGNotaAvailability : opérateurs disponibles cette semaine (unique server+discord_id)
NGNotaHistory      : dernier range assigné par opérateur (PK composite server+discord_id)

Refonte multi-serveurs phase 9 : remplace AlphaNotaConfig/AlphaNotaWeekState/
AlphaNotaAvailability/AlphaNotaHistory (clés guild_id) par des modèles clés
par `NGServer.name` (server), cohérent avec NGStaffMember/NGRankConfig/
NGONUConfig (phases 6-8).
"""
from __future__ import annotations

from sqlalchemy import BigInteger, Boolean, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from utils.db.base import Base, TimestampMixin

NOTA_OPERATOR_GRADES = {"administrateur", "super_moderateur"}


class NGNotaConfig(Base, TimestampMixin):
    """
    Configuration du système de notations, une ligne par serveur NG.

    Timings (weekday 0=lundi...6=dimanche, heure/minute) :
        send_presence_*  - envoi du message de présence staff + rappels DM
        deadline_*       - fermeture du vote de disponibilité (bloque le bouton)
        send_public_*    - envoi du message public de notation + reset semaine
    """
    __tablename__ = "ng_nota_configs"

    server: Mapped[str] = mapped_column(String(50), primary_key=True)

    channel_staff_id: Mapped[int | None]  = mapped_column(BigInteger, nullable=True)
    channel_public_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    channel_logs_id: Mapped[int | None]   = mapped_column(BigInteger, nullable=True)
    role_id: Mapped[int | None]           = mapped_column(BigInteger, nullable=True)

    countries_count: Mapped[int] = mapped_column(Integer, nullable=False, default=238, server_default="238")

    send_presence_weekday: Mapped[int | None] = mapped_column(Integer, nullable=True)
    send_presence_hour:    Mapped[int | None] = mapped_column(Integer, nullable=True)
    send_presence_minute:  Mapped[int | None] = mapped_column(Integer, nullable=True)

    deadline_weekday: Mapped[int | None] = mapped_column(Integer, nullable=True)
    deadline_hour:    Mapped[int | None] = mapped_column(Integer, nullable=True)
    deadline_minute:  Mapped[int | None] = mapped_column(Integer, nullable=True)

    send_public_weekday: Mapped[int | None] = mapped_column(Integer, nullable=True)
    send_public_hour:    Mapped[int | None] = mapped_column(Integer, nullable=True)
    send_public_minute:  Mapped[int | None] = mapped_column(Integer, nullable=True)

    url_country_lookup: Mapped[str | None] = mapped_column(String(300), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")

    def to_dict(self) -> dict:
        return {
            "server":                 self.server,
            "channel_staff_id":       self.channel_staff_id,
            "channel_public_id":      self.channel_public_id,
            "channel_logs_id":        self.channel_logs_id,
            "role_id":                self.role_id,
            "countries_count":        self.countries_count,
            "send_presence_weekday":  self.send_presence_weekday,
            "send_presence_hour":     self.send_presence_hour,
            "send_presence_minute":   self.send_presence_minute,
            "deadline_weekday":       self.deadline_weekday,
            "deadline_hour":          self.deadline_hour,
            "deadline_minute":        self.deadline_minute,
            "send_public_weekday":    self.send_public_weekday,
            "send_public_hour":       self.send_public_hour,
            "send_public_minute":     self.send_public_minute,
            "url_country_lookup":     self.url_country_lookup,
            "enabled":                self.enabled,
        }

    def __repr__(self) -> str:
        return f"<NGNotaConfig server={self.server!r} enabled={self.enabled}>"


class NGNotaWeekState(Base, TimestampMixin):
    """État de la semaine courante. Resetté chaque semaine après envoi public."""
    __tablename__ = "ng_nota_week_states"

    server: Mapped[str] = mapped_column(String(50), primary_key=True)

    availability_message_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    public_message_id: Mapped[int | None]        = mapped_column(BigInteger, nullable=True)
    reminder_sent: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    # JSON text : [[start, end, discord_id], ...] — les assignments de la semaine courante
    assigned_ranges: Mapped[str] = mapped_column(Text, nullable=False, default="[]", server_default="'[]'")

    def to_dict(self) -> dict:
        return {
            "server":                   self.server,
            "availability_message_id":  self.availability_message_id,
            "public_message_id":        self.public_message_id,
            "reminder_sent":            self.reminder_sent,
            "assigned_ranges":          self.assigned_ranges,
        }


class NGNotaAvailability(Base, TimestampMixin):
    """Opérateurs disponibles pour la semaine courante. Nettoyé au reset hebdo."""
    __tablename__ = "ng_nota_availabilities"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    server:     Mapped[str] = mapped_column(String(50), nullable=False)
    discord_id: Mapped[int] = mapped_column(BigInteger, nullable=False)

    __table_args__ = (
        UniqueConstraint("server", "discord_id", name="uq_ng_nota_availability"),
        Index("ix_ng_nota_avail_server", "server"),
    )


class NGNotaHistory(Base, TimestampMixin):
    """
    Dernier range assigné par opérateur et par serveur NG.
    Mis à jour chaque semaine après envoi public. Utilisé pour :
      - la rotation (tri par last_range_start = ordre de la semaine précédente)
      - l'anti-répétition (évite de réassigner le même bloc)
    """
    __tablename__ = "ng_nota_history"

    server:           Mapped[str] = mapped_column(String(50), primary_key=True)
    discord_id:       Mapped[int] = mapped_column(BigInteger, primary_key=True)
    last_range_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_range_end:   Mapped[int | None] = mapped_column(Integer, nullable=True)

    def __repr__(self) -> str:
        return (
            f"<NGNotaHistory server={self.server!r} user={self.discord_id} "
            f"range={self.last_range_start}-{self.last_range_end}>"
        )
