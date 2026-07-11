"""
views/bienvenue/config_view.py — Interface /config bienvenue.
"""

from __future__ import annotations

import logging
from typing import Optional

import discord
from discord import ButtonStyle, Interaction
from discord.ui import ActionRow, Button, Container, Section, Separator, TextDisplay

from utils.bienvenue_render import (
    build_bienvenue_embed,
    build_bienvenue_view,
    is_valid_image_url,
    render_template,
    resolve_image_url,
)

from utils.boutique.gold_manager import is_gold, send_gold_error
from utils.container_universel import error_container, send_ephemeral, success_container
from utils.db.models.bienvenue import BienvenueFormat
from utils.managers.bienvenue_manager import load_bienvenue_config, reset_bienvenue_config, save_bienvenue_config
from views._components.base_view import BaseLayoutView
from views._components.channel_select import ChannelSelect
from views._components.text_modal import TextModal
from utils.settings import settings


# ============================================================
# 📦 Constantes
# ============================================================

log = logging.getLogger(__name__)

VARIABLES_HELP_SHORT = "Vous disposez de **plusieurs variables** pour __personnaliser__\nvos **message** de __bienvenue__ et de __départ__."

VARIABLES_FULL = [
    ("{user}", "Nom Discord du membre"),
    ("{display_name}", "Nom d'affichage du membre"),
    ("{mention}", "Mention du membre (@membre)"),
    ("{id}", "ID Discord du membre"),
    ("{member_created_at}", "Date de création du compte Discord (JJ/MM/AAAA)"),
    ("{server}", "Nom du serveur"),
    ("{member_count}", "Nombre de membres du serveur"),
    ("{guild_created_at}", "Date de création du serveur (JJ/MM/AAAA)"),
]

KIND_LABELS = {
    "arrive": ("🛬", "Arrivée", "arrivee"),
    "depart": ("🛫", "Départ", "depart"),
}


# ============================================================
# 🔩 Fonctions utilitaires
# ============================================================

def _preview_text(text: str, max_len: int = 90) -> str:
    """Renvoie un apperçu du texte, tronqué si nécéssaire."""
    text = text or ""
    return (text[: max_len - 1] + "…") if len(text) > max_len else text


def _state_btn(active: bool, label_on: str = "Activé", label_off: str = "Désactivé") -> Button:
    """Renvoie un bouton d'état ON/OFF selon le statut."""
    return Button(
        label=label_on if active else label_off,
        style=ButtonStyle.success if active else ButtonStyle.danger,
        emoji="<:valider:1495444292867723284>" if active else "<:annuler:1495444256754761979>",
    )


async def create_bienvenue_view(guild_id: int, bot, author_id: Optional[int] = None, page: str = "main") -> Optional[BaseLayoutView]:
    """Construit l'interface de configuration bienvenue."""

    guild = bot.get_guild(guild_id)
    if guild is None:
        log.error("[Bienvenue] Guild %s introuvable dans le cache", guild_id)
        return None

    cfg = await load_bienvenue_config(guild_id)
    gold = is_gold(guild_id)
    return BienvenueView(guild=guild, bot=bot, author_id=author_id, cfg=cfg, gold=gold, page=page)


# ============================================================
# 🧩 Class principale
# ============================================================

class BienvenueView(BaseLayoutView):
    def __init__(self, *, guild: discord.Guild, bot, author_id: Optional[int], cfg: dict, gold: bool, page: str = "main"):
        super().__init__(owner_id=author_id, timeout=600)
        self.guild = guild
        self.bot = bot
        self.cfg = cfg
        self.gold = gold
        self.page = page
        self._build()


    async def _rerender(self, interaction: Interaction, *, page: Optional[str] = None) -> None:
        """Recharge la config depuis la DB et met à jour l'interface."""

        new_cfg = await load_bienvenue_config(self.guild.id)

        new_view = BienvenueView(
            guild=self.guild, bot=self.bot, author_id=self.owner_id,
            cfg=new_cfg, gold=is_gold(self.guild.id),
            page=page if page is not None else self.page,
        )
        await self.push_update(interaction, view=new_view)


    def _build(self) -> None:
        """Construit la page demandée."""

        c = Container()
        if self.page in ("arrive", "depart"):
            self._build_detail(c, self.page)
        else:
            self._build_main(c)
        self.add_item(c)


    def _build_main(self, c: Container) -> None:
        """Construit la page principale de l'interface."""

        cfg = self.cfg
        system_active = cfg.get("system_active", False)


        c.add_item(TextDisplay(f"# 👋 Configuration Bienvenue"))
        c.add_item(Separator())

        btn_sys = _state_btn(system_active)
        btn_sys.callback = self._cb_toggle_system
        c.add_item(Section(
            TextDisplay(
            "**🔘 Statut du système**\n"
            "-# Active ou désactive le système de bienvenue."
        ),
        accessory=btn_sys
        ))
        c.add_item(Separator())

        for key, (emoji, label, _) in KIND_LABELS.items():
            active = cfg.get(f"{key}_active", False)
            channel_id = cfg.get(f"{key}_channel_id")
            fmt = cfg.get(f"{key}_format", BienvenueFormat.EMBED.value)
            fmt_label = "Embed" if fmt == BienvenueFormat.EMBED.value else "Texte"
            ch_txt = f"<#{channel_id}>" if channel_id else "__Aucun salon__"
            state_txt = "🟢 ON" if active else "🔴 OFF"

            open_btn = Button(label="Configurer", style=ButtonStyle.secondary, emoji="<:parametre:1495444004328706059>")
            open_btn.callback = self._make_cb_open(key)
            c.add_item(Section(
                TextDisplay(f"**{emoji} {label}** — {state_txt}\n-# {ch_txt} · format {fmt_label}"),
                accessory=open_btn,
            ))
            c.add_item(Separator())

        c.add_item(TextDisplay(f"### 📌 __Variables__ :\n{VARIABLES_HELP_SHORT}"))
        c.add_item(Separator())

        vars_btn_main = Button(
            label="Liste des variables",
            style=ButtonStyle.secondary,
            emoji="<:info:1495443961144152094>",
        )
        vars_btn_main.callback = self._cb_show_variables

        doc_btn = Button(
            label="Documentation",
            style=ButtonStyle.link,
            url=settings.doc_url,
            emoji="📚",
        )

        c.add_item(ActionRow(vars_btn_main, doc_btn))
        c.add_item(Separator())
        c.add_item(TextDisplay("-# GuideOn Studio"))


    def _build_detail(self, c: Container, kind: str) -> None:
        """Construit la page de gestion arrivée ou départ."""

        cfg = self.cfg
        emoji, label, embed_kind = KIND_LABELS[kind]
        active = cfg.get(f"{kind}_active", False)
        channel_id = cfg.get(f"{kind}_channel_id")
        message = cfg.get(f"{kind}_message", "")
        fmt = cfg.get(f"{kind}_format", BienvenueFormat.EMBED.value)
        image_url = cfg.get(f"{kind}_image_url")
        is_embed = fmt == BienvenueFormat.EMBED.value

        c.add_item(TextDisplay(f"# 👋 Gestion message d'arrivée"))
        c.add_item(Separator())

        btn_active = _state_btn(active)
        btn_active.callback = self._make_cb_toggle_kind(kind)
        c.add_item(Section(TextDisplay("**Etat du message d'arrivée**"), accessory=btn_active))
        c.add_item(Separator())

        ch_txt = f"<#{channel_id}>" if channel_id else "`Non configuré`"
        btn_channel = Button(label="Modifier", style=ButtonStyle.secondary, emoji="<:modifier:1495444144712192003>")
        btn_channel.callback = self._make_cb_pick_channel(kind)
        c.add_item(Section(TextDisplay(f"⇝ **Salon**\n-# {ch_txt}"), accessory=btn_channel))
        c.add_item(Separator())

        btn_embed = Button(
            label="Embed", style=ButtonStyle.primary if is_embed else ButtonStyle.secondary,
            emoji="🖼️", disabled=is_embed,
        )
        btn_text = Button(
            label="Texte", style=ButtonStyle.primary if not is_embed else ButtonStyle.secondary,
            emoji="📄", disabled=not is_embed,
        )
        btn_embed.callback = self._make_cb_set_format(kind, BienvenueFormat.EMBED.value)
        btn_text.callback = self._make_cb_set_format(kind, BienvenueFormat.TEXT.value)
        c.add_item(TextDisplay("⇝ **Format du message**"))
        c.add_item(ActionRow(btn_embed, btn_text))
        c.add_item(Separator())

        btn_msg = Button(label="Modifier", style=ButtonStyle.secondary, emoji="<:modifier:1495444144712192003>")
        btn_msg.callback = self._make_cb_edit_message(kind)
        rendered_preview = render_template(message, member=self.guild.me, guild=self.guild)
        c.add_item(Section(
            TextDisplay(f"⇝ **Message**\n-# {_preview_text(rendered_preview)}"),
            accessory=btn_msg,
        ))
        c.add_item(Separator())

        if is_embed:
            if self.gold:
                if image_url:
                    c.add_item(TextDisplay("**Image**\n-# ✅ Image personnalisée active"))
                    btn_rm_img = Button(label="Retirer l'image", style=ButtonStyle.danger, emoji="<:supprimer:1495444051623809075>")
                    btn_rm_img.callback = self._make_cb_remove_image(kind)
                    c.add_item(ActionRow(btn_rm_img))
                else:
                    btn_img = Button(label="Ajouter une image", style=ButtonStyle.secondary, emoji="<:plus:1495444111505752154>")
                    btn_img.callback = self._make_cb_edit_image(kind)
                    c.add_item(Section(
                        TextDisplay("**Image**\n-# `Bannière par défaut`"),
                        accessory=btn_img,
                    ))
            else:
                note = (
                    "-# 🔒 Image personnalisée sauvegardée, inactive tant que Gold+ n'est pas actif"
                    if image_url else "-# 🔒 Réservé aux serveurs Gold+"
                )
                lock_btn = Button(label="Gold+ requis", style=ButtonStyle.secondary, emoji="🔒")
                lock_btn.callback = self._cb_gold_lock
                c.add_item(Section(TextDisplay(f"**Image personnalisée** ✨\n{note}"), accessory=lock_btn))
            c.add_item(Separator())

        c.add_item(TextDisplay(f"-# 📌 {VARIABLES_HELP_SHORT}"))
        c.add_item(Separator())

        # Aperçu (Gold+) + Variables (liste complète, gratuit)
        preview_suffix = "" if self.gold else " (Gold+)"
        preview_btn = Button(label=f"Aperçu{preview_suffix}", style=ButtonStyle.secondary, emoji="👁️")
        preview_btn.callback = self._make_cb_preview(kind)
        vars_btn = Button(label="Variables", style=ButtonStyle.secondary, emoji="❓")
        vars_btn.callback = self._cb_show_variables
        c.add_item(ActionRow(preview_btn, vars_btn))
        c.add_item(Separator())

        back_btn = Button(label="Retour", style=ButtonStyle.secondary, emoji="◀️")
        back_btn.callback = self._cb_back
        c.add_item(ActionRow(back_btn))
        c.add_item(Separator())
        c.add_item(TextDisplay("-# GuideOn Studio"))

    # ------------------------------------------------------------------
    # Callbacks — navigation
    # ------------------------------------------------------------------

    def _make_cb_open(self, kind: str):
        async def cb(interaction: Interaction):
            await self._rerender(interaction, page=kind)
        return cb

    async def _cb_back(self, interaction: Interaction) -> None:
        await self._rerender(interaction, page="main")

    # ------------------------------------------------------------------
    # Callbacks — actions
    # ------------------------------------------------------------------

    async def _cb_toggle_system(self, interaction: Interaction) -> None:
        current = self.cfg.get("system_active", False)
        await save_bienvenue_config(self.guild.id, {"system_active": not current})
        await self._rerender(interaction)

    async def _cb_reset(self, interaction: Interaction) -> None:
        await reset_bienvenue_config(self.guild.id)
        await self._rerender(interaction, page="main")

    async def _cb_gold_lock(self, interaction: Interaction) -> None:
        await send_gold_error(interaction)

    async def _cb_show_variables(self, interaction: Interaction) -> None:
        """Liste complète des variables — éphémère, gratuit, disponible partout."""
        lines = [f"`{var}` — {desc}" for var, desc in VARIABLES_FULL]
        view = BaseLayoutView(owner_id=self.owner_id, timeout=120)
        c = Container()
        c.add_item(TextDisplay("# 📌 Variables disponibles"))
        c.add_item(Separator())
        c.add_item(TextDisplay("\n".join(lines)))
        c.add_item(Separator())
        c.add_item(TextDisplay("-# Utilisables dans les messages d'arrivée et de départ."))
        view.add_item(c)
        await interaction.response.send_message(view=view, ephemeral=True)

    def _make_cb_toggle_kind(self, kind: str):
        async def cb(interaction: Interaction):
            current = self.cfg.get(f"{kind}_active", False)
            await save_bienvenue_config(self.guild.id, {f"{kind}_active": not current})
            await self._rerender(interaction, page=kind)
        return cb

    def _make_cb_set_format(self, kind: str, fmt: str):
        async def cb(interaction: Interaction):
            await save_bienvenue_config(self.guild.id, {f"{kind}_format": fmt})
            await self._rerender(interaction, page=kind)
        return cb

    def _make_cb_edit_message(self, kind: str):
        _, label, _ = KIND_LABELS[kind]

        async def cb(interaction: Interaction):
            current = self.cfg.get(f"{kind}_message", "")

            async def on_submit(inter: Interaction, value: str):
                await save_bienvenue_config(self.guild.id, {f"{kind}_message": value.strip()})
                await self._rerender(inter, page=kind)

            modal = TextModal(
                title=f"✏️ Message — {label}",
                label="Message",
                placeholder="Variables : {user} {mention} {server} {member_count}",
                default=current,
                min_length=1,
                max_length=2000,
                style=discord.TextStyle.paragraph,
                on_submit=on_submit,
            )
            await interaction.response.send_modal(modal)
        return cb

    def _make_cb_edit_image(self, kind: str):
        _, label, _ = KIND_LABELS[kind]

        async def cb(interaction: Interaction):
            if not is_gold(self.guild.id):
                await send_gold_error(interaction)
                return
            current = self.cfg.get(f"{kind}_image_url") or ""

            async def on_submit(inter: Interaction, value: str):
                value = value.strip()
                if value and not is_valid_image_url(value):
                    await send_ephemeral(inter, error_container(
                        "URL d'image invalide.\n"
                        "-# Formats acceptés : .png .jpg .gif .webp, ou un lien Discord/Imgur."
                    ))
                    return
                await save_bienvenue_config(self.guild.id, {f"{kind}_image_url": value or None})
                await self._rerender(inter, page=kind)

            modal = TextModal(
                title=f"🖼️ Image — {label}",
                label="URL de l'image",
                placeholder="https://cdn.discordapp.com/... ou https://i.imgur.com/...",
                default=current,
                min_length=0,
                max_length=500,
                required=False,
                on_submit=on_submit,
            )
            await interaction.response.send_modal(modal)
        return cb

    def _make_cb_remove_image(self, kind: str):
        async def cb(interaction: Interaction):
            await save_bienvenue_config(self.guild.id, {f"{kind}_image_url": None})
            await self._rerender(interaction, page=kind)
        return cb

    def _make_cb_pick_channel(self, kind: str):
        async def cb(interaction: Interaction):
            parent = interaction

            async def on_select(sel: Interaction, channel_id: int):
                channel = sel.guild.get_channel(channel_id)
                if isinstance(channel, discord.TextChannel):
                    perms = channel.permissions_for(sel.guild.me)
                    if not (perms.send_messages and perms.view_channel):
                        await sel.response.edit_message(
                            view=error_container(f"Je ne peux pas **écrire** dans {channel.mention}.")
                        )
                        return
                await save_bienvenue_config(self.guild.id, {f"{kind}_channel_id": channel_id})
                await sel.response.edit_message(view=success_container("Salon **mis à jour** !"))
                await self._rerender(parent, page=kind)

            select = ChannelSelect(placeholder="Sélectionner un salon", on_select=on_select)
            temp = BaseLayoutView(owner_id=self.owner_id, timeout=120)
            tc = Container()
            tc.add_item(TextDisplay("📥 Choisis le salon :"))
            tc.add_item(ActionRow(select))
            temp.add_item(tc)
            await interaction.response.send_message(view=temp, ephemeral=True)
        return cb

    def _make_cb_preview(self, kind: str):
        """Aperçu éphémère, Gold+ — jamais envoyé dans le salon réel.
        Rendu avec les mêmes fonctions que l'envoi réel : fidèle à 100%."""
        _, _, embed_kind = KIND_LABELS[kind]

        async def cb(interaction: Interaction):
            if not is_gold(self.guild.id):
                await send_gold_error(interaction)
                return

            cfg = self.cfg
            message = cfg.get(f"{kind}_message", "")
            fmt = cfg.get(f"{kind}_format", BienvenueFormat.EMBED.value)
            image_url = cfg.get(f"{kind}_image_url")
            rendered = render_template(message, member=self.guild.me, guild=self.guild)

            if fmt == BienvenueFormat.TEXT.value:
                await interaction.response.send_message(
                    view=build_bienvenue_view(rendered, kind=embed_kind), ephemeral=True,
                )
            else:
                resolved_image = resolve_image_url(self.guild.id, image_url)
                embed, file = build_bienvenue_embed(rendered, kind=embed_kind, custom_image_url=resolved_image)
                kwargs = {"embed": embed, "ephemeral": True}
                if file is not None:
                    kwargs["file"] = file
                await interaction.response.send_message(**kwargs)
        return cb