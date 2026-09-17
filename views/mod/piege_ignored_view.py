"""
views/mod/piege_ignored_view.py — Gestion de l'immunité pour le piège (honeypot).
"""

from __future__ import annotations

import discord
from discord import ButtonStyle
from discord.ui import ActionRow, Button, Container, Section, Separator, TextDisplay

from views._components.paginated_view import PaginatedView
from views._components.role_select import RoleSelect
from views._components.user_select import UserSelect

from utils.managers.honeypot_manager import (
    add_ignored_member,
    add_ignored_role,
    load_config,
    remove_ignored_member,
    remove_ignored_role,
)


# ============================================================
# 🥰 Emojis
# ============================================================

ICON_HEADER = "<:bouclier:1539013183577133106>"
ICON_DELETE = "<:supprimer:1495444051623809075>"
EMOJI_BACK = "<:retour:1515658955190308995>"


# ============================================================
# 🔩 Paramètres
# ============================================================

MAX_ADD_AT_ONCE = 5
PER_PAGE = 7


# ============================================================
# 🖥️ Création de l'interface
# ============================================================

class PiegeIgnoredListView(PaginatedView):
    """Liste paginée des rôles/membres ignorés, avec ajout et suppression."""

    def __init__(self, *, guild: discord.Guild, moderator_id: int, ignored_role_ids: list[int], ignored_member_ids: list[int], page: int = 0):
        self.guild = guild
        self.moderator_id = moderator_id

        items: list[tuple[str, int]] = (
            [("role", role_id) for role_id in ignored_role_ids]
            + [("member", member_id) for member_id in ignored_member_ids]
        )
        super().__init__(items, per_page=PER_PAGE, owner_id=moderator_id)

        if page:
            self.page = min(page, self.total_pages - 1)
            self._build()

    @classmethod
    async def create(cls, *, guild: discord.Guild, moderator_id: int, page: int = 0) -> "PiegeIgnoredListView":
        cfg = await load_config(guild.id)
        return cls(
            guild=guild,
            moderator_id=moderator_id,
            ignored_role_ids=cfg.get("ignored_role_ids") or [],
            ignored_member_ids=cfg.get("ignored_member_ids") or [],
            page=page,
        )


    def build_page_container(self, page_items: list[tuple[str, int]]) -> Container:
        container = Container()
        container.add_item(TextDisplay(f"# {ICON_HEADER} Rôles & membres ignorés"))
        container.add_item(Separator())

        if not page_items:
            container.add_item(TextDisplay("-# Aucun rôle ni membre ignoré pour l'instant."))
        else:
            for entry_type, entry_id in page_items:
                container.add_item(Section(
                    TextDisplay(self._entry_label(entry_type, entry_id)),
                    accessory=self._remove_button(entry_type, entry_id),
                ))
        container.add_item(Separator())

        role_select = RoleSelect(
            placeholder="Ajouter un/des rôle(s) ignoré(s)",
            on_select=self._on_add_roles,
            max_values=MAX_ADD_AT_ONCE,
        )
        container.add_item(ActionRow(role_select))

        user_select = UserSelect(
            placeholder="Ajouter un/des membre(s) ignoré(s)",
            on_select=self._on_add_members,
            max_values=MAX_ADD_AT_ONCE,
        )
        container.add_item(ActionRow(user_select))
        container.add_item(Separator())

        back_btn = Button(label="Retour", style=ButtonStyle.secondary, emoji=EMOJI_BACK)
        back_btn.callback = self._cb_back
        container.add_item(ActionRow(back_btn))

        return container

    def _entry_label(self, entry_type: str, entry_id: int) -> str:
        if entry_type == "role":
            role = self.guild.get_role(entry_id)
            return f"🚫 {role.mention}" if role is not None else f"🚫 `Rôle supprimé ({entry_id})`"
        member = self.guild.get_member(entry_id)
        return f"🚫 {member.mention}" if member is not None else f"🚫 `Membre introuvable ({entry_id})`"

    def _remove_button(self, entry_type: str, entry_id: int) -> Button:
        btn = Button(style=ButtonStyle.danger, emoji=ICON_DELETE)
        btn.callback = self._cb_remove_role(entry_id) if entry_type == "role" else self._cb_remove_member(entry_id)
        return btn


    async def _on_add_roles(self, interaction: discord.Interaction, role_ids: list[int]) -> None:
        for role_id in role_ids:
            await add_ignored_role(self.guild.id, role_id)
        await self._reload(interaction)

    async def _on_add_members(self, interaction: discord.Interaction, member_ids: list[int]) -> None:
        for member_id in member_ids:
            await add_ignored_member(self.guild.id, member_id)
        await self._reload(interaction)


    def _cb_remove_role(self, role_id: int):
        async def _callback(interaction: discord.Interaction) -> None:
            await remove_ignored_role(self.guild.id, role_id)
            await self._reload(interaction)
        return _callback

    def _cb_remove_member(self, member_id: int):
        async def _callback(interaction: discord.Interaction) -> None:
            await remove_ignored_member(self.guild.id, member_id)
            await self._reload(interaction)
        return _callback


    async def _reload(self, interaction: discord.Interaction) -> None:
        """Rafraîchit l'interface avec les données mises à jour."""
        
        new_view = await PiegeIgnoredListView.create(guild=self.guild, moderator_id=self.moderator_id, page=self.page)
        await self.push_update(interaction, view=new_view)

    async def _cb_back(self, interaction: discord.Interaction) -> None:
        from views.mod.piege_config_view import PiegeConfigView

        view = await PiegeConfigView.create(guild=self.guild, moderator_id=self.moderator_id)
        await self.push_update(interaction, view=view)