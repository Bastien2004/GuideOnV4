"""
views/mod/unwarn_select_view.py — Selection paginee des avertissements
actifs (non revoques) du serveur, pour /mod unwarn.

Liste directement les warns (et non les membres) : un membre averti peut
avoir quitte le serveur depuis, ce qu'un UserSelect natif (limite aux
membres actuels) ne permettrait pas de retrouver.
"""
from __future__ import annotations

import discord
from discord.ui import ActionRow, Container, Select, Separator, TextDisplay

from utils.container_universel import error_container
from utils.managers.mod_sanction_manager import unwarn as apply_unwarn
from views._components.paginated_view import PaginatedView
from views.mod._revocation_common import RevocationConfirmView


class UnwarnSelectView(PaginatedView):
    """Liste paginee des avertissements actifs, pour selectionner lequel revoquer."""

    def __init__(self, entries: list[dict], *, guild: discord.Guild, moderator_id: int):
        self.guild = guild
        self.moderator_id = moderator_id
        super().__init__(entries, per_page=25, owner_id=moderator_id, timeout=300)

    def build_page_container(self, page_items: list[dict]) -> Container:
        container = Container()
        container.add_item(TextDisplay("# 🚫 Révoquer un avertissement"))
        container.add_item(TextDisplay(f"-# {len(self.items)} avertissement(s) actif(s)"))
        container.add_item(Separator())

        if not page_items:
            container.add_item(TextDisplay("-# 🤷 Aucun avertissement actif sur ce serveur."))
            return container

        options = []
        for entry in page_items:
            member = self.guild.get_member(entry["user_id"])
            who = member.display_name if member is not None else f"Membre {entry['user_id']}"
            options.append(
                discord.SelectOption(
                    label=f"#{entry['id']} — {who}"[:100],
                    description=entry["reason"][:100],
                    value=entry["id"],
                )
            )

        select = Select(placeholder="Choisir un avertissement à révoquer", options=options, min_values=1, max_values=1)
        select.callback = self._make_callback(select)
        container.add_item(ActionRow(select))
        return container

    def _make_callback(self, select: Select):
        async def cb(interaction: discord.Interaction) -> None:
            sanction_id = select.values[0]
            entry = next((e for e in self.items if e["id"] == sanction_id), None)
            if entry is None:
                await interaction.response.send_message(
                    view=error_container("Avertissement introuvable."), ephemeral=True,
                )
                return

            member = self.guild.get_member(entry["user_id"])
            target_display = member.mention if member is not None else f"<@{entry['user_id']}>"

            async def on_confirm(reason: str | None) -> dict:
                return await apply_unwarn(entry["id"], self.moderator_id, reason)

            async def build_back_view() -> discord.ui.View:
                return UnwarnSelectView(self.items, guild=self.guild, moderator_id=self.moderator_id)

            confirm_view = RevocationConfirmView(
                title="Confirmer la révocation de l'avertissement",
                target_display=target_display,
                moderator_id=self.moderator_id,
                on_confirm=on_confirm,
                build_back_view=build_back_view,
                action_label="révocation de l'avertissement",
            )
            await interaction.response.edit_message(view=confirm_view)
        return cb
