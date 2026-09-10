"""
views/exp/info_view.py — /exp info : menu explicatif du système d'EXP.

REFONTE (2026-09, retour Paul : "un système de menu... tout bien séparer") :
remplace l'ancien mur de texte unique par un menu à 3 sections (Select) —
Gains / Paliers / Commandes — chacune sur son propre écran avec un bouton
Retour, à l'image des hubs du bot (cf. views/medialink/medialink_dashboard_view.py
et views/mod/automod_dashboard_view.py, même principe de navigation).

Une seule classe porte tout (pas de sous-vues séparées) : le contenu est
100% statique/lecture seule (aucune mutation, juste 4 écrans différents),
donc un simple attribut `self.section` + une méthode `_build_xxx()` par
écran suffit — inutile de complexifier avec plusieurs fichiers/classes
pour un menu aussi simple.
"""
from __future__ import annotations

import discord
from discord import ButtonStyle, SelectOption
from discord.ui import ActionRow, Button, Container, Select, Separator, TextDisplay

from utils.managers.exp_manager import LEVEL_TIERS, MAX_LEVEL
from utils.settings import settings
from views._components.base_view import BaseLayoutView

EMOJI_BACK = "<:retour:1515658955190308995>"

_SECTION_OPTIONS = [
    SelectOption(label="Les gains", value="gains", emoji="💰", description="Comment gagner de l'EXP"),
    SelectOption(label="Les paliers", value="paliers", emoji="🏔️", description="Les rangs et niveaux"),
    SelectOption(label="Les commandes", value="commandes", emoji="📜", description="Toutes les commandes /exp"),
]

_COMMANDS = [
    ("`/exp level [membre]`", "Affiche la carte de niveau et l'EXP d'un membre (toi par défaut)."),
    ("`/exp leaderboard`", "Affiche le classement EXP du serveur."),
    ("`/exp info`", "Affiche ce menu explicatif."),
    ("`/exp gestion <membre>`", "**Admin** — Ajuste manuellement l'EXP d'un membre."),
    ("`/exp config`", "**Admin** — Configure le système d'EXP (gains, rôle boost, annonce de level-up)."),
]


def _boost_role_label(role_id: int | None, guild: discord.Guild) -> str:
    if role_id is None:
        return "`Aucun rôle boost configuré sur ce serveur.`"
    role = guild.get_role(role_id)
    return role.mention if role is not None else "`Rôle supprimé`"


class ExpInfoView(BaseLayoutView):
    """Menu explicatif de /exp info — écran d'accueil + 3 sections."""

    def __init__(self, *, guild: discord.Guild, cfg: dict, owner_id: int | None = None):
        super().__init__(owner_id=owner_id, timeout=300)
        self.guild = guild
        self.cfg = cfg
        self.section = "home"
        self._build()

    @classmethod
    async def create(cls, *, guild: discord.Guild, cfg: dict, owner_id: int | None = None) -> "ExpInfoView":
        return cls(guild=guild, cfg=cfg, owner_id=owner_id)

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def _build(self) -> None:
        self.clear_items()
        builders = {
            "gains": self._build_gains,
            "paliers": self._build_paliers,
            "commandes": self._build_commandes,
        }
        container = builders.get(self.section, self._build_home)()
        self.add_item(container)

    def _footer(self, container: Container) -> None:
        container.add_item(Separator())
        container.add_item(TextDisplay("-# GuideOn Studio"))

    def _back_button(self) -> Button:
        btn = Button(label="Retour", style=ButtonStyle.secondary, emoji=EMOJI_BACK)
        btn.callback = self._cb_back
        return btn

    def _build_home(self) -> Container:
        container = Container()
        container.add_item(TextDisplay("# 🧮 Système d'Expérience"))
        container.add_item(TextDisplay(
            f"Chaque membre progresse à travers **{MAX_LEVEL} niveaux**, répartis en "
            f"**{len(LEVEL_TIERS)} paliers** personnalisés propres à GuideOn.\n"
            f"-# Choisis une section ci-dessous pour en savoir plus."
        ))
        container.add_item(Separator())

        select = Select(placeholder="📖 Choisir une section", options=_SECTION_OPTIONS)
        select.callback = self._cb_select_section
        container.add_item(ActionRow(select))
        container.add_item(Separator())

        doc_btn = Button(label="Documentation", style=ButtonStyle.link, url=settings.doc_url, emoji="📚")
        container.add_item(ActionRow(doc_btn))
        self._footer(container)
        return container

    def _build_gains(self) -> Container:
        container = Container()
        container.add_item(TextDisplay("# 💰 Les gains d'EXP"))
        container.add_item(TextDisplay("-# Valeurs actuellement configurées sur ce serveur."))
        container.add_item(Separator())

        per_message = self.cfg.get("exp_per_message", 10)
        per_voice = self.cfg.get("exp_per_voice_minute", 2)
        boost_role_id = self.cfg.get("boost_role_id")
        boost_percent = self.cfg.get("boost_percent", 0)

        container.add_item(TextDisplay(
            f"**💬 Message**\n-# `+{per_message} EXP` par message envoyé, avec un cooldown "
            f"de 60 secondes entre deux gains (anti-spam)."
        ))
        container.add_item(Separator())
        container.add_item(TextDisplay(
            f"**🎙️ Vocal**\n-# `+{per_voice} EXP` par minute passée dans un salon vocal."
        ))
        container.add_item(Separator())

        if boost_role_id and boost_percent > 0:
            container.add_item(TextDisplay(
                f"**🚀 Rôle boost**\n-# {_boost_role_label(boost_role_id, self.guild)} bénéficie "
                f"de **+{boost_percent}%** d'EXP sur tous ses gains (message et vocal)."
            ))
        else:
            container.add_item(TextDisplay(f"**🚀 Rôle boost**\n-# {_boost_role_label(boost_role_id, self.guild)}"))
        container.add_item(Separator())

        container.add_item(ActionRow(self._back_button()))
        self._footer(container)
        return container

    def _build_paliers(self) -> Container:
        container = Container()
        container.add_item(TextDisplay("# 🏔️ Les paliers"))
        container.add_item(TextDisplay(
            f"-# {len(LEVEL_TIERS)} paliers répartis sur {MAX_LEVEL} niveaux — plus le niveau "
            f"est élevé, plus il faut d'EXP pour progresser au suivant."
        ))
        container.add_item(Separator())

        tier_lines = [
            f"**{tier['name']}** — Niveaux `{tier['range'][0]}` à `{tier['range'][1]}`"
            for tier in LEVEL_TIERS
        ]
        container.add_item(TextDisplay("\n".join(tier_lines)))
        container.add_item(Separator())

        container.add_item(ActionRow(self._back_button()))
        self._footer(container)
        return container

    def _build_commandes(self) -> Container:
        container = Container()
        container.add_item(TextDisplay("# 📜 Les commandes"))
        container.add_item(Separator())

        lines = [f"{cmd}\n-# {desc}" for cmd, desc in _COMMANDS]
        container.add_item(TextDisplay("\n\n".join(lines)))
        container.add_item(Separator())

        container.add_item(ActionRow(self._back_button()))
        self._footer(container)
        return container

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    async def _cb_select_section(self, interaction: discord.Interaction) -> None:
        self.section = interaction.data["values"][0]
        self._build()
        await self.push_update(interaction)

    async def _cb_back(self, interaction: discord.Interaction) -> None:
        self.section = "home"
        self._build()
        await self.push_update(interaction)
