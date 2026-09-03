"""
views/medialink/medialink_statistics_view.py — écran "Statistiques"
(§16).

STUB explicitement bloqué : dépend de
utils/db/models/medialink_statistics.py, dont le schéma n'est pas
tranché (comptage à la volée vs. table d'agrégats — cf. ce fichier pour
le détail de l'arbitrage en attente). Écrire cette vue avant ce choix
reviendrait à figer une UI sur une source de données qui n'existe pas
encore.
"""
from __future__ import annotations

import discord

from views._components.base_view import BaseLayoutView


class MediaLinkStatisticsView(BaseLayoutView):
    def __init__(self, *, guild_id: int, owner_id: int):
        super().__init__(owner_id=owner_id, timeout=300)
        self.guild_id = guild_id

    @classmethod
    async def build(cls, *, guild: discord.Guild, owner_id: int) -> "MediaLinkStatisticsView":
        raise NotImplementedError(
            "MediaLinkStatisticsView.build — attend l'arbitrage sur "
            "utils/db/models/medialink_statistics.py (comptage à la volée vs. agrégats)"
        )
