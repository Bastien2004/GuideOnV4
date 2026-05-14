"""
Bouton final qui publie le panel.

C'est ici qu'on fait l'appel au manager (côté ton collègue dev).
Pour l'instant on log juste — quand ticket_manager sera prêt on décommentera.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord

from views.ticket.embeds import build_public_panel_embed

if TYPE_CHECKING:
    from cogs.ticket._state import TicketPanelDraft
    from views.ticket.panel_setup_view import PanelSetupView

log = logging.getLogger(__name__)


class PublishButton(discord.ui.Button):
    def __init__(self, draft: "TicketPanelDraft", *, parent: "PanelSetupView", row: int):
        self._draft = draft
        self._parent = parent
        super().__init__(
            label="✅ Publier le panel",
            style=discord.ButtonStyle.success,
            custom_id="ticket_setup_publish",
            row=row,
            disabled=not draft.is_valid(),
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        if not self._draft.is_valid():
            await interaction.response.send_message(
                f"❌ Champs manquants : {', '.join(self._draft.missing_fields())}",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)

        # 1) Poster le panel public dans le salon courant
        channel = interaction.channel
        if channel is None:
            return

        embed = build_public_panel_embed(self._draft.title or "", self._draft.description or "")

        # TODO (avec le collègue dev) : importer PublicPanelView et l'attacher au message
        # from views.ticket.panel_public_view import PanelPublicView
        # public_view = PanelPublicView(panel_id=0)
        # message = await channel.send(embed=embed, view=public_view)

        message = await channel.send(embed=embed)  # TEMPORAIRE : sans view

        # 2) TODO : sauvegarder en DB via ticket_manager
        # from utils.db.session import get_session
        # from utils.managers.ticket_manager import create_panel
        # async with get_session() as session:
        #     panel = await create_panel(
        #         session,
        #         guild_id=self._draft.guild_id,
        #         channel_id=channel.id,
        #         message_id=message.id,
        #         title=self._draft.title,
        #         description=self._draft.description,
        #         category_open_id=self._draft.category_open_id,
        #         transcript_channel_id=self._draft.transcript_channel_id,
        #         staff_role_ids=self._draft.staff_role_ids,
        #         category_closed_id=self._draft.category_closed_id,
        #         ping_role_id=self._draft.ping_role_id,
        #         ban_role_id=self._draft.ban_role_id,
        #     )

        log.info("Panel ticket publié (DB désactivée) guild=%s", self._draft.guild_id)

        await interaction.followup.send(
            f"✅ Panel publié dans {channel.mention}.\n"
            f"⚠ DB désactivée — la persistance sera activée quand ticket_manager sera prêt.",
            ephemeral=True,
        )
        self._parent.stop()
