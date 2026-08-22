"""
utils/ng_derank_logic.py — Logique métier du derank staff NG.

Extrait de cogs/alpha/derank.py (fichier devenu trop lourd). Découpage :

- cogs/alpha/derank.py       : seulement la commande /alpha derank
- views/alpha/derank_view.py : la view de confirmation (DerankConfirmView)
- utils/ng_derank_logic.py   : calcul de l'état cible, garde-fous, persistance
                               DB, rôles Discord, pseudo, annonces, refresh
                               stafflist

Multi-serveurs depuis la refonte phase 12 : execute_derank accepte le kwarg
`server` obligatoire (plus de défaut "alpha" depuis le nettoyage nomenclature).
Renommé alpha_derank_logic.py → ng_derank_logic.py pour clarifier sa nature
réelle.
"""
from __future__ import annotations

import logging

import discord
from discord.ui import Container, LayoutView, Separator, TextDisplay

from utils.ng_rank_logic import apply_staff_roles, compute_nick_prefix
from utils.db.models.staff_grades import GRADE_LABELS
from utils.managers.ng_staff_manager import remove_staff_member, update_staff_member
from utils.managers.ng_statut_manager import list_statut_defs, revoke_all_statuts, revoke_statut
from utils.ng_server_display import get_server_display_name

log = logging.getLogger(__name__)

# Refonte multi-serveurs phase 12 : execute_derank accepte désormais un
# paramètre `server` obligatoire (kwarg-only, plus de défaut "alpha" depuis
# le nettoyage nomenclature) — voir la même note dans utils/ng_rank_logic.py.
#
# Statuts (Paul, 2026-08-22) : comme dans ng_rank_logic.py, les clés de
# `secondary` sont désormais les `key` des NGStatutDef du serveur
# (statut_defs, résolus via ng_statut_manager.list_statut_defs) plutôt que
# "journaliste"/"affilie"/"builder" en dur.


def secondary_dict(member_data: dict, statut_defs: list[dict]) -> dict[str, bool]:
    """Extrait l'état des statuts secondaires d'un membre, pour les statuts
    définis sur ce serveur (statut_defs)."""
    held = {s["key"] for s in member_data.get("statuts", [])}
    return {d["key"]: d["key"] in held for d in statut_defs}


# ============================================================
# 🧮 Calcul de l'état cible + garde-fous
# ============================================================

def compute_target_state(role: str, grade: str | None, secondary: dict[str, bool]) -> tuple[str | None, dict[str, bool]]:
    """Calcule (grade_cible, statuts_cibles) selon le type de derank demandé."""
    if role == "complet":
        return None, {key: False for key in secondary}
    if role == "staff":
        return None, dict(secondary)
    # statut secondaire spécifique (clé dynamique, ex: journaliste/affilie/builder)
    target_secondary = dict(secondary)
    target_secondary[role] = False
    return grade, target_secondary


def guard_message(
    role: str, pseudo_jeu: str, grade: str | None, secondary: dict[str, bool], statut_defs: list[dict],
) -> str | None:
    """Renvoie un message d'avertissement si le derank demandé n'a rien à faire, sinon None."""
    if role == "staff" and not grade:
        return f"**{pseudo_jeu}** n'a aucun grade staff à retirer."
    statut_def = next((d for d in statut_defs if d["key"] == role), None)
    if statut_def is not None and not secondary.get(role, False):
        return f"**{pseudo_jeu}** n'est pas **{statut_def['label']}**."
    return None


# ============================================================
# 📁 Construction des annonces
# ============================================================

def build_derank_announcement(
    membre: discord.Member, role: str, old_grade: str | None, *,
    emoji: str | None = None, statut_label: str | None = None, statut_badge: str | None = None,
) -> LayoutView:
    """Annonce publique de derank.

    `emoji` : emoji d'annonce configuré par serveur (NGRankConfig.rank_emoji),
    remplace l'ancien logo Alpha codé en dur (Paul, 2026-08-22).
    `statut_label`/`statut_badge` : libellé/emoji du NGStatutDef concerné
    (fournis par l'appelant, résolus via ng_statut_manager) quand `role` est
    la clé d'un statut secondaire plutôt que "complet"/"staff".
    """
    prefix = f"{emoji} " if emoji else ""
    view = LayoutView(timeout=None)
    c = Container()

    if role == "complet":
        label = GRADE_LABELS.get(old_grade, old_grade) if old_grade else "l'équipe"
        c.add_item(TextDisplay(f"{prefix}Merci à <@{membre.id}> pour son travail en tant que **{label}** !"))

    elif role == "staff":
        label = GRADE_LABELS.get(old_grade, old_grade) if old_grade else "Staff"
        c.add_item(TextDisplay(f"{prefix}**Merci** à <@{membre.id}> pour son travail chez les **{label}** !"))

    else:
        badge = statut_badge or ""
        c.add_item(TextDisplay(
            f"{prefix}**Merci** à <@{membre.id}> pour son travail chez les **{statut_label or role}** ! {badge}".rstrip()
        ))

    view.add_item(c)
    return view


def build_journaliste_derank_message(pseudo_jeu: str, role: str, old_grade: str | None, journaliste_ping_id: int | None) -> LayoutView:
    """Message pour les journalistes (affiche de remerciement)."""

    ping = f"<@&{journaliste_ping_id}> " if journaliste_ping_id else ""

    view = LayoutView(timeout=None)
    c = Container()
    c.add_item(TextDisplay("# 📸 Affiche de derank"))
    c.add_item(Separator())

    if role == "staff":
        label = GRADE_LABELS.get(old_grade, old_grade) if old_grade else "Staff"
        c.add_item(TextDisplay(
            f"Hey {ping} ! **{pseudo_jeu}** quitte le **Staff** en tant que **{label}**.\n"
            f"Merci de créer et poster l'affiche de remerciement. 🎨"
        ))

    elif role == "journaliste":
        c.add_item(TextDisplay(
            f"Hey {ping} ! **{pseudo_jeu}** quitte l'équipe des **Journalistes**.\n"
            f"Merci de créer et poster l'affiche de remerciement. 🎨"
        ))

    else:
        label = GRADE_LABELS.get(old_grade, old_grade) if old_grade else "l'équipe"
        c.add_item(TextDisplay(
            f"Hey {ping} ! **{pseudo_jeu}** ne fait plus partie de l'équipe (**{label}**).\n"
            f"Merci de créer et poster l'affiche de remerciement. 🎨"
        ))

    view.add_item(c)
    return view


async def _fetch_channel(bot: discord.Client, channel_id: int):
    """Récupère le salon d'envoi."""
    try:
        return await bot.fetch_channel(channel_id)
    except (discord.NotFound, discord.HTTPException):
        return None


async def send_with_reaction(bot, channel_id, view, emoji) -> None:
    """Envoie l'annonce de derank et ajoute la réaction."""

    if not channel_id:
        return
    channel = bot.get_channel(channel_id) or await _fetch_channel(bot, channel_id)
    if not channel:
        return

    try:
        sent = await channel.send(view=view)
        if emoji:
            try:
                await sent.add_reaction(emoji)
            except discord.HTTPException:
                pass

    except discord.HTTPException:
        log.warning("[NGSTAFF DERANK] Impossible d'envoyer dans le salon %d", channel_id)


async def send_to_channel(bot, channel_id, view) -> None:
    """Envoie le message de derank aux journalistes."""

    if not channel_id:
        return

    channel = bot.get_channel(channel_id) or await _fetch_channel(bot, channel_id)
    if not channel:
        return
    try:
        await channel.send(view=view)

    except discord.HTTPException:
        log.warning("[NGSTAFF DERANK] Impossible d'envoyer dans le salon %d", channel_id)


# ============================================================
# ⚙️ Exécution complète du derank (une fois confirmé)
# ============================================================

async def execute_derank(
    bot: discord.Client,
    membre: discord.Member,
    member_data: dict,
    cfg: dict,
    guild_id: int,
    role: str,
    *,
    server: str,
) -> None:
    """
    Exécute le derank déjà confirmé : persistance DB, rôles Discord, pseudo,
    annonces, rafraîchissement de la stafflist.

    Aucune vérification de garde ici (voir guard_message) : elles doivent
    avoir été faites par l'appelant avant d'invoquer cette fonction.
    """
    grade = member_data["grade"]
    discord_id = member_data["discord_id"]
    statut_defs = await list_statut_defs(server)
    secondary = secondary_dict(member_data, statut_defs)
    target_grade, target_secondary = compute_target_state(role, grade, secondary)
    statut_def = next((d for d in statut_defs if d["key"] == role), None)

    # ── Persistance DB ────────────────────────────────────
    has_remaining_state = target_grade is not None or any(target_secondary.values())

    if not has_remaining_state:
        # Plus rien à conserver -> statuts + ligne staff supprimés entièrement.
        await revoke_all_statuts(server, discord_id)
        await remove_staff_member(server, discord_id)
    else:
        # Retire uniquement les statuts qui doivent disparaître (secondary -> target_secondary).
        for key, was_held in secondary.items():
            if was_held and not target_secondary.get(key, False):
                await revoke_statut(server, discord_id, key)
        await update_staff_member(server, discord_id, grade=target_grade)

    # ── Rôles Discord ──────────────────────────────────────
    await apply_staff_roles(
        membre, cfg,
        grade=target_grade,
        secondary=target_secondary,
        statut_defs=statut_defs,
        reason=f"Derank {get_server_display_name(server)} : {role}",
    )

    # ── Pseudo Discord ──────────────────────────────────────
    if role == "complet":
        try:
            await membre.edit(nick=membre.name, reason=f"Derank {get_server_display_name(server)} complet")
        except (discord.Forbidden, discord.HTTPException):
            log.warning("[NGSTAFF DERANK] Impossible de renommer %s", membre.id)
    else:
        prefix = compute_nick_prefix(target_grade, target_secondary, statut_defs)
        new_nick = f"{prefix} | {member_data['pseudo_jeu']}" if prefix else member_data["pseudo_jeu"]
        try:
            await membre.edit(nick=new_nick, reason=f"Derank {get_server_display_name(server)} : {role}")
        except (discord.Forbidden, discord.HTTPException):
            log.warning("[NGSTAFF DERANK] Impossible de renommer %s", membre.id)

    # ── Annonces ──────────────────────────────────────────
    await send_with_reaction(
        bot,
        cfg.get("rank_channel_id"),
        build_derank_announcement(
            membre, role, grade, emoji=cfg.get("rank_emoji"),
            statut_label=statut_def["label"] if statut_def else None,
            statut_badge=statut_def.get("emoji") if statut_def else None,
        ),
        cfg.get("rank_emoji"),
    )

    if role in ("complet", "staff", "journaliste"):
        await send_to_channel(
            bot,
            cfg.get("journaliste_channel_id"),
            build_journaliste_derank_message(member_data["pseudo_jeu"], role, grade, cfg.get("journaliste_ping_id")),
        )

    from utils.managers.ng_stafflist_manager import refresh_staff_message
    await refresh_staff_message(bot, guild_id, server=server)