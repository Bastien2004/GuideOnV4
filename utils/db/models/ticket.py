"""
utils/db/models/ticket.py — Modèles du système de tickets.


- TicketPanel : la configuration d'un panel (titre, message, salons, rôles…).
- Ticket      : un ticket ouvert (1 ligne = 1 salon Discord).
"""
from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    Boolean,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)

from sqlalchemy.orm import Mapped, mapped_column, relationship
from utils.db.base import Base, TimestampMixin


class TicketPanel(Base, TimestampMixin):
    """Configuration d'un panel de tickets."""

    __tablename__ = "ticket_panels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Identifiant du panel (id unique et guild).
    panel_id: Mapped[str] = mapped_column(String(64), nullable=False)
    guild_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)

    # Emplacement du panel (salon et id message).
    channel_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    message_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    # Présentation (titre du panel et message du panel).
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    panel_message: Mapped[str] = mapped_column(Text, nullable=False)

    # Salons / catégories (catégorie open et close + salon transcript).
    ticket_category_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    transcript_channel_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    closed_category_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    # Rôles (rôle ping à l'open + rôle ban ticket).
    ping_role_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    role_ban_ticket_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    # Compteurs (ticket ouvert actuellement, ticket ouvert en tout, ticket fermé en tout).
    counter: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    open_tickets_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    deleted_tickets_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Rôles staff (1 à 3) — table de jointure.
    staff_roles: Mapped[list["TicketPanelStaffRole"]] = relationship(
        back_populates="panel",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="selectin",
    )

    # Tickets ouverts sur ce panel.
    tickets: Mapped[list["Ticket"]] = relationship(
        back_populates="panel",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="noload",
    )

    __table_args__ = (
        # Un panel est unique.
        UniqueConstraint("guild_id", "panel_id", name="uq_ticket_panel_guild_panel_id"),
        Index("ix_ticket_panel_guild_message", "guild_id", "message_id"),
    )

    @property
    def staff_role_ids(self) -> list[int]:
        """Liste des IDs de rôles staff."""
        return [r.role_id for r in sorted(self.staff_roles, key=lambda r: r.id)]

    def to_dict(self) -> dict:
        """Représentation (compat views/manager)."""

        return {
            "panel_id": self.panel_id,
            "guild_id": self.guild_id,
            "channel_id": self.channel_id,
            "message_id": self.message_id,
            "title": self.title,
            "panel_message": self.panel_message,
            "ticket_category_id": self.ticket_category_id,
            "transcript_channel_id": self.transcript_channel_id,
            "closed_category_id": self.closed_category_id,
            "ping_role_id": self.ping_role_id,
            "role_ban_ticket_id": self.role_ban_ticket_id,
            "counter": self.counter,
            "open_tickets_count": self.open_tickets_count,
            "deleted_tickets_count": self.deleted_tickets_count,
            "staff_roles": self.staff_role_ids,
        }

    def __repr__(self) -> str:
        return (
            f"<TicketPanel id={self.id} panel_id={self.panel_id!r} "
            f"guild_id={self.guild_id} title={self.title!r}>"
        )




class TicketPanelStaffRole(Base):
    """Table de jointure : un rôle staff autorisé sur un panel."""

    __tablename__ = "ticket_panel_staff_roles"

    # Identifiant de l'utilisateur.
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Identifiant du panel.
    panel_id_fk: Mapped[int] = mapped_column(
        ForeignKey("ticket_panels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Identifiant du ou des rôle(s) staff.
    role_id: Mapped[int] = mapped_column(BigInteger, nullable=False)

    # Récupère le panel.
    panel: Mapped["TicketPanel"] = relationship(back_populates="staff_roles")

    __table_args__ = (
        UniqueConstraint("panel_id_fk", "role_id", name="uq_ticket_panel_staff_role"),
    )

    def __repr__(self) -> str:
        return (
            f"<TicketPanelStaffRole panel_fk={self.panel_id_fk} "
            f"role_id={self.role_id}>"
        )


class Ticket(Base, TimestampMixin):
    """Un ticket ouvert = un salon Discord."""

    __tablename__ = "tickets"

    # Channel  ID du ticket.
    channel_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)

    # Guilde ID du ticket.
    guild_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)

    # Récupération du panel.
    panel_fk: Mapped[int] = mapped_column(
        ForeignKey("ticket_panels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    panel_id: Mapped[str] = mapped_column(String(64), nullable=False)

    # Créateur du ticket (ID + pseudo).
    creator_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    pseudo: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Numéro du ticket (ex : 0001).
    ticket_number: Mapped[str] = mapped_column(String(16), nullable=False)

    # Nom original du ticket (pour le rename close).
    original_name: Mapped[str] = mapped_column(String(100), nullable=False)

    # Raison de l'ouverture du ticket.
    raison: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Statut du ticket (ouvert ou fermé).
    closed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Date d'ouverture du ticket.
    opened_at: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)

    # Date du dernier rename du ticket.
    last_rename_at: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)

    # Id du message bot envoyé à l'ouverture.
    welcome_message_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    # Récupère le panel.
    panel: Mapped["TicketPanel"] = relationship(back_populates="tickets")

    __table_args__ = (
        Index("ix_ticket_panel_creator", "panel_id", "creator_id", "closed"),
    )

    def to_dict(self) -> dict:
        """Représentation dict proche du format ticket V3."""
        return {
            "channel_id": self.channel_id,
            "guild_id": self.guild_id,
            "panel_id": self.panel_id,
            "creator_id": self.creator_id,
            "pseudo": self.pseudo,
            "ticket_number": self.ticket_number,
            "original_name": self.original_name,
            "raison": self.raison,
            "closed": self.closed,
            "opened_at": self.opened_at,
            "last_rename_at": self.last_rename_at,
            "welcome_message_id": self.welcome_message_id,
        }

    def __repr__(self) -> str:
        return (
            f"<Ticket channel_id={self.channel_id} "
            f"ticket_number={self.ticket_number!r} closed={self.closed}>"
        )