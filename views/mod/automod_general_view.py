"""
views/mod/automod_general_view.py — Configuration des paramètres généraux automod.

Deux réglages :
  - salon d'alerte staff (ChannelSelect, textuel/annonce uniquement)
  - notifications dans le salon d'origine (toggle bool)
"""
from __future__ import annotations

import discord
from discord import ButtonStyle, Interaction
from discord.ui import ActionRow, Button, Container, Section, Separator, TextDisplay

from utils.container_universel import error_container
from utils.managers import mod_automod_general_manager as general_mgr
from views._components.base_view import BaseLayoutView
from views._components.channel_select import ChannelSelect


CHANNEL_TYPES = [discord.ChannelType.text, discord.ChannelType.news]


class AutomodGeneralView(BaseLayoutView):
    """Vue de configuration des paramètres généraux d'automod."""

    def __init__(self, *, guild: discord.Guild, owner_id: int, cfg: dict, parent_dashboard):
        super().__init__(owner_id=owner_id, timeout=300)
        self.guild = guild
        self.cfg = cfg
        self.parent_dashboard = parent_dashboard
        self._build()

    @classmethod
    async def build(
        cls, *, guild: discord.Guild, owner_id: int, parent_dashboard,
    ) -> "AutomodGeneralView":
        cfg = await general_mgr.load_general(guild.id)
        return cls(guild=guild, owner_id=owner_id, cfg=cfg, parent_dashboard=parent_dashboard)

    async def _refresh(self, interaction: Interaction) -> None:
        self.cfg = await general_mgr.load_general(self.guild.id)
        self.clear_items()
        self._build()
        await self.push_update(interaction)

    def _build(self) -> None:
        container = Container()
        container.add_item(TextDisplay("# ⚙️ Paramètres généraux"))
        container.add_item(TextDisplay(
            "-# Réglages transverses à tous les systèmes d'auto-modération."
        ))
        container.add_item(Separator())

        # ── Salon d'alerte staff ──────────────────────────
        alert_ch_id = self.cfg.get("alert_channel_id")
        alert_ch_line = (
            f"<#{alert_ch_id}>" if alert_ch_id else "`Aucun salon configuré`"
        )
        container.add_item(TextDisplay(
            f"**📥 Salon d'alerte staff**\n"
            f"-# Chaque infraction y sera loggée avec les détails complets.\n"
            f"-# Actuel : {alert_ch_line}"
        ))
        select = ChannelSelect(
            placeholder="Choisir un salon d'alerte",
            on_select=self._on_channel_select,
            channel_types=CHANNEL_TYPES,
        )
        container.add_item(ActionRow(select))

        if alert_ch_id:
            btn_clear = Button(
                label="Retirer le salon d'alerte", emoji="🗑️", style=ButtonStyle.danger,
            )
            btn_clear.callback = self._on_clear_alert_channel
            container.add_item(ActionRow(btn_clear))

        container.add_item(Separator())

        # ── Toggle notifications dans le salon ───────────
        notify = self.cfg.get("notify_in_channel", True)
        toggle_label = "Désactiver" if notify else "Activer"
        toggle_emoji = "🔕" if notify else "🔔"
        toggle_style = ButtonStyle.danger if notify else ButtonStyle.success
        state_line = "✅ Activées" if notify else "❌ Désactivées"

        btn_toggle = Button(label=toggle_label, emoji=toggle_emoji, style=toggle_style)
        btn_toggle.callback = self._on_toggle_notify

        container.add_item(Section(
            TextDisplay(
                f"**🔔 Notifications dans le salon d'origine**\n"
                f"-# Court message posté au membre lorsque son message est supprimé.\n"
                f"-# Actuel : {state_line}"
            ),
            accessory=btn_toggle,
        ))

        container.add_item(Separator())

        # ── Retour ────────────────────────────────────────
        btn_back = Button(label="Retour", emoji="↩️", style=ButtonStyle.secondary)
        btn_back.callback = self._on_back
        container.add_item(ActionRow(btn_back))

        container.add_item(Separator())
        container.add_item(TextDisplay("-# GuideOn Studio · Auto-modération"))
        self.add_item(container)

    # ────────────────────────────────────────────────────────
    # Callbacks
    # ────────────────────────────────────────────────────────

    async def _on_channel_select(self, interaction: Interaction, channel_id: int) -> None:
        channel = self.guild.get_channel(channel_id)
        if not isinstance(channel, (discord.TextChannel, discord.abc.GuildChannel)):
            await interaction.response.send_message(
                view=error_container("Salon invalide."), ephemeral=True,
            )
            return
        # Vérifie que le bot peut y envoyer.
        me = self.guild.me
        if me is not None and not channel.permissions_for(me).send_messages:
            await interaction.response.send_message(
                view=error_container(
                    f"Le bot n'a pas la permission d'écrire dans {channel.mention}."
                ),
                ephemeral=True,
            )
            return

        await general_mgr.save_general(self.guild.id, alert_channel_id=channel_id)
        await self._refresh(interaction)

    async def _on_clear_alert_channel(self, interaction: Interaction) -> None:
        await general_mgr.save_general(self.guild.id, alert_channel_id=None)
        await self._refresh(interaction)

    async def _on_toggle_notify(self, interaction: Interaction) -> None:
        current = self.cfg.get("notify_in_channel", True)
        await general_mgr.save_general(self.guild.id, notify_in_channel=not current)
        await self._refresh(interaction)

    async def _on_back(self, interaction: Interaction) -> None:
        # Recharge le dashboard parent pour refléter les nouveaux paramètres.
        from views.mod.automod_dashboard_view import AutomodDashboardView
        new_view = await AutomodDashboardView.build(
            guild=self.guild, owner_id=self.owner_id,
        )
        await interaction.response.edit_message(view=new_view)