"""
utils/ng_rank_logic.py — Logique centralisée de la gestion des rôles Discord
staff NG et orchestration du rank-up (/alpha rank, /ngstaff rank) : DB,
rôles, pseudo, annonces.

Malgré le nommage historique "alpha_*" des symboles internes qu'elle
manipule (GRADE_LABELS, SECONDARY_STATUSES, etc.), cette logique est
100% multi-serveurs depuis la refonte phase 12 : le paramètre `server`
(kwarg-only, défaut "alpha") sélectionne la source des données NG
appropriée. Renommé alpha_rank_logic.py → ng_rank_logic.py pour clarifier
sa nature réelle.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import discord

from utils.settings import settings
from utils.db.models.alpha_staff import (
    GRADE_LABELS,
    GRADE_PREFIXES,
    GRADE_TO_ROLE_ATTR,
    SECONDARY_STATUSES,
    STAFF_GENERAL_GRADES,
    STATUT_INCOMPATIBLE_GRADES,
    STATUTS_SECONDAIRES_ORDER,
)
from utils.managers.ng_staff_manager import update_staff_member, upsert_staff_member
from views.alpha.rank_view import (
    build_dev_message,
    build_grade_announcement,
    build_journaliste_message,
    build_statut_announcement,
)

log = logging.getLogger(__name__)

NICK_PREFIX_PRIORITY: tuple[str, ...] = ("affilie", "journaliste", "builder")

# Refonte multi-serveurs phase 12 : execute_grade_rank/execute_statut_rank
# acceptent désormais un paramètre `server` optionnel (kwarg-only, défaut
# "alpha") pour rester 100% compatibles avec /alpha rank (qui ne le passe
# jamais) tout en permettant à /ngstaff rank de le résoudre dynamiquement
# via ng_server_manager.get_server_by_guild(interaction.guild_id).


# ============================================================
# 🎭 Rôles Discord — attribution/retrait
# ============================================================

def compute_nick_prefix(grade: str | None, secondary: dict[str, bool]) -> str | None:
    """Détermine le préfixe de rename de pseudo Discord ("Guide", "Affilié", "Builder"...). """

    if grade:
        return GRADE_PREFIXES.get(grade, grade)

    for key in NICK_PREFIX_PRIORITY:
        if secondary.get(key):
            return SECONDARY_STATUSES[key]["label"]

    return None


def strip_incompatible_statuses(grade: str | None, secondary: dict[str, bool]) -> dict[str, bool]:
    """Vérification de compatibilité."""

    if grade not in STATUT_INCOMPATIBLE_GRADES:
        return dict(secondary)
    return {key: False for key in secondary}


def _all_managed_role_ids(cfg: dict) -> set[int]:
    """Récupère tous les IDs de rôle géré."""

    ids: set[int] = set()

    for grade in GRADE_TO_ROLE_ATTR:
        rid = cfg.get(GRADE_TO_ROLE_ATTR[grade])
        if rid:
            ids.add(rid)

    rid = cfg.get("role_equipe_id")
    if rid:
        ids.add(rid)

    for meta in SECONDARY_STATUSES.values():
        rid = cfg.get(meta["role_attr"])
        if rid:
            ids.add(rid)

    return ids


def _target_role_ids(cfg: dict, grade: str | None, secondary: dict[str, bool]) -> set[int]:
    """Récupération du rôle à distribuer."""

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

    for key, meta in SECONDARY_STATUSES.items():
        if effective_secondary.get(key):
            rid = cfg.get(meta["role_attr"])
            if rid:
                ids.add(rid)

    return ids


async def apply_staff_roles(
    membre: discord.Member,
    cfg: dict,
    *,
    grade: str | None,
    secondary: dict[str, bool] | None = None,
    reason: str = "GuideOn Alpha",
) -> None:
    """Applique le don ou le retrait de rôle."""

    secondary = secondary or {}

    target_ids = _target_role_ids(cfg, grade, secondary)
    managed_ids = _all_managed_role_ids(cfg)
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
            log.warning("[ALPHA RANK] Ajout du rôle impossible pour %s : %s", membre.id, e)

    if to_remove:
        try:
            await membre.remove_roles(*to_remove, reason=reason)
        except (discord.Forbidden, discord.HTTPException) as e:
            log.warning("[ALPHA RANK] Retrait du rôle impossible pour %s : %s", membre.id, e)


# ============================================================
# ⬆️ Orchestration /alpha rank — extrait de cogs/alpha/rank.py
# ============================================================

class RankValidationError(Exception):
    """Erreur métier à afficher à l'utilisateur (pas une exception technique) —
    levée quand la demande de rank est refusée pour une raison fonctionnelle
    (statut incompatible, déjà attribué, pseudo builder manquant, ...)."""

    def __init__(self, message: str, *, warning: bool = False) -> None:
        super().__init__(message)
        self.message = message
        self.warning = warning  # True -> warning_container, False -> error_container


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


async def _send_with_reaction(
    bot: discord.Client, channel_id: int | None, view: discord.ui.LayoutView, emoji: str | None
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
        log.warning("[RANK ALPHA] Impossible d'envoyer dans le salon %d", channel_id)


async def execute_grade_rank(
    bot: discord.Client,
    guild_id: int,
    membre: discord.Member,
    pseudo: str,
    new_grade: str,
    cfg: dict,
    existing: dict | None,
    *,
    server: str = "alpha",
) -> RankResult:
    """Change le grade (hiérarchie staff) d'un membre : DB, rôles, pseudo, annonces, stafflist."""

    old_grade = existing["grade"] if existing else None
    is_promotion = existing is not None

    current_secondary = {
        key: existing.get(f"is_{key}", False) for key in STATUTS_SECONDAIRES_ORDER
    } if existing else {key: False for key in STATUTS_SECONDAIRES_ORDER}

    target_secondary = strip_incompatible_statuses(new_grade, current_secondary)
    statuses_stripped = new_grade in STATUT_INCOMPATIBLE_GRADES and any(current_secondary.values())

    await upsert_staff_member(
        server, membre.id, pseudo, new_grade,
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
        "⚠️ Statut(s) Journaliste/Affilié/Builder retiré(s) (incompatible avec ce grade)."
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
    pseudo_jeu_builder: str | None,
    *,
    server: str = "alpha",
) -> RankResult:
    """Attribue un statut secondaire (journaliste/affilié/builder) cumulable : DB, rôles, annonces, stafflist.

    Lève RankValidationError si la demande doit être refusée (grade
    incompatible, statut déjà attribué, pseudo builder manquant).
    """

    meta = SECONDARY_STATUSES[statut]
    current_grade = existing["grade"] if existing else None

    # ❌ Incompatibilité Admin/SM — refus net, pas de retrait automatique
    # (ce sens-là n'a jamais été demandé : seul grade→Admin/SM strip les
    # statuts, jamais l'inverse).
    if current_grade in STATUT_INCOMPATIBLE_GRADES:
        raise RankValidationError(
            f"**{existing['pseudo_jeu']}** est **{GRADE_LABELS.get(current_grade, current_grade)}** : "
            f"ce grade est incompatible avec le statut **{meta['label']}**.",
            warning=True,
        )

    if existing and existing.get(f"is_{statut}", False):
        raise RankValidationError(
            f"**{existing['pseudo_jeu']}** est déjà **{meta['label']}**.",
            warning=True,
        )

    # 🧱 Builder : pseudo_jeu_builder obligatoire
    builder_pseudo_clean: str | None = None
    if statut == "builder":
        if not pseudo_jeu_builder or not pseudo_jeu_builder.strip():
            raise RankValidationError(
                "Le paramètre `pseudo_jeu_builder` est **obligatoire** pour attribuer le statut Builder "
                "(c'est le pseudo du second compte Minecraft dédié au build)."
            )
        builder_pseudo_clean = pseudo_jeu_builder.strip()

    update_kwargs: dict = {f"is_{statut}": True}
    if statut == "builder":
        update_kwargs["pseudo_jeu_builder"] = builder_pseudo_clean

    if existing:
        await update_staff_member(server, membre.id, **update_kwargs)
        target_secondary = {
            key: existing.get(f"is_{key}", False) for key in STATUTS_SECONDAIRES_ORDER
        }
        target_secondary[statut] = True
    else:
        # Statut "pur" — pas de grade existant.
        await upsert_staff_member(
            server, membre.id, pseudo, None,
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
        bot, cfg.get("rank_channel_id"),
        build_statut_announcement(membre, statut, emoji=cfg.get("rank_emoji")),
        cfg.get("rank_emoji"),
    )

    if statut == "journaliste":
        await _send_to_channel(
            bot, cfg.get("journaliste_channel_id"),
            build_journaliste_message(pseudo, meta["label"], cfg.get("journaliste_ping_id"), existing is not None),
        )

    if not existing:
        await _send_to_channel(
            bot, settings.dev_ping_channel_id,
            build_dev_message(pseudo, settings.dev_ping_role_id),
        )

    # 📋 Mise à jour de la liste staff (import local, évite un import circulaire de cog).
    from utils.managers.ng_stafflist_manager import refresh_staff_message
    await refresh_staff_message(bot, guild_id, server=server)

    return RankResult(label=meta["label"], new_nick=new_nick, builder_pseudo=builder_pseudo_clean)