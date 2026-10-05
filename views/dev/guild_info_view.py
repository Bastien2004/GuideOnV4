"""
views/dev/guild_info_view.py — Panel d'informations serveur pour /dev guild_info.

2026-10-06 (Paul, refonte) : remplace l'ancienne vue plate (LayoutView
statique, 6 TextDisplay, un seul écran) par un vrai panel interactif
BaseLayoutView à deux pages, dans le style des autres panels GuideOn
(Section/accessory, boutons de navigation, émojis custom) :

 - GuildInfoOverviewView : infos Discord du serveur + stats bot + résumé
   des systèmes configurés, avec un bouton "Systèmes" vers le détail et un
   bouton "Actualiser".
 - GuildInfoSystemsView : détail d'une catégorie de systèmes (Modération /
   Automod / Serveur / Engagement / Extra), sélectionnée via une rangée de
   5 boutons (une par catégorie — c'est tout ce qu'un ActionRow Discord
   peut contenir), avec "Retour" et "Actualiser".

Le snapshot GuildInfoData (déjà coûteux : ~25 managers) est réutilisé tel
quel entre l'aperçu et les onglets de la page Systèmes — changer d'onglet
ne refait AUCUNE requête DB. Seul le bouton "Actualiser" (sur les deux
pages) relance utils.guild_info.gather_guild_info pour prendre un nouveau
snapshot.
"""
from __future__ import annotations

import discord
from discord import ButtonStyle
from discord.ui import ActionRow, Button, Container, Section, Separator, TextDisplay

from utils.guild_info import GuildInfoData, SystemCategory, gather_guild_info
from views._components.base_view import BaseLayoutView

EMOJI_BACK = "<:retour:1515658955190308995>"
EMOJI_REFRESH = "🔄"
EMOJI_SYSTEMS = "🧩"


def _state_emoji(ok: bool) -> str:
    return "🟢" if ok else "🔴"


# ============================================================
# 🏠 Page 1 — Aperçu
# ============================================================

class GuildInfoOverviewView(BaseLayoutView):
    """Page principale : infos Discord + stats bot + résumé systèmes."""

    def __init__(self, *, guild: discord.Guild, info: GuildInfoData, owner_id: int):
        super().__init__(owner_id=owner_id, timeout=600)
        self.guild = guild
        self.info = info
        self._build()

    @classmethod
    async def build(cls, *, guild: discord.Guild, owner_id: int) -> "GuildInfoOverviewView":
        info = await gather_guild_info(guild)
        return cls(guild=guild, info=info, owner_id=owner_id)

    def _build(self) -> None:
        guild, info = self.guild, self.info
        container = Container()

        container.add_item(TextDisplay(f"# 🏠 {guild.name}"))
        container.add_item(Separator())

        owner_mention = f"<@{guild.owner_id}>" if guild.owner_id else "*Inconnu*"
        container.add_item(TextDisplay("### 📋 __Discord__ :"))
        container.add_item(TextDisplay(
            f"**ID :** `{guild.id}`\n"
            f"**Propriétaire :** {owner_mention}\n"
            f"**Membres :** {guild.member_count or 0}\n"
            f"**Créé :** {discord.utils.format_dt(guild.created_at, style='D')}\n"
            f"**Salons :** {len(guild.channels)} • **Rôles :** {len(guild.roles)}\n"
            f"**Boost :** Niveau {guild.premium_tier} ({guild.premium_subscription_count} boost(s))"
        ))
        container.add_item(Separator())

        admin_state = _state_emoji(info.bot_is_admin)
        container.add_item(TextDisplay("### 🤖 __Bot__ :"))
        container.add_item(TextDisplay(
            f"**Ajout au serveur :** {info.bot_joined_at}\n"
            f"**Permissions :** {admin_state} {info.bot_perms_label}\n"
            f"**Shard :** {guild.shard_id if guild.shard_id is not None else 0}"
        ))
        container.add_item(Separator())

        container.add_item(TextDisplay(
            f"### {EMOJI_SYSTEMS} __Systèmes__ — {info.active_count}/{info.total_count} actif(s) :"
        ))
        summary_lines = [
            f"{cat.emoji} **{cat.label}** — {cat.active_count}/{cat.toggle_count} actif(s)"
            for cat in info.categories
        ]
        systems_btn = Button(label="Détails des systèmes", style=ButtonStyle.primary, emoji=EMOJI_SYSTEMS)
        systems_btn.callback = self._cb_open_systems
        container.add_item(Section(
            TextDisplay("\n".join(summary_lines)),
            accessory=systems_btn,
        ))
        container.add_item(Separator())

        refresh_btn = Button(label="Actualiser", style=ButtonStyle.secondary, emoji=EMOJI_REFRESH)
        refresh_btn.callback = self._cb_refresh
        container.add_item(ActionRow(refresh_btn))

        container.add_item(Separator())
        container.add_item(TextDisplay("-# GuideOn Studio"))

        self.add_item(container)

    async def _cb_open_systems(self, interaction: discord.Interaction) -> None:
        view = GuildInfoSystemsView(
            guild=self.guild, info=self.info, owner_id=self.owner_id,
            active_key=self.info.categories[0].key,
        )
        await self.push_update(interaction, view=view)

    async def _cb_refresh(self, interaction: discord.Interaction) -> None:
        view = await GuildInfoOverviewView.build(guild=self.guild, owner_id=self.owner_id)
        await self.push_update(interaction, view=view)


# ============================================================
# 🧩 Page 2 — Détail des systèmes (onglets par catégorie)
# ============================================================

class GuildInfoSystemsView(BaseLayoutView):
    """Détail d'une catégorie de systèmes, avec bascule par boutons."""

    def __init__(self, *, guild: discord.Guild, info: GuildInfoData, owner_id: int, active_key: str):
        super().__init__(owner_id=owner_id, timeout=600)
        self.guild = guild
        self.info = info
        self.active_key = active_key
        self._build()

    def _active_category(self) -> SystemCategory:
        return next(c for c in self.info.categories if c.key == self.active_key)

    def _build(self) -> None:
        cat = self._active_category()
        container = Container()

        container.add_item(TextDisplay(f"# {EMOJI_SYSTEMS} Systèmes — {self.guild.name}"))
        container.add_item(Separator())

        container.add_item(TextDisplay(
            f"### {cat.emoji} __{cat.label}__ — {cat.active_count}/{cat.toggle_count} actif(s) :"
        ))
        entries_text = "\n".join(entry.render() for entry in cat.entries) or "*Aucune entrée.*"
        container.add_item(TextDisplay(entries_text))
        container.add_item(Separator())

        tab_buttons = []
        for category in self.info.categories:
            style = ButtonStyle.primary if category.key == self.active_key else ButtonStyle.secondary
            btn = Button(label=category.label, style=style, emoji=category.emoji)
            btn.callback = self._cb_switch(category.key)
            tab_buttons.append(btn)
        container.add_item(ActionRow(*tab_buttons))

        back_btn = Button(label="Retour", style=ButtonStyle.secondary, emoji=EMOJI_BACK)
        back_btn.callback = self._cb_back
        refresh_btn = Button(label="Actualiser", style=ButtonStyle.secondary, emoji=EMOJI_REFRESH)
        refresh_btn.callback = self._cb_refresh
        container.add_item(ActionRow(back_btn, refresh_btn))

        container.add_item(Separator())
        container.add_item(TextDisplay("-# GuideOn Studio"))

        self.add_item(container)

    def _cb_switch(self, key: str):
        async def _callback(interaction: discord.Interaction) -> None:
            view = GuildInfoSystemsView(
                guild=self.guild, info=self.info, owner_id=self.owner_id, active_key=key,
            )
            await self.push_update(interaction, view=view)
        return _callback

    async def _cb_back(self, interaction: discord.Interaction) -> None:
        view = GuildInfoOverviewView(guild=self.guild, info=self.info, owner_id=self.owner_id)
        await self.push_update(interaction, view=view)

    async def _cb_refresh(self, interaction: discord.Interaction) -> None:
        info = await gather_guild_info(self.guild)
        view = GuildInfoSystemsView(
            guild=self.guild, info=info, owner_id=self.owner_id, active_key=self.active_key,
        )
        await self.push_update(interaction, view=view)


# ============================================================
# 🧭 Point d'entrée pour cogs/dev/guild_info.py
# ============================================================

async def build_guild_info_view(guild: discord.Guild, owner_id: int) -> GuildInfoOverviewView:
    """Construit directement la page d'aperçu (appelle gather_guild_info)."""
    return await GuildInfoOverviewView.build(guild=guild, owner_id=owner_id)
