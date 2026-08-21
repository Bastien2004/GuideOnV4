"""
utils/db/models/mod_logs.py — Configuration du systeme de logs /mod (par serveur).

Un seul pack actif a la fois (stagiaire/chercheur/espion), chaque pack
etant cumulatif (chercheur inclut stagiaire, espion inclut chercheur) —
la logique de cumul vit dans utils.managers.mod_log_manager.PACK_EVENTS,
pas ici. Un seul salon de logs "pack" par serveur (log_channel_id).

`mod_action_channel_id` est un salon INDEPENDANT du pack : quand il est
configure, les actions de moderation (mod_action) y sont envoyees EN
EXCLUSIVITE (plus du tout mélangées aux autres événements du pack, même si
un pack est actif) — c'est le salon "actions de modération uniquement"
demandé par Paul. Laissé à None, le comportement historique s'applique
(mod_action suit le pack comme n'importe quel autre événement).
"""
from __future__ import annotations

from sqlalchemy import BigInteger, String
from sqlalchemy.orm import Mapped, mapped_column

from utils.db.base import Base, TimestampMixin


class LogConfig(Base, TimestampMixin):
    """Reglages du systeme de logs, par serveur."""

    __tablename__ = "mod_log_configs"

    guild_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)

    log_channel_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    # "stagiaire" | "chercheur" | "espion" | None (logs desactives).
    selected_pack: Mapped[str | None] = mapped_column(String(16), nullable=True)

    # Salon dédié, indépendant du pack — uniquement les actions de modération.
    mod_action_channel_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    def to_dict(self) -> dict:
        return {
            "guild_id": self.guild_id,
            "log_channel_id": self.log_channel_id,
            "selected_pack": self.selected_pack,
            "mod_action_channel_id": self.mod_action_channel_id,
        }

    def __repr__(self) -> str:  # pragma: no cover - debug only
        return f"<LogConfig guild_id={self.guild_id} selected_pack={self.selected_pack!r}>"