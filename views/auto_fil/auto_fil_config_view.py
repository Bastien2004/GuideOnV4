"""
views/auto_fil/auto_fil_config_view.py — Interface de configuration du
système "Auto-fil" (/config auto_fil, Paul, 2026-10-15).

Crée automatiquement un fil (thread) sous chaque message posté dans un
salon configuré. Patron repris de JoinToCreateConfigView
(views/join_to_create/join_to_create_config_view.py) : liste des salons
configurés (0 à limite), ChannelSelect pour en ajouter un, bouton
Supprimer par entrée, palier Gold+ (1 salon par défaut, 3 en Gold+) avec
upsell quand la limite est atteinte.

⚠️ Cooldown (Paul) : "le bot vérifie si le salon possède déjà un cooldown,
dans le cas contraire, il en impose un de 10s" — confirmé = le slowmode
natif Discord du salon (channel.slowmode_delay / rate_limit_per_user), PAS
un minuteur interne au bot. Posé UNE FOIS, au moment où le salon est
ajouté ici (_on_select_channel) — pas revérifié à chaque message par le
listener (cogs/events/auto_fil_listener.py) : une fois réglé, un admin
reste libre de le changer ensuite dans les paramètres Discord du salon
sans que le bot ne le réimpose.
"""
from __future__ import annotations

import logging

import discord
from discord import ButtonStyle
from discord.ui import ActionRow, Button, Container, Section, Separator, TextDisplay

from utils.boutique.gold_manager import is_gold, send_gold_error
from utils.container_universel import error_container, send_ephemeral
from utils.managers.auto_fil_manager import (
    LIMITE_DEFAUT,
    LIMITE_GOLD,
    can_add_config,
    channel_already_used,
    create_config,
    delete_config,
    list_configs,
)
from utils.settings import settings
from views._components.base_view import BaseLayoutView
from views._components.channel_select import ChannelSelect

log = logging.getLogger(__name__)

ICON_DELETE = "<:supprimer:1495444051623809075>"
ICON_PLUS = "<:plus:1495444111505752154>"

# Slowmode (en secondes) imposé si le salon n'en a aucun au moment de l'ajout.
DEFAULT_SLOWMODE_SECONDS = 10


class AutoFilConfigView(BaseLayoutView):
    """Gestion du panneau de configuration du système Auto-fil."""

    def __init__(self, *, guild: discord.Guild, moderator_id: int, configs: list[dict] | None = None):
        super().__init__(owner_id=moderator_id, timeout=300)
        self.guild = guild
        self.moderator_id = moderator_id
        self.configs = configs or []
        self._build()

    @classmethod
    async def create(cls, *, guild: discord.Guild, moderator_id: int) -> "AutoFilConfigView":
        configs = await list_configs(guild.id)
        return cls(guild=guild, moderator_id=moderator_id, configs=configs)

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def _build(self) -> None:
        self.clear_items()

        container = Container()
        container.add_item(TextDisplay("# 🧵 Configuration Auto-fil"))
        container.add_item(TextDisplay(
            "➥ Crée automatiquement un **fil** sous chaque message posté dans un salon configuré."
        ))
        container.add_item(Separator())

        gold = is_gold(self.guild.id)
        limite = LIMITE_GOLD if gold else LIMITE_DEFAUT
        nb = len(self.configs)

        container.add_item(TextDisplay(f"### 📋 __Salons configurés__ ({nb}/{limite})"))
        container.add_item(Separator())

        if not self.configs:
            container.add_item(TextDisplay("*Aucun salon auto-fil configuré.*"))
            container.add_item(Separator())
        else:
            for cfg in self.configs:
                cfg_id = cfg["id"]
                channel = self.guild.get_channel(cfg["channel_id"])
                channel_display = channel.mention if channel is not None else "`Salon supprimé`"

                slowmode_display = ""
                if isinstance(channel, (discord.TextChannel, discord.Thread)):
                    slowmode_display = f"\n-# ⏱️ Slowmode actuel : **{channel.slowmode_delay}s**"

                delete_btn = Button(label="Retirer", style=ButtonStyle.danger, emoji=ICON_DELETE)
                delete_btn.callback = self._cb_delete_config(cfg_id)
                container.add_item(Section(
                    TextDisplay(f"**🧵 {channel_display}**{slowmode_display}"),
                    accessory=delete_btn,
                ))
                container.add_item(Separator())

        if nb < limite:
            chan_select = ChannelSelect(
                placeholder="Choisir un salon",
                on_select=self._on_select_channel,
            )
            container.add_item(TextDisplay(f"**{ICON_PLUS} Ajouter un salon**"))
            container.add_item(ActionRow(chan_select))

        elif gold:
            container.add_item(TextDisplay("-# Limite de salons auto-fil atteinte."))

        else:
            upsell_btn = Button(label="Passer Gold+", style=ButtonStyle.secondary, emoji="🔒")
            upsell_btn.callback = self._cb_gold_lock
            container.add_item(Section(
                TextDisplay(
                    "**🔒 Vous avez atteint la limite de salons auto-fil**\n"
                    "-# Passez Gold+ pour configurer jusqu'à 3 salons."
                ),
                accessory=upsell_btn,
            ))

        container.add_item(Separator())
        btn_doc = Button(label="Documentation", style=ButtonStyle.link, url=settings.doc_url, emoji="📚")
        container.add_item(ActionRow(btn_doc))
        container.add_item(Separator())
        container.add_item(TextDisplay("-# GuideOn Studio"))

        self.add_item(container)

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    async def _refresh(self, interaction: discord.Interaction) -> None:
        self.configs = await list_configs(self.guild.id)
        self._build()
        await self.push_update(interaction)

    async def _cb_gold_lock(self, interaction: discord.Interaction) -> None:
        await send_gold_error(interaction)

    async def _on_select_channel(self, interaction: discord.Interaction, channel_id: int) -> None:
        can_add, nb, limite = await can_add_config(self.guild.id)
        if not can_add:
            await send_ephemeral(interaction, error_container(f"Limite de salons auto-fil atteinte ({nb}/{limite})."))
            return

        if await channel_already_used(self.guild.id, channel_id):
            await send_ephemeral(interaction, error_container("Ce salon est **déjà** configuré pour l'auto-fil."))
            return

        channel = self.guild.get_channel(channel_id)
        if not isinstance(channel, discord.TextChannel):
            await send_ephemeral(interaction, error_container("Ce salon est **introuvable** ou n'est pas un salon textuel."))
            return

        me = self.guild.me
        if me is not None:
            perms = channel.permissions_for(me)
            missing = []
            if not perms.view_channel:
                missing.append("Voir le salon")
            if not perms.create_public_threads:
                missing.append("Créer des fils publics")
            if not perms.manage_channels:
                missing.append("Gérer les salons")
            if missing:
                await send_ephemeral(
                    interaction,
                    error_container(
                        f"Je n'ai pas les permissions nécessaires dans {channel.mention} : "
                        f"**{', '.join(missing)}**."
                    ),
                )
                return

        # Cooldown (Paul) : slowmode natif du salon, imposé à 10s si absent.
        # Posé UNE FOIS ici, pas revérifié par le listener à chaque message
        # (cf. docstring module). On ne send_ephemeral PAS tout de suite en
        # cas d'échec : l'interaction doit d'abord servir à rafraîchir le
        # panneau (edit_message, plus bas) — un send_ephemeral ici la
        # consommerait et _refresh() finirait par éditer le mauvais message
        # (edit_original_response sur ce message d'erreur éphémère au lieu
        # du panneau). L'avertissement, s'il y en a un, part en followup
        # APRÈS le rafraîchissement (send_ephemeral route alors vers
        # followup.send puisque la réponse est déjà consommée).
        slowmode_warning: str | None = None
        if channel.slowmode_delay == 0:
            try:
                await channel.edit(
                    slowmode_delay=DEFAULT_SLOWMODE_SECONDS,
                    reason=f"Auto-fil activé par {interaction.user} — aucun cooldown existant",
                )
            except (discord.Forbidden, discord.HTTPException):
                log.warning(
                    "[CONFIG AUTO_FIL] Échec réglage slowmode guild=%s channel=%s",
                    self.guild.id, channel.id,
                )
                slowmode_warning = (
                    f"Le salon a été activé, mais je n'ai pas pu régler son cooldown "
                    f"à **{DEFAULT_SLOWMODE_SECONDS}s** (permissions insuffisantes) — à faire manuellement."
                )

        try:
            await create_config(self.guild.id, channel_id)
        except Exception:
            log.exception(
                "[CONFIG AUTO_FIL] Échec enregistrement guild=%s channel=%s", self.guild.id, channel.id,
            )
            await send_ephemeral(interaction, error_container("**Erreur interne** : le salon n'a pas été enregistré."))
            return

        await self._refresh(interaction)
        if slowmode_warning is not None:
            await send_ephemeral(interaction, error_container(slowmode_warning))

    def _cb_delete_config(self, config_id: int):
        async def _callback(interaction: discord.Interaction) -> None:
            await delete_config(config_id)
            await self._refresh(interaction)
        return _callback
