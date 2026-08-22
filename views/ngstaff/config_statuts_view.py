"""
views/ngstaff/config_statuts_view.py — /ngstaff config → Statuts.

CRUD des statuts secondaires (badges non hiérarchiques, ex: builder,
journaliste, avocat, équipe com...) librement définis par serveur NG.
Remplace le système figé à 3 entrées (SECONDARY_STATUSES, utils/db/models/
alpha_staff.py) qui ne permettait ni d'ajouter, ni de renommer, ni de
retirer un statut sans toucher au code (Paul, 2026-08-22).

Voir utils/managers/ng_statut_manager.py pour la logique CRUD sous-jacente.
"""

from __future__ import annotations

import discord
from discord import ButtonStyle, Interaction
from discord.ui import ActionRow, Button, Container, LayoutView, Separator, TextDisplay

from utils.container_universel import error_container, warning_container
from utils.managers.ng_statut_manager import (
    NGStatutError,
    create_statut_def,
    delete_statut_def,
    list_statut_defs,
    update_statut_def,
)
from views._components.role_select import RoleSelect


def _role(val: int | None) -> str:
    return f"<@&{val}>" if val else "`Non configuré`"


# ════════════════════════════════════════════════════════════
# 🏠 Vue principale — liste des statuts
# ════════════════════════════════════════════════════════════

class NGStatutsConfigView(LayoutView):
    """Liste des statuts configurés pour le serveur, + ajout/édition/suppression."""

    def __init__(
        self, guild_id: int, server: str, statut_defs: list[dict], owner_id: int, *, dashboard: str = "ngstaff"
    ) -> None:
        super().__init__(timeout=300)
        self.guild_id = guild_id
        self.server = server
        self.statut_defs = statut_defs
        self.owner_id = owner_id
        self.dashboard = dashboard
        self._build()

    async def interaction_check(self, interaction: Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                "Seul l'**auteur** peut utiliser ce menu.", ephemeral=True
            )
            return False
        return True

    def _build(self) -> None:
        c = Container()
        c.add_item(TextDisplay(f"# 🎖️ Configuration — Statuts `{self.server}`"))
        c.add_item(Separator())
        c.add_item(TextDisplay(
            "Statuts secondaires (non hiérarchiques, cumulables avec un grade ou seuls) : "
            "builder, journaliste, avocat, équipe com... librement définis pour ce serveur."
        ))
        c.add_item(Separator())

        if not self.statut_defs:
            c.add_item(TextDisplay("*Aucun statut configuré pour ce serveur.*"))
        else:
            lines = []
            for d in self.statut_defs:
                emoji = d["emoji"] or "•"
                pseudo_flag = " · 🔁 second pseudo requis" if d["requires_second_pseudo"] else ""
                lines.append(f"{emoji} **{d['label']}** (`{d['key']}`) — {_role(d['role_id'])}{pseudo_flag}")
            c.add_item(TextDisplay("\n".join(lines)))

        c.add_item(Separator())

        options = [
            discord.SelectOption(label=d["label"], value=d["key"], emoji=d["emoji"] or None)
            for d in self.statut_defs
        ][:25]
        if options:
            select = discord.ui.Select(placeholder="Modifier un statut existant...", options=options)
            select.callback = self._on_select_edit
            c.add_item(ActionRow(select))

        btn_add = Button(label="➕ Ajouter un statut", style=ButtonStyle.success, custom_id="statut_add")
        btn_back = Button(label="↩️ Tableau de bord", style=ButtonStyle.secondary, custom_id="statut_back")
        btn_add.callback = self._on_add
        btn_back.callback = self._on_back
        c.add_item(ActionRow(btn_add, btn_back))
        c.add_item(TextDisplay("-# GuideOn Studio"))
        self.add_item(c)

    async def _on_select_edit(self, interaction: Interaction) -> None:
        key = interaction.data["values"][0]
        statut_def = next((d for d in self.statut_defs if d["key"] == key), None)
        if statut_def is None:
            return await interaction.response.send_message(
                "Ce statut a été supprimé entre-temps.", ephemeral=True
            )
        await interaction.response.edit_message(
            view=_StatutDetailView(self.guild_id, self.server, statut_def, self.owner_id, dashboard=self.dashboard)
        )

    async def _on_add(self, interaction: Interaction) -> None:
        async def on_submit(inter: Interaction, values: tuple[str, str]) -> None:
            label, emoji = values
            try:
                await create_statut_def(self.server, label.strip(), emoji=emoji.strip() or None)
            except NGStatutError as e:
                view = warning_container(e.message) if e.warning else error_container(e.message)
                return await inter.response.edit_message(view=view)
            statut_defs = await list_statut_defs(self.server)
            await inter.response.edit_message(
                view=NGStatutsConfigView(self.guild_id, self.server, statut_defs, self.owner_id, dashboard=self.dashboard)
            )

        modal = _StatutLabelModal(title="➕ Nouveau statut", on_submit=on_submit)
        await interaction.response.send_modal(modal)

    async def _on_back(self, interaction: Interaction) -> None:
        if self.dashboard == "ngstaff":
            from views.ngstaff.config_dashboard_view import NGStaffConfigDashboardView
            await interaction.response.edit_message(
                view=NGStaffConfigDashboardView(self.guild_id, self.server, self.owner_id)
            )
        else:
            from views.alpha.config_dashboard_view import ConfigDashboardView
            await interaction.response.edit_message(
                view=ConfigDashboardView(self.guild_id, self.owner_id)
            )


# ════════════════════════════════════════════════════════════
# 📝 Modal libellé + emoji (partagé ajout/édition)
# ════════════════════════════════════════════════════════════

class _StatutLabelModal(discord.ui.Modal):
    def __init__(
        self, *, title: str, on_submit, default_label: str = "", default_emoji: str = "",
    ) -> None:
        super().__init__(title=title)
        self._on_submit = on_submit
        self.label_input = discord.ui.TextInput(
            label="Libellé (ex: Builder, Avocat, Équipe Com...)",
            default=default_label,
            min_length=1, max_length=64,
            required=True,
        )
        self.emoji_input = discord.ui.TextInput(
            label="Emoji badge (optionnel)",
            placeholder="Ex: 🧱 ou <:Nom:1234567890123456789>",
            default=default_emoji,
            min_length=0, max_length=100,
            required=False,
        )
        self.add_item(self.label_input)
        self.add_item(self.emoji_input)

    async def on_submit(self, interaction: Interaction) -> None:
        await self._on_submit(interaction, (self.label_input.value, self.emoji_input.value or ""))


# ════════════════════════════════════════════════════════════
# 🔍 Détail d'un statut — rôle, second pseudo, suppression
# ════════════════════════════════════════════════════════════

class _StatutDetailView(LayoutView):
    def __init__(
        self, guild_id: int, server: str, statut_def: dict, owner_id: int, *, dashboard: str = "ngstaff"
    ) -> None:
        super().__init__(timeout=300)
        self.guild_id = guild_id
        self.server = server
        self.statut_def = statut_def
        self.owner_id = owner_id
        self.dashboard = dashboard
        self._build()

    async def interaction_check(self, interaction: Interaction) -> bool:
        return interaction.user.id == self.owner_id

    def _build(self) -> None:
        d = self.statut_def
        c = Container()
        c.add_item(TextDisplay(f"## {d['emoji'] or '🎖️'} {d['label']}"))
        c.add_item(Separator())
        c.add_item(TextDisplay(
            f"• Clé technique : `{d['key']}`\n"
            f"• Rôle Discord attribué : {_role(d['role_id'])}\n"
            f"• Nécessite un second pseudo (ex: compte builder dédié) : "
            f"{'✅ Oui' if d['requires_second_pseudo'] else '❌ Non'}"
        ))
        c.add_item(ActionRow(RoleSelect(
            placeholder="Choisir le rôle Discord associé à ce statut",
            on_select=self._save_role,
        )))
        c.add_item(Separator())

        btn_label = Button(label="📝 Libellé / Emoji", style=ButtonStyle.primary, custom_id="statut_edit_label")
        btn_toggle = Button(
            label="🔁 Second pseudo : désactiver" if d["requires_second_pseudo"] else "🔁 Second pseudo : activer",
            style=ButtonStyle.secondary, custom_id="statut_toggle_pseudo",
        )
        btn_delete = Button(label="🗑️ Supprimer", style=ButtonStyle.danger, custom_id="statut_delete")
        btn_back = Button(label="↩️ Retour", style=ButtonStyle.secondary, custom_id="statut_detail_back")
        btn_label.callback = self._on_label
        btn_toggle.callback = self._on_toggle
        btn_delete.callback = self._on_delete
        btn_back.callback = self._on_back

        c.add_item(ActionRow(btn_label, btn_toggle, btn_delete, btn_back))
        c.add_item(TextDisplay("-# GuideOn Studio"))
        self.add_item(c)

    async def _save_role(self, interaction: Interaction, role_ids: list[int]) -> None:
        d = await update_statut_def(self.server, self.statut_def["key"], role_id=role_ids[0])
        await interaction.response.edit_message(
            view=_StatutDetailView(self.guild_id, self.server, d, self.owner_id, dashboard=self.dashboard)
        )

    async def _on_label(self, interaction: Interaction) -> None:
        async def on_submit(inter: Interaction, values: tuple[str, str]) -> None:
            label, emoji = values
            try:
                d = await update_statut_def(
                    self.server, self.statut_def["key"], label=label.strip(), emoji=emoji.strip() or None,
                )
            except NGStatutError as e:
                view = warning_container(e.message) if e.warning else error_container(e.message)
                return await inter.response.edit_message(view=view)
            await inter.response.edit_message(
                view=_StatutDetailView(self.guild_id, self.server, d, self.owner_id, dashboard=self.dashboard)
            )

        modal = _StatutLabelModal(
            title="📝 Modifier le statut",
            default_label=self.statut_def["label"],
            default_emoji=self.statut_def["emoji"] or "",
            on_submit=on_submit,
        )
        await interaction.response.send_modal(modal)

    async def _on_toggle(self, interaction: Interaction) -> None:
        d = await update_statut_def(
            self.server, self.statut_def["key"],
            requires_second_pseudo=not self.statut_def["requires_second_pseudo"],
        )
        await interaction.response.edit_message(
            view=_StatutDetailView(self.guild_id, self.server, d, self.owner_id, dashboard=self.dashboard)
        )

    async def _on_delete(self, interaction: Interaction) -> None:
        await interaction.response.edit_message(
            view=_ConfirmDeleteStatutView(self.guild_id, self.server, self.statut_def, self.owner_id, dashboard=self.dashboard)
        )

    async def _on_back(self, interaction: Interaction) -> None:
        statut_defs = await list_statut_defs(self.server)
        await interaction.response.edit_message(
            view=NGStatutsConfigView(self.guild_id, self.server, statut_defs, self.owner_id, dashboard=self.dashboard)
        )


# ════════════════════════════════════════════════════════════
# ✅ Confirmation de suppression
# ════════════════════════════════════════════════════════════

class _ConfirmDeleteStatutView(LayoutView):
    def __init__(
        self, guild_id: int, server: str, statut_def: dict, owner_id: int, *, dashboard: str = "ngstaff"
    ) -> None:
        super().__init__(timeout=60)
        self.guild_id = guild_id
        self.server = server
        self.statut_def = statut_def
        self.owner_id = owner_id
        self.dashboard = dashboard
        self._build()

    async def interaction_check(self, interaction: Interaction) -> bool:
        return interaction.user.id == self.owner_id

    def _build(self) -> None:
        d = self.statut_def
        c = Container()
        c.add_item(TextDisplay("## ⚠️ Confirmer la suppression"))
        c.add_item(Separator())
        c.add_item(TextDisplay(
            f"Supprimer le statut **{d['label']}** (`{d['key']}`) ?\n\n"
            "-# Les membres qui le détiennent le perdent immédiatement (côté liste staff). "
            "Le rôle Discord associé n'est PAS retiré automatiquement — un `/ngstaff derank` "
            "ou une resynchronisation manuelle reste nécessaire pour ça."
        ))
        c.add_item(Separator())

        btn_confirm = Button(label="✅ Confirmer", style=ButtonStyle.danger, custom_id="statut_del_confirm")
        btn_cancel = Button(label="↩️ Annuler", style=ButtonStyle.secondary, custom_id="statut_del_cancel")
        btn_confirm.callback = self._on_confirm
        btn_cancel.callback = self._on_cancel
        c.add_item(ActionRow(btn_confirm, btn_cancel))
        c.add_item(TextDisplay("-# GuideOn Studio"))
        self.add_item(c)

    async def _on_confirm(self, interaction: Interaction) -> None:
        await delete_statut_def(self.server, self.statut_def["key"])
        statut_defs = await list_statut_defs(self.server)
        await interaction.response.edit_message(
            view=NGStatutsConfigView(self.guild_id, self.server, statut_defs, self.owner_id, dashboard=self.dashboard)
        )

    async def _on_cancel(self, interaction: Interaction) -> None:
        await interaction.response.edit_message(
            view=_StatutDetailView(self.guild_id, self.server, self.statut_def, self.owner_id, dashboard=self.dashboard)
        )