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
from discord import ButtonStyle
from discord.ui import ActionRow, Button, Container, Separator, TextDisplay
from sqlalchemy import select

from utils.db.models.medialink_log import MediaLog
from utils.db.session import get_session
from views._components.base_view import BaseLayoutView

EMOJI_BACK = "<:retour:1515658955190308995>"

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
        container.add_item(TextDisplay("# 🗒️ Logs"))
        container.add_item(TextDisplay(f"-# {len(self.logs)} entrée(s) récente(s) sur ce serveur."))
        container.add_item(Separator())

        if not self.logs:
            container.add_item(TextDisplay("*Aucun événement journalisé pour l'instant.*"))
        else:
            icon = {"info": "🔵", "warning": "🟡", "error": "🔴"}
            lines = [
                f"{icon.get(log['level'], '🔵')} **`{log['event_type']}`**\n-# {log['message']}"
                for log in self.logs
            ]
            container.add_item(TextDisplay("\n".join(lines)))

        container.add_item(Separator())
        back_btn = Button(label="Retour au hub", style=ButtonStyle.secondary, emoji=EMOJI_BACK)
        back_btn.callback = self._cb_back
        container.add_item(ActionRow(back_btn))
        container.add_item(Separator())
        container.add_item(TextDisplay("-# GuideOn Studio"))

        self.add_item(container)

    async def _cb_back(self, interaction: discord.Interaction) -> None:
        from views.medialink.medialink_dashboard_view import MediaLinkHubView

        view = await MediaLinkHubView.build(guild=interaction.guild, owner_id=self.owner_id)
        await self.push_update(interaction, view=view)