"""
views/_components/select_page.py — Page de sélection centralisée (rôle / salon / catégorie / utilisateur).


Exemple usage avec le système d'auto-rôle (cf views/autorole/config_view.py) :

    async def _cb_set_role(interaction: discord.Interaction) -> None:
        await interaction.response.edit_message(
            view=SelectPageView(
                kind="role",
                title="🎯 Rôle automatique 1",
                current_value=cfg.get("role_id_1"),
                owner_id=author_id,
                on_save=lambda value: save_autorole_config(guild_id, {"role_id_1": value}),
                build_return_view=lambda: create_autorole_view(guild_id, bot, author_id),
            )
        )
"""

from __future__ import annotations

import logging
from typing import Awaitable, Callable, Literal, Optional

import discord
from discord import ButtonStyle
from discord.ui import ActionRow, Button, Container, LayoutView, Separator, TextDisplay

from utils.container_universel import error_container
from views._components.base_view import BaseLayoutView
from views._components.channel_select import ChannelSelect
from views._components.role_select import RoleSelect
from views._components.user_select import UserSelect

from utils.settings import settings

log = logging.getLogger(__name__)

SelectKind = Literal["role", "channel", "category", "user"]


_DEFAULT_CHANNEL_TYPES: dict[str, list[discord.ChannelType]] = {
    "channel": [discord.ChannelType.text, discord.ChannelType.news],
    "category": [discord.ChannelType.category],
}

BuildReturnView = Callable[[], Awaitable[LayoutView]]
OnSave = Callable[[int], Awaitable[None]]
Validate = Callable[[discord.Interaction, int], Awaitable[Optional[str]]]


def _display_current(kind: SelectKind, value: int | None) -> str:
    """Rendu de la valeur actuelle — mentions Discord brutes, résolues côté client."""
    if value is None:
        return "`Non configuré`"
    if kind == "role":
        return f"<@&{value}>"
    if kind == "user":
        return f"<@{value}>"
    return f"<#{value}>"  # channel / category


class SelectPageView(BaseLayoutView):
    """Page de sélection unique, centralisée, pour rôle/salon/catégorie/utilisateur."""

    def __init__(
        self,
        *,
        kind: SelectKind,
        title: str,
        build_return_view: BuildReturnView,
        on_save: OnSave,
        current_value: int | None = None,
        description: str | None = None,
        placeholder: str | None = None,
        channel_types: list[discord.ChannelType] | None = None,
        validate: Validate | None = None,
        owner_id: int | None = None,
        doc_url: str = settings.doc_url,
        timeout: float | None = 300,
    ) -> None:
        super().__init__(owner_id=owner_id, timeout=timeout)

        self._build_return_view = build_return_view
        self._on_save = on_save
        self._validate = validate
        self._kind = kind

        select = self._make_select(kind, placeholder, channel_types)

        container = Container()
        container.add_item(TextDisplay(f"# {title}"))
        container.add_item(Separator())
        if description:
            container.add_item(TextDisplay(description))
        container.add_item(TextDisplay(f"**Actuellement :** {_display_current(kind, current_value)}"))
        container.add_item(ActionRow(select))
        container.add_item(Separator())

        back_btn = Button(label="Retour", style=ButtonStyle.secondary, emoji="<:retour:1515658955190308995>")
        back_btn.callback = self._on_back

        doc_btn = Button(label="Documentation", style=ButtonStyle.link, url=doc_url, emoji="📚")
        container.add_item(ActionRow(back_btn, doc_btn))

        container.add_item(Separator())
        container.add_item(TextDisplay("-# GuideOn Studio"))

        self.add_item(container)

    # ── Construction du select selon le kind ─────────────────

    def _make_select(
        self,
        kind: SelectKind,
        placeholder: str | None,
        channel_types: list[discord.ChannelType] | None,
    ):
        if kind == "role":
            return RoleSelect(
                placeholder=placeholder or "Choisir un rôle",
                on_select=self._on_select_role,
            )
        if kind == "user":
            return UserSelect(
                placeholder=placeholder or "Choisir un utilisateur",
                on_select=self._on_select_user,
            )
        if kind in ("channel", "category"):
            types = channel_types or _DEFAULT_CHANNEL_TYPES[kind]
            default_ph = "Choisir un salon" if kind == "channel" else "Choisir une catégorie"
            return ChannelSelect(
                placeholder=placeholder or default_ph,
                channel_types=types,
                on_select=self._on_select_channel,
            )
        raise ValueError(f"SelectPageView: kind inconnu {kind!r}")

    # ── Callbacks des selects (signatures différentes selon le composant) ──

    async def _on_select_role(self, interaction: discord.Interaction, ids: list[int]) -> None:
        await self._finish(interaction, ids[0])

    async def _on_select_user(self, interaction: discord.Interaction, ids: list[int]) -> None:
        await self._finish(interaction, ids[0])

    async def _on_select_channel(self, interaction: discord.Interaction, channel_id: int) -> None:
        await self._finish(interaction, channel_id)

    # ── Sauvegarde + retour à la page précédente ─────────────

    async def _finish(self, interaction: discord.Interaction, value: int) -> None:
        if self._validate is not None:
            error = await self._validate(interaction, value)
            if error:
                await interaction.response.send_message(
                    view=error_container(error), ephemeral=True
                )
                return

        await self._on_save(value)
        return_view = await self._build_return_view()
        await self.push_update(interaction, view=return_view)

    async def _on_back(self, interaction: discord.Interaction) -> None:
        return_view = await self._build_return_view()
        await self.push_update(interaction, view=return_view)