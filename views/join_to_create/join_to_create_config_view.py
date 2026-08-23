"""
views/join_to_create/join_to_create_config_view.py — Interface de configuration du système de join to create.
"""

from __future__ import annotations

import discord
from discord import ButtonStyle
from discord.ui import ActionRow, Button, Container, Separator, TextDisplay

from utils.container_universel import error_container, send_ephemeral, warning_container
from utils.managers.join_to_create_manager import load_config, set_category, set_trigger_channel
from views._components.base_view import BaseLayoutView
from views._components.channel_select import ChannelSelect
from views._components.text_modal import TextModal

ICON_MODIFIER = "<:modifier:1495444144712192003>"
_CATEGORY_CHANNEL_LIMIT = 50


class JoinToCreateConfigView(BaseLayoutView):
    """Panneau /config join_to_create : catégorie destination + salon déclencheur."""

    def __init__(self, *, guild: discord.Guild, moderator_id: int, cfg: dict | None = None):
        super().__init__(owner_id=moderator_id, timeout=300)
        self.guild = guild
        self.moderator_id = moderator_id
        self.cfg = cfg or {"trigger_channel_id": None, "trigger_channel_name": None, "category_id": None}
        self._build()

    @classmethod
    async def create(cls, *, guild: discord.Guild, moderator_id: int) -> "JoinToCreateConfigView":
        cfg = await load_config(guild.id)
        return cls(guild=guild, moderator_id=moderator_id, cfg=cfg)

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def _build(self) -> None:
        self.clear_items()

        container = Container()
        container.add_item(TextDisplay("# <:audio:1541185132977983508> Configuration Join to Create"))
        container.add_item(TextDisplay("➥ Crée un __salon vocal__ **éphémère** automatiquement."))
        container.add_item(Separator())

        # ── Catégorie destination ────────────────────────────
        category_id = self.cfg.get("category_id")
        category_display = f"<#{category_id}>" if category_id else "`Non configurée`"

        cat_select = ChannelSelect(
            placeholder="Choisir la catégorie des salons vocaux",
            on_select=self._on_select_category,
            channel_types=[discord.ChannelType.category],
        )
        container.add_item(TextDisplay(f"**<:fichier:1495446721520730242> Catégorie des salons vocaux**\n-# {category_display}"))
        container.add_item(ActionRow(cat_select))
        container.add_item(Separator())

        # ── Salon déclencheur ─────────────────────────────────
        trigger_id = self.cfg.get("trigger_channel_id")
        trigger_display = f"<#{trigger_id}>" if trigger_id else "`Non configuré`"

        container.add_item(TextDisplay(f"**☎️ Salon déclencheur** : {trigger_display}"))

        category_ready = category_id is not None
        if category_ready:
            btn_trigger = Button(label="Configurer le nom", style=ButtonStyle.primary, emoji=ICON_MODIFIER)
        else:
            btn_trigger = Button(label="Configurez d'abord la catégorie", style=ButtonStyle.secondary, disabled=True)
            
        btn_trigger.callback = self._on_open_trigger_modal
        container.add_item(ActionRow(btn_trigger))
        container.add_item(Separator())

        container.add_item(TextDisplay(
            f"-# Limite : le nombre de vocaux actifs est plafonné par la limite "
            f"Discord de {_CATEGORY_CHANNEL_LIMIT} salons par catégorie. Au-delà, "
            "le membre est expulsé du salon déclencheur et prévenu en MP."
        ))
        container.add_item(TextDisplay("-# GuideOn Studio"))

        self.add_item(container)

    async def _refresh(self, interaction: discord.Interaction) -> None:
        self.cfg = await load_config(self.guild.id)
        self._build()
        await self.push_update(interaction)

    # ------------------------------------------------------------------
    # Callbacks — catégorie
    # ------------------------------------------------------------------

    async def _on_select_category(self, interaction: discord.Interaction, channel_id: int) -> None:
        channel = self.guild.get_channel(channel_id)
        if not isinstance(channel, discord.CategoryChannel):
            await interaction.response.send_message(
                view=error_container("Catégorie introuvable."), ephemeral=True,
            )
            return

        if self.guild.me is not None:
            perms = channel.permissions_for(self.guild.me)
            if not (perms.manage_channels and perms.view_channel):
                await interaction.response.send_message(
                    view=error_container(
                        f"Je n'ai pas la permission de gérer les salons dans **{channel.name}**."
                    ),
                    ephemeral=True,
                )
                return

        await set_category(self.guild.id, channel_id)
        await self._refresh(interaction)

    # ------------------------------------------------------------------
    # Callbacks — salon déclencheur
    # ------------------------------------------------------------------

    async def _on_open_trigger_modal(self, interaction: discord.Interaction) -> None:
        if self.cfg.get("category_id") is None:
            await interaction.response.send_message(
                view=warning_container("Configurez d'abord la **catégorie** de destination."),
                ephemeral=True,
            )
            return

        modal = TextModal(
            title="Salon déclencheur",
            label="Nom du salon déclencheur",
            placeholder="『☎』¦créer ta voc",
            default=self.cfg.get("trigger_channel_name") or "",
            min_length=1,
            max_length=100,
            on_submit=self._on_submit_trigger_name,
        )
        await interaction.response.send_modal(modal)

    async def _on_submit_trigger_name(self, interaction: discord.Interaction, value: str) -> None:
        name = value.strip()
        if not name:
            await send_ephemeral(interaction, warning_container("Le nom ne peut pas être vide."))
            return

        category_id = self.cfg.get("category_id")
        category = self.guild.get_channel(category_id) if category_id else None
        if not isinstance(category, discord.CategoryChannel):
            await send_ephemeral(interaction, error_container("La catégorie configurée est introuvable."))
            return

        me = self.guild.me
        if me is None or not category.permissions_for(me).manage_channels:
            await send_ephemeral(
                interaction,
                error_container(f"Je n'ai pas la permission de gérer les salons dans **{category.name}**."),
            )
            return

        existing_id = self.cfg.get("trigger_channel_id")
        existing = self.guild.get_channel(existing_id) if existing_id else None
        audit_reason = f"Configuration Join to Create par {interaction.user}"

        try:
            if isinstance(existing, discord.VoiceChannel):
                if existing.name != name:
                    await existing.edit(name=name, reason=audit_reason)
                channel = existing
            else:
                channel = await self.guild.create_voice_channel(
                    name=name, category=category, reason=audit_reason,
                )
        except discord.Forbidden:
            await send_ephemeral(
                interaction, error_container("Permissions insuffisantes pour créer/modifier ce salon."),
            )
            return
        except discord.HTTPException:
            await send_ephemeral(
                interaction, error_container("Erreur Discord lors de la création/modification du salon."),
            )
            return

        await set_trigger_channel(self.guild.id, channel.id, name)
        await self._refresh(interaction)