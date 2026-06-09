"""
cogs/alpha/rank.py — Gestion d'un rank-up du staff Alpha
"""

from __future__ import annotations

import logging

import discord
from discord import app_commands, Interaction
from discord.ui import Container, LayoutView, Separator, TextDisplay

from utils.botbancmd import verifier_ban_utilisateur
from utils.control_admin import verifier_commande
from utils.track_commande import tracker_commande

from utils.container_universel import success_container
from utils.error_handler import handle_app_command_error
from utils.perm_alpha import check_op_alpha

from utils.managers.alpha_staff_manager import get_staff_member, upsert_staff_member
from utils.managers.alpha_rank_config_manager import load_rank_config
from utils.db.models.alpha_staff import GRADES_ORDER, GRADE_LABELS, GRADE_PREFIXES, GRADE_TO_ROLE_ATTR

log = logging.getLogger(__name__)


# ============================================================
#  📁 Fonctions utilitaires
# ============================================================

GRADE_CHOICES = [
    app_commands.Choice(name=GRADE_LABELS[g], value=g)
    for g in GRADES_ORDER
]


async def _send_to_channel(bot: discord.Client, channel_id: int | None, view: LayoutView) -> bool:
    """Envoie une view dans un salon donné."""

    if not channel_id:
        return False
    channel = bot.get_channel(channel_id) or await _fetch_channel(bot, channel_id)
    if channel is None:
        return False
    try:
        await channel.send(view=view)
        return True
    except discord.HTTPException:
        log.warning("[RANK ALPHA] Impossible d'envoyer dans le salon %d", channel_id)
        return False


async def _fetch_channel(bot: discord.Client, channel_id: int):
    try:
        return await bot.fetch_channel(channel_id)
    except (discord.NotFound, discord.HTTPException):
        return None


def _build_rank_announcement(membre: discord.Member, pseudo_jeu: str, grade: str, is_promotion: bool, old_grade: str | None) -> LayoutView:
    """Construction du message de rank du salon rank-derank."""

    label = GRADE_LABELS.get(grade, grade)
    old_label = GRADE_LABELS.get(old_grade, old_grade) if old_grade else None

    view = LayoutView(timeout=None)
    c = Container()

    if is_promotion and old_label:
        c.add_item(TextDisplay(f"<:Alpha:1500414179650048070> Félicitations à <@{membre.id}> qui passe de **{old_label}** à **{label}** !"))

    else:
        c.add_item(TextDisplay(f"<:Alpha:1500414179650048070> Bienvenue à <@{membre.id}> qui rejoint le staff en tant que **{label}** !"))

    view.add_item(c)
    return view


def _build_journaliste_message(pseudo_jeu: str, grade: str, journaliste_ping_id: int | None, is_promotion: bool) -> LayoutView:
    label = GRADE_LABELS.get(grade, grade)
    ping = f"<@&{journaliste_ping_id}> " if journaliste_ping_id else ""
    action = "promu" if is_promotion else "rank"

    view = LayoutView(timeout=None)
    c = Container()
    c.add_item(TextDisplay("# 📸 Affiche de rank"))
    c.add_item(Separator())
    c.add_item(TextDisplay(
        f"{ping}* ! *{pseudo_jeu}** a été **{action}** **{label}** !\n"
        f"Merci de lui préparer l'affiche de rank. 🎨"
    ))

    view.add_item(c)
    return view


def _build_dev_message(pseudo_jeu: str, dev_ping_id: int | None) -> LayoutView:
    ping = f"<@&{dev_ping_id}> " if dev_ping_id else ""

    view = LayoutView(timeout=None)
    c = Container()
    c.add_item(TextDisplay("# 🖼️ Emoji head — Nouveau staff"))
    c.add_item(Separator())
    c.add_item(TextDisplay(
        f"{ping}Merci d'ajouter l'**emoji skin head** pour **{pseudo_jeu}** (nouveau staff).\n"
        f"Une fois l'emoji créé, n'oubliez pas de l'ajouter via `/dev edit_list`. 🎭"
    ))

    view.add_item(c)
    return view


# ════════════════════════════════════════════════════════════
# 🧭 Commande : /alpha rank
# ════════════════════════════════════════════════════════════

@app_commands.guild_only()
@app_commands.checks.cooldown(1, 10)
@app_commands.command(name="rank", description="⬆️ [OP] Rank-up un membre du staff Alpha")
@app_commands.describe(membre="Membre Discord à rank-up", pseudo_jeu="Pseudo Minecraft du membre", grade="Nouveau grade attribué")
@app_commands.choices(grade=GRADE_CHOICES)
async def rank(interaction: Interaction, membre: discord.Member, pseudo_jeu: str, grade: app_commands.Choice[str]) -> None:

    # 🛡️ Vérification ban utilisateur.
    if not await verifier_ban_utilisateur(interaction):
        return

    # 🔐 Permission OP Alpha.
    if not await check_op_alpha(interaction, "**effectuer un **rank-up**"):
        return

    # 🕒 Defer.
    try:
        await interaction.response.defer(ephemeral=True)
    except (discord.NotFound, discord.HTTPException):
        return

    # ⚙️ Vérification maintenance.
    if not await verifier_commande(interaction, "alpha_rank"):
        return

    # 📊 Tracking.
    await tracker_commande(interaction, "alpha_rank")

    # 📋 Récupèration de la configuration de rank.
    cfg = await load_rank_config(interaction.guild_id)

    # 🔍 Vérification promotion ou nouveau ?
    existing = await get_staff_member(membre.id)
    is_promotion = existing is not None
    old_grade = existing["grade"] if existing else None

    # ✍️ Mise à jour de la Base de Données.
    await upsert_staff_member(discord_id=membre.id, pseudo_jeu=pseudo_jeu.strip(), grade=grade.value)

    # 🎭 Gestion des rôles Discord
    try:
        # 🗑️ Retirer l'ancien rôle si promotion vers un grade différent
        if is_promotion and old_grade and old_grade != grade.value:
            old_role_id = cfg.get(GRADE_TO_ROLE_ATTR.get(old_grade, ""))
            if old_role_id:
                old_role = interaction.guild.get_role(old_role_id)
                if old_role and old_role in membre.roles:
                    await membre.remove_roles(old_role, reason=f"Rank Alpha : promotion → {GRADE_LABELS[grade.value]}")

        # ➕ Ajouter le nouveau rôle
        new_role_id = cfg.get(GRADE_TO_ROLE_ATTR.get(grade.value, ""))
        if new_role_id:
            new_role = interaction.guild.get_role(new_role_id)
            if new_role and new_role not in membre.roles:
                await membre.add_roles(new_role, reason=f"Rank Alpha : {GRADE_LABELS[grade.value]}")

    except discord.Forbidden:
        log.warning("[RANK ALPHA] Impossible de gérer les rôles pour %s", membre.id)
    except discord.HTTPException as e:
        log.warning("[RANK ALPHA] Erreur HTTP rôles : %s", e)

    # 📛 Rename Discord
    prefix = GRADE_PREFIXES.get(grade.value, grade.value)
    new_nick = f"{prefix} | {pseudo_jeu.strip()}"
    try:
        await membre.edit(nick=new_nick, reason=f"Rank Alpha : {GRADE_LABELS[grade.value]}")
    except (discord.Forbidden, discord.HTTPException):
        log.warning("[RANK ALPHA] Impossible de renommer %s", membre.id)

    # 📢 Envoie message salon rank/derank.
    await _send_to_channel(interaction.client, cfg.get("rank_channel_id"), _build_rank_announcement(membre, pseudo_jeu.strip(), grade.value, is_promotion, old_grade))

    # 📸 Envoie message journalistes.
    await _send_to_channel(
        interaction.client,
        cfg.get("journaliste_channel_id"),
        _build_journaliste_message(
            pseudo_jeu.strip(), grade.value,
            cfg.get("journaliste_ping_id"),
            is_promotion,
        ),
    )

    # 🎨 Envoie message dev pour l'emoji (nouveau staff only).
    if not is_promotion:
        await _send_to_channel(
            interaction.client,
            cfg.get("dev_channel_id"),
            _build_dev_message(pseudo_jeu.strip(), cfg.get("dev_ping_id")),
        )

    # 🔄 Rafraîchissement liste des staffs.
    from cogs.alpha.stafflist import refresh_staff_message
    await refresh_staff_message(interaction.client, interaction.guild_id)

    # ✅ Confirmation du rank-up.
    label = GRADE_LABELS.get(grade.value, grade.value)
    action_txt = "promu" if is_promotion else "ranké"
    await interaction.followup.send(
        view=success_container(
            f"**{pseudo_jeu.strip()}** (<@{membre.id}>) {action_txt} **{label}** avec succès !\n"
            f"• Rôle Discord mis à jour\n"
            f"• Pseudo renommé : `{new_nick}`\n"
            f"• Messages envoyés\n"
            f"• Liste staff rafraîchie"
        ),
        ephemeral=True,
    )


# ============================================================
# ❌ Gestion des erreurs
# ============================================================

@rank.error
async def rank_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    await handle_app_command_error(interaction, error)