"""
views/mod/unmute_select_view.py — Selection paginee des membres actuellement
mutes (/mod unmute).

Un UserSelect natif listerait n'importe quel membre du serveur sans
distinguer qui est reellement mute : on liste donc directement les mutes
actifs enregistres en base (utils.managers.mod_sanction_manager.get_active_mutes).
"""
from __future__ import annotations

import discord
from discord.ui import ActionRow, Container, Select, Separator, TextDisplay

from utils.container_universel import error_container
from utils.managers.mod_sanction_manager import unmute as apply_unmute
from views._components.paginated_view import PaginatedView
from views.mod._revocation_common import RevocationConfirmView


class UnmuteSelectView(PaginatedView):
    """Liste paginee des membres mutes actifs, pour selectionner qui demuter."""

    def __init__(self, entries: list[dict], *, guild: discord.Guild, moderator_id: int):
        self.guild = guild
        self.moderator_id = moderator_id
        super().__init__(entries, per_page=25, owner_id=moderator_id, timeout=300)

    def build_page_container(self, page_items: list[dict]) -> Container:
        container = Container()
        container.add_item(TextDisplay("# 🔊 Lever un mute"))
        container.add_item(TextDisplay(f"-# {len(self.items)} membre(s) muet(s) actuellement"))
        container.add_item(Separator())

        if not page_items:
            container.add_item(TextDisplay("-# 🤷 Aucun membre muet sur ce serveur."))
            return container

        options = []
        for entry in page_items:
            member = self.guild.get_member(entry["user_id"])
            who = member.display_name if member is not None else f"Membre {entry['user_id']}"
            options.append(
                discord.SelectOption(
                    label=who[:100],
                    description=f"#{entry['id']} — {entry['reason']}"[:100],
                    value=entry["id"],
                )
            )

        select = Select(placeholder="Choisir un membre à démuter", options=options, min_values=1, max_values=1)
        select.callback = self._make_callback(select)
        container.add_item(ActionRow(select))
        return container

    def _make_callback(self, select: Select):
        async def cb(interaction: discord.Interaction) -> None:
            sanction_id = select.values[0]
            entry = next((e for e in self.items if e["id"] == sanction_id), None)
            if entry is None:
                await interaction.response.send_message(
                    view=error_container("Sanction introuvable."), ephemeral=True,
                )
                return

            member = self.guild.get_member(entry["user_id"])
            if member is None:
                try:
                    member = await self.guild.fetch_member(entry["user_id"])
                except discord.HTTPException:
                    await interaction.response.send_message(
                        view=error_container("Ce membre ne semble plus être sur ce serveur."),
                        ephemeral=True,
                    )
                    return

            target_display = member.mention

            async def on_confirm(reason: str | None) -> dict:
                return await apply_unmute(member, self.moderator_id, reason)

            async def build_back_view() -> discord.ui.View:
                return UnmuteSelectView(self.items, guild=self.guild, moderator_id=self.moderator_id)

            confirm_view = RevocationConfirmView(
                title="Confirmer la levée du mute",
                target_display=target_display,
                moderator_id=self.moderator_id,
                on_confirm=on_confirm,
                build_back_view=build_back_view,
                action_label="levée de mute",
            )
            await interaction.response.edit_message(view=confirm_view)
        return cb
