"""
views/mod/automod_antifullcaps_view.py — Configuration Anti Full Maj.

3 réglages :
  - toggle activation
  - min_length (longueur minimale du message pour être analysé)
  - ratio_threshold (proportion de MAJ à partir de laquelle on déclenche,
    exprimée en % dans l'UI pour la lisibilité)
"""
from __future__ import annotations

import discord
from discord import ButtonStyle, Interaction
from discord.ui import ActionRow, Button, Container, Section, Separator, TextDisplay

from utils.container_universel import warning_container
from utils.managers import mod_automod_antifullcaps_manager as mgr
from views._components.base_view import BaseLayoutView
from views._components.text_modal import TextModal


MIN_LENGTH_ABS_MIN = 1
MIN_LENGTH_ABS_MAX = 500
RATIO_ABS_MIN = 10   # en pourcents
RATIO_ABS_MAX = 100


class AutomodAntifullcapsView(BaseLayoutView):
    """Configuration du système Anti Full Maj."""

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
        min_length = self.cfg.get("min_length", 10)
        ratio_pct = int(round(self.cfg.get("ratio_threshold", 0.7) * 100))

        # Header
        state_dot = "🟢" if enabled else "🔴"
        state_label = "Activé" if enabled else "Désactivé"
        container.add_item(TextDisplay(f"# 🔠 Anti Full Maj · {state_dot} {state_label}"))
        container.add_item(TextDisplay(
            "-# Bloque les messages majoritairement en MAJUSCULES."
        ))
        container.add_item(Separator())

        # Toggle
        toggle_label = "Désactiver" if enabled else "Activer"
        toggle_emoji = "🔴" if enabled else "🟢"
        toggle_style = ButtonStyle.danger if enabled else ButtonStyle.success
        btn_toggle = Button(label=toggle_label, emoji=toggle_emoji, style=toggle_style)
        btn_toggle.callback = self._on_toggle
        container.add_item(Section(
            TextDisplay(
                "**⚡ Activation**\n"
                "-# Analyse chaque message avant publication."
            ),
            accessory=btn_toggle,
        ))
        container.add_item(Separator())

        # Réglage : longueur minimale
        btn_min = Button(label="Modifier", emoji="✏️", style=ButtonStyle.secondary)
        btn_min.callback = self._on_edit_min_length
        container.add_item(Section(
            TextDisplay(
                "**📏 Longueur minimale**\n"
                f"-# Messages plus courts que **{min_length} caractères** ignorés (protège \"OK\", \"LOL\"…).\n"
                f"-# Plage autorisée : {MIN_LENGTH_ABS_MIN} → {MIN_LENGTH_ABS_MAX}"
            ),
            accessory=btn_min,
        ))
        container.add_item(Separator())

        # Réglage : ratio
        btn_ratio = Button(label="Modifier", emoji="✏️", style=ButtonStyle.secondary)
        btn_ratio.callback = self._on_edit_ratio
        container.add_item(Section(
            TextDisplay(
                "**📊 Seuil de déclenchement**\n"
                f"-# À partir de **{ratio_pct}%** de lettres en MAJUSCULES → suppression.\n"
                f"-# Plage autorisée : {RATIO_ABS_MIN}% → {RATIO_ABS_MAX}%"
            ),
            accessory=btn_ratio,
        ))
        container.add_item(Separator())

        # Retour
        btn_back = Button(label="Retour", emoji="↩️", style=ButtonStyle.secondary)
        btn_back.callback = self._on_back
        container.add_item(ActionRow(btn_back))

        container.add_item(Separator())
        container.add_item(TextDisplay("-# GuideOn Studio · Auto-modération"))
        self.add_item(container)

    # ─────────── Callbacks ───────────

    async def _on_toggle(self, interaction: Interaction) -> None:
        current = self.cfg.get("enabled", False)
        await mgr.set_enabled(self.guild.id, not current)
        await self._refresh(interaction)

    async def _on_edit_min_length(self, interaction: Interaction) -> None:
        async def submit(inter: Interaction, value: str) -> None:
            try:
                n = int(value.strip())
            except ValueError:
                await inter.response.send_message(
                    view=warning_container("La valeur doit être un **nombre entier**."),
                    ephemeral=True,
                )
                return
            if n < MIN_LENGTH_ABS_MIN or n > MIN_LENGTH_ABS_MAX:
                await inter.response.send_message(
                    view=warning_container(
                        f"La longueur doit être comprise entre **{MIN_LENGTH_ABS_MIN}** "
                        f"et **{MIN_LENGTH_ABS_MAX}**."
                    ),
                    ephemeral=True,
                )
                return
            await mgr.save_config(self.guild.id, min_length=n)
            await self._refresh(inter)

        await interaction.response.send_modal(TextModal(
            title="Longueur minimale",
            label="Nombre de caractères minimum",
            placeholder="Ex : 10",
            default=str(self.cfg.get("min_length", 10)),
            required=True,
            max_length=4,
            on_submit=submit,
        ))

    async def _on_edit_ratio(self, interaction: Interaction) -> None:
        async def submit(inter: Interaction, value: str) -> None:
            raw = value.strip().rstrip("%").strip()
            try:
                pct = int(raw)
            except ValueError:
                await inter.response.send_message(
                    view=warning_container("La valeur doit être un **nombre entier** (pourcentage)."),
                    ephemeral=True,
                )
                return
            if pct < RATIO_ABS_MIN or pct > RATIO_ABS_MAX:
                await inter.response.send_message(
                    view=warning_container(
                        f"Le pourcentage doit être compris entre **{RATIO_ABS_MIN}%** "
                        f"et **{RATIO_ABS_MAX}%**."
                    ),
                    ephemeral=True,
                )
                return
            await mgr.save_config(self.guild.id, ratio_threshold=pct / 100.0)
            await self._refresh(inter)

        current_pct = int(round(self.cfg.get("ratio_threshold", 0.7) * 100))
        await interaction.response.send_modal(TextModal(
            title="Seuil de déclenchement",
            label="Pourcentage de MAJ (10 à 100)",
            placeholder="Ex : 70",
            default=str(current_pct),
            required=True,
            max_length=4,
            on_submit=submit,
        ))

    async def _on_back(self, interaction: Interaction) -> None:
        from views.mod.automod_dashboard_view import AutomodDashboardView
        new_view = await AutomodDashboardView.build(
            guild=self.guild, owner_id=self.owner_id,
        )
        await interaction.response.edit_message(view=new_view)