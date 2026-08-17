"""
views/mod/automod_dashboard_view.py — Menu principal de /mod config.

Liste les 8 sous-systèmes d'auto-modération avec leur statut (activé/désactivé)
et un bouton "Configurer" par entrée. Une section "Paramètres généraux" en
haut regroupe les réglages transverses (salon d'alerte, notifications dans
le salon).

Les 7 systèmes non encore implémentés apparaissent grisés ("À venir") pour
que le staff visualise l'ambition finale du dashboard, mais leur bouton est
désactivé.
"""
from __future__ import annotations

import discord
from discord import ButtonStyle, Interaction
from discord.ui import ActionRow, Button, Container, Section, Separator, TextDisplay

from utils.managers import (
    mod_automod_antifullcaps_manager as antifullcaps_mgr,
    mod_automod_antispam_emoji_manager as antispam_emoji_mgr,
    mod_automod_antispam_mention_manager as antispam_mention_mgr,
    mod_automod_banword_manager as banword_mgr,
    mod_automod_general_manager as general_mgr,
)
from views._components.base_view import BaseLayoutView


# ============================================================
# 📋 Registre visuel des systèmes
# ============================================================
#
# Ajouter un système : nouvelle entrée + fonction de chargement du statut +
# import de la vue de config correspondante. Le squelette est prêt.

_SYSTEMS: list[dict] = [
    {"key": "banword", "emoji": "🚫", "name": "Ban Word",
     "desc": "Liste de mots interdits avec anti-contournement.",
     "available": True},
    {"key": "nolink", "emoji": "🔗", "name": "No Link",
     "desc": "Bloque les liens sauf dans les salons de la whitelist.",
     "available": False},
    {"key": "antilink", "emoji": "☠️", "name": "Anti Link",
     "desc": "Bloque les liens finissant par des TLD blacklistées.",
     "available": False},
    {"key": "antispam_msg", "emoji": "💬", "name": "Anti Spam Message",
     "desc": "Détecte le même message répété (inter-salons).",
     "available": False},
    {"key": "antispam_mention", "emoji": "📣", "name": "Anti Spam Mention",
     "desc": "Limite le nombre de mentions par message.",
     "available": True},
    {"key": "antiflood", "emoji": "🌊", "name": "Anti Flood",
     "desc": "Détecte les messages incohérents (ratio voyelle/consonne).",
     "available": False},
    {"key": "antifullcaps", "emoji": "🔠", "name": "Anti Full Maj",
     "desc": "Détecte les messages entièrement en majuscules.",
     "available": True},
    {"key": "antispam_emoji", "emoji": "😀", "name": "Anti Spam Emoji",
     "desc": "Limite le nombre d'emojis par message.",
     "available": True},
]


class AutomodDashboardView(BaseLayoutView):
    """Menu principal du dashboard d'auto-modération."""

    def __init__(
        self, *, guild: discord.Guild, owner_id: int,
        general_cfg: dict, statuses: dict[str, bool],
    ):
        super().__init__(owner_id=owner_id, timeout=300)
        self.guild = guild
        self.general_cfg = general_cfg
        self.statuses = statuses
        self._build()

    @classmethod
    async def build(cls, *, guild: discord.Guild, owner_id: int) -> "AutomodDashboardView":
        """Factory async : charge les statuts avant de construire la vue."""
        general_cfg = await general_mgr.load_general(guild.id)
        statuses = {
            "banword": (await banword_mgr.load_config(guild.id))["enabled"],
            "antifullcaps": (await antifullcaps_mgr.load_config(guild.id))["enabled"],
            "antispam_mention": (await antispam_mention_mgr.load_config(guild.id))["enabled"],
            "antispam_emoji": (await antispam_emoji_mgr.load_config(guild.id))["enabled"],
        }
        # (Ajouter ici les autres load_config au fur et à mesure de l'impl.)
        return cls(
            guild=guild, owner_id=owner_id,
            general_cfg=general_cfg, statuses=statuses,
        )

    async def _refresh(self, interaction: Interaction) -> None:
        """Recharge les statuts DB et met à jour la vue in-place."""
        self.general_cfg = await general_mgr.load_general(self.guild.id)
        self.statuses = {
            "banword": (await banword_mgr.load_config(self.guild.id))["enabled"],
            "antifullcaps": (await antifullcaps_mgr.load_config(self.guild.id))["enabled"],
            "antispam_mention": (await antispam_mention_mgr.load_config(self.guild.id))["enabled"],
            "antispam_emoji": (await antispam_emoji_mgr.load_config(self.guild.id))["enabled"],
        }
        self.clear_items()
        self._build()
        await self.push_update(interaction)

    def _build(self) -> None:
        container = Container()

        # ── Header ────────────────────────────────────────
        container.add_item(TextDisplay("# 🛡️ Auto-modération"))
        container.add_item(TextDisplay(
            "-# Dashboard central de configuration. Les administrateurs Discord "
            "ne sont **jamais** filtrés par ces règles."
        ))
        container.add_item(Separator())

        # ── Paramètres généraux ──────────────────────────
        alert_ch_id = self.general_cfg.get("alert_channel_id")
        alert_ch_line = (
            f"<#{alert_ch_id}>" if alert_ch_id else "`Non configuré`"
        )
        notify = self.general_cfg.get("notify_in_channel", True)
        notify_line = "✅ Activées" if notify else "❌ Désactivées"

        btn_general = Button(label="Configurer", emoji="⚙️", style=ButtonStyle.primary)
        btn_general.callback = self._open_general

        container.add_item(Section(
            TextDisplay(
                f"**⚙️ Paramètres généraux**\n"
                f"-# Salon d'alerte staff : {alert_ch_line}\n"
                f"-# Notifications dans le salon : {notify_line}"
            ),
            accessory=btn_general,
        ))
        container.add_item(Separator())

        # ── Systèmes ──────────────────────────────────────
        container.add_item(TextDisplay("## Systèmes d'auto-modération"))

        for i, sys in enumerate(_SYSTEMS):
            enabled = self.statuses.get(sys["key"], False)

            if sys["available"]:
                status_dot = "🟢" if enabled else "🔴"
                status_label = "Activé" if enabled else "Désactivé"
                btn = Button(label="Configurer", emoji="⚙️", style=ButtonStyle.primary)
                btn.callback = self._make_open_system(sys["key"])
            else:
                status_dot = "⚪"
                status_label = "À venir"
                btn = Button(label="Bientôt", emoji="🚧", style=ButtonStyle.secondary, disabled=True)

            container.add_item(Section(
                TextDisplay(
                    f"**{sys['emoji']} {sys['name']}** · {status_dot} {status_label}\n"
                    f"-# {sys['desc']}"
                ),
                accessory=btn,
            ))

        container.add_item(Separator())
        container.add_item(TextDisplay("-# GuideOn Studio · Auto-modération"))
        self.add_item(container)

    # ────────────────────────────────────────────────────────
    # Callbacks
    # ────────────────────────────────────────────────────────

    async def _open_general(self, interaction: Interaction) -> None:
        # Import local pour éviter le cycle d'imports (les vues enfant
        # importent le dashboard pour le "retour").
        from views.mod.automod_general_view import AutomodGeneralView
        new_view = await AutomodGeneralView.build(
            guild=self.guild, owner_id=self.owner_id, parent_dashboard=self,
        )
        await interaction.response.edit_message(view=new_view)

    def _make_open_system(self, key: str):
        async def cb(interaction: Interaction) -> None:
            if key == "banword":
                from views.mod.automod_banword_view import AutomodBanwordView
                new_view = await AutomodBanwordView.build(
                    guild=self.guild, owner_id=self.owner_id, parent_dashboard=self,
                )
                await interaction.response.edit_message(view=new_view)
                return
            if key == "antifullcaps":
                from views.mod.automod_antifullcaps_view import AutomodAntifullcapsView
                new_view = await AutomodAntifullcapsView.build(
                    guild=self.guild, owner_id=self.owner_id, parent_dashboard=self,
                )
                await interaction.response.edit_message(view=new_view)
                return
            if key == "antispam_mention":
                from views.mod.automod_antispam_mention_view import AutomodAntispamMentionView
                new_view = await AutomodAntispamMentionView.build(
                    guild=self.guild, owner_id=self.owner_id, parent_dashboard=self,
                )
                await interaction.response.edit_message(view=new_view)
                return
            if key == "antispam_emoji":
                from views.mod.automod_antispam_emoji_view import AutomodAntispamEmojiView
                new_view = await AutomodAntispamEmojiView.build(
                    guild=self.guild, owner_id=self.owner_id, parent_dashboard=self,
                )
                await interaction.response.edit_message(view=new_view)
                return
            # (Futurs systèmes ici.)
        return cb