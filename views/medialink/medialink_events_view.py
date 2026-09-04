"""
views/medialink/medialink_events_view.py — configuration des règles
(Rules, §3) d'UNE connexion : quel event_type → quel salon → quel
template → quel rôle à mentionner. Et l'écran "Événements" du hub
(vue d'ensemble toutes connexions confondues).

RESTYLÉ (2026-09) — mêmes conventions que medialink_dashboard_view.py :
émotes custom du serveur, ActionRow pour les rangées de boutons, lignes
"**gras** — état" / "-# sous-texte".

── YOUTUBE : SELECT NATIFS (2026-09, Provider réel branché) ─────────
Pour une connexion YouTube (cf. medialink_platforms_view.py, même date),
"Ajouter une règle" n'ouvre plus le Modal manuel mais AddRuleView
(ci-dessous) : un Select pour l'event_type — rempli depuis
YouTubeProvider.capabilities, comme prévu par le TODO d'origine, donc il
suit automatiquement les capabilities réelles du Provider — un
ChannelSelect natif Discord pour le salon (composant partagé
views/_components/channel_select.py, déjà utilisé ailleurs dans le bot,
ex. views/mod/logs_config_view.py), et un Select pour le template
existant. Un Modal Discord ne pouvant pas contenir de Select (limite de
l'API), ça ne pouvait pas rester un Modal une fois ces 3 champs
transformés en Select — d'où cet écran séparé (confirmé avec Paul).

── ÉVÉNEMENT(S) : SÉLECTION MULTIPLE (2026-09) ────────────────────────
BUG DE FOND CORRIGÉ : un Short YouTube (vidéo ≤180s, cf.
providers/youtube.py::_SHORT_MAX_SECONDS) a un event_type distinct
("youtube.short_published") de "youtube.video_published" — un admin qui
ne crée qu'une règle "Nouvelle vidéo" ne reçoit donc JAMAIS d'annonce
pour ses Shorts, silencieusement (event_manager.resolve_active_rules()
fait une correspondance stricte sur event_type, §9 du cahier des
charges — aucune règle trouvée = SKIPPED, sans erreur visible). Trouvé
en prod (connexion créée sans règle "short_published", plusieurs Shorts
jamais annoncés avant que ce soit remarqué).

Plutôt que de créer les règles automatiquement à la connexion (impossible
proprement : le salon/template ne sont choisis qu'à cette étape-ci,
cf. medialink_platforms_view.py::_submit_youtube, pas au moment de la
connexion), le Select d'event_type devient multi-sélection : l'admin
choisit "Nouvelle vidéo" ET "Nouveau Short" en une fois, sur le même
salon/template choisis une seule fois, et _cb_confirm crée une MediaRule
par event_type sélectionné. Reste un choix explicite de l'admin (il peut
tout aussi bien ne cocher que "Live" s'il ne veut pas des Shorts), pas
une création silencieuse en son nom.

── TWITCH / TIKTOK / REDDIT : TOUJOURS EN AJOUT MANUEL (provisoire) ──
Leurs Providers sont encore des stubs (cf. medialink_platforms_view.py) :
AddRuleModal (Modal, saisie manuelle par TextInput) reste le flux pour
ces 3 plateformes, cf. _cb_add_rule qui dispatche selon la plateforme de
la connexion. À basculer vers AddRuleView au même principe que YouTube
au fur et à mesure que Bastien livre chaque Provider.
"""
from __future__ import annotations

import discord
from discord import ButtonStyle, SelectOption
from discord.ui import ActionRow, Button, Container, Section, Select, Separator, TextDisplay

from utils.container_universel import error_container, send_ephemeral
from utils.db.models.medialink_connection import MediaPlatform
from utils.managers import medialink_manager as medialink_mgr
from utils.medialink.providers.base import ProviderCapabilities
from utils.medialink.providers.youtube import YouTubeProvider
from views._components.base_view import BaseLayoutView
from views._components.channel_select import ChannelSelect

EMOJI_ADD = "<:plus:1495444111505752154>"
EMOJI_DELETE = "<:supprimer:1495444051623809075>"
EMOJI_BACK = "<:retour:1515658955190308995>"
EMOJI_VALID = "<:valider:1495444292867723284>"
EMOJI_CANCEL = "<:annuler:1495444256754761979>"

_PLATFORM_EMOJI = {
    "youtube": "▶️",
    "twitch": "🟣",
    "tiktok": "🎵",
    "reddit": "🔴",
}

# capability → (event_type, label affiché, emoji) — un seul provider réel
# pour l'instant (YouTube), mais la liste d'options se déduit de ses
# capabilities réelles plutôt que d'être figée en dur (cf. docstring).
_YOUTUBE_EVENT_CATALOG: list[tuple[ProviderCapabilities, str, str, str]] = [
    (ProviderCapabilities.NEW_POST, "youtube.video_published", "Nouvelle vidéo", "▶️"),
    (ProviderCapabilities.SHORT_FORM, "youtube.short_published", "Nouveau Short", "🎬"),
    (ProviderCapabilities.LIVE_STATUS, "youtube.live_started", "Passage en live", "🔴"),
]


def _build_event_options(capabilities: ProviderCapabilities) -> list[SelectOption]:
    return [
        SelectOption(label=label, value=event_type, emoji=emoji)
        for cap, event_type, label, emoji in _YOUTUBE_EVENT_CATALOG
        if cap in capabilities
    ]


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
        self.template_id_input = discord.ui.TextInput(
            label="ID du template (optionnel)",
            placeholder="Voir le bouton Annonces du hub — laisser vide si aucun",
            required=False,
            max_length=16,
        )
        self.add_item(self.event_type_input)
        self.add_item(self.channel_id_input)
        self.add_item(self.template_id_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        raw_channel_id = self.channel_id_input.value.strip()
        if not raw_channel_id.isdigit():
            await interaction.response.send_message(
                "❌ L'ID du salon doit être un nombre (clic droit sur le salon → Copier l'identifiant).",
                ephemeral=True,
            )
            return

        raw_template_id = self.template_id_input.value.strip()
        if raw_template_id and not raw_template_id.isdigit():
            await interaction.response.send_message(
                "❌ L'ID du template doit être un nombre (visible dans l'écran Annonces du hub), "
                "ou laissé vide.",
                ephemeral=True,
            )
            return

        template_id = int(raw_template_id) if raw_template_id else None
        if template_id is not None and await medialink_mgr.get_template(template_id) is None:
            await interaction.response.send_message(
                "❌ Aucun template avec cet ID — vérifie dans l'écran Annonces du hub, "
                "ou laisse le champ vide pour une règle sans template.",
                ephemeral=True,
            )
            return

        await medialink_mgr.add_rule(
            self.connection["id"],
            self.event_type_input.value.strip(),
            int(raw_channel_id),
            template_id=template_id,
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
        emoji = _PLATFORM_EMOJI.get(self.connection["platform"], "🔗")
        container.add_item(TextDisplay(f"# 🔧 Règles — {emoji} {label}"))
        container.add_item(TextDisplay(f"-# {len(self.rules)} règle(s) configurée(s) pour cette connexion."))
        container.add_item(Separator())

        if not self.rules:
            container.add_item(TextDisplay("*Aucune règle configurée pour cette connexion.*"))
        else:
            for rule in self.rules:
                enabled = rule.get("enabled", True)
                toggle_btn = Button(
                    label="Désactiver" if enabled else "Activer",
                    style=ButtonStyle.danger if enabled else ButtonStyle.success,
                    emoji=EMOJI_CANCEL if enabled else EMOJI_VALID,
                )
                toggle_btn.callback = self._cb_toggle_rule(rule["id"])
                template_note = f"template #{rule['template_id']}" if rule.get("template_id") else "sans template"
                state_badge = "🟢 Active" if enabled else "⚪ Inactive"
                container.add_item(Section(
                    TextDisplay(
                        f"**`{rule['event_type']}`** — {state_badge}\n"
                        f"-# → <#{rule['channel_id']}> · {template_note}"
                    ),
                    accessory=toggle_btn,
                ))

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
        if self.connection["platform"] == MediaPlatform.YOUTUBE.value:
            # Provider réel : Select natifs plutôt qu'un Modal (cf. docstring).
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


class AddRuleView(BaseLayoutView):
    """Ajout d'une (ou plusieurs) règle(s) pour une connexion dont le
    Provider est réel (YouTube actuellement, cf. docstring de module) :
    un Select MULTI-sélection pour le/les event_type(s), un ChannelSelect
    natif Discord pour le salon, et un Select pour le template existant.
    Impossible de tout mettre dans un Modal Discord (qui ne peut pas
    contenir de Select), donc le choix se fait par rerender successifs
    de cette même vue, au même principe que
    views/mod/logs_config_view.py::_refresh.

    Sélection multiple du type d'événement (2026-09, cf. docstring de
    module) : évite qu'un admin crée une règle "Nouvelle vidéo" sans
    penser à "Nouveau Short" à côté — même salon/template, un seul choix
    d'un coup, une MediaRule créée par event_type coché.
    """

    def __init__(self, *, connection: dict, owner_id: int, templates: list[dict]):
        super().__init__(owner_id=owner_id, timeout=300)
        self.connection = connection
        self.templates = templates
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

        event_options = _build_event_options(YouTubeProvider.capabilities)
        if not event_options:
            # Défense en profondeur : ne devrait pas arriver tant que
            # YouTube a au moins une capability, cf. _YOUTUBE_EVENT_CATALOG.
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
            match = next((label for _, et, label, _ in _YOUTUBE_EVENT_CATALOG if et == event_type), None)
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

        # Une MediaRule par event_type coché, toutes sur le même salon
        # et le même template — cf. docstring de classe.
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
    """Écran "Événements" du hub — TOUTES les règles de la guild, toutes
    connexions confondues, en lecture seule (§16 : vue d'ensemble). Pour
    modifier une règle précise, on passe par Plateformes → Gérer → cette
    connexion (ConnectionRulesView, ci-dessus) — pas de duplication du
    flux d'édition ici, juste la vue d'ensemble qui manquait au hub."""

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
        container.add_item(TextDisplay("# ⚡ Événements"))
        container.add_item(TextDisplay(f"-# {len(self.rules)} règle(s) configurée(s) sur ce serveur."))
        container.add_item(Separator())

        if not self.rules:
            container.add_item(
                TextDisplay(
                    "*Aucune règle configurée pour l'instant — ajoute une connexion "
                    "puis une règle depuis l'écran Plateformes.*"
                )
            )
        else:
            lines = []
            for rule in self.rules:
                status_icon = "🟢" if rule.get("enabled", True) else "⚪"
                platform_emoji = _PLATFORM_EMOJI.get(rule["connection_platform"], "🔗")
                template_note = f"template #{rule['template_id']}" if rule.get("template_id") else "sans template"
                lines.append(
                    f"{status_icon} {platform_emoji} **{rule['connection_label']}** — "
                    f"`{rule['event_type']}` → <#{rule['channel_id']}>\n-# {template_note}"
                )
            container.add_item(TextDisplay("\n".join(lines)))

        container.add_item(Separator())
        back_btn = Button(label="Retour au hub", style=ButtonStyle.secondary, emoji=EMOJI_BACK)
        back_btn.callback = self._cb_back
        container.add_item(ActionRow(back_btn))
        container.add_item(Separator())
        container.add_item(TextDisplay("-# GuideOn Studio"))

        self.add_item(container)

    async def _cb_back(self, interaction: discord.Interaction) -> None:
        from views.medialink.medialink_dashboard_view import MediaLinkHubView

        view = await MediaLinkHubView.build(guild=interaction.guild, owner_id=self.owner_id)
        await self.push_update(interaction, view=view)