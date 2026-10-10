"""
utils/db/models/eco.py — Modèles du système d'économie (/eco).

Trois tables, toutes scopées par guild_id : chaque joueur a un solde
DIFFÉRENT sur chaque serveur, aucun partage inter-serveurs (cf. demande
de Paul : 80$ sur le serveur A et 98821$ sur le serveur B ne permettent
pas d'acheter un objet à 98880 sur le serveur C).

- EcoConfig : 1 ligne par serveur (PK = guild_id). Config du système :
  montant du /eco daily (200$ par défaut), activation du leaderboard.
  Équivalent de InviteConfig / ExpConfig.

- EcoAccount : 1 ligne par (serveur, membre). Solde courant (balance) et
  horodatage de la dernière réclamation /eco daily (last_daily_at), pour
  le cooldown GLISSANT de 24h (last_daily_at + 24h <= now, pas un reset
  à heure fixe). Le solde ne descend jamais sous 0 — clampé côté manager
  (utils.managers.eco_manager), pas de notion de dette en V1.

- EcoTransactionLog : historique append-only de tout mouvement de solde
  (gain /eco daily, ajustement admin via /eco gestion). Répond à "qui a
  donné/retiré combien, à qui, quand, pourquoi" sans reconstruction —
  balance_after fige le solde résultant au moment du mouvement. Pensée
  pour un futur /eco historique, et pour couvrir dès le départ les
  mouvements à venir (achats boutique, transferts entre joueurs) sans
  avoir à redesigner la table : il suffira d'ajouter des valeurs à
  EcoTransactionType.

Tous les IDs Discord (snowflakes) sont en BigInteger — convention des
modèles récents (invite.py, exp.py), à préférer au String(32) legacy
utilisé par boutique.py/permission.py (code V3 compat, pas pertinent ici).
"""
from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Enum, Index, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from utils.db.base import Base, TimestampMixin

# Valeurs par défaut de la config.
DEFAULT_DAILY_AMOUNT = 200
DEFAULT_LEADERBOARD_ENABLED = True


class EcoTransactionType(str, enum.Enum):
    """Type de mouvement enregistré dans EcoTransactionLog.

    V1 : seulement les 3 valeurs ci-dessous (daily + gestion admin).
    Prévu pour grandir (ex: SHOP_PURCHASE, TRANSFER) sans migration de
    structure — seulement d'ajout de valeur à cet enum + une migration
    qui l'enregistre côté DB (native_enum=False : stocké en texte, donc
    aucun ALTER TYPE nécessaire à l'ajout d'une valeur, cf. `native_enum`
    plus bas).
    """

    DAILY = "daily"
    ADMIN_ADD = "admin_add"
    ADMIN_REMOVE = "admin_remove"


class EcoConfig(Base, TimestampMixin):
    """Configuration du système d'économie pour un serveur."""

    __tablename__ = "eco_configs"

    # guild_id en PK : une seule config par serveur.
    guild_id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=False
    )

    daily_amount: Mapped[int] = mapped_column(
        Integer,
        default=DEFAULT_DAILY_AMOUNT,
        nullable=False,
        server_default=str(DEFAULT_DAILY_AMOUNT),
    )

    # Désactivable par serveur (Paul : "peut être désactivé par les admin
    # depuis le /eco config selon les serveurs").
    leaderboard_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=DEFAULT_LEADERBOARD_ENABLED,
        nullable=False,
        server_default="true",
    )

    def to_dict(self) -> dict:
        """Représentation dict de la config (clés stables pour la view/manager)."""
        return {
            "daily_amount": self.daily_amount,
            "leaderboard_enabled": self.leaderboard_enabled,
        }

    def __repr__(self) -> str:  # pragma: no cover - debug only
        return (
            f"<EcoConfig guild_id={self.guild_id} daily_amount={self.daily_amount} "
            f"leaderboard_enabled={self.leaderboard_enabled}>"
        )


class EcoAccount(Base, TimestampMixin):
    """Solde d'un membre sur un serveur donné."""

    __tablename__ = "eco_accounts"

    # PK composite (guild_id, user_id) : une ligne par membre et par
    # serveur — c'est CE découplage qui garantit l'isolation des soldes
    # entre serveurs (aucune colonne "solde global" nulle part).
    guild_id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=False
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=False
    )

    balance: Mapped[int] = mapped_column(
        BigInteger, default=0, nullable=False, server_default="0"
    )

    # Dernière réclamation /eco daily réussie. None = jamais réclamé
    # (autorisé immédiatement). Cooldown glissant : comparé à
    # now - timedelta(hours=24) côté manager, PAS un reset à heure fixe.
    last_daily_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        # Classement : lister/trier les membres d'un serveur.
        Index("ix_eco_accounts_guild", "guild_id"),
    )

    def to_dict(self) -> dict:
        return {
            "guild_id": self.guild_id,
            "user_id": self.user_id,
            "balance": self.balance,
            "last_daily_at": self.last_daily_at,
        }

    def __repr__(self) -> str:  # pragma: no cover - debug only
        return (
            f"<EcoAccount guild_id={self.guild_id} user_id={self.user_id} "
            f"balance={self.balance} last_daily_at={self.last_daily_at}>"
        )


class EcoTransactionLog(Base, TimestampMixin):
    """Historique append-only des mouvements de solde.

    Jamais modifiée/supprimée en usage normal — seulement des INSERT.
    created_at (TimestampMixin) sert d'horodatage du mouvement.
    """

    __tablename__ = "eco_transaction_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    guild_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)  # compte concerné

    type: Mapped[EcoTransactionType] = mapped_column(
        Enum(EcoTransactionType, name="eco_transaction_type", native_enum=False, length=16),
        nullable=False,
    )

    # Delta RÉELLEMENT appliqué au solde (peut être négatif pour un
    # retrait). Si un /eco gestion retirer demande plus que le solde
    # disponible, amount = -balance_avant (clampé), PAS la valeur
    # demandée par l'admin — balance_after reste donc toujours cohérent
    # avec balance_avant + amount.
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)

    # Solde après application du mouvement (snapshot, pas de recalcul
    # nécessaire pour afficher l'historique).
    balance_after: Mapped[int] = mapped_column(BigInteger, nullable=False)

    # Auteur de l'action : None pour /eco daily (le joueur agit sur son
    # propre compte, cf. user_id). Sinon l'admin qui a exécuté /eco
    # gestion — toujours renseigné pour ce type de mouvement.
    actor_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        # Historique d'un membre sur un serveur donné (/eco historique à venir).
        Index("ix_eco_tx_guild_user", "guild_id", "user_id"),
        # Audit chronologique à l'échelle du serveur.
        Index("ix_eco_tx_guild_created", "guild_id", "created_at"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "guild_id": self.guild_id,
            "user_id": self.user_id,
            "type": self.type.value,
            "amount": self.amount,
            "balance_after": self.balance_after,
            "actor_id": self.actor_id,
            "reason": self.reason,
            "created_at": self.created_at,
        }

    def __repr__(self) -> str:  # pragma: no cover - debug only
        return (
            f"<EcoTransactionLog id={self.id} guild_id={self.guild_id} "
            f"user_id={self.user_id} type={self.type.value} amount={self.amount} "
            f"balance_after={self.balance_after}>"
        )
