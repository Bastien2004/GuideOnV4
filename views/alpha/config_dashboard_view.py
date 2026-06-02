"""
views/alpha/config_dashboard_view.py — Hub de configuration Alpha.

Dashboard principal ouvert par /dev config_alpha.
Liste tous les systèmes configurables avec un bouton par système.
Chaque bouton transforme la vue (edit_message) vers la config du système concerné.

Systèmes :
  ✅ Rank/Derank   → ConfigRankView (salons, rôles, pings)
  🔜 Notations     → placeholder (à implémenter)
  🔜 ONU           → placeholder (à implémenter)
  🔜 Autres        → placeholder (futurs systèmes)
"""
from __future__ import annotations

import discord
from discord import ButtonStyle, Interaction
from discord.ui import ActionRow, Button, Container, LayoutView, Separator, TextDisplay

from utils.managers.alpha_rank_config_manager import load_rank_config


# ── Helpers ──────────────────────────────────────────────────

def _ch(val: int | None) -> str:
    return f"<#{val}>" if val else "❌ *Non configuré*"

def _role(val: int | None) -> str:
    return f"<@&{val}>" if val else "❌ *Non configuré*"

def _ok(val) -> str:
    return "✅" if val else "❌"


# ════════════════════════════════════════════════════════════
# 🏠 Dashboard principal
# ════════════════════════════════════════════════════════════

class ConfigDashboardView(LayoutView):
    """Hub de configuration — liste tous les systèmes Alpha."""

    def __init__(self, guild_id: int, owner_id: int) -> None:
        super().__init__(timeout=300)
        self.guild_id = guild_id
        self.owner_id = owner_id
        self._build()

    async def interaction_check(self, interaction: Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                "Seul l'auteur peut utiliser ce menu.", ephemeral=True
            )
            return False
        return True

    def _build(self) -> None:
        c = Container()
        c.add_item(TextDisplay("# ⚙️ Configuration Alpha — Hub"))
        c.add_item(Separator())
        c.add_item(TextDisplay(
            "Sélectionnez un système à configurer.\n"
            "Chaque section contient les salons, rôles et options propres à ce système."
        ))
        c.add_item(Separator())

        # ── Système Rank/Derank ──
        btn_rank = Button(
            label="⚙️ Système Rank / Derank",
            style=ButtonStyle.primary,
            custom_id="dash_rank",
        )
        btn_rank.callback = self._on_rank
        c.add_item(ActionRow(btn_rank))

        # ── Système Notations ──
        btn_nota = Button(
            label="📋 Système Notations",
            style=ButtonStyle.secondary,
            custom_id="dash_nota",
            disabled=True,  # Pas encore implémenté
        )
        c.add_item(ActionRow(btn_nota))

        # ── Système ONU ──
        btn_onu = Button(
            label="🌐 Système ONU",
            style=ButtonStyle.secondary,
            custom_id="dash_onu",
            disabled=True,  # Pas encore implémenté
        )
        c.add_item(ActionRow(btn_onu))

        c.add_item(Separator())
        c.add_item(TextDisplay(
            "-# Les systèmes grisés sont en cours de développement."
        ))
        c.add_item(TextDisplay("-# GuideOn Studio"))
        self.add_item(c)

    async def _on_rank(self, interaction: Interaction) -> None:
        cfg = await load_rank_config(self.guild_id)
        from views.alpha.config_alpha_view import ConfigRankView
        await interaction.response.edit_message(
            view=ConfigRankView(self.guild_id, cfg, self.owner_id)
        )