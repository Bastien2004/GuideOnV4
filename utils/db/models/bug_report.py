"""
utils/db/models/bug_report.py — Modèle des rapports de bug (/report).

Remplace l'ancien stockage JSON (data/reports.json). Une ligne = un rapport
finalisé. Le draft en cours de saisie reste, lui, en mémoire (transitoire).

L'ID métier "RPT-0001" est dérivé d'un Integer auto-incrémenté (PK) : on formate
`RPT-{id:04d}` à l'affichage, ce qui supprime le compteur JSON et garantit
l'unicité par la PK.
"""
from __future__ import annotations

from sqlalchemy import BigInteger, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from cogs.api.base import Base, TimestampMixin


class BugReport(Base, TimestampMixin):
    __tablename__ = "bug_reports"

    # PK auto : sert aussi de numéro de référence (RPT-0001 = id 1).
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Auteur
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    user_tag: Mapped[str] = mapped_column(String(64), nullable=False)

    # Serveur d'origine (nullable : commande guild_only mais on garde souple)
    guild_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)

    # Contenu
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    importance: Mapped[str] = mapped_column(String(20), nullable=False)
    attachment_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    @property
    def reference(self) -> str:
        """Référence affichée : RPT-0001."""
        return f"RPT-{self.id:04d}"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "reference": self.reference,
            "user_id": self.user_id,
            "user_tag": self.user_tag,
            "guild_id": self.guild_id,
            "title": self.title,
            "description": self.description,
            "importance": self.importance,
            "attachment_url": self.attachment_url,
        }

    def __repr__(self) -> str:  # pragma: no cover
        return f"<BugReport {self.reference} user={self.user_id} importance={self.importance!r}>"