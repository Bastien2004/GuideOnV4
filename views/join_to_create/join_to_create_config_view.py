"""
views/join_to_create/join_to_create_config_view.py — Interface de configuration du système de join to create.
"""

from __future__ import annotations

import logging

import discord
from discord import ButtonStyle
from discord.ui import ActionRow, Button, Container, Section, Separator, TextDisplay

from utils.boutique.gold_manager import is_gold, send_gold_error
from utils.container_universel import error_container, send_ephemeral, warning_container
from utils.managers.join_to_create_manager import (
    LIMITE_TRIGGERS_DEFAUT,
    LIMITE_TRIGGERS_GOLD,
    can_add_trigger,
    category_already_used,
    create_trigger,
    delete_trigger,
    list_triggers,
    rename_trigger,
)
from utils.settings import settings
from views._components.base_view import BaseLayoutView
from views._components.channel_select import ChannelSelect
from views._components.text_modal import TextModal

log = logging.getLogger(__name__)

ICON_MODIFIER = "<:modifier:1495444144712192003>"
ICON_PLUS = "<:plus:1495444111505752154>"
ICON_DELETE = "<:supprimer:1495444051623809075>"
ICON_BACK = "<:retour:1515658955190308995>"

DEFAULT_TRIGGER_NAME = "➕ 𝓒réer ta 𝓥ocal"


class JoinToCreateConfigView(BaseLayoutView):
    """Panneau /config join_to_create : liste des salons déclencheurs (+
    catégorie de chacun), jusqu'à LIMITE_TRIGGERS_GOLD en Gold+ sinon
    LIMITE_TRIGGERS_DEFAUT (cf. utils.managers.join_to_create_manager)."""

    def __init__(self, *, guild: discord.Guild, moderator_id: int, triggers: list[dict] | None = None):
        super().__init__(owner_id=moderator_id, timeout=300)
        self.guild = guild
        self.moderator_id = moderator_id
        self.triggers = triggers or []
        self._build()

    @classmethod
    async def create(cls, *, guild: discord.Guild, moderator_id: int) -> "JoinToCreateConfigView":
        triggers = await list_triggers(guild.id)
        return cls(guild=guild, moderator_id=moderator_id, triggers=triggers)

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def _build(self) -> None:
        self.clear_items()

        container = Container()
        container.add_item(TextDisplay("# <:audio:1541185132977983508> Configuration Join to Create"))
        container.add_item(TextDisplay("➥ Crée un __salon vocal__ **éphémère** automatiquement."))
        container.add_item(Separator())

        gold = is_gold(self.guild.id)
        limite = LIMITE_TRIGGERS_GOLD if gold else LIMITE_TRIGGERS_DEFAUT
        nb = len(self.triggers)

        # ── Liste des salons déclencheurs ────────────────────
        upgrade_hint = "" if gold else f"\n-# 💡 Passe Gold+ pour débloquer jusqu'à {LIMITE_TRIGGERS_GOLD} salons déclencheurs"
        container.add_item(TextDisplay(f"### <:lister:1495445288364675192> __Salons déclencheurs__ ({nb}/{limite}){upgrade_hint}"))
        container.add_item(Separator())

        if not self.triggers:
            container.add_item(TextDisplay("*Aucun salon déclencheur configuré.*"))
            container.add_item(Separator())
        else:
            for trigger in self.triggers:
                trigger_id = trigger["id"]
                channel_display = f"<#{trigger['trigger_channel_id']}>" if trigger.get("trigger_channel_id") else "`Salon introuvable`"
                category_display = f"<#{trigger['category_id']}>" if trigger.get("category_id") else "`Catégorie introuvable`"

                rename_btn = Button(label="Renommer", style=ButtonStyle.secondary, emoji=ICON_MODIFIER)
                rename_btn.callback = self._cb_open_rename_modal(trigger_id)
                container.add_item(Section(
                    TextDisplay(
                        f"**☎️ {channel_display}**\n"
                        f"-# <:fichier:1495446721520730242> {category_display}"
                    ),
                    accessory=rename_btn,
                ))

                delete_btn = Button(label="Supprimer ce déclencheur", style=ButtonStyle.danger, emoji=ICON_DELETE)
                delete_btn.callback = self._cb_delete_trigger(trigger_id)
                container.add_item(ActionRow(delete_btn))
                container.add_item(Separator())

        # ── Ajouter un déclencheur, ou upsell Gold+ si limite atteinte ──
        if nb < limite:
            cat_select = ChannelSelect(
                placeholder="Choisir la catégorie du nouveau salon déclencheur",
                on_select=self._on_select_new_trigger_category,
                channel_types=[discord.ChannelType.category],
            )
            container.add_item(TextDisplay(
                f"**{ICON_PLUS} Ajouter un salon déclencheur**\n"
                "-# Choisis d'abord la catégorie de destination (le nom sera ensuite demandé)."
            ))
            container.add_item(ActionRow(cat_select))
        elif gold:
            # Déjà Gold+ et au maximum (3/3) : rien de plus à proposer,
            # pas d'upsell puisqu'il n'y a pas de palier au-dessus.
            container.add_item(TextDisplay(f"-# Limite de {LIMITE_TRIGGERS_GOLD} salons déclencheurs atteinte."))
        else:
            upsell_btn = Button(label="Passer Gold+", style=ButtonStyle.secondary, emoji="🔒")
            upsell_btn.callback = self._cb_gold_lock
            container.add_item(Section(
                TextDisplay(
                    "**🔒 Vous avez atteint la limite de salon déclencheur**\n"
                    f"-# Passez Gold+ pour en configurer jusqu'à {LIMITE_TRIGGERS_GOLD} au lieu de {LIMITE_TRIGGERS_DEFAUT}."
                ),
                accessory=upsell_btn,
            ))

        container.add_item(Separator())
        btn_doc = Button(label="Documentation", style=ButtonStyle.link, url=settings.doc_url, emoji="📚")
        container.add_item(ActionRow(btn_doc))
        container.add_item(Separator())
        container.add_item(TextDisplay("-# GuideOn Studio"))

        self.add_item(container)

    async def _refresh(self, interaction: discord.Interaction) -> None:
        self.triggers = await list_triggers(self.guild.id)
        self._build()
        await self.push_update(interaction)

    # ------------------------------------------------------------------
    # Callbacks — Gold+ (limite atteinte)
    # ------------------------------------------------------------------

    async def _cb_gold_lock(self, interaction: discord.Interaction) -> None:
        await send_gold_error(interaction)

    # ------------------------------------------------------------------
    # Callbacks — ajout d'un nouveau déclencheur
    # ------------------------------------------------------------------

    async def _on_select_new_trigger_category(self, interaction: discord.Interaction, category_id: int) -> None:
        # Re-vérifiée ici (pas seulement à l'affichage) : protège contre une
        # guild qui aurait atteint la limite entre l'ouverture du panneau et
        # ce clic (ex: deux admins configurent en même temps).
        can_add, nb, limite = await can_add_trigger(self.guild.id)
        if not can_add:
            await send_ephemeral(interaction, warning_container(f"Limite de salons déclencheurs atteinte ({nb}/{limite})."))
            return

        category = self.guild.get_channel(category_id)
        if not isinstance(category, discord.CategoryChannel):
            await send_ephemeral(interaction, error_container("Catégorie introuvable."))
            return

        if self.guild.me is not None:
            perms = category.permissions_for(self.guild.me)
            if not (perms.manage_channels and perms.view_channel):
                await send_ephemeral(interaction, error_container("Je n'ai pas la **permission** de gérer les salons dans cette catégorie."))
                return

        if await category_already_used(self.guild.id, category_id):
            await send_ephemeral(
                interaction,
                warning_container("Cette catégorie est déjà utilisée par un autre salon déclencheur. Choisis-en une différente."),
            )
            return

        # send_modal() doit être LA réponse à cette interaction (pas de
        # defer/send avant) — appelable ici puisque le ChannelSelect
        # n'a pas encore répondu, même mécanique que l'ancien
        # _on_open_trigger_modal.
        modal = TextModal(
            title="Nouveau salon déclencheur",
            label="Nom du salon déclencheur",
            placeholder=DEFAULT_TRIGGER_NAME,
            default="",
            min_length=1,
            max_length=100,
            on_submit=self._on_submit_new_trigger_name(category_id),
        )
        await interaction.response.send_modal(modal)

    def _on_submit_new_trigger_name(self, category_id: int):
        async def _callback(interaction: discord.Interaction, value: str) -> None:
            name = value.strip()
            if not name:
                await send_ephemeral(interaction, warning_container("Le nom ne peut pas être vide."))
                return

            # Re-vérifications juste avant la création : protège contre une
            # double-soumission (deux flux "Ajouter" lancés avant qu'un
            # premier n'ait fini) — même logique défensive que l'ancienne
            # garde de _on_quick_create_trigger (Paul, 2026-08-24), cette
            # fois sur le NOMBRE de déclencheurs plutôt que sur une simple
            # présence/absence.
            can_add, nb, limite = await can_add_trigger(self.guild.id)
            if not can_add:
                await send_ephemeral(interaction, warning_container(f"Limite de salons déclencheurs atteinte ({nb}/{limite})."))
                return

            if await category_already_used(self.guild.id, category_id):
                await send_ephemeral(interaction, warning_container("Cette catégorie est déjà utilisée par un autre salon déclencheur."))
                return

            category = self.guild.get_channel(category_id)
            if not isinstance(category, discord.CategoryChannel):
                await send_ephemeral(interaction, error_container("La catégorie choisie est introuvable."))
                return

            me = self.guild.me
            if me is None or not category.permissions_for(me).manage_channels:
                await send_ephemeral(
                    interaction, error_container(f"Je n'ai pas la permission de gérer les salons dans **{category.name}**."),
                )
                return

            try:
                channel = await self.guild.create_voice_channel(
                    name=name, category=category, reason=f"Join to Create — nouveau déclencheur par {interaction.user}",
                )
            except discord.Forbidden:
                await send_ephemeral(interaction, error_container("Permissions insuffisantes pour créer ce salon."))
                return
            except discord.HTTPException:
                await send_ephemeral(interaction, error_container("Erreur Discord lors de la création du salon."))
                return

            try:
                await create_trigger(
                    self.guild.id, trigger_channel_id=channel.id, trigger_channel_name=name, category_id=category_id,
                )
            except Exception:
                log.exception(
                    "[CONFIG JOIN_TO_CREATE] Échec enregistrement déclencheur guild=%s channel=%s",
                    self.guild.id, channel.id,
                )
                # Le salon Discord existe mais pas en config : mieux vaut
                # l'annuler que laisser un déclencheur fantôme non géré.
                try:
                    await channel.delete(reason="Join to Create — enregistrement échoué")
                except (discord.Forbidden, discord.HTTPException):
                    pass
                await send_ephemeral(interaction, error_container("Erreur interne : le salon a été annulé."))
                return

            await self._refresh(interaction)
        return _callback

    # ------------------------------------------------------------------
    # Callbacks — renommer un déclencheur existant
    # ------------------------------------------------------------------

    def _cb_open_rename_modal(self, trigger_id: int):
        async def _callback(interaction: discord.Interaction) -> None:
            trigger = next((t for t in self.triggers if t["id"] == trigger_id), None)
            if trigger is None:
                await send_ephemeral(interaction, error_container("Ce déclencheur n'existe plus."))
                return

            modal = TextModal(
                title="Renommer le salon déclencheur",
                label="Nouveau nom du salon déclencheur",
                placeholder=DEFAULT_TRIGGER_NAME,
                default=trigger.get("trigger_channel_name") or "",
                min_length=1,
                max_length=100,
                on_submit=self._on_submit_rename(trigger_id),
            )
            await interaction.response.send_modal(modal)
        return _callback

    def _on_submit_rename(self, trigger_id: int):
        async def _callback(interaction: discord.Interaction, value: str) -> None:
            name = value.strip()
            if not name:
                await send_ephemeral(interaction, warning_container("Le nom ne peut pas être vide."))
                return

            trigger = next((t for t in self.triggers if t["id"] == trigger_id), None)
            if trigger is None:
                await send_ephemeral(interaction, error_container("Ce déclencheur n'existe plus."))
                await self._refresh(interaction)
                return

            channel = self.guild.get_channel(trigger.get("trigger_channel_id"))
            if isinstance(channel, discord.VoiceChannel):
                try:
                    if channel.name != name:
                        await channel.edit(name=name, reason=f"Join to Create — renommage par {interaction.user}")
                except discord.Forbidden:
                    await send_ephemeral(interaction, error_container("Permissions insuffisantes pour renommer ce salon."))
                    return
                except discord.HTTPException:
                    await send_ephemeral(interaction, error_container("Erreur Discord lors du renommage."))
                    return

            await rename_trigger(trigger_id, name)
            await self._refresh(interaction)
        return _callback

    # ------------------------------------------------------------------
    # Callbacks — supprimer un déclencheur existant
    # ------------------------------------------------------------------

    def _cb_delete_trigger(self, trigger_id: int):
        async def _callback(interaction: discord.Interaction) -> None:
            trigger = next((t for t in self.triggers if t["id"] == trigger_id), None)
            if trigger is None:
                await self._refresh(interaction)
                return

            channel = self.guild.get_channel(trigger.get("trigger_channel_id"))
            if isinstance(channel, discord.VoiceChannel):
                try:
                    await channel.delete(reason=f"Join to Create — suppression déclencheur par {interaction.user}")
                except (discord.Forbidden, discord.HTTPException) as exc:
                    log.warning(
                        "[CONFIG JOIN_TO_CREATE] Suppression salon échouée guild=%s channel=%s erreur=%s",
                        self.guild.id, channel.id, exc,
                    )

            await delete_trigger(trigger_id)
            await self._refresh(interaction)
        return _callback