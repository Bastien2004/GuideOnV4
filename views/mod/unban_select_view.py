"""
views/mod/unban_select_view.py — Selection paginee des membres bannis
(guild.bans()), pour /mod unban.

Un UserSelect natif ne peut pas lister un membre banni (il a quitte le
serveur, Discord ne le propose pas dans un select de membres) : on
reconstruit donc la meme UX de selection paginee que les menus existants,
mais a partir de la liste de bans Discord elle-meme.
"""
from __future__ import annotations

import logging

import discord
from discord.ui import ActionRow, Container, Select, Separator, TextDisplay

from utils.container_universel import error_container
from utils.managers.mod_sanction_manager import unban as apply_unban
from views._components.paginated_view import PaginatedView
from views.mod._revocation_common import RevocationConfirmView

log = logging.getLogger(__name__)

# Borne defensive : on ne charge jamais plus de MAX_BANS_FETCHED entrees en
# une fois (evite de saturer l'API sur un serveur avec un tres grand nombre
# de bans — cas extreme mais possible).
MAX_BANS_FETCHED = 1000


async def fetch_banned_entries(guild: discord.Guild) -> list[dict]:
    """Recupere la liste des membres bannis du serveur (bornee a MAX_BANS_FETCHED)."""
    entries: list[dict] = []
    async for ban_entry in guild.bans(limit=MAX_BANS_FETCHED):
        entries.append({
            "user_id": ban_entry.user.id,
            "user": ban_entry.user,
            "reason": ban_entry.reason,
        })
    return entries


class UnbanSelectView(PaginatedView):
    """Liste paginee des membres bannis, pour selectionner qui debannir."""

    def __init__(self, entries: list[dict], *, guild: discord.Guild, moderator_id: int):
        self.guild = guild
        self.moderator_id = moderator_id
        super().__init__(entries, per_page=25, owner_id=moderator_id, timeout=300)

    def build_page_container(self, page_items: list[dict]) -> Container:
        container = Container()
        container.add_item(TextDisplay("# 🔓 Débannir un membre"))
        container.add_item(TextDisplay(f"-# {len(self.items)} membre(s) banni(s) au total"))
        container.add_item(Separator())

        if not page_items:
            container.add_item(TextDisplay("-# 🤷 Aucun membre banni sur ce serveur."))
            return container

        options = [
            discord.SelectOption(
                label=str(entry["user"])[:100],
                description=(entry["reason"] or "Aucune raison enregistrée")[:100],
                value=str(entry["user_id"]),
            )
            for entry in page_items
        ]

        select = Select(placeholder="Choisir un membre banni", options=options, min_values=1, max_values=1)
        select.callback = self._make_callback(select)
        container.add_item(ActionRow(select))
        return container

    def _make_callback(self, select: Select):
        async def cb(interaction: discord.Interaction) -> None:
            user_id = int(select.values[0])
            entry = next((e for e in self.items if e["user_id"] == user_id), None)
            if entry is None:
                await interaction.response.send_message(
                    view=error_container("Membre introuvable dans la liste des bannis."), ephemeral=True,
                )
                return

            target_display = f"**{entry['user']}** (`{user_id}`)"

            async def on_confirm(reason: str | None) -> dict:
                return await apply_unban(self.guild, user_id, self.moderator_id, reason)

            async def build_back_view() -> discord.ui.View:
                return UnbanSelectView(self.items, guild=self.guild, moderator_id=self.moderator_id)

            confirm_view = RevocationConfirmView(
                title="Confirmer le débannissement",
                target_display=target_display,
                moderator_id=self.moderator_id,
                on_confirm=on_confirm,
                build_back_view=build_back_view,
                action_label="levée du bannissement",
            )
            await interaction.response.edit_message(view=confirm_view)
        return cb
