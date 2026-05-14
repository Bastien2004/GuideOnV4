"""
Commande /ticket panel_create

PATRON À SUIVRE pour les autres commandes :
- Décorer avec @app_commands.command + checks de permission
- Construire un draft (dataclass d'état)
- Instancier la View modulaire
- Envoyer la réponse en ephemeral

La logique métier (DB, validation profonde, etc.) est dans utils/managers/ticket_manager.py
- on ne touche PAS à la DB depuis le cog directement.
"""
from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands

from cogs.ticket._state import TicketPanelDraft
from utils.permission import has_perm
from views.ticket.panel_setup_view import PanelSetupView

log = logging.getLogger(__name__)


class TicketPanelCreate(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="ticket_panel_create",
        description="🎫 Créer un nouveau panel de tickets",
    )
    @has_perm(manage_channels=True)
    async def ticket_panel_create(self, interaction: discord.Interaction) -> None:
        if interaction.guild is None:
            await interaction.response.send_message(
                "❌ Commande utilisable uniquement en serveur.", ephemeral=True
            )
            return

        draft = TicketPanelDraft(guild_id=interaction.guild.id)
        view = PanelSetupView(draft, owner_id=interaction.user.id)

        await interaction.response.send_message(
            embed=view.build_embed(),
            view=view,
            ephemeral=True,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(TicketPanelCreate(bot))
