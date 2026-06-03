"""
views/alpha/config_content_view.py — Configuration des commandes contenu Discord.

Permet de configurer depuis le dashboard les salons, pings et emojis des
trois commandes de contenu : nous_rejoindre, index, regle_interne.

Chaque select/modal sauvegarde immédiatement et rafraîchit la vue.
Bouton ↩️ Tableau de bord pour revenir au hub.
"""
from __future__ import annotations

import logging

import discord
from discord import ButtonStyle, Interaction
from discord.ui import ActionRow, Button, Container, LayoutView, Separator, TextDisplay

from utils.managers.alpha_rank_config_manager import load_rank_config, save_rank_config
from views._components.channel_select import ChannelSelect
from views._components.role_select import RoleSelect
from views._components.text_modal import TextModal

log = logging.getLogger(__name__)


# ── Helpers d'affichage ──────────────────────────────────────

def _ch(val: int | None) -> str:
    return f"<#{val}>" if val else "*Non configuré*"

def _role(val: int | None) -> str:
    return f"<@&{val}>" if val else "*Non configuré*"

def _emoji(val: int | None) -> str:
    return f"`{val}`" if val else "*Non configuré*"


# ════════════════════════════════════════════════════════════
# 🖼️ Vue principale
# ════════════════════════════════════════════════════════════

class ConfigContentView(LayoutView):
    """Dashboard de configuration des commandes de contenu Alpha."""

    def __init__(self, guild_id: int, cfg: dict, owner_id: int) -> None:
        super().__init__(timeout=300)
        self.guild_id = guild_id
        self.cfg = cfg
        self.owner_id = owner_id
        self._build()

    async def interaction_check(self, interaction: Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                "Seul l'auteur peut utiliser ce menu.", ephemeral=True
            )
            return False
        return True

    def _refresh(self, interaction: Interaction):
        """Retourne un coroutine qui recharge la config et rafraîchit la vue."""
        async def _do():
            self.cfg = await load_rank_config(self.guild_id)
            await interaction.response.edit_message(
                view=ConfigContentView(self.guild_id, self.cfg, self.owner_id)
            )
        return _do

    def _build(self) -> None:
        cfg = self.cfg
        c = Container()

        # ── Header ────────────────────────────────────────────
        c.add_item(TextDisplay("## 📢 Configuration — Contenu Discord"))
        c.add_item(Separator())

        # ── Nous rejoindre ────────────────────────────────────
        c.add_item(TextDisplay(
            f"**📌 Nous Rejoindre**\n"
            f"• Salon : {_ch(cfg.get('content_nous_rejoindre_channel_id'))}\n"
            f"• Ping rôle : {_role(cfg.get('content_nous_rejoindre_ping_id'))}\n"
            f"• Emoji réaction (ID) : {_emoji(cfg.get('content_nous_rejoindre_emoji_id'))}"
        ))

        sel_nr_ch = ChannelSelect(
            placeholder="Salon → Nous rejoindre",
            on_select=lambda i, ch: self._save_and_refresh(i, "content_nous_rejoindre_channel_id", ch),
            channel_types=[discord.ChannelType.text],
        )
        sel_nr_ping = RoleSelect(
            placeholder="Ping rôle → Nous rejoindre",
            on_select=lambda i, ids: self._save_and_refresh(i, "content_nous_rejoindre_ping_id", ids[0]),
        )
        btn_nr_emoji = Button(
            label="🖼️ Emoji — Nous rejoindre",
            style=ButtonStyle.secondary,
            custom_id="nr_emoji",
        )
        btn_nr_emoji.callback = lambda i: self._open_emoji_modal(
            i, "content_nous_rejoindre_emoji_id", "Nous Rejoindre"
        )
        c.add_item(ActionRow(sel_nr_ch))
        c.add_item(ActionRow(sel_nr_ping))
        c.add_item(ActionRow(btn_nr_emoji))
        c.add_item(Separator())

        # ── Index ─────────────────────────────────────────────
        c.add_item(TextDisplay(
            f"**📋 Index**\n"
            f"• Salon : {_ch(cfg.get('content_index_channel_id'))}\n"
            f"• Emoji réaction (ID) : {_emoji(cfg.get('content_index_emoji_id'))}"
        ))

        sel_idx_ch = ChannelSelect(
            placeholder="Salon → Index",
            on_select=lambda i, ch: self._save_and_refresh(i, "content_index_channel_id", ch),
            channel_types=[discord.ChannelType.text],
        )
        btn_idx_emoji = Button(
            label="🖼️ Emoji — Index",
            style=ButtonStyle.secondary,
            custom_id="idx_emoji",
        )
        btn_idx_emoji.callback = lambda i: self._open_emoji_modal(
            i, "content_index_emoji_id", "Index"
        )
        c.add_item(ActionRow(sel_idx_ch))
        c.add_item(ActionRow(btn_idx_emoji))
        c.add_item(Separator())

        # ── Règle interne ─────────────────────────────────────
        c.add_item(TextDisplay(
            f"**⚖️ Règle Interne**\n"
            f"• Salon : {_ch(cfg.get('content_regle_interne_channel_id'))}\n"
            f"• Emoji réaction (ID) : {_emoji(cfg.get('content_regle_interne_emoji_id'))}"
        ))

        sel_ri_ch = ChannelSelect(
            placeholder="Salon → Règle interne",
            on_select=lambda i, ch: self._save_and_refresh(i, "content_regle_interne_channel_id", ch),
            channel_types=[discord.ChannelType.text],
        )
        btn_ri_emoji = Button(
            label="🖼️ Emoji — Règle interne",
            style=ButtonStyle.secondary,
            custom_id="ri_emoji",
        )
        btn_ri_emoji.callback = lambda i: self._open_emoji_modal(
            i, "content_regle_interne_emoji_id", "Règle Interne"
        )
        c.add_item(ActionRow(sel_ri_ch))
        c.add_item(ActionRow(btn_ri_emoji))
        c.add_item(Separator())

        # ── Retour ────────────────────────────────────────────
        btn_back = Button(label="↩️ Tableau de bord", style=ButtonStyle.secondary, custom_id="content_back")
        btn_back.callback = self._on_back
        c.add_item(ActionRow(btn_back))
        c.add_item(TextDisplay("-# GuideOn Studio"))
        self.add_item(c)

    # ── Helpers de sauvegarde ─────────────────────────────────

    async def _save_and_refresh(self, interaction: Interaction, field: str, value: int) -> None:
        self.cfg = await save_rank_config(self.guild_id, **{field: value})
        await interaction.response.edit_message(
            view=ConfigContentView(self.guild_id, self.cfg, self.owner_id)
        )

    async def _open_emoji_modal(self, interaction: Interaction, field: str, label: str) -> None:
        current = self.cfg.get(field)

        async def on_submit(inter: Interaction, value: str) -> None:
            value = value.strip()
            try:
                emoji_id = int(value)
            except ValueError:
                await inter.response.send_message(
                    "L'ID doit être un **nombre entier** (ex: `1496902732316016665`).",
                    ephemeral=True,
                )
                return
            self.cfg = await save_rank_config(self.guild_id, **{field: emoji_id})
            await inter.response.edit_message(
                view=ConfigContentView(self.guild_id, self.cfg, self.owner_id)
            )

        modal = TextModal(
            title=f"Emoji — {label}",
            label="ID Discord de l'emoji (nombre entier)",
            placeholder="Ex: 1496902732316016665",
            default=str(current) if current else "",
            min_length=1,
            max_length=25,
            on_submit=on_submit,
        )
        await interaction.response.send_modal(modal)

    async def _on_back(self, interaction: Interaction) -> None:
        from views.alpha.config_dashboard_view import ConfigDashboardView
        await interaction.response.edit_message(
            view=ConfigDashboardView(self.guild_id, self.owner_id)
        )