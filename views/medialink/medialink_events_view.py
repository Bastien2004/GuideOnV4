"""
views/medialink/medialink_events_view.py — configuration des règles
(Rules, §3) d'UNE connexion : quel event_type → quel salon → quel
template → quel rôle à mentionner.

STUB : la liste des event_type proposés doit venir de
BaseMediaProvider.capabilities (ProviderCapabilities) de la connexion
concernée — pas encore exploitable tant que les Providers réels
n'existent pas. Le CRUD (utils.managers.medialink_manager.add_rule/
remove_rule/set_rule_enabled/list_rules) est déjà prêt à être branché
dessus.
"""
from __future__ import annotations

import discord
from discord import ButtonStyle
from discord.ui import Button, Container, Section, Separator, TextDisplay

from utils.managers import medialink_manager as medialink_mgr
from views._components.base_view import BaseLayoutView

# NOTE : core.manager.list_rules() n'existe pas encore (cf. build() plus
# bas) — pas d'import de core.manager tant que rien ici ne l'utilise
# réellement, pour éviter un import mort.


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
        raise NotImplementedError(
            "events._cb_add_rule — sélection event_type (depuis "
            "ProviderCapabilities de la connexion) + salon + template (roadmap A1/A2)"
        )
