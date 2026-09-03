"""
views/medialink/medialink_events_view.py — configuration des règles
(Rules, §3) d'UNE connexion : quel event_type → quel salon → quel
template → quel rôle à mentionner.

── MODE ACTUEL : AJOUT MANUEL (provisoire) ──────────────────────────
Même logique que medialink_platforms_view.py : la liste des event_type
proposés devrait venir de BaseMediaProvider.capabilities de la connexion
concernée, mais ça n'est pas exploitable tant que les Providers réels
n'existent pas. En attendant, "Ajouter une règle" ouvre un Modal où
event_type et le salon (par ID) sont saisis à la main — pas de
validation contre une liste de types réels, pas de sélecteur de salon
Discord natif (ChannelSelect) pour l'instant.

QUAND LES PROVIDERS EXISTERONT (roadmap A1/A2) — à faire à ce moment-là :
  - Remplacer le TextInput event_type par un Select rempli depuis
    ProviderCapabilities de la connexion.
  - Remplacer le TextInput channel_id par un discord.ui.ChannelSelect
    (plus fiable qu'un ID copié-collé à la main).
"""
from __future__ import annotations

import discord
from discord import ButtonStyle
from discord.ui import Button, Container, Section, Separator, TextDisplay

from utils.managers import medialink_manager as medialink_mgr
from views._components.base_view import BaseLayoutView


class AddRuleModal(discord.ui.Modal):
    """Saisie manuelle d'une règle — cf. note en tête de fichier."""

    def __init__(self, *, connection: dict, owner_id: int):
        super().__init__(title="Ajouter une règle (mode manuel)")
        self.connection = connection
        self.owner_id = owner_id

        self.event_type_input = discord.ui.TextInput(
            label="Type d'événement (event_type)",
            placeholder="Ex : youtube.video_published",
            required=True,
            max_length=48,
        )
        self.channel_id_input = discord.ui.TextInput(
            label="ID du salon Discord",
            placeholder="Clic droit sur le salon → Copier l'identifiant",
            required=True,
            max_length=32,
        )
        self.add_item(self.event_type_input)
        self.add_item(self.channel_id_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        raw_channel_id = self.channel_id_input.value.strip()
        if not raw_channel_id.isdigit():
            await interaction.response.send_message(
                "❌ L'ID du salon doit être un nombre (clic droit sur le salon → Copier l'identifiant).",
                ephemeral=True,
            )
            return

        await medialink_mgr.add_rule(
            self.connection["id"],
            self.event_type_input.value.strip(),
            int(raw_channel_id),
        )

        view = await ConnectionRulesView.build(connection=self.connection, owner_id=self.owner_id)
        await interaction.response.edit_message(view=view)


class ConnectionRulesView(BaseLayoutView):
    """Liste + gestion des règles d'une connexion."""

    def __init__(self, *, connection: dict, owner_id: int, rules: list[dict]):
        super().__init__(owner_id=owner_id, timeout=300)
        self.connection = connection
        self.rules = rules
        self._build()

    @classmethod
    async def build(cls, *, connection: dict, owner_id: int) -> "ConnectionRulesView":
        rules = await medialink_mgr.list_rules(connection["id"])
        return cls(connection=connection, owner_id=owner_id, rules=rules)

    def _build(self) -> None:
        container = Container()
        label = self.connection.get("external_username") or self.connection["external_id"]
        container.add_item(TextDisplay(f"# 🔧 Règles — {label}"))
        container.add_item(Separator())

        if not self.rules:
            container.add_item(TextDisplay("*Aucune règle configurée pour cette connexion.*"))
        else:
            for rule in self.rules:
                toggle_btn = Button(
                    label="Désactiver" if rule.get("enabled", True) else "Activer",
                    style=ButtonStyle.secondary,
                )
                toggle_btn.callback = self._cb_toggle_rule(rule["id"])
                container.add_item(Section(
                    TextDisplay(
                        f"➥ `{rule['event_type']}` → <#{rule['channel_id']}>"
                    ),
                    accessory=toggle_btn,
                ))

        container.add_item(Separator())
        add_btn = Button(label="Ajouter une règle", style=ButtonStyle.primary, emoji="➕")
        add_btn.callback = self._cb_add_rule
        container.add_item(add_btn)

        remove_btn = Button(label="Supprimer la connexion", style=ButtonStyle.danger, emoji="🗑️")
        remove_btn.callback = self._cb_remove_connection
        container.add_item(remove_btn)

        back_btn = Button(label="Retour au dashboard", style=ButtonStyle.secondary)
        back_btn.callback = self._cb_back
        container.add_item(back_btn)

        self.add_item(container)

    def _cb_toggle_rule(self, rule_id: int):
        async def _callback(interaction: discord.Interaction) -> None:
            current = next((r for r in self.rules if r["id"] == rule_id), None)
            if current is None:
                return
            await medialink_mgr.set_rule_enabled(rule_id, not current.get("enabled", True))
            view = await ConnectionRulesView.build(connection=self.connection, owner_id=self.owner_id)
            await self.push_update(interaction, view=view)
        return _callback

    async def _cb_add_rule(self, interaction: discord.Interaction) -> None:
        modal = AddRuleModal(connection=self.connection, owner_id=self.owner_id)
        await interaction.response.send_modal(modal)

    async def _cb_remove_connection(self, interaction: discord.Interaction) -> None:
        await medialink_mgr.remove_connection(self.connection["guild_id"], self.connection["id"])

        from views.medialink.medialink_dashboard_view import MediaLinkDashboardView

        view = await MediaLinkDashboardView.build(guild=interaction.guild, owner_id=self.owner_id)
        await self.push_update(interaction, view=view)

    async def _cb_back(self, interaction: discord.Interaction) -> None:
        from views.medialink.medialink_dashboard_view import MediaLinkDashboardView

        view = await MediaLinkDashboardView.build(guild=interaction.guild, owner_id=self.owner_id)
        await self.push_update(interaction, view=view)
