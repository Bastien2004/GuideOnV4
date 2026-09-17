"""
views/mod/logs_config_view.py — Interface de configuration du système de logs (/mod logs).
"""

from __future__ import annotations

import discord
from discord import ButtonStyle
from discord.ui import ActionRow, Button, Container, Section, Separator, TextDisplay

from utils.boutique.gold_manager import is_gold, send_gold_error
from utils.container_universel import error_container, warning_container

from utils.settings import settings
from views._components.base_view import BaseLayoutView
from views._components.channel_select import ChannelSelect

from utils.managers.mod_log_manager import (
    GOLD_REQUIRED_PACKS,
    PACK_KEYS,
    PACK_LABELS,
    LogConfigError,
    clear_mod_action_channel,
    load_log_config,
    set_channel,
    set_mod_action_channel,
    set_pack,
)


# ============================================================
# 🥰 Emojis
# ============================================================

ICON_MODIFIER = "<:modifier:1495444144712192003>"
ICON_VALIDER = "<:valider:1495444292867723284>"
ICON_ANNULER = "<:annuler:1495444256754761979>"


# ============================================================
# 🔩 Paramètres
# ============================================================

PACK_DESCRIPTIONS: dict[str, str] = {
    "stagiaire": (
        "Messages supprimés et modifiés, arrivées et départs,\n"
        "dons et retraits de rôles et actions GuideON MOD."
    ),
    "chercheur": (
        "Pack Stagiaire + gestion des salons et des rôles,\n"
        "connexion et déconnexion vocale, mise en muet/sourdine,\n"
        "expulsion et déplacement vocal, modification du serveur et renommage."
    ),
    "espion": (
        "Logs Chercheur + création et suppression d'emojis et stickers,\n"
        "changements de nom et d'avatar, boosts serveur, message\n."
        "épinglé et désépinglé."
    ),
}


# ============================================================
# 💻 Création de l'interface
# ============================================================

class LogsConfigView(BaseLayoutView):
    """Construction du /mod logs."""

    def __init__(self, *, guild: discord.Guild, moderator_id: int, cfg: dict | None = None):
        super().__init__(owner_id=moderator_id, timeout=300)
        self.guild = guild
        self.moderator_id = moderator_id
        self.cfg = cfg or {"log_channel_id": None, "selected_pack": None, "mod_action_channel_id": None}
        self._build()

    @classmethod
    async def create(cls, *, guild: discord.Guild, moderator_id: int) -> "LogsConfigView":
        cfg = await load_log_config(guild.id)
        return cls(guild=guild, moderator_id=moderator_id, cfg=cfg)


    def _build(self) -> None:
        self.clear_items()

        container = Container()
        container.add_item(TextDisplay("# <:protect_config:1539608365704028340> Configuration des logs"))
        container.add_item(Separator())

        channel_id = self.cfg.get("log_channel_id")
        channel_display = f"<#{channel_id}>" if channel_id else "`Non configuré`"
        select = ChannelSelect(
            placeholder="Choisir le salon de logs",
            on_select=self._on_select_channel,
            channel_types=[discord.ChannelType.text, discord.ChannelType.news],
        )
        container.add_item(TextDisplay(f"**📍 Salon de logs** : -# {channel_display}"))
        container.add_item(ActionRow(select))
        container.add_item(Separator())


        mod_action_channel_id = self.cfg.get("mod_action_channel_id")
        mod_action_display = f"<#{mod_action_channel_id}>" if mod_action_channel_id else "`Non configuré`"
        mod_action_select = ChannelSelect(
            placeholder="(Option) Choisir le salon de modération",
            on_select=self._on_select_mod_action_channel,
            channel_types=[discord.ChannelType.text, discord.ChannelType.news],
        )
        container.add_item(TextDisplay(
            f"**🛡️ Salon de modération** : -# {mod_action_display}\n"
            "-# Une fois configuré, les actions de modération (warn/mute/ban …)\n"
            " y sont envoyées exclusivement et indépendamment des pack."
        ))
        container.add_item(ActionRow(mod_action_select))
        if mod_action_channel_id:
            btn_clear_mod_action = Button(
                label="Retirer le salon dédié", style=ButtonStyle.danger,
                emoji="<:supprimer:1495444051623809075>",
            )
            btn_clear_mod_action.callback = self._on_clear_mod_action_channel
            container.add_item(ActionRow(btn_clear_mod_action))
        container.add_item(Separator())

        container.add_item(TextDisplay(
            "**📦 Pack actif**\n"
            "-# Un seul pack peut être actif à la fois. En activer un nouveau désactive l'ancien."
        ))
        container.add_item(Separator())

        selected_pack = self.cfg.get("selected_pack")
        server_is_gold = is_gold(self.guild.id)

        for pack_key in PACK_KEYS:
            emoji, label = PACK_LABELS[pack_key]
            active = selected_pack == pack_key
            gold_locked = pack_key in GOLD_REQUIRED_PACKS and not server_is_gold

            status = "🟢" if active else "⚫"
            gold_hint = " ✨" if pack_key in GOLD_REQUIRED_PACKS else ""
            text = f"{status} {emoji} __**{label}**__{gold_hint}\n-# {PACK_DESCRIPTIONS[pack_key]}"

            if gold_locked:
                btn = Button(label="Gold+", style=ButtonStyle.secondary, emoji="✨")
            elif active:
                btn = Button(label="Activé", style=ButtonStyle.success, emoji=ICON_VALIDER)
            else:
                btn = Button(label="Désactivé", style=ButtonStyle.danger, emoji=ICON_ANNULER)
            btn.callback = self._make_toggle_callback(pack_key)

            container.add_item(Section(TextDisplay(text), accessory=btn))
            container.add_item(Separator())

        btn_doc = Button(label="Documentation", style=ButtonStyle.link, url=settings.doc_url, emoji="📚")
        container.add_item(ActionRow(btn_doc))
        container.add_item(Separator())
        container.add_item(TextDisplay("-# GuideOn Studio"))

        self.add_item(container)

    async def _refresh(self, interaction: discord.Interaction) -> None:
        self.cfg = await load_log_config(self.guild.id)
        self._build()
        await self.push_update(interaction)

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    async def _on_select_channel(self, interaction: discord.Interaction, channel_id: int) -> None:
        channel = self.guild.get_channel(channel_id)
        if channel is not None and self.guild.me is not None:
            perms = channel.permissions_for(self.guild.me)
            if not (perms.send_messages and perms.view_channel):
                await interaction.response.send_message(
                    view=error_container(f"Je n'ai pas la permission d'écrire dans {channel.mention}."),
                    ephemeral=True,
                )
                return

        await set_channel(self.guild.id, channel_id)
        await self._refresh(interaction)

    async def _on_select_mod_action_channel(self, interaction: discord.Interaction, channel_id: int) -> None:
        channel = self.guild.get_channel(channel_id)
        if channel is not None and self.guild.me is not None:
            perms = channel.permissions_for(self.guild.me)
            if not (perms.send_messages and perms.view_channel):
                await interaction.response.send_message(
                    view=error_container(f"Je n'ai pas la permission d'écrire dans {channel.mention}."),
                    ephemeral=True,
                )
                return

        await set_mod_action_channel(self.guild.id, channel_id)
        await self._refresh(interaction)

    async def _on_clear_mod_action_channel(self, interaction: discord.Interaction) -> None:
        await clear_mod_action_channel(self.guild.id)
        await self._refresh(interaction)

    def _make_toggle_callback(self, pack_key: str):
        async def cb(interaction: discord.Interaction) -> None:
            if pack_key in GOLD_REQUIRED_PACKS and not is_gold(self.guild.id):
                await send_gold_error(interaction)
                return

            new_value = None if self.cfg.get("selected_pack") == pack_key else pack_key
            try:
                await set_pack(self.guild.id, new_value)
            except LogConfigError as e:
                view = warning_container(e.message) if e.warning else error_container(e.message)
                await interaction.response.send_message(view=view, ephemeral=True)
                return

            await self._refresh(interaction)
        return cb