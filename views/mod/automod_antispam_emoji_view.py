"""
views/mod/automod_antispam_emoji_view.py — Configuration Anti Spam Emoji.

2 réglages : toggle + max_emoji (unicode + custom Discord confondus).
"""
from __future__ import annotations

import discord
from discord import ButtonStyle, Interaction
from discord.ui import ActionRow, Button, Container, Section, Separator, TextDisplay

from utils.container_universel import warning_container
from utils.managers import mod_automod_antispam_emoji_manager as mgr
from views._components.base_view import BaseLayoutView
from views._components.text_modal import TextModal


MAX_EMOJI_ABS_MIN = 1
MAX_EMOJI_ABS_MAX = 100


class AutomodAntispamEmojiView(BaseLayoutView):
    """Configuration du système Anti Spam Emoji."""

    def __init__(self, *, guild: discord.Guild, owner_id: int, cfg: dict, parent_dashboard):
        super().__init__(owner_id=owner_id, timeout=300)
        self.guild = guild
        self.cfg = cfg
        self.parent_dashboard = parent_dashboard
        self._build()

    @classmethod
    async def build(cls, *, guild: discord.Guild, owner_id: int, parent_dashboard):
        cfg = await mgr.load_config(guild.id)
        return cls(guild=guild, owner_id=owner_id, cfg=cfg, parent_dashboard=parent_dashboard)

    async def _refresh(self, interaction: Interaction) -> None:
        self.cfg = await mgr.load_config(self.guild.id)
        self.clear_items()
        self._build()
        await self.push_update(interaction)

    def _build(self) -> None:
        container = Container()
        enabled = self.cfg.get("enabled", False)
        max_emoji = self.cfg.get("max_emoji", 10)

        state_dot = "🟢" if enabled else "🔴"
        state_label = "Activé" if enabled else "Désactivé"
        container.add_item(TextDisplay(f"# 😀 Anti Spam Emoji · {state_dot} {state_label}"))
        container.add_item(TextDisplay(
            "-# Bloque les messages contenant un nombre excessif d'emojis "
            "(Unicode + custom Discord confondus)."
        ))
        container.add_item(Separator())

        # Toggle
        toggle_label = "Désactiver" if enabled else "Activer"
        toggle_emoji_btn = "🔴" if enabled else "🟢"
        toggle_style = ButtonStyle.danger if enabled else ButtonStyle.success
        btn_toggle = Button(label=toggle_label, emoji=toggle_emoji_btn, style=toggle_style)
        btn_toggle.callback = self._on_toggle
        container.add_item(Section(
            TextDisplay(
                "**⚡ Activation**\n"
                "-# Analyse chaque message avant publication."
            ),
            accessory=btn_toggle,
        ))
        container.add_item(Separator())

        # Réglage
        btn_max = Button(label="Modifier", emoji="✏️", style=ButtonStyle.secondary)
        btn_max.callback = self._on_edit_max
        container.add_item(Section(
            TextDisplay(
                "**📊 Seuil de déclenchement**\n"
                f"-# Un message avec plus de **{max_emoji} emojis** est bloqué.\n"
                f"-# Plage autorisée : {MAX_EMOJI_ABS_MIN} → {MAX_EMOJI_ABS_MAX}"
            ),
            accessory=btn_max,
        ))
        container.add_item(Separator())

        # Retour
        btn_back = Button(label="Retour", emoji="↩️", style=ButtonStyle.secondary)
        btn_back.callback = self._on_back
        container.add_item(ActionRow(btn_back))

        container.add_item(Separator())
        container.add_item(TextDisplay("-# GuideOn Studio · Auto-modération"))
        self.add_item(container)

    async def _on_toggle(self, interaction: Interaction) -> None:
        current = self.cfg.get("enabled", False)
        await mgr.set_enabled(self.guild.id, not current)
        await self._refresh(interaction)

    async def _on_edit_max(self, interaction: Interaction) -> None:
        async def submit(inter: Interaction, value: str) -> None:
            try:
                n = int(value.strip())
            except ValueError:
                await inter.response.send_message(
                    view=warning_container("La valeur doit être un **nombre entier**."),
                    ephemeral=True,
                )
                return
            if n < MAX_EMOJI_ABS_MIN or n > MAX_EMOJI_ABS_MAX:
                await inter.response.send_message(
                    view=warning_container(
                        f"La valeur doit être comprise entre **{MAX_EMOJI_ABS_MIN}** "
                        f"et **{MAX_EMOJI_ABS_MAX}**."
                    ),
                    ephemeral=True,
                )
                return
            await mgr.save_config(self.guild.id, max_emoji=n)
            await self._refresh(inter)

        await interaction.response.send_modal(TextModal(
            title="Nombre maximum d'emojis",
            label="Nombre max autorisé par message",
            placeholder="Ex : 10",
            default=str(self.cfg.get("max_emoji", 10)),
            required=True,
            max_length=3,
            on_submit=submit,
        ))

    async def _on_back(self, interaction: Interaction) -> None:
        from views.mod.automod_dashboard_view import AutomodDashboardView
        new_view = await AutomodDashboardView.build(
            guild=self.guild, owner_id=self.owner_id,
        )
        await interaction.response.edit_message(view=new_view)