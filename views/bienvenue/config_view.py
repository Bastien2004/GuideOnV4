"""
views/bienvenue/config_view.py — Interface /config bienvenue.
"""
from __future__ import annotations

import logging
from typing import Optional

import discord
from discord import ButtonStyle, Interaction
from discord.ui import ActionRow, Button, Container, LayoutView, Section, Separator, TextDisplay

from utils.boutique.gold_manager import is_gold, send_gold_error
from utils.container_universel import error_container, success_container
from utils.managers.bienvenue_manager import load_bienvenue_config, reset_bienvenue_config, save_bienvenue_config
from utils.bienvenue_render import build_bienvenue_embed, render_template

from views._components.channel_select import ChannelSelect
from views._components.text_modal import TextModal

log = logging.getLogger(__name__)

VARIABLES_HELP = (
    "`{user}` — Nom de l'utilisateur\n"
    "`{mention}` — Mention de l'utilisateur\n"
    "`{server}` — Nom du serveur\n"
    "`{member_count}` — Nombre de membres"
)


# ======================================================
# =================== UI HELPERS =======================
# ======================================================

def _preview(text: str, max_len: int = 70) -> str:
    text = text or ""
    return (text[: max_len - 1] + "…") if len(text) > max_len else text

def _state_btn(active: bool) -> Button:
    return Button(
        label="Activé" if active else "Désactivé",
        style=ButtonStyle.success if active else ButtonStyle.danger,
        emoji="🟢" if active else "🔴",
    )


# ======================================================
# =============== CONSTRUCTION DE LA VUE ===============
# ======================================================

async def create_bienvenue_view(guild_id: int, bot, author_id: Optional[int] = None,) -> Optional[LayoutView]:
    """Construction de l'interface de création."""

    guild = bot.get_guild(guild_id)
    if guild is None:
        log.error("Guild %s introuvable dans le cache", guild_id)
        return None

    cfg = await load_bienvenue_config(guild_id)
    gold = is_gold(guild_id)

    system_active = cfg.get("system_active", False)
    arrive_active = cfg.get("arrive_active", False)
    depart_active = cfg.get("depart_active", False)
    arrive_channel = cfg.get("arrive_channel_id")
    depart_channel = cfg.get("depart_channel_id")
    arrive_message = cfg.get("arrive_message", "")
    depart_message = cfg.get("depart_message", "")

    issues = []
    if system_active:
        if arrive_active and not arrive_channel:
            issues.append("arrivée activée sans salon")
        if depart_active and not depart_channel:
            issues.append("départ activé sans salon")
        if not arrive_active and not depart_active:
            issues.append("aucune annonce active")
    if not system_active:
        etat = "-# ⚪ Système **désactivé**"
    elif issues:
        etat = "-# ⚠️ Actif mais incomplet : " + ", ".join(issues)
    else:
        etat = "-# ✅ Système **opérationnel**"

    view = LayoutView(timeout=None)
    container = Container()

    container.add_item(TextDisplay(f"# 👋 Configuration · Bienvenue\n{etat}"))
    container.add_item(Separator())

    btn_sys = _state_btn(system_active)
    btn_sys.callback = _cb_toggle(guild_id, bot, author_id, "system_active")
    container.add_item(Section(
        TextDisplay("**État du système**"),
        accessory=btn_sys,
    ))
    container.add_item(Separator())

    _add_block(
        container, guild, guild_id, bot, author_id,
        titre="🛬 Arrivée",
        active=arrive_active, active_key="arrive_active",
        channel_id=arrive_channel, channel_key="arrive_channel_id",
        message=arrive_message, message_key="arrive_message",
    )
    container.add_item(Separator())

    _add_block(
        container, guild, guild_id, bot, author_id,
        titre="🛫 Départ",
        active=depart_active, active_key="depart_active",
        channel_id=depart_channel, channel_key="depart_channel_id",
        message=depart_message, message_key="depart_message",
    )
    container.add_item(Separator())

    container.add_item(TextDisplay(f"### 📌 Variables\n{VARIABLES_HELP}"))
    container.add_item(Separator())

    suffix = "" if gold else " (Gold+)"
    btn_test_a = Button(label="Test arrivée" + suffix, style=ButtonStyle.secondary, emoji="🧪")
    btn_test_d = Button(label="Test départ" + suffix, style=ButtonStyle.secondary, emoji="🧪")
    btn_reset = Button(label="Réinitialiser", style=ButtonStyle.danger, emoji="<:recharger:1495444327629852703>")
    btn_test_a.callback = _cb_test(guild_id, bot, author_id, "arrive")
    btn_test_d.callback = _cb_test(guild_id, bot, author_id, "depart")
    btn_reset.callback = _cb_reset(guild_id, bot, author_id)
    container.add_item(ActionRow(btn_test_a, btn_test_d, btn_reset))

    container.add_item(Separator())
    container.add_item(TextDisplay("-# GuideOn Studio"))

    view.add_item(container)
    return view


def _add_block(
    container, guild, guild_id, bot, author_id, *,
    titre, active, active_key, channel_id, channel_key, message, message_key,
):
    """Ajoute un bloc d'annonce (toggle + salon + message) au container."""
    state = "🟢 ON" if active else "🔴 OFF"
    ch_txt = f"<#{channel_id}>" if channel_id else "`aucun salon`"
    warn = "" if (channel_id or not active) else " ⚠️"

    btn_toggle = _state_btn(active)
    btn_toggle.callback = _cb_toggle(guild_id, bot, author_id, active_key)
    container.add_item(Section(
        TextDisplay(f"### {titre} — {state}\n-# Salon : {ch_txt}{warn}"),
        accessory=btn_toggle,
    ))

    btn_channel = Button(label="Salon", style=ButtonStyle.secondary, emoji="<:salons:1508535670333902999>")
    btn_channel.callback = _cb_pick_channel(guild_id, bot, author_id, channel_key)

    btn_msg = Button(label="Message", style=ButtonStyle.secondary, emoji="<:modifier:1495444144712192003>")
    btn_msg.callback = _cb_edit_message(guild_id, bot, author_id, message_key)

    container.add_item(Section(
        TextDisplay(f"-# Aperçu : {_preview(render_template(message, member=guild.me, guild=guild), 90)}"),
        accessory=btn_msg,
    ))
    container.add_item(ActionRow(btn_channel))


# ======================================================
# ===================== CALLBACKS ======================
# ======================================================

def _guard(author_id: Optional[int]):
    async def check(interaction: Interaction) -> bool:
        if author_id is not None and interaction.user.id != author_id:
            await interaction.response.send_message(
                view=error_container("Seul l'**auteur** de la commande peut utiliser ce __menu__."),
                ephemeral=True,
            )
            return False
        member = interaction.user
        if not isinstance(member, discord.Member) or not member.guild_permissions.administrator:
            await interaction.response.send_message(
                view=error_container("Vous devez être **Administrateur**."),
                ephemeral=True,
            )
            return False
        return True
    return check


async def _rerender(interaction: Interaction, guild_id: int, bot, author_id):
    new_view = await create_bienvenue_view(guild_id, bot, author_id)
    if new_view is None:
        await interaction.response.send_message(
            view=error_container("Serveur **introuvable**."), ephemeral=True
        )
        return
    if interaction.response.is_done():
        await interaction.edit_original_response(view=new_view)
    else:
        await interaction.response.edit_message(view=new_view)


def _cb_toggle(guild_id, bot, author_id, key):
    check = _guard(author_id)

    async def cb(interaction: Interaction):
        if not await check(interaction):
            return
        current = (await load_bienvenue_config(guild_id)).get(key, False)
        await save_bienvenue_config(guild_id, {key: not current})
        await _rerender(interaction, guild_id, bot, author_id)
    return cb


def _cb_reset(guild_id, bot, author_id):
    check = _guard(author_id)

    async def cb(interaction: Interaction):
        if not await check(interaction):
            return
        await reset_bienvenue_config(guild_id)
        await _rerender(interaction, guild_id, bot, author_id)
    return cb


def _cb_edit_message(guild_id, bot, author_id, message_key):
    check = _guard(author_id)

    async def cb(interaction: Interaction):
        if not await check(interaction):
            return
        current = (await load_bienvenue_config(guild_id)).get(message_key, "")

        async def on_submit(inter: Interaction, value: str):
            await save_bienvenue_config(guild_id, {message_key: value.strip()})
            await _rerender(inter, guild_id, bot, author_id)

        modal = TextModal(
            title="💬 Personnaliser le message",
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


def _cb_pick_channel(guild_id, bot, author_id, channel_key):
    check = _guard(author_id)

    async def cb(interaction: Interaction):
        if not await check(interaction):
            return

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
            await save_bienvenue_config(guild_id, {channel_key: channel_id})
            await sel.response.edit_message(view=success_container("Salon **mis à jour** !"))
            new_view = await create_bienvenue_view(guild_id, bot, author_id)
            if new_view:
                try:
                    await parent.edit_original_response(view=new_view)
                except (discord.NotFound, discord.HTTPException):
                    log.warning("[Bienvenue] Mise à jour de la view après sélection salon impossible")

        select = ChannelSelect(
            placeholder="Sélectionner un salon texte",
            on_select=on_select,
            channel_types=[discord.ChannelType.text],
        )
        temp = LayoutView(timeout=120)
        c = Container()
        c.add_item(TextDisplay("📥 Choisis le salon :"))
        c.add_item(ActionRow(select))
        temp.add_item(c)
        await interaction.response.send_message(view=temp, ephemeral=True)
    return cb


def _cb_test(guild_id, bot, author_id, page):
    check = _guard(author_id)

    async def cb(interaction: Interaction):
        if not await check(interaction):
            return
        if not is_gold(guild_id):
            await send_gold_error(interaction)
            return

        cfg = await load_bienvenue_config(guild_id)
        is_arrive = page == "arrive"
        channel_id = cfg.get("arrive_channel_id" if is_arrive else "depart_channel_id")
        message = cfg.get("arrive_message" if is_arrive else "depart_message", "")

        if not channel_id:
            await interaction.response.send_message(
                view=error_container("**Aucun** salon défini pour cette __annonce__."), ephemeral=True
            )
            return
        channel = bot.get_channel(channel_id)
        if not isinstance(channel, discord.TextChannel):
            await interaction.response.send_message(
                view=error_container("Le salon configuré est **introuvable**."), ephemeral=True
            )
            return

        rendered = render_template(message, member=interaction.guild.me, guild=interaction.guild)
        embed_kind = "arrivee" if is_arrive else "depart"
        embed, file = build_bienvenue_embed(rendered, kind=embed_kind)
        embed.set_footer(text="GuideON Studio · 🧪 Message de test")
        try:
            if file is not None:
                await channel.send(embed=embed, file=file)
            else:
                await channel.send(embed=embed)
            await interaction.response.send_message(
                view=success_container(f"Test envoyé dans {channel.mention} !"), ephemeral=True
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                view=error_container(f"Permission **refusée** dans {channel.mention}."), ephemeral=True
            )
    return cb


# ======================================================
# ========== COMPAT COG : BienvenueConfigView ==========
# ======================================================

class BienvenueConfigView:
    @classmethod
    async def create(cls, guild_id: int, author_id: int, bot) -> LayoutView:
        view = await create_bienvenue_view(guild_id, bot, author_id)
        if view is None:
            return error_container("**Impossible** de charger la __configuration__ (serveur introuvable).")
        return view