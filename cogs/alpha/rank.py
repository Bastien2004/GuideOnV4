"""
cogs/alpha/rank.py — Commande /alpha rank

Logique journaliste :
  - grade == "journaliste" → attribue le statut journaliste (cumulable avec grade de modération,
    sauf super_moderateur et administrateur)
  - autre grade           → attribue le grade de modération (préserve le statut journaliste,
    le retire automatiquement si incompatible avec SM/Admin)
"""
from __future__ import annotations

import logging

import discord
from discord import app_commands, Interaction
from discord.ui import Container, LayoutView, Separator, TextDisplay

from utils.botbancmd import verifier_ban_utilisateur
from utils.control_admin import verifier_commande
from utils.track_commande import tracker_commande
from utils.container_universel import success_container, warning_container
from utils.error_handler import handle_app_command_error
from utils.perm_alpha import check_op_alpha
from utils.managers.alpha_staff_manager import get_staff_member, upsert_staff_member, update_staff_member
from utils.managers.alpha_rank_config_manager import load_rank_config
from utils.db.models.alpha_staff import (
    GRADES_ORDER, GRADE_LABELS, GRADE_PREFIXES, GRADE_TO_ROLE_ATTR,
    JOURNALISTE_INCOMPATIBLE_GRADES,
)

log = logging.getLogger(__name__)

GRADE_CHOICES = [
    app_commands.Choice(name=GRADE_LABELS[g], value=g)
    for g in GRADES_ORDER
]


# ── Helpers ────────────────────────────────────────────────

async def _fetch_channel(bot: discord.Client, channel_id: int):
    try:
        return await bot.fetch_channel(channel_id)
    except (discord.NotFound, discord.HTTPException):
        return None


async def _send_with_reaction(
    bot: discord.Client,
    channel_id: int | None,
    view: LayoutView,
    emoji: str | None,
) -> None:
    """Envoie une view dans un salon et ajoute une réaction si configurée."""
    if not channel_id:
        return
    channel = bot.get_channel(channel_id) or await _fetch_channel(bot, channel_id)
    if channel is None:
        return
    try:
        sent = await channel.send(view=view)
        if emoji:
            try:
                await sent.add_reaction(emoji)
            except discord.HTTPException:
                pass
    except discord.HTTPException:
        log.warning("[RANK ALPHA] Impossible d'envoyer dans le salon %d", channel_id)


async def _send_to_channel(bot: discord.Client, channel_id: int | None, view: LayoutView) -> None:
    if not channel_id:
        return
    channel = bot.get_channel(channel_id) or await _fetch_channel(bot, channel_id)
    if channel is None:
        return
    try:
        await channel.send(view=view)
    except discord.HTTPException:
        log.warning("[RANK ALPHA] Impossible d'envoyer dans le salon %d", channel_id)


def _build_rank_announcement(
    membre: discord.Member,
    pseudo_jeu: str,
    grade: str,
    is_promotion: bool,
    old_grade: str | None,
    journaliste_only: bool = False,
) -> LayoutView:
    label = GRADE_LABELS.get(grade, grade)
    old_label = GRADE_LABELS.get(old_grade, old_grade) if old_grade else None

    view = LayoutView(timeout=None)
    c = Container()

    if journaliste_only and old_grade and old_grade != "journaliste":
        # Attribution journaliste sur un grade existant
        c.add_item(TextDisplay(
            f"<:Alpha:1500414179650048070> <@{membre.id}> (**{old_label}**) "
            f"rejoint également l'équipe des **Journalistes** ! 📰"
        ))
    elif is_promotion and old_label:
        c.add_item(TextDisplay(
            f"<:Alpha:1500414179650048070> Félicitations à <@{membre.id}> qui passe "
            f"de **{old_label}** à **{label}** !"
        ))
    else:
        c.add_item(TextDisplay(
            f"<:Alpha:1500414179650048070> Bienvenue à <@{membre.id}> qui rejoint "
            f"le staff en tant que **{label}** !"
        ))

    view.add_item(c)
    return view


def _build_journaliste_message(
    pseudo_jeu: str,
    grade: str,
    journaliste_ping_id: int | None,
    is_promotion: bool,
) -> LayoutView:
    label = GRADE_LABELS.get(grade, grade)
    ping = f"<@&{journaliste_ping_id}> " if journaliste_ping_id else ""
    action = "promu" if is_promotion else "ranké"

    view = LayoutView(timeout=None)
    c = Container()
    c.add_item(TextDisplay("# 📸 Affiche de rank"))
    c.add_item(Separator())
    c.add_item(TextDisplay(
        f"{ping}**{pseudo_jeu}** a été **{action}** **{label}** !\n"
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
@app_commands.describe(
    membre="Membre Discord à rank-up",
    pseudo_jeu="Pseudo Minecraft du membre",
    grade="Grade à attribuer (journaliste = statut cumulable)",
)
@app_commands.choices(grade=GRADE_CHOICES)
async def rank(
    interaction: Interaction,
    membre: discord.Member,
    pseudo_jeu: str,
    grade: app_commands.Choice[str],
) -> None:

    if not await verifier_ban_utilisateur(interaction):
        return
    if not await check_op_alpha(interaction, "**effectuer un rank-up**"):
        return

    try:
        await interaction.response.defer(ephemeral=True)
    except (discord.NotFound, discord.HTTPException):
        return

    if not await verifier_commande(interaction, "alpha_rank"):
        return
    await tracker_commande(interaction, "alpha_rank")

    cfg = await load_rank_config(interaction.guild_id)
    existing = await get_staff_member(membre.id)
    pseudo = pseudo_jeu.strip()

    # ════════════════════════════════════════════════════════
    # BRANCHE A — Attribution du statut Journaliste
    # ════════════════════════════════════════════════════════
    if grade.value == "journaliste":

        if existing:
            current_grade = existing["grade"]

            # Incompatibilité SM/Admin
            if current_grade in JOURNALISTE_INCOMPATIBLE_GRADES:
                label_cur = GRADE_LABELS.get(current_grade, current_grade)
                return await interaction.followup.send(
                    view=warning_container(
                        f"**{existing['pseudo_jeu']}** est **{label_cur}** : "
                        f"ce grade est incompatible avec le rôle Journaliste."
                    ),
                    ephemeral=True,
                )

            if existing["is_journaliste"]:
                return await interaction.followup.send(
                    view=warning_container(
                        f"**{existing['pseudo_jeu']}** est déjà **Journaliste**."
                    ),
                    ephemeral=True,
                )

            # Ajout du statut journaliste sur un grade existant
            await update_staff_member(membre.id, pseudo_jeu=pseudo, is_journaliste=True)
            is_new_staff = False
            journaliste_only = True      # pour le message d'annonce
            display_grade = current_grade
        else:
            # Nouveau pur journaliste
            await upsert_staff_member(membre.id, pseudo, "journaliste", is_journaliste=True)
            is_new_staff = True
            journaliste_only = False
            display_grade = "journaliste"

        # Rôle Discord journaliste
        try:
            journ_role_id = cfg.get(GRADE_TO_ROLE_ATTR["journaliste"])
            if journ_role_id:
                journ_role = interaction.guild.get_role(journ_role_id)
                if journ_role and journ_role not in membre.roles:
                    await membre.add_roles(journ_role, reason="Rank Alpha : Journaliste")
        except (discord.Forbidden, discord.HTTPException):
            log.warning("[RANK ALPHA] Impossible d'ajouter le rôle journaliste à %s", membre.id)

        # Rename uniquement si pur journaliste (existant garde son prefix de grade)
        new_nick = None
        if not existing or existing["grade"] == "journaliste":
            new_nick = f"Journaliste | {pseudo}"
            try:
                await membre.edit(nick=new_nick, reason="Rank Alpha : Journaliste")
            except (discord.Forbidden, discord.HTTPException):
                log.warning("[RANK ALPHA] Impossible de renommer %s", membre.id)

        # Messages
        old_grade_for_msg = existing["grade"] if existing else None
        await _send_with_reaction(
            interaction.client,
            cfg.get("rank_channel_id"),
            _build_rank_announcement(membre, pseudo, display_grade, bool(existing), old_grade_for_msg, journaliste_only),
            cfg.get("rank_emoji"),
        )
        await _send_to_channel(
            interaction.client,
            cfg.get("journaliste_channel_id"),
            _build_journaliste_message(pseudo, display_grade, cfg.get("journaliste_ping_id"), bool(existing)),
        )
        if is_new_staff:
            await _send_to_channel(
                interaction.client,
                cfg.get("dev_channel_id"),
                _build_dev_message(pseudo, cfg.get("dev_ping_id")),
            )

    # ════════════════════════════════════════════════════════
    # BRANCHE B — Attribution d'un grade de modération
    # ════════════════════════════════════════════════════════
    else:
        is_promotion = existing is not None
        old_grade = existing["grade"] if existing else None
        # Préserve le statut journaliste sauf si incompatible
        keep_journaliste = existing.get("is_journaliste", False) if existing else False
        journaliste_stripped = False

        if keep_journaliste and grade.value in JOURNALISTE_INCOMPATIBLE_GRADES:
            keep_journaliste = False
            journaliste_stripped = True

        await upsert_staff_member(membre.id, pseudo, grade.value, is_journaliste=keep_journaliste)

        # Rôles Discord
        try:
            # Retirer l'ancien grade (si différent)
            if is_promotion and old_grade and old_grade != grade.value and old_grade != "journaliste":
                old_role_id = cfg.get(GRADE_TO_ROLE_ATTR.get(old_grade, ""))
                if old_role_id:
                    old_role = interaction.guild.get_role(old_role_id)
                    if old_role and old_role in membre.roles:
                        await membre.remove_roles(old_role, reason=f"Rank Alpha → {GRADE_LABELS[grade.value]}")

            # Retirer le rôle journaliste si incompatible
            if journaliste_stripped:
                journ_role_id = cfg.get(GRADE_TO_ROLE_ATTR["journaliste"])
                if journ_role_id:
                    journ_role = interaction.guild.get_role(journ_role_id)
                    if journ_role and journ_role in membre.roles:
                        await membre.remove_roles(journ_role, reason="Rank Alpha : SM/Admin incompatible avec Journaliste")

            # Ajouter le nouveau grade
            new_role_id = cfg.get(GRADE_TO_ROLE_ATTR.get(grade.value, ""))
            if new_role_id:
                new_role = interaction.guild.get_role(new_role_id)
                if new_role and new_role not in membre.roles:
                    await membre.add_roles(new_role, reason=f"Rank Alpha : {GRADE_LABELS[grade.value]}")

        except (discord.Forbidden, discord.HTTPException) as e:
            log.warning("[RANK ALPHA] Erreur rôles %s : %s", membre.id, e)

        # Rename
        prefix = GRADE_PREFIXES.get(grade.value, grade.value)
        new_nick = f"{prefix} | {pseudo}"
        try:
            await membre.edit(nick=new_nick, reason=f"Rank Alpha : {GRADE_LABELS[grade.value]}")
        except (discord.Forbidden, discord.HTTPException):
            log.warning("[RANK ALPHA] Impossible de renommer %s", membre.id)

        # Messages
        await _send_with_reaction(
            interaction.client,
            cfg.get("rank_channel_id"),
            _build_rank_announcement(membre, pseudo, grade.value, is_promotion, old_grade),
            cfg.get("rank_emoji"),
        )
        await _send_to_channel(
            interaction.client,
            cfg.get("journaliste_channel_id"),
            _build_journaliste_message(pseudo, grade.value, cfg.get("journaliste_ping_id"), is_promotion),
        )
        if not is_promotion:
            await _send_to_channel(
                interaction.client,
                cfg.get("dev_channel_id"),
                _build_dev_message(pseudo, cfg.get("dev_ping_id")),
            )

    # Refresh stafflist
    from cogs.alpha.stafflist import refresh_staff_message
    await refresh_staff_message(interaction.client, interaction.guild_id)

    # Confirmation
    label = GRADE_LABELS.get(grade.value, grade.value)
    extra = "\n⚠️ Statut Journaliste retiré (incompatible avec ce grade)." if (grade.value != "journaliste" and 'journaliste_stripped' in dir() and journaliste_stripped) else ""
    nick_line = f"\n• Pseudo renommé : `{new_nick}`" if new_nick else ""
    await interaction.followup.send(
        view=success_container(
            f"**{pseudo}** (<@{membre.id}>) → **{label}** ✅\n"
            f"• Rôle(s) Discord mis à jour"
            f"{nick_line}\n"
            f"• Messages envoyés\n"
            f"• Liste staff rafraîchie"
            f"{extra}"
        ),
        ephemeral=True,
    )


@rank.error
async def rank_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    await handle_app_command_error(interaction, error)