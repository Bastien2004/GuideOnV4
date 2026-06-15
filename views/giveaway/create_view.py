"""
views/giveaway/create_view.py — Wizard de création de giveaway.

Construit un LayoutView avec 4 sections obligatoires (prix, durée, gagnants,
salon) + 4 sections optionnelles de prérequis (rôle requis, rôle interdit,
min invitations, ancienneté serveur), puis un bouton "Lancer" actif uniquement
si les obligatoires sont remplis.

ctx : dict mutable partagé entre la vue et ses callbacks. Clés :
    prize: str | None
    duration_seconds: int | None
    winners_count: int | None
    channel_id: int | None
    requirements: dict  # role_id, min_invites, min_server_age_days, forbidden_role_id
"""
from __future__ import annotations

import logging
import re
from typing import Optional

import discord
from discord import ButtonStyle, Interaction
from discord.ui import ActionRow, Button, Container, LayoutView, Section, Separator, TextDisplay

from utils.container_universel import error_container, success_container
from utils.managers.giveaway_manager import create_giveaway
from views._components.channel_select import ChannelSelect
from views._components.role_select import RoleSelect
from views._components.text_modal import TextModal
from views.giveaway.panel_view import build_giveaway_panel

log = logging.getLogger(__name__)

# Limites raisonnables (cohérentes avec le V3)
MIN_DURATION = 10            # 10 secondes
MAX_DURATION = 365 * 86400   # 1 an
MAX_WINNERS = 100
MAX_PRIZE_LENGTH = 500
MAX_MIN_INVITES = 10_000
MAX_SERVER_AGE_DAYS = 3650   # 10 ans


# ======================================================
# =================== HELPERS ==========================
# ======================================================

def parse_duration(s: str) -> int:
    """Convertit '1d2h30m15s' en secondes. Retourne 0 si invalide/vide."""
    total = 0
    for val, unit in re.findall(r"(\d+)([dhms])", s.strip().lower()):
        v = int(val)
        if unit == "d":   total += v * 86400
        elif unit == "h": total += v * 3600
        elif unit == "m": total += v * 60
        elif unit == "s": total += v
    return total


def fmt_duration(seconds: int) -> str:
    """Formate des secondes en '1j 2h 30m'."""
    d, r = divmod(int(seconds), 86400)
    h, r = divmod(r, 3600)
    m, s = divmod(r, 60)
    parts = []
    if d: parts.append(f"{d}j")
    if h: parts.append(f"{h}h")
    if m: parts.append(f"{m}m")
    if s: parts.append(f"{s}s")
    return " ".join(parts) if parts else "0s"


def _check_complete(ctx: dict) -> tuple[bool, list[str]]:
    missing = []
    if not ctx.get("prize"):            missing.append("Prix")
    if not ctx.get("duration_seconds"): missing.append("Durée")
    if not ctx.get("winners_count"):    missing.append("Gagnants")
    if not ctx.get("channel_id"):       missing.append("Salon")
    return (len(missing) == 0, missing)


def _fmt_channel(guild: discord.Guild, channel_id: Optional[int]) -> str:
    if not channel_id:
        return "`Non défini`"
    ch = guild.get_channel(channel_id)
    return ch.mention if ch else "`Salon introuvable`"


def _fmt_role(guild: discord.Guild, role_id: Optional[int]) -> str:
    if not role_id:
        return "`Aucun`"
    r = guild.get_role(role_id)
    return r.mention if r else "`Rôle introuvable`"


async def _rerender(interaction: Interaction, guild: discord.Guild, ctx: dict,
                    author_id: int, locked: bool = False):
    new_view = await create_giveaway_setup_view(guild, ctx, author_id, locked=locked)
    if interaction.response.is_done():
        await interaction.edit_original_response(view=new_view)
    else:
        await interaction.response.edit_message(view=new_view)


def _guard(author_id: int):
    async def check(interaction: Interaction) -> bool:
        if interaction.user.id != author_id:
            await interaction.response.send_message(
                view=error_container("Seul l'**auteur** peut utiliser ce menu."),
                ephemeral=True,
            )
            return False
        return True
    return check


# ======================================================
# =============== VUE PRINCIPALE =======================
# ======================================================

async def create_giveaway_setup_view(
    guild: discord.Guild, ctx: dict, author_id: int, locked: bool = False
) -> LayoutView:
    """Construit le wizard. `locked=True` désactive tous les boutons (après lancement)."""
    view = LayoutView(timeout=600)
    container = Container()

    is_complete, missing = _check_complete(ctx)
    req = ctx.get("requirements") or {}

    if locked:
        status = "✅ Giveaway lancé — cette fenêtre est terminée."
    elif is_complete:
        status = "✅ Prêt à être lancé"
    else:
        status = f"⚠️ Manquant : {', '.join(missing)}"

    container.add_item(TextDisplay("# 🎉 Créer un giveaway"))
    container.add_item(TextDisplay(f"-# {status}"))
    container.add_item(Separator())

    # ─── 🏆 Prix ──────────────────────────────────────
    prize_display = ctx.get("prize") or "`Non défini`"
    btn_prize = Button(emoji="✏️", style=ButtonStyle.secondary, disabled=locked)
    btn_prize.callback = _cb_prize(guild, ctx, author_id)
    container.add_item(Section(
        TextDisplay(f"### 🏆 Prix à gagner\n**{prize_display}**"),
        accessory=btn_prize,
    ))

    # ─── ⏱️ Durée ────────────────────────────────────
    dur_display = fmt_duration(ctx["duration_seconds"]) if ctx.get("duration_seconds") else "`Non défini`"
    btn_dur = Button(emoji="✏️", style=ButtonStyle.secondary, disabled=locked)
    btn_dur.callback = _cb_duration(guild, ctx, author_id)
    container.add_item(Section(
        TextDisplay(f"### ⏱️ Durée\n**{dur_display}**"),
        accessory=btn_dur,
    ))

    # ─── 👥 Gagnants ─────────────────────────────────
    win_display = str(ctx["winners_count"]) if ctx.get("winners_count") else "`Non défini`"
    btn_win = Button(emoji="✏️", style=ButtonStyle.secondary, disabled=locked)
    btn_win.callback = _cb_winners(guild, ctx, author_id)
    container.add_item(Section(
        TextDisplay(f"### 👥 Nombre de gagnants\n**{win_display}**"),
        accessory=btn_win,
    ))

    # ─── 📢 Salon ─────────────────────────────────────
    ch_display = _fmt_channel(guild, ctx.get("channel_id"))
    btn_ch = Button(emoji="✏️", style=ButtonStyle.secondary, disabled=locked)
    btn_ch.callback = _cb_channel(guild, ctx, author_id)
    container.add_item(Section(
        TextDisplay(f"### 📢 Salon d'envoi\n**{ch_display}**"),
        accessory=btn_ch,
    ))

    container.add_item(Separator())
    container.add_item(TextDisplay("### 📋 Prérequis *(optionnel)*"))

    # ─── 🎭 Rôle requis ──────────────────────────────
    role_display = _fmt_role(guild, req.get("role_id"))
    btn_role = Button(emoji="✏️", style=ButtonStyle.secondary, disabled=locked)
    btn_role.callback = _cb_role(guild, ctx, author_id, "role_id", "rôle requis")
    container.add_item(Section(
        TextDisplay(f"🎭 **Rôle requis :** {role_display}"),
        accessory=btn_role,
    ))

    # ─── 🚫 Rôle interdit ────────────────────────────
    forbidden_display = _fmt_role(guild, req.get("forbidden_role_id"))
    btn_forbid = Button(emoji="✏️", style=ButtonStyle.secondary, disabled=locked)
    btn_forbid.callback = _cb_role(guild, ctx, author_id, "forbidden_role_id", "rôle interdit")
    container.add_item(Section(
        TextDisplay(f"🚫 **Rôle interdit :** {forbidden_display}"),
        accessory=btn_forbid,
    ))

    # ─── 📨 Min invitations ──────────────────────────
    inv_display = str(req["min_invites"]) if req.get("min_invites") else "`Aucun`"
    btn_inv = Button(emoji="✏️", style=ButtonStyle.secondary, disabled=locked)
    btn_inv.callback = _cb_number(
        guild, ctx, author_id, "min_invites",
        "Min invitations", "Nombre minimum d'invitations",
        max_value=MAX_MIN_INVITES,
    )
    container.add_item(Section(
        TextDisplay(f"📨 **Invitations min :** {inv_display}"),
        accessory=btn_inv,
    ))

    # ─── 📅 Ancienneté serveur ───────────────────────
    age_display = f"{req['min_server_age_days']} jour(s)" if req.get("min_server_age_days") else "`Aucune`"
    btn_age = Button(emoji="✏️", style=ButtonStyle.secondary, disabled=locked)
    btn_age.callback = _cb_number(
        guild, ctx, author_id, "min_server_age_days",
        "Ancienneté serveur", "Ancienneté minimum sur le serveur (en jours)",
        max_value=MAX_SERVER_AGE_DAYS,
    )
    container.add_item(Section(
        TextDisplay(f"📅 **Ancienneté serveur :** {age_display}"),
        accessory=btn_age,
    ))

    container.add_item(Separator())

    # ─── 🚀 Lancer ───────────────────────────────────
    btn_launch = Button(
        label="Lancer le giveaway",
        style=ButtonStyle.success,
        emoji="🚀",
        disabled=(locked or not is_complete),
    )
    btn_launch.callback = _cb_launch(guild, ctx, author_id)
    container.add_item(ActionRow(btn_launch))

    container.add_item(Separator())
    container.add_item(TextDisplay("-# GuideOn Studio"))

    view.add_item(container)
    return view


# ======================================================
# ===================== CALLBACKS ======================
# ======================================================

def _cb_prize(guild, ctx, author_id):
    check = _guard(author_id)
    async def cb(interaction: Interaction):
        if not await check(interaction):
            return
        async def on_submit(inter: Interaction, value: str):
            value = value.strip()
            if not value:
                await inter.response.send_message(
                    view=error_container("Le prix ne peut pas être **vide**."),
                    ephemeral=True,
                )
                return
            if len(value) > MAX_PRIZE_LENGTH:
                await inter.response.send_message(
                    view=error_container(f"Le prix doit faire **moins de {MAX_PRIZE_LENGTH}** caractères."),
                    ephemeral=True,
                )
                return
            ctx["prize"] = value
            await _rerender(inter, guild, ctx, author_id)
        modal = TextModal(
            title="🏆 Prix à gagner",
            label="Quel est le prix ?",
            placeholder="Ex : Nitro classique 1 mois",
            default=ctx.get("prize") or "",
            min_length=1, max_length=MAX_PRIZE_LENGTH,
            style=discord.TextStyle.short,
            on_submit=on_submit,
        )
        await interaction.response.send_modal(modal)
    return cb


def _cb_duration(guild, ctx, author_id):
    check = _guard(author_id)
    async def cb(interaction: Interaction):
        if not await check(interaction):
            return
        async def on_submit(inter: Interaction, value: str):
            secs = parse_duration(value)
            if secs <= 0:
                await inter.response.send_message(
                    view=error_container(
                        "Format invalide. Utilise des unités : `d` (jours), "
                        "`h` (heures), `m` (minutes), `s` (secondes).\n"
                        "*Exemples :* `1d`, `2h30m`, `45m`"
                    ),
                    ephemeral=True,
                )
                return
            if secs < MIN_DURATION:
                await inter.response.send_message(
                    view=error_container(f"Durée minimum : **{MIN_DURATION} secondes**."),
                    ephemeral=True,
                )
                return
            if secs > MAX_DURATION:
                await inter.response.send_message(
                    view=error_container("Durée maximum : **1 an**."),
                    ephemeral=True,
                )
                return
            ctx["duration_seconds"] = secs
            await _rerender(inter, guild, ctx, author_id)
        current = fmt_duration(ctx["duration_seconds"]) if ctx.get("duration_seconds") else ""
        modal = TextModal(
            title="⏱️ Durée du giveaway",
            label="Durée (ex: 1d2h30m)",
            placeholder="1d, 2h30m, 45m, 1h…",
            default=current,
            min_length=2, max_length=20,
            style=discord.TextStyle.short,
            on_submit=on_submit,
        )
        await interaction.response.send_modal(modal)
    return cb


def _cb_winners(guild, ctx, author_id):
    check = _guard(author_id)
    async def cb(interaction: Interaction):
        if not await check(interaction):
            return
        async def on_submit(inter: Interaction, value: str):
            try:
                n = int(value.strip())
            except ValueError:
                await inter.response.send_message(
                    view=error_container("Le nombre de gagnants doit être un **entier**."),
                    ephemeral=True,
                )
                return
            if n < 1:
                await inter.response.send_message(
                    view=error_container("Il faut au moins **1 gagnant**."),
                    ephemeral=True,
                )
                return
            if n > MAX_WINNERS:
                await inter.response.send_message(
                    view=error_container(f"Maximum **{MAX_WINNERS}** gagnants."),
                    ephemeral=True,
                )
                return
            ctx["winners_count"] = n
            await _rerender(inter, guild, ctx, author_id)
        modal = TextModal(
            title="👥 Nombre de gagnants",
            label="Combien de gagnants ?",
            placeholder="1, 2, 5…",
            default=str(ctx["winners_count"]) if ctx.get("winners_count") else "1",
            min_length=1, max_length=3,
            style=discord.TextStyle.short,
            on_submit=on_submit,
        )
        await interaction.response.send_modal(modal)
    return cb


def _cb_channel(guild, ctx, author_id):
    check = _guard(author_id)
    async def cb(interaction: Interaction):
        if not await check(interaction):
            return

        async def on_select(sel: Interaction, channel_id: int):
            ch = sel.guild.get_channel(channel_id)
            if ch is None:
                await sel.response.send_message(
                    view=error_container("Salon **introuvable**."), ephemeral=True,
                )
                return
            me = sel.guild.me
            if me is not None and not ch.permissions_for(me).send_messages:
                await sel.response.send_message(
                    view=error_container(
                        f"Je n'ai **pas la permission** d'écrire dans {ch.mention}."
                    ),
                    ephemeral=True,
                )
                return
            ctx["channel_id"] = channel_id
            new_view = await create_giveaway_setup_view(guild, ctx, author_id)
            await sel.response.edit_message(view=new_view)

        async def on_cancel(cancel_inter: Interaction):
            new_view = await create_giveaway_setup_view(guild, ctx, author_id)
            await cancel_inter.response.edit_message(view=new_view)

        select = ChannelSelect(
            placeholder="Sélectionner un salon",
            on_select=on_select,
            channel_types=[discord.ChannelType.text],
        )
        btn_cancel = Button(label="Annuler", style=ButtonStyle.secondary, emoji="↩️")
        btn_cancel.callback = on_cancel

        temp = LayoutView(timeout=120)
        c = Container()
        c.add_item(TextDisplay("# 📢 Choisir le salon d'envoi"))
        c.add_item(TextDisplay("-# Le giveaway sera publié dans ce salon."))
        c.add_item(Separator())
        c.add_item(ActionRow(select))
        c.add_item(Separator())
        c.add_item(ActionRow(btn_cancel))
        temp.add_item(c)
        await interaction.response.edit_message(view=temp)
    return cb


def _cb_role(guild, ctx, author_id, key: str, label: str):
    """Callback pour role_id ou forbidden_role_id."""
    check = _guard(author_id)
    async def cb(interaction: Interaction):
        if not await check(interaction):
            return

        async def back_to_wizard(inter: Interaction):
            new_view = await create_giveaway_setup_view(guild, ctx, author_id)
            await inter.response.edit_message(view=new_view)

        async def on_select(sel: Interaction, role_ids: list[int]):
            if not role_ids:
                return
            role_id = role_ids[0]
            role = sel.guild.get_role(role_id)
            if role is None:
                await sel.response.send_message(
                    view=error_container("Rôle **introuvable**."), ephemeral=True,
                )
                return
            if role.is_default():
                await sel.response.send_message(
                    view=error_container("Le rôle **@everyone** ne peut pas être utilisé."),
                    ephemeral=True,
                )
                return
            ctx.setdefault("requirements", {})[key] = role_id
            new_view = await create_giveaway_setup_view(guild, ctx, author_id)
            await sel.response.edit_message(view=new_view)

        async def on_clear(clear_inter: Interaction):
            ctx.setdefault("requirements", {})[key] = None
            new_view = await create_giveaway_setup_view(guild, ctx, author_id)
            await clear_inter.response.edit_message(view=new_view)

        select = RoleSelect(
            placeholder=f"Sélectionner un {label}",
            on_select=on_select,
            min_values=1, max_values=1,
        )
        btn_cancel = Button(label="Annuler", style=ButtonStyle.secondary, emoji="↩️")
        btn_cancel.callback = back_to_wizard

        temp = LayoutView(timeout=120)
        c = Container()
        c.add_item(TextDisplay(f"# 🎭 Choisir le **{label}**"))
        c.add_item(Separator())
        c.add_item(ActionRow(select))
        c.add_item(Separator())
        # Si déjà défini, bouton de retrait + Annuler
        if ctx.get("requirements", {}).get(key):
            btn_clear = Button(label="Retirer ce rôle", style=ButtonStyle.danger, emoji="🗑️")
            btn_clear.callback = on_clear
            c.add_item(ActionRow(btn_clear, btn_cancel))
        else:
            c.add_item(ActionRow(btn_cancel))
        temp.add_item(c)
        await interaction.response.edit_message(view=temp)
    return cb


def _cb_number(guild, ctx, author_id, key: str, title: str, label: str,
               max_value: int):
    """Callback générique pour min_invites et min_server_age_days."""
    check = _guard(author_id)
    async def cb(interaction: Interaction):
        if not await check(interaction):
            return
        async def on_submit(inter: Interaction, value: str):
            value = value.strip()
            # Vide → on retire la condition
            if not value or value == "0":
                ctx.setdefault("requirements", {})[key] = None
                await _rerender(inter, guild, ctx, author_id)
                return
            try:
                n = int(value)
            except ValueError:
                await inter.response.send_message(
                    view=error_container("La valeur doit être un **nombre entier**."),
                    ephemeral=True,
                )
                return
            if n < 0:
                await inter.response.send_message(
                    view=error_container("La valeur doit être **positive**."),
                    ephemeral=True,
                )
                return
            if n > max_value:
                await inter.response.send_message(
                    view=error_container(f"Maximum : **{max_value}**."),
                    ephemeral=True,
                )
                return
            ctx.setdefault("requirements", {})[key] = n
            await _rerender(inter, guild, ctx, author_id)
        current = ctx.get("requirements", {}).get(key)
        modal = TextModal(
            title=f"📝 {title}",
            label=label,
            placeholder="Laisse vide ou 0 pour retirer",
            default=str(current) if current else "",
            min_length=0, max_length=6,
            style=discord.TextStyle.short,
            on_submit=on_submit,
        )
        await interaction.response.send_modal(modal)
    return cb


def _cb_launch(guild, ctx, author_id):
    check = _guard(author_id)
    async def cb(interaction: Interaction):
        if not await check(interaction):
            return
        is_complete, missing = _check_complete(ctx)
        if not is_complete:
            await interaction.response.send_message(
                view=error_container(f"Manquant : {', '.join(missing)}"),
                ephemeral=True,
            )
            return
        await interaction.response.defer(ephemeral=True)
        await _finalize_giveaway(interaction, guild, ctx, author_id)
    return cb


# ======================================================
# ================== FINALISATION ======================
# ======================================================

async def _finalize_giveaway(
    interaction: Interaction, guild: discord.Guild, ctx: dict, author_id: int
):
    """Crée le giveaway en DB, envoie le panel, met à jour avec le message_id."""
    channel = guild.get_channel(ctx["channel_id"])
    if not channel or not isinstance(channel, discord.TextChannel):
        await interaction.followup.send(
            view=error_container("Salon **invalide ou introuvable**."),
            ephemeral=True,
        )
        return
    me = guild.me
    if me is None or not channel.permissions_for(me).send_messages:
        await interaction.followup.send(
            view=error_container(f"Je n'ai pas la permission d'écrire dans {channel.mention}."),
            ephemeral=True,
        )
        return

    requirements = {
        k: v for k, v in (ctx.get("requirements") or {}).items() if v
    }

    # 1) Créer l'entrée DB (message_id=None pour l'instant)
    try:
        gid = await create_giveaway(
            guild_id=guild.id,
            channel_id=channel.id,
            host_id=author_id,
            prize=ctx["prize"],
            winners_count=ctx["winners_count"],
            duration_seconds=ctx["duration_seconds"],
            requirements=requirements,
        )
    except Exception:
        log.exception("Échec création giveaway DB")
        await interaction.followup.send(
            view=error_container("Erreur lors de la **création** du giveaway."),
            ephemeral=True,
        )
        return

    # 2) Construire les données d'affichage et envoyer le panel
    from datetime import datetime, timedelta, timezone as tz
    panel_data = {
        "id": gid,
        "prize": ctx["prize"],
        "winners_count": ctx["winners_count"],
        "end_time": datetime.now(tz.utc) + timedelta(seconds=ctx["duration_seconds"]),
        "ended": False,
        "host_id": author_id,
        "winners": [],
        "participants_count": 0,
        "requirements": requirements,
    }

    try:
        msg = await channel.send(view=build_giveaway_panel(panel_data, guild))
        await msg.add_reaction("🎉")
    except discord.Forbidden:
        # Rollback : supprime le giveaway créé en DB
        from utils.managers.giveaway_manager import delete_giveaway
        await delete_giveaway(gid)
        await interaction.followup.send(
            view=error_container(f"Permission refusée d'écrire dans {channel.mention}."),
            ephemeral=True,
        )
        return
    except discord.HTTPException as e:
        from utils.managers.giveaway_manager import delete_giveaway
        await delete_giveaway(gid)
        await interaction.followup.send(
            view=error_container(f"Erreur Discord : `{e}`"),
            ephemeral=True,
        )
        return

    # 3) Enregistrer message_id
    from utils.managers.giveaway_manager import set_message_id
    await set_message_id(gid, msg.id)

    # 4) Verrouiller le wizard et notifier
    locked_view = await create_giveaway_setup_view(guild, ctx, author_id, locked=True)
    try:
        await interaction.edit_original_response(view=locked_view)
    except (discord.NotFound, discord.HTTPException):
        pass

    await interaction.followup.send(
        view=success_container(
            f"Giveaway lancé !\n"
            f"-# **Prix :** {ctx['prize']}\n"
            f"-# **Salon :** {channel.mention}\n"
            f"-# **ID :** `{gid}`\n\n"
            f"Utilise `/giveaway manage {gid}` pour gérer ce giveaway."
        ),
        ephemeral=True,
    )


# ======================================================
# ========== COMPAT COMMANDE : GiveawayCreateView ======
# ======================================================

class GiveawayCreateView:
    @classmethod
    async def create(cls, guild: discord.Guild, author_id: int) -> LayoutView:
        ctx = {
            "prize": None,
            "duration_seconds": None,
            "winners_count": None,
            "channel_id": None,
            "requirements": {
                "role_id": None,
                "min_invites": None,
                "min_server_age_days": None,
                "forbidden_role_id": None,
            },
        }
        return await create_giveaway_setup_view(guild, ctx, author_id)