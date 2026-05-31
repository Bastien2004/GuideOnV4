"""
views/giveaway/manage_view.py — Vue /giveaway manage <id>.

Affiche les infos d'un giveaway et propose des actions selon son état :
- Actif : Prolonger / Terminer maintenant / Voir participants (Gold+) / Supprimer
- Terminé : Reroll / Voir participants (Gold+) / Supprimer

Actions destructives (Terminer / Supprimer) protégées par modal de confirmation.
"""
from __future__ import annotations

import logging
import random
from datetime import datetime, timedelta, timezone
from typing import Optional

import discord
from discord import ButtonStyle, Interaction
from discord.ui import (
    ActionRow, Button, Container, LayoutView, Section, Separator, TextDisplay,
)

from utils.container_universel import error_container, info_container, success_container
from utils.managers.giveaway_manager import (
    count_participants,
    delete_giveaway,
    end_giveaway,
    get_giveaway,
    get_participants,
    update_giveaway,
)
from views._components.text_modal import TextModal
from views.giveaway.create_view import fmt_duration, parse_duration
from views.giveaway.panel_view import build_giveaway_panel

log = logging.getLogger(__name__)

MAX_EXTEND_SECONDS = 30 * 86400  # 30 jours


# ======================================================
# =================== BUILD VIEW =======================
# ======================================================

async def create_manage_view(giveaway_data: dict, guild: discord.Guild,
                             owner_id: int, is_gold_guild: bool) -> LayoutView:
    """Construit la vue de gestion."""
    view = LayoutView(timeout=300)
    container = Container()

    gid = giveaway_data["id"]
    prize = giveaway_data["prize"]
    winners_count = giveaway_data["winners_count"]
    end_time = giveaway_data["end_time"]
    if end_time.tzinfo is None:
        end_time = end_time.replace(tzinfo=timezone.utc)
    ended = giveaway_data["ended"]
    host_id = giveaway_data["host_id"]
    requirements = giveaway_data.get("requirements") or {}
    winners = giveaway_data.get("winners") or []

    nb_participants = await count_participants(gid)
    host = guild.get_member(host_id)
    host_display = host.mention if host else f"`ID {host_id}`"
    status = "🔴 Terminé" if ended else "🟢 En cours"
    end_display = (f"<t:{int(end_time.timestamp())}:f>" if ended
                   else f"<t:{int(end_time.timestamp())}:R>")

    # ── En-tête ───────────────────────────────────────
    container.add_item(TextDisplay(f"# 🛠️ Gestion · `{gid}`"))
    container.add_item(TextDisplay(f"-# {status}"))
    container.add_item(Separator())

    # ── Infos ─────────────────────────────────────────
    info_lines = [
        f"🏆 **Prix :** {prize}",
        f"👥 **Gagnants à tirer :** {winners_count}",
        f"👤 **Participants :** {nb_participants}",
        f"📅 **{'Terminé' if ended else 'Fin'} :** {end_display}",
        f"🎤 **Organisateur :** {host_display}",
    ]
    req_lines = []
    if requirements.get("role_id"):
        req_lines.append(f"  • Rôle requis : <@&{requirements['role_id']}>")
    if requirements.get("forbidden_role_id"):
        req_lines.append(f"  • Rôle interdit : <@&{requirements['forbidden_role_id']}>")
    if requirements.get("min_invites"):
        req_lines.append(f"  • Invitations : {requirements['min_invites']}+")
    if requirements.get("min_server_age_days"):
        req_lines.append(f"  • Ancienneté serveur : {requirements['min_server_age_days']}j+")
    if req_lines:
        info_lines.append("")
        info_lines.append("📋 **Prérequis :**")
        info_lines.extend(req_lines)
    container.add_item(TextDisplay("### 📊 Informations\n" + "\n".join(info_lines)))

    # ── Gagnants (si terminé) ─────────────────────────
    if ended:
        container.add_item(Separator())
        if winners:
            mentions = " ".join(f"<@{w}>" for w in winners)
            container.add_item(TextDisplay(f"### 🏆 Gagnants\n{mentions}"))
        else:
            container.add_item(TextDisplay("### 🏆 Gagnants\n-# 😔 Aucun gagnant — pas assez de participants."))

    container.add_item(Separator())

    # ── Actions ───────────────────────────────────────
    container.add_item(TextDisplay("### ⚙️ Actions"))

    if not ended:
        # Prolonger
        btn_ext = Button(label="Prolonger", style=ButtonStyle.primary, emoji="⏱️")
        btn_ext.callback = _cb_extend(gid, guild, owner_id, is_gold_guild)
        container.add_item(Section(
            TextDisplay("**⏱️ Prolonger le giveaway**\n-# Ajoute du temps à la fin actuelle."),
            accessory=btn_ext,
        ))
        # Terminer
        btn_end = Button(label="Terminer", style=ButtonStyle.danger, emoji="🛑")
        btn_end.callback = _cb_end_now(gid, guild, owner_id, is_gold_guild)
        container.add_item(Section(
            TextDisplay("**🛑 Terminer maintenant**\n-# Tire les gagnants et clôture immédiatement."),
            accessory=btn_end,
        ))
    else:
        # Reroll
        btn_reroll = Button(label="Reroll", style=ButtonStyle.secondary, emoji="🔄")
        btn_reroll.callback = _cb_reroll(gid, guild, owner_id, is_gold_guild)
        container.add_item(Section(
            TextDisplay("**🔄 Reroll les gagnants**\n-# Tire de nouveaux gagnants parmi les participants."),
            accessory=btn_reroll,
        ))

    # Voir participants (Gold+)
    btn_parts = Button(label="Participants", style=ButtonStyle.secondary, emoji="👥")
    btn_parts.callback = _cb_view_participants(gid, guild, owner_id, is_gold_guild)
    container.add_item(Section(
        TextDisplay("**👥 Voir les participants** *(Gold+)*\n-# Liste complète des inscrits."),
        accessory=btn_parts,
    ))

    container.add_item(Separator())

    # Supprimer
    btn_del = Button(label="Supprimer", style=ButtonStyle.danger, emoji="🗑️")
    btn_del.callback = _cb_delete(gid, guild, owner_id, is_gold_guild)
    container.add_item(Section(
        TextDisplay("**🗑️ Supprimer le giveaway**\n-# Supprime définitivement ce giveaway et son message."),
        accessory=btn_del,
    ))

    container.add_item(Separator())
    container.add_item(TextDisplay("-# GuideOn Studio"))

    view.add_item(container)
    return view


# ======================================================
# ===================== HELPERS ========================
# ======================================================

def _guard(owner_id: int):
    async def check(interaction: Interaction) -> bool:
        if interaction.user.id != owner_id:
            await interaction.response.send_message(
                view=error_container("Seul l'**auteur** peut utiliser ce menu."),
                ephemeral=True,
            )
            return False
        return True
    return check


async def _rerender_root(interaction: Interaction, gid: str, guild: discord.Guild,
                        owner_id: int, is_gold_guild: bool):
    """Recharge les données et réaffiche la vue principale (edit du message)."""
    fresh = await get_giveaway(gid)
    if fresh is None:
        return
    new_view = await create_manage_view(fresh, guild, owner_id, is_gold_guild)
    try:
        await interaction.edit_original_response(view=new_view)
    except (discord.NotFound, discord.HTTPException):
        log.warning("[Giveaway] Re-render manage impossible (msg supprimé ?)")


async def _refresh_public_panel(gid: str, guild: discord.Guild):
    """Met à jour le message public du giveaway."""
    data = await get_giveaway(gid)
    if data is None or data.get("message_id") is None:
        return
    channel = guild.get_channel(data["channel_id"])
    if channel is None:
        return
    try:
        msg = await channel.fetch_message(data["message_id"])
        nb = await count_participants(gid)
        data["participants_count"] = nb
        await msg.edit(view=build_giveaway_panel(data, guild))
    except (discord.NotFound, discord.Forbidden, discord.HTTPException):
        pass


# ======================================================
# ===================== CALLBACKS ======================
# ======================================================

def _cb_extend(gid, guild, owner_id, is_gold_guild):
    check = _guard(owner_id)
    async def cb(interaction: Interaction):
        if not await check(interaction):
            return
        # Vérif état frais
        data = await get_giveaway(gid)
        if data is None or data["ended"]:
            await interaction.response.send_message(
                view=error_container("Giveaway introuvable ou déjà terminé."),
                ephemeral=True,
            )
            return

        async def on_submit(inter: Interaction, value: str):
            secs = parse_duration(value)
            if secs <= 0:
                await inter.response.send_message(
                    view=error_container("Format invalide. Ex : `1h`, `30m`, `2d`."),
                    ephemeral=True,
                )
                return
            if secs > MAX_EXTEND_SECONDS:
                await inter.response.send_message(
                    view=error_container("Maximum **30 jours** d'extension à la fois."),
                    ephemeral=True,
                )
                return
            fresh = await get_giveaway(gid)
            if fresh is None or fresh["ended"]:
                await inter.response.send_message(
                    view=error_container("Giveaway introuvable ou déjà terminé."),
                    ephemeral=True,
                )
                return
            new_end = fresh["end_time"] + timedelta(seconds=secs)
            await update_giveaway(gid, end_time=new_end)
            await _refresh_public_panel(gid, guild)
            await inter.response.send_message(
                view=success_container(f"Giveaway prolongé de **{fmt_duration(secs)}**."),
                ephemeral=True,
            )
            await _rerender_root(inter, gid, guild, owner_id, is_gold_guild)

        modal = TextModal(
            title="⏱️ Prolonger le giveaway",
            label="Durée à ajouter (ex: 1h, 30m)",
            placeholder="1h, 30m, 2d…",
            default="1h",
            min_length=2, max_length=20,
            style=discord.TextStyle.short,
            on_submit=on_submit,
        )
        await interaction.response.send_modal(modal)
    return cb


def _cb_end_now(gid, guild, owner_id, is_gold_guild):
    check = _guard(owner_id)
    async def cb(interaction: Interaction):
        if not await check(interaction):
            return

        async def on_submit(inter: Interaction, value: str):
            if value.strip().upper() != "TERMINER":
                await inter.response.send_message(
                    view=error_container("Confirmation invalide. Tape `TERMINER` exactement."),
                    ephemeral=True,
                )
                return
            await inter.response.defer(ephemeral=True)
            fresh = await get_giveaway(gid)
            if fresh is None or fresh["ended"]:
                await inter.followup.send(
                    view=error_container("Giveaway déjà terminé ou introuvable."),
                    ephemeral=True,
                )
                return
            # Tirage
            participants = await get_participants(gid)
            wc = fresh["winners_count"]
            if not participants:
                winners = []
            elif len(participants) <= wc:
                winners = list(participants)
            else:
                winners = random.sample(participants, wc)
            await end_giveaway(gid, winners)
            await _refresh_public_panel(gid, guild)
            await inter.followup.send(
                view=success_container(
                    f"Giveaway **terminé**. {len(winners)} gagnant(s) tiré(s)."
                ),
                ephemeral=True,
            )
            await _rerender_root(inter, gid, guild, owner_id, is_gold_guild)

        modal = TextModal(
            title="🛑 Terminer le giveaway",
            label="Tape TERMINER pour confirmer",
            placeholder="TERMINER",
            default="",
            min_length=1, max_length=10,
            style=discord.TextStyle.short,
            on_submit=on_submit,
        )
        await interaction.response.send_modal(modal)
    return cb


def _cb_reroll(gid, guild, owner_id, is_gold_guild):
    check = _guard(owner_id)
    async def cb(interaction: Interaction):
        if not await check(interaction):
            return
        await interaction.response.defer(ephemeral=True)
        fresh = await get_giveaway(gid)
        if fresh is None:
            await interaction.followup.send(
                view=error_container("Giveaway introuvable."),
                ephemeral=True,
            )
            return
        participants = await get_participants(gid)
        if not participants:
            await interaction.followup.send(
                view=error_container("Aucun participant — reroll impossible."),
                ephemeral=True,
            )
            return
        wc = fresh["winners_count"]
        new_winners = (list(participants) if len(participants) <= wc
                       else random.sample(participants, wc))
        await update_giveaway(gid, winners=new_winners)

        # Annonce publique
        channel = guild.get_channel(fresh["channel_id"])
        if channel is not None:
            mentions = " ".join(f"<@{w}>" for w in new_winners)
            try:
                container = Container()
                container.add_item(TextDisplay(f"# 🔄 Reroll — Nouveaux gagnants !"))
                container.add_item(Separator())
                container.add_item(TextDisplay(
                    f"Pour **{fresh['prize']}** :\n{mentions}"
                ))
                container.add_item(Separator())
                container.add_item(TextDisplay(f"-# ID `{gid}` · GuideOn Studio"))
                public_view = LayoutView(timeout=None)
                public_view.add_item(container)
                await channel.send(
                    view=public_view,
                    allowed_mentions=discord.AllowedMentions(users=True),
                )
            except discord.HTTPException:
                log.warning("[Giveaway] Échec envoi annonce reroll")

        await _refresh_public_panel(gid, guild)
        await interaction.followup.send(
            view=success_container(f"Reroll effectué : {len(new_winners)} nouveau(x) gagnant(s)."),
            ephemeral=True,
        )
        await _rerender_root(interaction, gid, guild, owner_id, is_gold_guild)
    return cb


def _cb_view_participants(gid, guild, owner_id, is_gold_guild):
    check = _guard(owner_id)
    async def cb(interaction: Interaction):
        if not await check(interaction):
            return
        if not is_gold_guild:
            from utils.boutique.gold_manager import send_gold_error
            await send_gold_error(interaction)
            return
        await interaction.response.defer(ephemeral=True)
        participants = await get_participants(gid)
        if not participants:
            await interaction.followup.send(
                view=info_container("Aucun participant pour l'instant."),
                ephemeral=True,
            )
            return
        # Affichage paginé simple : on liste tout dans un container
        lines = [f"-# 👤 <@{uid}>" for uid in participants]
        # Trim si trop long (Discord limite à ~4000 chars sur un TextDisplay)
        text = "\n".join(lines)
        if len(text) > 3500:
            text = "\n".join(lines[:150]) + f"\n-# *...et {len(lines) - 150} autre(s)*"

        view = LayoutView(timeout=300)
        c = Container()
        c.add_item(TextDisplay(f"# 👥 Participants · `{gid}`"))
        c.add_item(TextDisplay(f"-# Total : **{len(participants)}**"))
        c.add_item(Separator())
        c.add_item(TextDisplay(text))
        c.add_item(Separator())
        c.add_item(TextDisplay("-# GuideOn Studio · ✨ Gold+"))
        view.add_item(c)
        await interaction.followup.send(view=view, ephemeral=True)
    return cb


def _cb_delete(gid, guild, owner_id, is_gold_guild):
    check = _guard(owner_id)
    async def cb(interaction: Interaction):
        if not await check(interaction):
            return

        async def on_submit(inter: Interaction, value: str):
            if value.strip().upper() != "SUPPRIMER":
                await inter.response.send_message(
                    view=error_container("Confirmation invalide. Tape `SUPPRIMER` exactement."),
                    ephemeral=True,
                )
                return
            await inter.response.defer(ephemeral=True)
            data = await get_giveaway(gid)
            if data is not None:
                # Supprimer le message public
                ch = guild.get_channel(data["channel_id"])
                if ch is not None and data.get("message_id"):
                    try:
                        msg = await ch.fetch_message(data["message_id"])
                        await msg.delete()
                    except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                        pass
                await delete_giveaway(gid)
            await inter.followup.send(
                view=success_container(f"Giveaway `{gid}` supprimé."),
                ephemeral=True,
            )
            # Supprimer le panel manage aussi
            try:
                await inter.delete_original_response()
            except (discord.NotFound, discord.HTTPException):
                pass

        modal = TextModal(
            title="🗑️ Supprimer le giveaway",
            label="Tape SUPPRIMER pour confirmer",
            placeholder="SUPPRIMER",
            default="",
            min_length=1, max_length=10,
            style=discord.TextStyle.short,
            on_submit=on_submit,
        )
        await interaction.response.send_modal(modal)
    return cb


# ======================================================
# ========= COMPAT COMMANDE : GiveawayManageView =======
# ======================================================

class GiveawayManageView:
    @classmethod
    async def create(cls, giveaway_data: dict, guild: discord.Guild,
                     owner_id: int, is_gold_guild: bool) -> LayoutView:
        return await create_manage_view(giveaway_data, guild, owner_id, is_gold_guild)