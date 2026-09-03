"""
views/medialink/medialink_logs_view.py — écran "Historique / Logs"
(§16), sur la table media_logs (utils/db/models/medialink_log.py).

STUB léger : la table existe déjà (pas de blocage de schéma comme pour
statistics), mais aucun code n'écrit encore de MediaLog nulle part (ça
viendra avec processor.py/scheduler.py, roadmap V1) — un écran de
consultation avant qu'il y ait quoi que ce soit à consulter n'apporterait
rien de testable. Le contrat ci-dessous suffit pour brancher dessus dès
que les premiers logs existent.
"""
from __future__ import annotations

import discord
from discord.ui import Container, Separator, TextDisplay
from sqlalchemy import select

from utils.db.models.medialink_log import MediaLog
from utils.db.session import get_session
from views._components.base_view import BaseLayoutView

_PAGE_SIZE = 10


class MediaLinkLogsView(BaseLayoutView):
    def __init__(self, *, guild_id: int, owner_id: int, logs: list[dict]):
        super().__init__(owner_id=owner_id, timeout=300)
        self.guild_id = guild_id
        self.logs = logs
        self._build()

    @classmethod
    async def build(cls, *, guild: discord.Guild, owner_id: int) -> "MediaLinkLogsView":
        async with get_session() as session:
            result = await session.execute(
                select(MediaLog)
                .where(MediaLog.guild_id == guild.id)
                .order_by(MediaLog.created_at.desc())
                .limit(_PAGE_SIZE)
            )
            logs = [row.to_dict() for row in result.scalars().all()]
        return cls(guild_id=guild.id, owner_id=owner_id, logs=logs)

    def _build(self) -> None:
        container = Container()
        container.add_item(TextDisplay("# 🗒️ Historique MEDIALINK"))
        container.add_item(Separator())

        if not self.logs:
            container.add_item(TextDisplay("*Aucun événement journalisé pour l'instant.*"))
        else:
            for log in self.logs:
                icon = {"info": "ℹ️", "warning": "⚠️", "error": "❌"}.get(log["level"], "ℹ️")
                container.add_item(TextDisplay(f"{icon} `{log['event_type']}` — {log['message']}"))

        self.add_item(container)
