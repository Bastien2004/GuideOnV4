"""
utils/db/models/qr_code.py — Historique des QR codes générés via /qr generate.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from utils.db.base import Base


class QRCode(Base):
    """Une entrée d'historique : un QR code généré par un utilisateur.

    2026-10-06 (Paul) : ajout de `guild_id`. Avant, l'historique (et la
    recherche "ce QR a déjà été généré par qui ?" dans /qr scan) était
    100% GLOBAL — sans aucune notion de serveur — alors que GuideOn tourne
    sur de nombreux serveurs indépendants. Conséquence concrète : /qr scan
    pouvait révéler qu'un membre d'un AUTRE serveur, totalement étranger,
    avait généré un contenu identique ("généré ici par @untel"), et
    /qr list permettait de consulter l'historique COMPLET (tous serveurs
    confondus) de n'importe quel utilisateur Discord. `guild_id` est
    nullable car les lignes créées avant ce correctif n'ont aucun moyen
    fiable d'être rattachées à un serveur a posteriori — elles restent en
    base (aucune perte de données) mais ne remontent plus jamais dans les
    nouvelles requêtes, toutes filtrées par guild_id courant (voir
    utils/managers/qr_manager.py). C'est le choix le plus sûr : on ne
    devine pas un guild_id, on arrête juste de faire remonter une donnée
    dont on ne connaît plus l'origine.
    """

    __tablename__ = "qr_codes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    guild_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    contenu: Mapped[str] = mapped_column(String(2000), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_qr_codes_guild_user", "guild_id", "user_id"),
        Index("ix_qr_codes_guild_contenu", "guild_id", "contenu"),
    )
