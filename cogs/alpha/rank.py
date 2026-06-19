"""
cogs/alpha/rank.py — Gestion des rank staff Alpha.
"""

from __future__ import annotations

import logging

import discord
from discord import app_commands, Interaction
from discord.ui import Container, LayoutView, Separator, TextDisplay

from utils.botbancmd import verifier_ban_utilisateur
from utils.control_admin import verifier_commande
from utils.track_commande import tracker_commande

from utils.container_universel import error_container, success_container, warning_container
from utils.error_handler import handle_app_command_error
from utils.perm_alpha import check_op_alpha

from utils.alpha_rank_logic import apply_staff_roles, compute_nick_prefix, strip_incompatible_statuses

from utils.managers.alpha_staff_manager import get_staff_member, upsert_staff_member, update_staff_member
from utils.managers.alpha_rank_config_manager import load_rank_config

from utils.db.models.alpha_staff import (GRADES_ORDER, GRADE_LABELS, SECONDARY_STATUSES, STATUTS_SECONDAIRES_ORDER, STATUT_INCOMPATIBLE_GRADES)

log = logging.getLogger(__name__)

TYPE_CHOICES = [
    app_commands.Choice(name="Grade (Staff)", value="grade"),
    app_commands.Choice(name="Statut (Journaliste / Affilié / Builder)", value="statut"),
]

GRADE_CHOICES = [
    app_commands.Choice(name=GRADE_LABELS[g], value=g)
    for g in GRADES_ORDER
]

STATUT_CHOICES = [
    app_commands.Choice(name=SECONDARY_STATUSES[s]["label"], value=s)
    for s in STATUTS_SECONDAIRES_ORDER
]

VALEUR_CHOICES = GRADE_CHOICES + STATUT_CHOICES


# ============================================================
# 📁  Fonctions utilitaires — envoi de messages
# ============================================================

async def _fetch_channel(bot: discord.Client, channel_id: int):
    """Récupère un salon par son ID."""
    try:
        return await bot.fetch_channel(channel_id)
    except (discord.NotFound, discord.HTTPException):
        return None


async def _send_with_reaction(bot: discord.Client, channel_id: int | None, view: LayoutView, emoji: str | None) -> None:
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
    """Envoie une view dans un salon sans réaction."""
    if not channel_id:
        return
    channel = bot.get_channel(channel_id) or await _fetch_channel(bot, channel_id)
    if channel is None:
        return
    try:
        await channel.send(view=view)
    except discord.HTTPException:
        log.warning("[RANK ALPHA] Impossible d'envoyer dans le salon %d", channel_id)


# ============================================================
# 📁  Fonctions utilitaires — construction des annonces
# ============================================================

def _build_grade_announcement(membre: discord.Member, grade: str, is_promotion: bool, old_grade: str | None) -> LayoutView:
    """Annonce publique pour un changement de grade (staff)."""

    label = GRADE_LABELS.get(grade, grade)
    old_label = GRADE_LABELS.get(old_grade, old_grade) if old_grade else None

    view = LayoutView(timeout=None)
    c = Container()

    if is_promotion and old_label:
        c.add_item(TextDisplay(
            f"<:Alpha:1500414179650048070> Félicitations à <@{membre.id}> qui passe de **{old_label}** à **{label}** !"
        ))
        
    else:
        c.add_item(TextDisplay(
            f"<:Alpha:1500414179650048070> Bienvenue à <@{membre.id}> qui rejoint l'équipe en tant que **{label}** !"
        ))

    view.add_item(c)
    return view


def _build_statut_announcement(membre: discord.Member, statut: str) -> LayoutView:
    """Annonce publique pour l'attribution d'un statut secondaire (journaliste/affilié/builder)."""
    meta = SECONDARY_STATUSES[statut]
    label = meta["label"]
    badge = meta["badge"] or ""

    view = LayoutView(timeout=None)
    c = Container()
    c.add_item(TextDisplay(
        f"<:Alpha:1500414179650048070> <@{membre.id}> rejoint l'équipe des **{label}** ! {badge}".rstrip()
    ))
    view.add_item(c)
    return view


def _build_journaliste_message(pseudo_jeu: str, label: str, journaliste_ping_id: int | None, is_promotion: bool) -> LayoutView:
    """Message pour les journalistes (affiche de félicitations)."""
    ping = f"<@&{journaliste_ping_id}> " if journaliste_ping_id else ""
    action = "promu" if is_promotion else "rank"

    view = LayoutView(timeout=None)
    c = Container()
    c.add_item(TextDisplay("# 📸 Affiche de rank"))
    c.add_item(Separator())
    c.add_item(TextDisplay(
        f"Hey {ping} ! **{pseudo_jeu}** a été **{action}** **{label}** !\n"
        f"Merci de lui préparer et de poster l'affiche de félicitations. 🎨"
    ))
    view.add_item(c)
    return view


def _build_dev_message(pseudo_jeu: str, dev_ping_id: int | None) -> LayoutView:
    """Message pour les développeurs (emoji head)."""
    ping = f"<@&{dev_ping_id}> " if dev_ping_id else ""
    view = LayoutView(timeout=None)
    c = Container()
    c.add_item(TextDisplay("# 🖼️ Emoji — Nouveau staff"))
    c.add_item(Separator())
    c.add_item(TextDisplay(
        f"Hey {ping} ! Merci d'ajouter l'**emoji head** pour **{pseudo_jeu}** (nouveau staff).\n"
        f"Une fois l'emoji créé sur le DDP, n'oubliez pas de l'ajouter via `/dev edit_list`. 🎭"
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
    pseudo_jeu="Pseudo NationsGlory du membre",
    type="Grade (hiérarchie staff) ou Statut (journaliste/affilié/builder)",
    valeur="Grade ou statut à attribuer (selon le type choisi)",
    pseudo_jeu_builder="Pseudo NationsGlory du compte builder (requis si type=statut, valeur=builder)",
)
@app_commands.choices(type=TYPE_CHOICES, valeur=VALEUR_CHOICES)
async def rank(
    interaction: Interaction,
    membre: discord.Member,
    pseudo_jeu: str,
    type: app_commands.Choice[str],
    valeur: app_commands.Choice[str],
    pseudo_jeu_builder: str | None = None,
) -> None:

    # 🛡️ Vérification ban utilisateur.
    if not await verifier_ban_utilisateur(interaction):
        return

    # 🔐 Vérification Opérateur.
    if not await check_op_alpha(interaction, "**effectuer un rank-up**"):
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

    # 🔎 Cohérence type/valeur — VALEUR_CHOICES est l'union des deux jeux de
    # choix (Discord ne permet pas de choix dynamiques sans autocomplete),
    # donc on doit valider manuellement que `valeur` appartient bien au bon
    # univers pour le `type` demandé.
    if type.value == "grade" and valeur.value not in GRADES_ORDER:
        return await interaction.followup.send(
            view=error_container(
                f"**{valeur.name}** n'est pas un grade valide. "
                f"Avec `type:Grade`, choisis parmi : {', '.join(GRADE_LABELS.values())}."
            ),
            ephemeral=True,
        )
    if type.value == "statut" and valeur.value not in STATUTS_SECONDAIRES_ORDER:
        return await interaction.followup.send(
            view=error_container(
                f"**{valeur.name}** n'est pas un statut valide. "
                f"Avec `type:Statut`, choisis parmi : Journaliste, Affilié, Builder."
            ),
            ephemeral=True,
        )

    cfg = await load_rank_config(interaction.guild_id)
    existing = await get_staff_member(membre.id)
    pseudo = pseudo_jeu.strip()

    # ────────────────────────────────────────────────────────
    # BRANCHE A — type=grade : changement de la hiérarchie staff
    # ────────────────────────────────────────────────────────
    if type.value == "grade":
        new_grade = valeur.value
        old_grade = existing["grade"] if existing else None
        is_promotion = existing is not None

        current_secondary = {
            key: existing.get(f"is_{key}", False) for key in STATUTS_SECONDAIRES_ORDER
        } if existing else {key: False for key in STATUTS_SECONDAIRES_ORDER}

        target_secondary = strip_incompatible_statuses(new_grade, current_secondary)
        statuses_stripped = new_grade in STATUT_INCOMPATIBLE_GRADES and any(current_secondary.values())

        await upsert_staff_member(
            membre.id, pseudo, new_grade,
            is_journaliste=target_secondary["journaliste"],
            is_affilie=target_secondary["affilie"],
            is_builder=target_secondary["builder"],
        )

        await apply_staff_roles(
            membre, cfg,
            grade=new_grade,
            secondary=target_secondary,
            reason=f"Rank Alpha : {GRADE_LABELS[new_grade]}",
        )

        prefix = compute_nick_prefix(new_grade, target_secondary)
        new_nick = f"{prefix} | {pseudo}" if prefix else pseudo
        try:
            await membre.edit(nick=new_nick, reason=f"Rank Alpha : {GRADE_LABELS[new_grade]}")
        except (discord.Forbidden, discord.HTTPException):
            log.warning("[RANK ALPHA] Impossible de renommer %s", membre.id)
            new_nick = None

        await _send_with_reaction(
            interaction.client,
            cfg.get("rank_channel_id"),
            _build_grade_announcement(membre, new_grade, is_promotion, old_grade),
            cfg.get("rank_emoji"),
        )

        await _send_to_channel(
            interaction.client,
            cfg.get("journaliste_channel_id"),
            _build_journaliste_message(pseudo, GRADE_LABELS[new_grade], cfg.get("journaliste_ping_id"), is_promotion),
        )

        if not is_promotion:
            await _send_to_channel(
                interaction.client,
                cfg.get("dev_channel_id"),
                _build_dev_message(pseudo, cfg.get("dev_ping_id")),
            )

        label = GRADE_LABELS[new_grade]
        extra = (
            "\n⚠️ Statut(s) Journaliste/Affilié/Builder retiré(s) (incompatible avec ce grade)."
            if statuses_stripped else ""
        )
        nick_line = f"\n• Pseudo renommé : `{new_nick}`" if new_nick else ""

        # 📋 Mise à jour de la liste staff (commune aux deux branches)
        from cogs.alpha.stafflist import refresh_staff_message
        await refresh_staff_message(interaction.client, interaction.guild_id)

        return await interaction.followup.send(
            view=success_container(
                f"**{pseudo}** (<@{membre.id}>) → **{label}** ✅\n"
                f"• Rôle(s) Discord mis à jour"
                f"{nick_line}\n"
                f"• Liste staff mise à jour"
                f"{extra}"
            ),
            ephemeral=True,
        )

    # ────────────────────────────────────────────────────────
    # BRANCHE B — type=statut : statut secondaire cumulable
    # ────────────────────────────────────────────────────────
    statut = valeur.value
    meta = SECONDARY_STATUSES[statut]
    current_grade = existing["grade"] if existing else None

    # ❌ Incompatibilité Admin/SM — refus net, pas de retrait automatique
    # (ce sens-là n'a jamais été demandé : seul grade→Admin/SM strip les
    # statuts, jamais l'inverse).
    if current_grade in STATUT_INCOMPATIBLE_GRADES:
        return await interaction.followup.send(
            view=warning_container(
                f"**{existing['pseudo_jeu']}** est **{GRADE_LABELS.get(current_grade, current_grade)}** : "
                f"ce grade est incompatible avec le statut **{meta['label']}**."
            ),
            ephemeral=True,
        )

    if existing and existing.get(f"is_{statut}", False):
        return await interaction.followup.send(
            view=warning_container(f"**{existing['pseudo_jeu']}** est déjà **{meta['label']}**."),
            ephemeral=True,
        )

    # 🧱 Builder : pseudo_jeu_builder obligatoire
    builder_pseudo_clean: str | None = None
    if statut == "builder":
        if not pseudo_jeu_builder or not pseudo_jeu_builder.strip():
            return await interaction.followup.send(
                view=error_container(
                    "Le paramètre `pseudo_jeu_builder` est **obligatoire** pour attribuer le statut Builder "
                    "(c'est le pseudo du second compte Minecraft dédié au build)."
                ),
                ephemeral=True,
            )
        builder_pseudo_clean = pseudo_jeu_builder.strip()

    update_kwargs: dict = {f"is_{statut}": True}
    if statut == "builder":
        update_kwargs["pseudo_jeu_builder"] = builder_pseudo_clean

    if existing:
        await update_staff_member(membre.id, **update_kwargs)
        target_secondary = {
            key: existing.get(f"is_{key}", False) for key in STATUTS_SECONDAIRES_ORDER
        }
        target_secondary[statut] = True
    else:
        # Statut "pur" — pas de grade existant.
        await upsert_staff_member(
            membre.id, pseudo, None,
            is_journaliste=(statut == "journaliste"),
            is_affilie=(statut == "affilie"),
            is_builder=(statut == "builder"),
            pseudo_jeu_builder=builder_pseudo_clean if statut == "builder" else None,
        )
        target_secondary = {key: False for key in STATUTS_SECONDAIRES_ORDER}
        target_secondary[statut] = True

    await apply_staff_roles(
        membre, cfg,
        grade=current_grade,
        secondary=target_secondary,
        reason=f"Rank Alpha : {meta['label']}",
    )

    # Le grade prime toujours sur le pseudo (s'il y en a un, le pseudo n'est
    # jamais retouché ici). Sans grade, le préfixe suit la priorité
    # Affilié > Journaliste > Builder — recalculée sur l'état COMPLET des
    # statuts (pas seulement celui qu'on vient d'activer), pour rester
    # correct en cas de cumul.
    new_nick = None
    if current_grade is None:
        prefix = compute_nick_prefix(None, target_secondary)
        new_nick = f"{prefix} | {pseudo}" if prefix else pseudo
        try:
            await membre.edit(nick=new_nick, reason=f"Rank Alpha : {meta['label']}")
        except (discord.Forbidden, discord.HTTPException):
            log.warning("[RANK ALPHA] Impossible de renommer %s", membre.id)
            new_nick = None

    await _send_with_reaction(
        interaction.client,
        cfg.get("rank_channel_id"),
        _build_statut_announcement(membre, statut),
        cfg.get("rank_emoji"),
    )

    if statut == "journaliste":
        await _send_to_channel(
            interaction.client,
            cfg.get("journaliste_channel_id"),
            _build_journaliste_message(pseudo, meta["label"], cfg.get("journaliste_ping_id"), existing is not None),
        )

    if not existing:
        await _send_to_channel(
            interaction.client,
            cfg.get("dev_channel_id"),
            _build_dev_message(pseudo, cfg.get("dev_ping_id")),
        )

    nick_line = f"\n• Pseudo renommé : `{new_nick}`" if new_nick else ""
    builder_line = f"\n• Pseudo builder : `{builder_pseudo_clean}`" if builder_pseudo_clean else ""

    # 📋 Mise à jour de la liste staff (commune aux deux branches)
    from cogs.alpha.stafflist import refresh_staff_message
    await refresh_staff_message(interaction.client, interaction.guild_id)

    await interaction.followup.send(
        view=success_container(
            f"**{pseudo}** (<@{membre.id}>) → **{meta['label']}** ✅\n"
            f"• Rôle(s) Discord mis à jour"
            f"{nick_line}"
            f"{builder_line}\n"
            f"• Liste staff mise à jour"
        ),
        ephemeral=True,
    )


# ============================================================
# ❌ Gestion des erreurs
# ============================================================

@rank.error
async def rank_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    await handle_app_command_error(interaction, error)