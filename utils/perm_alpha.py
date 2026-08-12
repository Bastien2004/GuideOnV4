"""
utils/perm_alpha.py — Vérification des permissions du système Alpha.

Hiérarchie :
    CREATOR / DEV      ──┐
    OP_ALPHA             ├──> is_op_alpha     (Admins / SM Alpha)
    MODO_PLUS_ALPHA      ├──> is_modo_plus    (Modo+ et au-dessus)
    MODO_ALPHA           └──> is_modo         (Modo et au-dessus)

Refonte multi-serveurs, phase 15 (nettoyage legacy) : is_op_alpha /
is_modo_plus / is_modo lisaient auparavant l'ancienne table
`permission_entries` (via utils.permission.get_ids) — gelée depuis la
phase 4, date à laquelle /dev permissions a basculé sur le nouveau
système RBAC (permission_grade_members, utils.managers.permission_rbac_
manager). Un membre promu OP Alpha via /dev permissions après la phase 4
n'était donc PLUS reconnu par ces trois fonctions, ni par aucune des
commandes /alpha qui en dépendent (index, regle_interne, nous_rejoindre,
event_start/regle/list, rank, derank, stafflist) — bug de staleness réel,
corrigé ici.

Les trois fonctions lisent maintenant has_grade() (RBAC) sur les grades
équivalents (staff_alpha.op / .modo_plus / .modo, cf migration
d8d9b015e428_rbac_modo_grades_and_legacy_backfill.py, phase 3) au lieu de
get_ids() (legacy). La hiérarchie OP ⊆ MODO_PLUS ⊆ MODO est déjà encodée
côté RBAC via permission_grade_includes (créée dans cette même migration
phase 3) — has_grade() la résout récursivement, donc il n'est plus
nécessaire de la ré-implémenter ici en Python (is_modo_plus n'a plus
besoin d'appeler is_op_alpha en plus de son propre has_grade : un membre
"op" est déjà reconnu "modo_plus" par has_grade("staff_alpha.modo_plus")
grâce à l'inclusion RBAC). DEV et CREATOR restent un OR explicite car ce
ne sont pas des membres de la catégorie staff_alpha.

Toutes les fonctions passent async (has_grade est async) — aucun appelant
externe n'existait pour les is_* nues (seuls les check_* de ce fichier les
utilisaient déjà en async), donc ce changement de signature n'a aucun
impact ailleurs dans le codebase (vérifié par grep avant ce changement).
"""

from __future__ import annotations

import discord
from discord import Interaction

from utils.container_universel import error_container, send_ephemeral
from utils.createur import is_creator
from utils.managers.ng_server_manager import get_server_by_guild
from utils.managers.permission_rbac_manager import has_grade


# ============================================================
# 📁 Fonctions
# ============================================================

async def is_op_alpha(interaction: discord.Interaction) -> bool:
    """True si OP Alpha (ou supérieur : DEV ou CREATOR)."""
    uid = interaction.user.id
    return (
        is_creator(uid)
        or await has_grade(uid, "equipe_guideon.dev")
        or await has_grade(uid, "staff_alpha.op")
    )


async def is_modo_plus(interaction: discord.Interaction) -> bool:
    """True si Modo+ Alpha ou supérieur (inclut OP Alpha via l'inclusion RBAC)."""
    uid = interaction.user.id
    return (
        is_creator(uid)
        or await has_grade(uid, "equipe_guideon.dev")
        or await has_grade(uid, "staff_alpha.modo_plus")
    )


async def is_modo(interaction: discord.Interaction) -> bool:
    """True si Modo Alpha ou supérieur (inclut Modo+ et OP Alpha via l'inclusion RBAC)."""
    uid = interaction.user.id
    return (
        is_creator(uid)
        or await has_grade(uid, "equipe_guideon.dev")
        or await has_grade(uid, "staff_alpha.modo")
    )


async def check_op_alpha(interaction: Interaction, action: str = "effectuer cette action") -> bool:
    """Vérification OP Alpha + Gestion d'erreur manque de permissions."""
    if await is_op_alpha(interaction):
        return True
    await send_ephemeral(interaction, error_container(f"Vous devez être **Opérateur** pour {action}."))
    return False


async def check_modo_plus(interaction: Interaction, action: str = "effectuer cette action") -> bool:
    """Vérification MODO+ Alpha + Gestion d'erreur manque de permissions."""
    if await is_modo_plus(interaction):
        return True
    await send_ephemeral(interaction, error_container(f"Vous devez être **Modérateur +** pour {action}."))
    return False


async def check_modo(interaction: Interaction, action: str = "effectuer cette action") -> bool:
    """Vérification MODO Alpha + Gestion d'erreur manque de permissions."""
    if await is_modo(interaction):
        return True
    await send_ephemeral(interaction, error_container(f"Vous devez être **Modérateur** pour {action}."))
    return False


async def require_alpha_guild(interaction: Interaction) -> bool:
    """
    Garde-fou défense-en-profondeur (refonte multi-serveurs, phase 13, §7 du
    prompt) : vérifie que l'interaction provient bien du Discord Alpha —
    seul Discord où les commandes "systèmes particuliers" (/alpha
    config_alpha, /alpha index, /alpha regle_interne, /alpha nous_rejoindre,
    /alpha event_start/event_regle/event_list) ont un sens.

    En usage normal, ces commandes ne sont enregistrées que sur le Discord
    Alpha (bot.py ne les synchronise jamais ailleurs) — ce guard ne devrait
    donc jamais se déclencher. Il protège contre une erreur de câblage
    future (ex : sync accidentel sur un autre Discord NG), dans le même
    esprit que require_ng_server côté /ngstaff (utils/ng_server_check.py),
    mais inversé : ici on rejette *sauf* si le serveur résolu est "alpha".
    """
    guild_id = interaction.guild_id
    server = get_server_by_guild(guild_id) if guild_id is not None else None
    if server is None or server.name != "alpha":
        await send_ephemeral(
            interaction,
            error_container("Cette commande est **réservée** au Discord Alpha."),
        )
        return False
    return True