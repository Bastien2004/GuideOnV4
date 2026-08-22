"""
utils/ng_rank_logic.py — Logique centralisée de la gestion du rank/derank.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import discord

from utils.settings import settings
from utils.db.models.staff_grades import GRADE_LABELS, GRADE_PREFIXES, GRADE_TO_ROLE_ATTR, STAFF_GENERAL_GRADES, STATUT_INCOMPATIBLE_GRADES
from utils.managers.ng_staff_manager import update_staff_member, upsert_staff_member
from utils.managers.ng_statut_manager import get_statut_def, grant_statut, list_statut_defs, revoke_statut
from utils.ng_server_display import get_server_display_name
from views.ngstaff.rank_view import (build_dev_message, build_grade_announcement, build_journaliste_message, build_statut_announcement)

log = logging.getLogger(__name__)


# ============================================================
# 🎭 Rôles Discord — attribution/retrait
# ============================================================

def compute_nick_prefix(grade: str | None, secondary: dict[str, bool], statut_defs: list[dict] | None = None) -> str | None:
    """Détermine le préfixe de rename de pseudo Discord ("Guide", "Journaliste"...)."""
    if grade:
        return GRADE_PREFIXES.get(grade, grade)

    for d in statut_defs or []:
        if secondary.get(d["key"]):
            return d["label"]

    return None


def strip_incompatible_statuses(grade: str | None, secondary: dict[str, bool]) -> dict[str, bool]:
    """Vérification de compatibilité."""

    if grade not in STATUT_INCOMPATIBLE_GRADES:
        return dict(secondary)
    return {key: False for key in secondary}


def _all_managed_role_ids(cfg: dict, statut_defs: list[dict] | None = None) -> set[int]:
    """Récupère tous les IDs de rôle géré."""

    ids: set[int] = set()

    for grade in GRADE_TO_ROLE_ATTR:
        rid = cfg.get(GRADE_TO_ROLE_ATTR[grade])
        if rid:
            ids.add(rid)

    rid = cfg.get("role_equipe_id")
    if rid:
        ids.add(rid)

    for d in statut_defs or []:
        if d.get("role_id"):
            ids.add(d["role_id"])

    return ids


def _target_role_ids(cfg: dict, grade: str | None, secondary: dict[str, bool], statut_defs: list[dict] | None = None) -> set[int]:
    """Récupération du/des rôle(s) à distribuer."""

    ids: set[int] = set()

    if grade in GRADE_TO_ROLE_ATTR:
        rid = cfg.get(GRADE_TO_ROLE_ATTR[grade])
        if rid:
            ids.add(rid)

        if grade in STAFF_GENERAL_GRADES:
            rid = cfg.get("role_equipe_id")
            if rid:
                ids.add(rid)

    effective_secondary = strip_incompatible_statuses(grade, secondary)

    for d in statut_defs or []:
        if effective_secondary.get(d["key"]) and d.get("role_id"):
            ids.add(d["role_id"])

    return ids


async def apply_staff_roles(membre: discord.Member, cfg: dict, *, grade: str | None, secondary: dict[str, bool] | None = None, statut_defs: list[dict] | None = None, reason: str = "GuideOn NGSTAFF") -> None:
    """Applique le don ou le retrait de rôle."""

    secondary = secondary or {}

    target_ids = _target_role_ids(cfg, grade, secondary, statut_defs)
    managed_ids = _all_managed_role_ids(cfg, statut_defs)
    current_ids = {r.id for r in membre.roles}

    to_add_ids = target_ids - current_ids
    to_remove_ids = (managed_ids - target_ids) & current_ids

    guild = membre.guild
    to_add = [r for rid in to_add_ids if (r := guild.get_role(rid)) is not None]
    to_remove = [r for rid in to_remove_ids if (r := guild.get_role(rid)) is not None]

    if to_add:
        try:
            await membre.add_roles(*to_add, reason=reason)
        except (discord.Forbidden, discord.HTTPException) as e:
            log.warning("[NGSTAFF RANK] Ajout du rôle impossible pour %s : %s", membre.id, e)

    if to_remove:
        try:
            await membre.remove_roles(*to_remove, reason=reason)
        except (discord.Forbidden, discord.HTTPException) as e:
            log.warning("[NGSTAFF RANK] Retrait du rôle impossible pour %s : %s", membre.id, e)


# ============================================================
# ⬆️ Orchestration /ngstaff rank
# ============================================================

class RankValidationError(Exception):
    """Gestion des erreurs."""

    def __init__(self, message: str, *, warning: bool = False) -> None:
        super().__init__(message)
        self.message = message
        self.warning = warning


@dataclass
class RankResult:
    """Résumé d'un rank-up réussi, pour construction du message de confirmation par le cog."""
    label: str
    new_nick: str | None = None
    builder_pseudo: str | None = None
    extra_warning: str | None = None


async def _fetch_channel(bot: discord.Client, channel_id: int):
    """Récupère un salon par son ID."""
    try:
        return await bot.fetch_channel(channel_id)
    except (discord.NotFound, discord.HTTPException):
        return None


async def _send_with_reaction(bot: discord.Client, channel_id: int | None, view: discord.ui.LayoutView, emoji: str | None) -> None:
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
        log.warning("[NGSTAFF RANK] Impossible d'envoyer dans le salon %d", channel_id)


async def _send_to_channel(bot: discord.Client, channel_id: int | None, view: discord.ui.LayoutView) -> None:
    """Envoie une view dans un salon sans réaction."""
    if not channel_id:
        return
    channel = bot.get_channel(channel_id) or await _fetch_channel(bot, channel_id)
    if channel is None:
        return
    try:
        await channel.send(view=view)
    except discord.HTTPException:
        log.warning("[NGSTAFF RANK] Impossible d'envoyer dans le salon %d", channel_id)


async def execute_grade_rank(bot: discord.Client, guild_id: int, membre: discord.Member, pseudo: str, new_grade: str, cfg: dict, existing: dict | None, *, server: str) -> RankResult:
    """Change le grade (hiérarchie staff) d'un membre : DB, rôles, pseudo, annonces, stafflist."""

    old_grade = existing["grade"] if existing else None
    is_promotion = existing is not None

    statut_defs = await list_statut_defs(server)
    held_statuts = {s["key"] for s in existing.get("statuts", [])} if existing else set()
    current_secondary = {d["key"]: d["key"] in held_statuts for d in statut_defs}

    target_secondary = strip_incompatible_statuses(new_grade, current_secondary)
    statuses_stripped = new_grade in STATUT_INCOMPATIBLE_GRADES and any(current_secondary.values())

    await upsert_staff_member(server, membre.id, pseudo, new_grade)

    if statuses_stripped:
        # 🚫 Grade incompatible (Admin/SM) : on retire réellement les statuts
        # en DB (table ng_staff_statuts), pas seulement côté rôles Discord.
        for key, was_held in current_secondary.items():
            if was_held:
                await revoke_statut(server, membre.id, key)

    await apply_staff_roles(
        membre, cfg,
        grade=new_grade,
        secondary=target_secondary,
        statut_defs=statut_defs,
        reason=f"Rank {get_server_display_name(server)} : {GRADE_LABELS[new_grade]}",
    )

    prefix = compute_nick_prefix(new_grade, target_secondary, statut_defs)
    new_nick = f"{prefix} | {pseudo}" if prefix else pseudo
    try:
        await membre.edit(nick=new_nick, reason=f"Rank {get_server_display_name(server)} : {GRADE_LABELS[new_grade]}")
    except (discord.Forbidden, discord.HTTPException):
        log.warning("[NGSTAFF RANK] Impossible de renommer %s", membre.id)
        new_nick = None

    await _send_with_reaction(
        bot, cfg.get("rank_channel_id"),
        build_grade_announcement(membre, new_grade, is_promotion, old_grade, emoji=cfg.get("rank_emoji")),
        cfg.get("rank_emoji"),
    )

    await _send_to_channel(
        bot, cfg.get("journaliste_channel_id"),
        build_journaliste_message(pseudo, GRADE_LABELS[new_grade], cfg.get("journaliste_ping_id"), is_promotion),
    )

    if not is_promotion:
        # 🛠️ Ping dev centralisé sur le serveur dev (settings), plus par-serveur
        # NG — cf. utils/settings.py (Paul, 2026-08-22).
        await _send_to_channel(
            bot, settings.dev_ping_channel_id,
            build_dev_message(pseudo, settings.dev_ping_role_id),
        )

    # 📋 Mise à jour de la liste staff (import local, évite un import circulaire de cog).
    from utils.managers.ng_stafflist_manager import refresh_staff_message
    await refresh_staff_message(bot, guild_id, server=server)

    extra = (
        "⚠️ Statut(s) secondaire(s) retiré(s) (incompatible avec ce grade)."
        if statuses_stripped else None
    )

    return RankResult(label=GRADE_LABELS[new_grade], new_nick=new_nick, extra_warning=extra)


async def execute_statut_rank(
    bot: discord.Client,
    guild_id: int,
    membre: discord.Member,
    pseudo: str,
    statut: str,
    cfg: dict,
    existing: dict | None,
    second_pseudo: str | None,
    *,
    server: str,
) -> RankResult:
    """Attribue un statut secondaire (librement défini par serveur, ex :
    journaliste/affilié/builder) cumulable : DB, rôles, annonces,
    stafflist.

    `statut` est la `key` d'un NGStatutDef existant pour ce serveur (résolu
    via ng_statut_manager, plus l'ancien dict figé SECONDARY_STATUSES —
    Paul, 2026-08-22). `second_pseudo` généralise l'ancien paramètre
    `pseudo_jeu_builder` : requis uniquement si le statut a
    `requires_second_pseudo=True` (n'importe quel statut peut désormais
    porter ce besoin, pas seulement Builder).

    Lève RankValidationError si la demande doit être refusée (statut
    inconnu pour ce serveur, grade incompatible, statut déjà attribué,
    second pseudo manquant).
    """

    statut_def = await get_statut_def(server, statut)
    if statut_def is None:
        raise RankValidationError(f"Le statut `{statut}` n'existe pas pour ce serveur.", warning=True)

    current_grade = existing["grade"] if existing else None

    # ❌ Incompatibilité Admin/SM — refus net, pas de retrait automatique
    # (ce sens-là n'a jamais été demandé : seul grade→Admin/SM strip les
    # statuts, jamais l'inverse).
    if current_grade in STATUT_INCOMPATIBLE_GRADES:
        raise RankValidationError(
            f"**{existing['pseudo_jeu']}** est **{GRADE_LABELS.get(current_grade, current_grade)}** : "
            f"ce grade est incompatible avec le statut **{statut_def['label']}**.",
            warning=True,
        )

    held_statuts = {s["key"] for s in existing.get("statuts", [])} if existing else set()
    if statut in held_statuts:
        raise RankValidationError(
            f"**{existing['pseudo_jeu']}** est déjà **{statut_def['label']}**.",
            warning=True,
        )

    # 🔁 Second pseudo (généralisation de pseudo_jeu_builder) : requis
    # uniquement si CE statut le demande.
    second_pseudo_clean: str | None = None
    if statut_def["requires_second_pseudo"]:
        if not second_pseudo or not second_pseudo.strip():
            raise RankValidationError(
                f"Le paramètre `pseudo_jeu_builder` est **obligatoire** pour attribuer le statut "
                f"**{statut_def['label']}** (second pseudo/compte dédié)."
            )
        second_pseudo_clean = second_pseudo.strip()

    if not existing:
        # Statut "pur" — pas de grade existant : on crée la ligne de base.
        await upsert_staff_member(server, membre.id, pseudo, None)

    await grant_statut(server, membre.id, statut, second_pseudo=second_pseudo_clean)

    statut_defs = await list_statut_defs(server)
    target_secondary = {d["key"]: d["key"] in held_statuts for d in statut_defs}
    target_secondary[statut] = True

    await apply_staff_roles(
        membre, cfg,
        grade=current_grade,
        secondary=target_secondary,
        statut_defs=statut_defs,
        reason=f"Rank {get_server_display_name(server)} : {statut_def['label']}",
    )

    # Le grade prime toujours sur le pseudo (s'il y en a un, le pseudo n'est
    # jamais retouché ici). Sans grade, le préfixe suit l'ordre de
    # `position` des statuts du serveur (voir compute_nick_prefix),
    # recalculé sur l'état COMPLET des statuts (pas seulement celui qu'on
    # vient d'activer), pour rester correct en cas de cumul.
    new_nick = None
    if current_grade is None:
        prefix = compute_nick_prefix(None, target_secondary, statut_defs)
        new_nick = f"{prefix} | {pseudo}" if prefix else pseudo
        try:
            await membre.edit(nick=new_nick, reason=f"Rank {get_server_display_name(server)} : {statut_def['label']}")
        except (discord.Forbidden, discord.HTTPException):
            log.warning("[NGSTAFF RANK] Impossible de renommer %s", membre.id)
            new_nick = None

    await _send_with_reaction(
        bot, cfg.get("rank_channel_id"),
        build_statut_announcement(
            membre, statut_def["label"], badge=statut_def.get("emoji"), emoji=cfg.get("rank_emoji"),
        ),
        cfg.get("rank_emoji"),
    )

    if statut == "journaliste":
        await _send_to_channel(
            bot, cfg.get("journaliste_channel_id"),
            build_journaliste_message(pseudo, statut_def["label"], cfg.get("journaliste_ping_id"), existing is not None),
        )

    if not existing:
        # 🛠️ Ping dev centralisé sur le serveur dev (settings), plus par-serveur
        # NG — cf. utils/settings.py (Paul, 2026-08-22).
        await _send_to_channel(
            bot, settings.dev_ping_channel_id,
            build_dev_message(pseudo, settings.dev_ping_role_id),
        )

    # 📋 Mise à jour de la liste staff (import local, évite un import circulaire de cog).
    from utils.managers.ng_stafflist_manager import refresh_staff_message
    await refresh_staff_message(bot, guild_id, server=server)

    return RankResult(label=statut_def["label"], new_nick=new_nick, builder_pseudo=second_pseudo_clean)