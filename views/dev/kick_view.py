"""
views/dev/kick_view.py — Vue de confirmation pour /dev kick, extraite de
cogs/dev/kick.py.

Reste en BaseLayoutView (pas LayoutView simple) : deux vrais boutons
interactifs avec callback bot-side (confirmer/annuler) qui doivent être
restreints au demandeur — même cas que les autres vues de confirmation du
projet (owner_id + interaction_check + on_error + on_timeout hérités de
BaseLayoutView).
"""
from __future__ import annotations

import logging

import discord
from discord import ButtonStyle, Interaction
from discord.ui import ActionRow, Button, Container, Separator, TextDisplay

from utils.container_universel import error_container, success_container, warning_container
from utils.kick import KickError, leave_guild
from views._components.base_view import BaseLayoutView

log = logging.getLogger(__name__)


class ConfirmKickView(BaseLayoutView):
    def __init__(self, guild: discord.Guild, requester_id: int) -> None:
        super().__init__(owner_id=requester_id, timeout=60)
        self.guild = guild
        self._build()

    def _build(self) -> None:
        g = self.guild
        owner = f"<@{g.owner_id}>" if g.owner_id else "*Inconnu*"

        c = Container()
        c.add_item(TextDisplay("# <:erreur:1495443907281031359> Confirmation — Kick bot"))
        c.add_item(Separator())
        c.add_item(TextDisplay(
            f"GuideOn va **quitter** ce serveur :\n\n"
            f"⇝ **Nom :** {g.name}\n"
            f"⇝ **ID :** `{g.id}`\n"
            f"⇝ **Propriétaire :** {owner}\n"
            f"⇝ **Membres :** `{g.member_count}`\n\n"
            f"<:erreur:1495443907281031359> Confirmer ?"
        ))
        c.add_item(Separator())

        btn_confirm = Button(label="<:valider:1495444292867723284> Confirmer", style=ButtonStyle.danger, custom_id="kick_confirm")
        btn_cancel = Button(label="<:annuler:1495444256754761979> Annuler", style=ButtonStyle.secondary, custom_id="kick_cancel")
        btn_confirm.callback = self._on_confirm
        btn_cancel.callback = self._on_cancel
        c.add_item(ActionRow(btn_confirm, btn_cancel))
        c.add_item(TextDisplay("-# GuideOn Studio"))
        self.add_item(c)

    async def _on_confirm(self, interaction: Interaction) -> None:
        await interaction.response.defer()
        g = self.guild
        name, gid = g.name, g.id

        try:
            await leave_guild(g)
        except KickError as e:
            await interaction.edit_original_response(view=error_container(e.message))
            return

        log.info("[DEV_KICK] Bot a quitté %s (%d) | demandé par %d", name, gid, self.owner_id)
        await interaction.edit_original_response(
            view=success_container(f"GuideOn a quitté **{name}** (`{gid}`)."))
        self.stop()

    async def _on_cancel(self, interaction: Interaction) -> None:
        await interaction.response.edit_message(view=warning_container("Départ annulé."))
        self.stop()


def build_confirm_kick_view(guild: discord.Guild, requester_id: int) -> ConfirmKickView:
    """Construit la vue de confirmation pour /dev kick."""
    return ConfirmKickView(guild, requester_id)