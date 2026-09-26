"""
views/medialink/medialink_events_view.py — configuration des règles d'une connexion.
"""
from __future__ import annotations

import discord
from discord import ButtonStyle, SelectOption
from discord.ui import ActionRow, Button, Container, Section, Select, Separator, TextDisplay

from utils.container_universel import error_container, send_ephemeral, warning_container
from utils.db.models.medialink_connection import MediaPlatform
from utils.managers import medialink_manager as medialink_mgr
from utils.medialink.providers.base import BaseMediaProvider, ProviderCapabilities
from utils.medialink.providers.twitch import TwitchProvider
from utils.medialink.providers.youtube import YouTubeProvider
from views._components.base_view import BaseLayoutView
from views._components.channel_select import ChannelSelect


# ============================================================
# 🔩 Paramètres
# ============================================================

_PLATFORM_EMOJI = {
    "youtube": "<:Youtube2:1545107295975772180>",
    "twitch": "<:Twitch2:1545053682129961081>",
    "tiktok": "<:TikTok:1545107255727235113>",
    "reddit": "<:Reddit:1545053589020483724>",
}

_YOUTUBE_EVENT_CATALOG: list[tuple[ProviderCapabilities, str, str, str]] = [
    (ProviderCapabilities.NEW_POST, "youtube.video_published", "Nouvelle vidéo", "<:video:1552023543665926235>"),
    (ProviderCapabilities.SHORT_FORM, "youtube.short_published", "Nouveau Short", "<:short:1552023508559863889>"),
    (ProviderCapabilities.LIVE_STATUS, "youtube.live_started", "Passage en live", "<:live:1552023803322966056>"),
]

_TWITCH_EVENT_CATALOG: list[tuple[ProviderCapabilities, str, str, str]] = [
    (ProviderCapabilities.LIVE_STATUS, "twitch.live_started", "Passage en live", "<:live:1552023803322966056>"),
]

_PLATFORM_PROVIDERS: dict[str, type[BaseMediaProvider]] = {
    MediaPlatform.YOUTUBE.value: YouTubeProvider,
    MediaPlatform.TWITCH.value: TwitchProvider,
}
_PLATFORM_EVENT_CATALOGS: dict[str, list[tuple[ProviderCapabilities, str, str, str]]] = {
    MediaPlatform.YOUTUBE.value: _YOUTUBE_EVENT_CATALOG,
    MediaPlatform.TWITCH.value: _TWITCH_EVENT_CATALOG,
}

# ============================================================
# 😂 Emojis
# ============================================================

EMOJI_ADD = "<:plus:1495444111505752154>"
EMOJI_DELETE = "<:supprimer:1495444051623809075>"
EMOJI_BACK = "<:retour:1515658955190308995>"
EMOJI_VALID = "<:valider:1495444292867723284>"
EMOJI_CANCEL = "<:annuler:1495444256754761979>"
EMOJI_EDIT = "<:modifier:1495444144712192003>"


# ============================================================
# ⚒️ Fonction utilitaire
# ============================================================

def _build_event_options(capabilities: ProviderCapabilities, catalog: list[tuple[ProviderCapabilities, str, str, str]]) -> list[SelectOption]:
    return [
        SelectOption(label=label, value=event_type, emoji=emoji)
        for cap, event_type, label, emoji in catalog
        if cap in capabilities
    ]


# ============================================================
# ➕ Ajout d'une règle
# ============================================================

class AddRuleModal(discord.ui.Modal):
    """Ajout d'une nouvelle règle."""

    def __init__(self, *, connection: dict, owner_id: int):
        super().__init__(title="Ajouter une règle")
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
        self.template_id_input = discord.ui.TextInput(
            label="ID du template (optionnel)",
            placeholder="Voir le bouton \"annonces\".",
            required=False,
            max_length=16,
        )
        self.add_item(self.event_type_input)
        self.add_item(self.channel_id_input)
        self.add_item(self.template_id_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        raw_channel_id = self.channel_id_input.value.strip()
        if not raw_channel_id.isdigit():
            await interaction.response.send_message("L'**identifiant** du salon doit être un nombre.", ephemeral=True)
            return

        raw_template_id = self.template_id_input.value.strip()
        if raw_template_id and not raw_template_id.isdigit():
            await interaction.response.send_message("L'**identifiant** du template doit être un nombre.", ephemeral=True)
            return

        template_id = int(raw_template_id) if raw_template_id else None
        if template_id is not None and await medialink_mgr.get_template(template_id) is None:
            await interaction.response.send_message("Aucun **template** existe avec cet identifiant.", ephemeral=True)
            return

        await medialink_mgr.add_rule(
            self.connection["id"],
            self.event_type_input.value.strip(),
            int(raw_channel_id),
            template_id=template_id,
        )

        view = await ConnectionRulesView.build(connection=self.connection, owner_id=self.owner_id)
        await interaction.response.edit_message(view=view)


# ============================================================
# 📋 Liste + gestion des règles
# ============================================================

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
        emoji = _PLATFORM_EMOJI.get(self.connection["platform"], "🔗")
        container.add_item(TextDisplay(f"# <:param:1552374201489297479> Règles — {emoji} {label}"))
        container.add_item(TextDisplay(f"-# {len(self.rules)} règle(s) configurée(s) pour cette connexion."))
        container.add_item(Separator())

        if not self.rules:
            container.add_item(TextDisplay("*Aucune règle configurée pour cette connexion.*"))
        else:
            for i, rule in enumerate(self.rules):
                enabled = rule.get("enabled", True)
                template_note = rule.get("template_name") or "sans template"
                state_badge = "🟢" if enabled else "⚪"
                manage_btn = Button(label="Gérer", style=ButtonStyle.secondary, emoji=EMOJI_EDIT)
                manage_btn.callback = self._cb_manage_rule(rule["id"])
                container.add_item(Section(
                    TextDisplay(
                        f"**{state_badge} - `{rule['event_type']}`**\n"
                        f"-# → <#{rule['channel_id']}> · {template_note}"
                    ),
                    accessory=manage_btn,
                ))
                if i < len(self.rules) - 1:
                    container.add_item(Separator())

        container.add_item(Separator())
        add_btn = Button(label="Ajouter une règle", style=ButtonStyle.success, emoji=EMOJI_ADD)
        add_btn.callback = self._cb_add_rule
        remove_btn = Button(label="Supprimer la connexion", style=ButtonStyle.danger, emoji=EMOJI_DELETE)
        remove_btn.callback = self._cb_remove_connection
        back_btn = Button(label="Retour", style=ButtonStyle.secondary, emoji=EMOJI_BACK)
        back_btn.callback = self._cb_back

        container.add_item(ActionRow(add_btn, remove_btn, back_btn))
        container.add_item(Separator())
        container.add_item(TextDisplay("-# GuideOn Studio"))

        self.add_item(container)

    def _cb_manage_rule(self, rule_id: int):
        """MODIFIÉ (2026-09) : remplace les deux boutons Activer/Désactiver
        + Supprimer affichés sous chaque règle par un unique bouton
        "Gérer" (Section + accessory, aligné à droite — même pattern que
        MediaLinkDashboardView pour les connexions). Ouvre RuleManageView,
        qui regroupe les actions (toggle, suppression) sur un écran dédié
        à la règle."""
        async def _callback(interaction: discord.Interaction) -> None:
            view = await RuleManageView.build(
                connection=self.connection, owner_id=self.owner_id, rule_id=rule_id,
            )
            if view is None:
                # Règle déjà supprimée entre-temps (double-clic, autre session) :
                # on rafraîchit simplement la liste plutôt que d'afficher un écran
                # de gestion sur une règle qui n'existe plus.
                refreshed = await ConnectionRulesView.build(connection=self.connection, owner_id=self.owner_id)
                await self.push_update(interaction, view=refreshed)
                return
            await self.push_update(interaction, view=view)
        return _callback

    async def _cb_add_rule(self, interaction: discord.Interaction) -> None:
        if self.connection["platform"] in medialink_mgr.BLOCKED_PLATFORMS:
            await interaction.response.send_message(
                view=warning_container("🚧 Cette plateforme sera **bientôt disponible**."),
                ephemeral=True,
            )
            return

        if self.connection["platform"] in _PLATFORM_PROVIDERS:
            view = await AddRuleView.build(connection=self.connection, owner_id=self.owner_id)
            await self.push_update(interaction, view=view)
        else:
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


class RuleManageView(BaseLayoutView):
    """Écran de gestion d'une règle unique (activer/désactiver, supprimer).

    AJOUTÉ (2026-09) en remplacement des deux boutons affichés directement
    sous chaque règle dans ConnectionRulesView : celle-ci n'affiche plus
    qu'un bouton "Gérer" par règle (Section + accessory), qui ouvre cet
    écran dédié — même profondeur de navigation que "Gérer" sur une
    connexion (MediaLinkDashboardView → ConnectionRulesView).
    """

    def __init__(self, *, connection: dict, owner_id: int, rule: dict):
        super().__init__(owner_id=owner_id, timeout=300)
        self.connection = connection
        self.rule = rule
        self._build()

    @classmethod
    async def build(cls, *, connection: dict, owner_id: int, rule_id: int) -> "RuleManageView | None":
        rules = await medialink_mgr.list_rules(connection["id"])
        rule = next((r for r in rules if r["id"] == rule_id), None)
        if rule is None:
            return None
        return cls(connection=connection, owner_id=owner_id, rule=rule)

    def _build(self) -> None:
        container = Container()
        rule = self.rule
        enabled = rule.get("enabled", True)
        template_note = rule.get("template_name") or "sans template"
        state_label = "🟢 Activée" if enabled else "⚪ Désactivée"

        container.add_item(TextDisplay("# <:param:1552374201489297479> Gérer la règle"))
        container.add_item(TextDisplay(
            f"**`{rule['event_type']}`**\n"
            f"-# → <#{rule['channel_id']}> · {template_note}\n"
            f"-# Statut : {state_label}"
        ))
        container.add_item(Separator())

        toggle_btn = Button(
            label="Désactiver" if enabled else "Activer",
            style=ButtonStyle.danger if enabled else ButtonStyle.success,
            emoji=EMOJI_CANCEL if enabled else EMOJI_VALID,
        )
        toggle_btn.callback = self._cb_toggle_rule
        delete_btn = Button(label="Supprimer", style=ButtonStyle.danger, emoji=EMOJI_DELETE)
        delete_btn.callback = self._cb_remove_rule
        back_btn = Button(label="Retour", style=ButtonStyle.secondary, emoji=EMOJI_BACK)
        back_btn.callback = self._cb_back

        container.add_item(ActionRow(toggle_btn, delete_btn, back_btn))
        container.add_item(Separator())
        container.add_item(TextDisplay("-# GuideOn Studio"))

        self.add_item(container)

    async def _cb_toggle_rule(self, interaction: discord.Interaction) -> None:
        await medialink_mgr.set_rule_enabled(self.rule["id"], not self.rule.get("enabled", True))
        view = await RuleManageView.build(
            connection=self.connection, owner_id=self.owner_id, rule_id=self.rule["id"],
        )
        await self.push_update(interaction, view=view)

    async def _cb_remove_rule(self, interaction: discord.Interaction) -> None:
        await medialink_mgr.remove_rule(self.rule["id"])
        view = await ConnectionRulesView.build(connection=self.connection, owner_id=self.owner_id)
        await self.push_update(interaction, view=view)

    async def _cb_back(self, interaction: discord.Interaction) -> None:
        view = await ConnectionRulesView.build(connection=self.connection, owner_id=self.owner_id)
        await self.push_update(interaction, view=view)


class AddRuleView(BaseLayoutView):
    """Ajout d'une (ou plusieurs) règle(s) pour une connexion."""

    def __init__(self, *, connection: dict, owner_id: int, templates: list[dict]):
        super().__init__(owner_id=owner_id, timeout=300)
        self.connection = connection
        self.templates = templates
        self.provider_cls = _PLATFORM_PROVIDERS[connection["platform"]]
        self.event_catalog = _PLATFORM_EVENT_CATALOGS[connection["platform"]]
        self._event_types: list[str] = []
        self._channel_id: int | None = None
        self._template_id: int | None = None
        self._build()

    @classmethod
    async def build(cls, *, connection: dict, owner_id: int) -> "AddRuleView":
        templates = await medialink_mgr.list_templates(connection["guild_id"])
        return cls(connection=connection, owner_id=owner_id, templates=templates)

    def _build(self) -> None:
        self.clear_items()

        container = Container()
        label = self.connection.get("external_username") or self.connection["external_id"]
        emoji = _PLATFORM_EMOJI.get(self.connection["platform"], "🔗")
        container.add_item(TextDisplay(f"# {EMOJI_ADD} Ajouter une règle — {emoji} {label}"))
        container.add_item(TextDisplay(
            "-# Choisis un ou plusieurs types d'événements (ex : Vidéo + Short) et un "
            "salon, puis valide. Ils partageront le même salon et le même template."
        ))
        container.add_item(Separator())

        event_options = _build_event_options(self.provider_cls.capabilities, self.event_catalog)
        if not event_options:
            event_options = [SelectOption(label="Aucun type disponible", value="__none__", emoji="⚠️", default=True)]
            event_disabled = True
            max_values = 1
        else:
            event_disabled = False
            max_values = len(event_options)
        event_select = Select(
            placeholder="Type(s) d'événement...",
            options=[
                SelectOption(
                    label=opt.label, value=opt.value, emoji=opt.emoji,
                    default=(opt.value in self._event_types),
                )
                for opt in event_options
            ],
            min_values=1, max_values=max_values, disabled=event_disabled,
        )
        event_select.callback = self._cb_pick_event
        container.add_item(TextDisplay(
            f"**Type(s) d'événement**\n-# {self._event_label()}"
        ))
        container.add_item(ActionRow(event_select))
        container.add_item(Separator())

        channel_select = ChannelSelect(
            placeholder="Salon Discord...",
            on_select=self._cb_pick_channel,
            channel_types=[discord.ChannelType.text, discord.ChannelType.news],
        )
        channel_display = f"<#{self._channel_id}>" if self._channel_id else "`Non choisi`"
        container.add_item(TextDisplay(f"**Salon**\n-# {channel_display}"))
        container.add_item(ActionRow(channel_select))
        container.add_item(Separator())

        template_options = [
            SelectOption(label="Aucun template", value="__none__", default=self._template_id is None)
        ]
        template_options += [
            SelectOption(label=t["name"], value=str(t["id"]), default=(self._template_id == t["id"]))
            for t in self.templates[:24]  # 25 options max sur un Select, 1 réservée à "Aucun"
        ]
        template_select = Select(
            placeholder="Template (optionnel)...", options=template_options, min_values=1, max_values=1,
        )
        template_select.callback = self._cb_pick_template
        container.add_item(TextDisplay(f"**Template**\n-# {self._template_label()}"))
        container.add_item(ActionRow(template_select))
        container.add_item(Separator())

        confirm_label = (
            f"Créer {len(self._event_types)} règle(s)" if len(self._event_types) > 1 else "Créer la règle"
        )
        confirm_btn = Button(
            label=confirm_label,
            style=ButtonStyle.success,
            emoji=EMOJI_VALID,
            disabled=not self._event_types or self._channel_id is None,
        )
        confirm_btn.callback = self._cb_confirm
        cancel_btn = Button(label="Annuler", style=ButtonStyle.secondary, emoji=EMOJI_BACK)
        cancel_btn.callback = self._cb_cancel
        container.add_item(ActionRow(confirm_btn, cancel_btn))
        container.add_item(Separator())
        container.add_item(TextDisplay("-# GuideOn Studio"))

        self.add_item(container)

    def _event_label(self) -> str:
        if not self._event_types:
            return "`Non choisi`"
        labels = []
        for event_type in self._event_types:
            match = next((label for _, et, label, _ in self.event_catalog if et == event_type), None)
            labels.append(f"{match} (`{event_type}`)" if match else f"`{event_type}`")
        return " · ".join(labels)

    def _template_label(self) -> str:
        if self._template_id is None:
            return "Aucun"
        tpl = next((t for t in self.templates if t["id"] == self._template_id), None)
        return tpl["name"] if tpl else "Aucun"

    # ── Callbacks ────────────────────────────────────────────────

    async def _cb_pick_event(self, interaction: discord.Interaction) -> None:
        values = interaction.data["values"]
        self._event_types = [v for v in values if v != "__none__"]
        self._build()
        await self.push_update(interaction)

    async def _cb_pick_channel(self, interaction: discord.Interaction, channel_id: int) -> None:
        self._channel_id = channel_id
        self._build()
        await self.push_update(interaction)

    async def _cb_pick_template(self, interaction: discord.Interaction) -> None:
        value = interaction.data["values"][0]
        self._template_id = int(value) if value != "__none__" else None
        self._build()
        await self.push_update(interaction)

    async def _cb_confirm(self, interaction: discord.Interaction) -> None:
        if not self._event_types or self._channel_id is None:
            await send_ephemeral(
                interaction,
                error_container("Choisis au moins un type d'événement et un salon avant de valider."),
            )
            return

        for event_type in self._event_types:
            await medialink_mgr.add_rule(
                self.connection["id"],
                event_type,
                self._channel_id,
                template_id=self._template_id,
            )

        view = await ConnectionRulesView.build(connection=self.connection, owner_id=self.owner_id)
        await self.push_update(interaction, view=view)

    async def _cb_cancel(self, interaction: discord.Interaction) -> None:
        view = await ConnectionRulesView.build(connection=self.connection, owner_id=self.owner_id)
        await self.push_update(interaction, view=view)


class GuildEventsOverviewView(BaseLayoutView):
    """Interface "Événements" du dashboard."""

    def __init__(self, *, guild_id: int, owner_id: int, rules: list[dict]):
        super().__init__(owner_id=owner_id, timeout=300)
        self.guild_id = guild_id
        self.rules = rules
        self._build()

    @classmethod
    async def build(cls, *, guild: discord.Guild, owner_id: int) -> "GuildEventsOverviewView":
        rules = await medialink_mgr.list_all_rules(guild.id)
        return cls(guild_id=guild.id, owner_id=owner_id, rules=rules)

    def _build(self) -> None:
        container = Container()
        container.add_item(TextDisplay("# <:Stat:1547703142466982039> Événements"))
        container.add_item(Separator())

        if not self.rules:
            container.add_item(
                TextDisplay("*Aucune règle configurée pour l'instant*")
            )
        else:
            lines = []
            for rule in self.rules:
                platform_emoji = _PLATFORM_EMOJI.get(rule["connection_platform"], "🔗")
                template_note = rule.get("template_name") or "sans template"
                lines.append(
                    f"{platform_emoji} **{rule['connection_label']}** — `{rule['event_type']}`\n"
                    f"➣ <#{rule['channel_id']}> - {template_note}\n"
                )
            container.add_item(TextDisplay("\n".join(lines)))

        container.add_item(Separator())
        back_btn = Button(label="Retour", style=ButtonStyle.secondary, emoji=EMOJI_BACK)
        back_btn.callback = self._cb_back
        container.add_item(ActionRow(back_btn))
        container.add_item(Separator())
        container.add_item(TextDisplay("-# GuideOn Studio"))

        self.add_item(container)

    async def _cb_back(self, interaction: discord.Interaction) -> None:
        from views.medialink.medialink_dashboard_view import MediaLinkHubView

        view = await MediaLinkHubView.build(guild=interaction.guild, owner_id=self.owner_id)
        await self.push_update(interaction, view=view)